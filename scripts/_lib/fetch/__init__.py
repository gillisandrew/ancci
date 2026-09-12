"""Acquiring source material.

Each source type sits behind the same small interface, because they break on their own
schedules: YouTube changes, GitHub rate-limits, a docs site restyles its code blocks.
Swapping one acquirer should never be a rewrite.

You never say which kind of thing you are handing over; the shape of what you pass says it.
"""

import re
from pathlib import Path

from .types import Fetched, FetchError

VIDEO_HOSTS = ("youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com")
# A repository, not a page in one: github.com/owner/name and nothing deeper.
REPO_URL = re.compile(r"^https?://(?:www\.)?github\.com/[\w.-]+/[\w.-]+/?$")
# Neither side may start with a dot, or `./docs` reads as a repository and gets cloned.
REPO_SLUG = re.compile(r"^[\w-][\w.-]*/[\w-][\w.-]*$")
PLAIN_TEXT = {".md", ".markdown", ".txt", ".rst"}


def detect(spec: str) -> str:
    """What kind of source this is: url, video, repo, pdf, epub or file."""
    spec = spec.strip()
    if spec.startswith(("http://", "https://")):
        host = spec.split("/")[2].lower()
        if host in VIDEO_HOSTS:
            return "video"
        if REPO_URL.match(spec):
            return "repo"
        return "url"
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
    # Anything written as a path is a missing file, never a repository. `owner/name` and a
    # bare relative path are genuinely ambiguous, so a leading ./ is how you say you meant
    # the file — and a path that does not exist should say so rather than be cloned.
    if spec.startswith((".", "/", "~")) or spec.endswith("/"):
        raise FetchError(f"no such file: {spec}")
    if REPO_SLUG.match(spec):
        return "repo"
    raise FetchError(f"not a URL, and no such file: {spec}")


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
    if kind == "repo":
        from . import repo

        return repo.fetch(spec, cache, **options)
    if kind == "pdf":
        from . import pdf

        return pdf.fetch(spec, cache, **options)
    from . import epub

    return epub.fetch(spec, cache)
