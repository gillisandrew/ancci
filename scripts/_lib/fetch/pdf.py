"""Reading a PDF.

pdfplumber and pypdf are both MIT, which is why they are here: the faster options in this
space are AGPL, and an AGPL dependency would force itself on a published MIT plugin.

The cost of that choice is that headings must be inferred. A PDF has no heading levels,
only text at sizes, so body size is taken as the most common size on the page and anything
meaningfully larger is promoted to a heading. It is a heuristic, and it is why every
extracted heading is marked with the page it came from: a citation should point somewhere
checkable even when the structure is a guess.
"""

from collections import Counter
from pathlib import Path

import pdfplumber
from pypdf import PdfReader

from ..sources import FileSource
from .types import Fetched, FetchError

# How much larger than body text a run must be before it reads as a heading.
H1_RATIO = 1.45
H2_RATIO = 1.20


def _title(path: Path) -> str:
    try:
        meta = PdfReader(str(path)).metadata
        if meta and (title := (meta.title or "").strip()):
            return title
    except Exception:  # noqa: BLE001 - a broken metadata block is not worth failing over
        pass
    return path.stem.replace("_", " ").replace("-", " ")


def _body_size(sizes: Counter) -> float:
    return sizes.most_common(1)[0][0] if sizes else 0.0


def _lines(page) -> list[tuple[str, float]]:
    """Page text as (line, max font size on that line)."""
    out: list[tuple[str, float]] = []
    for line in page.extract_text_lines(strip=True) or []:
        text = line.get("text", "").strip()
        if not text:
            continue
        sizes = [round(c.get("size", 0), 1) for c in line.get("chars", ())]
        out.append((text, max(sizes) if sizes else 0.0))
    return out


def extract(path: Path, pages: int | None = None) -> tuple[str, int]:
    """Markdown-ish text with inferred headings, each section marked with its page."""
    chunks: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        wanted = pdf.pages[:pages] if pages else pdf.pages
        sizes: Counter = Counter()
        per_page = []
        for page in wanted:
            lines = _lines(page)
            per_page.append((page.page_number, lines))
            sizes.update(size for _, size in lines if size)
        body = _body_size(sizes)

        for number, lines in per_page:
            chunks.append(f"\n\n<!-- page {number} -->")
            for text, size in lines:
                if body and size >= body * H1_RATIO:
                    chunks.append(f"\n\n# {text}")
                elif body and size >= body * H2_RATIO:
                    chunks.append(f"\n\n## {text}")
                else:
                    chunks.append(f"\n{text}")
        count = len(pdf.pages)
    text = "".join(chunks).strip()
    if not text:
        raise FetchError(f"no extractable text in {path.name}; it may be a scan needing OCR")
    return text, count


def fetch(spec: str, cache: Path, pages: int | None = None) -> Fetched:
    path = Path(spec).expanduser()
    if not path.is_file():
        raise FetchError(f"no such file: {path}")
    text, count = extract(path, pages)
    title = _title(path)
    return Fetched(
        text=f"# {title}\n{text}",
        citation=FileSource(path=str(path), at=f"{count} pages"),
        title=title,
        notes={"pages": str(count), "headings": "inferred from font size, not structural"},
    )
