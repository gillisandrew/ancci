"""Reading a video's transcript.

yt-dlp is asked for metadata only — never to download a video. It returns the caption
tracks alongside the title, duration and chapters, and the caption URL is fetched directly.

Timestamps are the point. A card citing a video should point at the moment, not the video,
so cues are merged into readable windows with a literal `[t=372]` marker at the start of
each: an author copying a nearby marker is far more reliable than one doing arithmetic.
"""

import json
import re
from pathlib import Path

import httpx
from yt_dlp import YoutubeDL

from ..sources import VideoSource
from .types import Fetched, FetchError

# How much transcript to gather under one timestamp. Long enough to be a readable
# paragraph, short enough that the marker still points near the words it precedes.
WINDOW_SECONDS = 60


def _info(url: str) -> dict:
    options = {"skip_download": True, "quiet": True, "no_warnings": True, "extract_flat": False}
    try:
        with YoutubeDL(options) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as exc:  # noqa: BLE001 - yt-dlp raises a wide variety
        raise FetchError(f"could not read video metadata: {str(exc).splitlines()[-1]}") from exc


def _track(info: dict, language: str) -> tuple[str, bool]:
    """The best caption track: a human-written one if it exists, else auto-generated."""
    for source, generated in ((info.get("subtitles") or {}, False), (info.get("automatic_captions") or {}, True)):
        for code in (language, f"{language}-orig", *[k for k in source if k.startswith(language)]):
            for fmt in source.get(code, ()):
                # json3 carries millisecond timings and none of VTT's duplicated scroll lines.
                if fmt.get("ext") == "json3":
                    return fmt["url"], generated
    raise FetchError("this video has no captions in the requested language")


def _cues(payload: dict) -> list[tuple[int, str]]:
    out = []
    for event in payload.get("events", ()):
        text = "".join(seg.get("utf8", "") for seg in event.get("segs", ()) if seg.get("utf8"))
        text = re.sub(r"\s+", " ", text).strip()
        if text and "tStartMs" in event:
            out.append((event["tStartMs"] // 1000, text))
    return out


def to_windows(cues: list[tuple[int, str]], window: int = WINDOW_SECONDS) -> str:
    """Merge cues into timestamped paragraphs an author can cite from."""
    if not cues:
        raise FetchError("the caption track was empty")
    blocks, start, buffer = [], cues[0][0], []
    for second, text in cues:
        if second - start >= window and buffer:
            blocks.append(f"[t={start}] " + " ".join(buffer))
            start, buffer = second, []
        buffer.append(text)
    if buffer:
        blocks.append(f"[t={start}] " + " ".join(buffer))
    return "\n\n".join(blocks)


def fetch(spec: str, cache: Path, language: str = "en") -> Fetched:
    info = _info(spec)
    url, generated = _track(info, language)
    try:
        payload = httpx.get(url, timeout=30, follow_redirects=True).json()
    except Exception as exc:  # noqa: BLE001
        raise FetchError(f"could not fetch captions: {exc}") from exc

    title = info.get("title") or info.get("id") or spec
    body = to_windows(_cues(payload))
    chapters = [c.get("title", "") for c in (info.get("chapters") or [])]

    return Fetched(
        text=f"# {title}\n\n{body}",
        citation=VideoSource(url=info.get("webpage_url") or spec),
        title=title,
        notes={
            "captions": "auto-generated" if generated else "human-written",
            "duration_s": str(info.get("duration") or "?"),
            "chapters": ", ".join(chapters[:12]) or "none",
            # Auto-captions mangle exactly the technical terms a card would test.
            "caution": "auto-generated captions misspell technical terms" if generated else "",
        },
    )
