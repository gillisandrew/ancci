"""Reading an EPUB.

An EPUB is a zip of XHTML, so it needs no library of its own — the web converter already
handles the hard part. The only real work is reading the spine so chapters arrive in
reading order rather than whatever order the zip happens to store them in.

Doing it this way also sidesteps a licensing trap: the obvious EPUB library is AGPL, which
a published MIT plugin cannot depend on.
"""

import zipfile
from pathlib import Path

from bs4 import BeautifulSoup

from ..sources import FileSource
from .types import Fetched, FetchError
from .web import to_markdown

CONTAINER = "META-INF/container.xml"


def _opf_path(archive: zipfile.ZipFile) -> str:
    try:
        container = BeautifulSoup(archive.read(CONTAINER), "xml")
    except KeyError as exc:
        raise FetchError("not a valid EPUB: no META-INF/container.xml") from exc
    rootfile = container.find("rootfile")
    if not rootfile or not rootfile.get("full-path"):
        raise FetchError("not a valid EPUB: container.xml names no rootfile")
    return rootfile["full-path"]


def reading_order(archive: zipfile.ZipFile) -> tuple[list[str], str | None]:
    """The spine, resolved to zip entry names, plus the book's title."""
    opf_name = _opf_path(archive)
    opf = BeautifulSoup(archive.read(opf_name), "xml")
    base = Path(opf_name).parent

    manifest = {
        item["id"]: item["href"]
        for item in opf.find_all("item")
        if item.get("id") and item.get("href")
    }
    names = []
    for ref in opf.find_all("itemref"):
        href = manifest.get(ref.get("idref", ""))
        if href:
            names.append((base / href).as_posix().lstrip("./"))
    if not names:
        raise FetchError("this EPUB has an empty spine")

    title_tag = opf.find("title")
    return names, title_tag.get_text(strip=True) if title_tag else None


def fetch(spec: str, cache: Path) -> Fetched:
    path = Path(spec).expanduser()
    if not path.is_file():
        raise FetchError(f"no such file: {path}")
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise FetchError(f"{path.name} is not a readable EPUB") from exc

    with archive:
        names, title = reading_order(archive)
        chapters = []
        for name in names:
            try:
                html = archive.read(name).decode("utf-8", errors="replace")
            except KeyError:
                continue  # a spine entry naming a missing file is common enough to ignore
            body, _ = to_markdown(html)
            if body:
                chapters.append(body)

    if not chapters:
        raise FetchError(f"no readable text in {path.name}")
    title = title or path.stem
    return Fetched(
        text=f"# {title}\n\n" + "\n\n---\n\n".join(chapters),
        citation=FileSource(path=str(path), at=f"{len(chapters)} chapters"),
        title=title,
        notes={"chapters": str(len(chapters))},
    )
