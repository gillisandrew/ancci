"""Acquiring source material.

Each source type sits behind the same small interface, because they break on their own
schedules: YouTube changes, a docs site restyles its code blocks. Swapping one acquirer
should never be a rewrite.

You never say which kind of thing you are handing over; the shape of what you pass says it.

Repositories are deliberately absent. Cloning one and reading its files is something an
agent already does well, and wrapping that in a fetcher only adds guesses about where the
documentation lives. See the add-source skill's `references/repo.md`.
"""

from pathlib import Path

from .types import Fetched, FetchError

VIDEO_HOSTS = ("youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com")
PLAIN_TEXT = {".md", ".markdown", ".txt", ".rst"}


def detect(spec: str) -> str:
    """What kind of source this is: url, video, pdf, epub or file."""
    spec = spec.strip()
    if spec.startswith(("http://", "https://")):
        host = spec.split("/")[2].lower()
        return "video" if host in VIDEO_HOSTS else "url"
    path = Path(spec).expanduser()
    if path.exists():
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return "pdf"
        if suffix == ".epub":
            return "epub"
        if suffix in PLAIN_TEXT:
            return "file"
        raise FetchError(f"don't know how to read {path.name}; expected a PDF, EPUB or text file")
    raise FetchError(
        f"not a URL, and no such file: {spec}. "
        "To read a repository, clone it and point this at the files you want."
    )


def _plain_file(spec: str, cache: Path) -> Fetched:
    """Markdown and text need no acquirer beyond reading them."""
    from ..sources import FileSource

    path = Path(spec).expanduser()
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        raise FetchError(f"{path.name} is empty")
    # A document's own first heading names it better than its filename does.
    heading = next((line[2:].strip() for line in text.splitlines()[:5] if line.startswith("# ")), "")
    title = heading or path.stem.replace("_", " ").replace("-", " ")
    return Fetched(text=text, citation=FileSource(path=str(path)), title=title)


def fetch(spec: str, cache: Path, **options) -> Fetched:
    """Acquire whatever `spec` points at. Imports the acquirer lazily so that a run which
    reads a local file never loads a video extractor it has no use for."""
    kind = detect(spec)
    if kind == "file":
        return _plain_file(spec, cache)
    if kind == "url":
        from . import web

        return web.fetch(spec, cache)
    if kind == "video":
        from . import video

        return video.fetch(spec, cache, **options)
    if kind == "pdf":
        from . import pdf

        return pdf.fetch(spec, cache, **options)
    from . import epub

    return epub.fetch(spec, cache)
