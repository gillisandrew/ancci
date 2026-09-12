#!/usr/bin/env -S uv run --script --no-config
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pydantic>=2.8",
#   "pyyaml>=6.0",
#   "beautifulsoup4>=4.13",
#   "html-to-markdown>=3.12",
#   "httpx>=0.28",
#   "lxml>=5.0",
#   "pdfplumber>=0.11",
#   "pypdf>=6.0",
#   "yt-dlp>=2026.0",
# ]
# ///
"""Fetch a source into a deck's cache and print how to cite it.

Give it a URL, a YouTube link, a GitHub repository, a PDF, an EPUB or a text file; the kind
is worked out from the shape of what you pass.

The extracted text is cached, never committed. Distilling it into a research note is a
reading job, not a parsing one, so this deliberately stops at the raw text.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import yaml  # noqa: E402

from _lib.cli import deck_argument, deck_from, run  # noqa: E402
from _lib.fetch import detect, fetch  # noqa: E402
from _lib.fetch.cache import cached_text  # noqa: E402
from _lib.sources import UrlSource  # noqa: E402

PREVIEW_LINES = 12


def citation_block(fetched) -> str:
    """The `sources:` entry to paste onto a card, in the shorthand a URL deserves."""
    citation = fetched.citation
    if isinstance(citation, UrlSource):
        body = f"  - {citation.url}"
    else:
        dumped = citation.model_dump(exclude_none=True)
        body = "  - " + yaml.safe_dump(dumped, sort_keys=False, width=100).strip().replace("\n", "\n    ")
    return f"sources:\n{body}"


def main() -> int:
    parser = argparse.ArgumentParser(prog="ancci add-source", description=__doc__)
    deck_argument(parser)
    parser.add_argument("source", help="URL, YouTube link, owner/repo, or a path to a PDF, EPUB or text file")
    parser.add_argument("--ref", help="repositories only: branch, tag or commit to read (default: the default branch)")
    parser.add_argument("--pages", type=int, help="PDFs only: read just the first N pages")
    parser.add_argument("--language", default="en", help="videos only: caption language (default: en)")
    parser.add_argument("--refresh", action="store_true", help="fetch again even if it is already cached")
    args = parser.parse_args()

    deck = deck_from(args)
    kind = detect(args.source)
    destination = cached_text(deck.root, args.source)

    options = {}
    if kind == "repo" and args.ref:
        options["ref"] = args.ref
    if kind == "pdf" and args.pages:
        options["pages"] = args.pages
    if kind == "video":
        options["language"] = args.language

    if destination.exists() and not args.refresh:
        text = destination.read_text()
        print(f"{kind}: already cached ({len(text):,} chars). Pass --refresh to fetch again.")
        print(f"cached: {destination}")
        return 0

    result = fetch(args.source, deck.root / ".ancci" / "cache", **options)
    destination.write_text(result.text)

    print(f"{kind}: {result.title}")
    print(f"{len(result.text):,} characters -> {destination}")
    for name, value in result.notes.items():
        if value:
            print(f"  {name}: {value}")
    print()
    print(citation_block(result))
    print()
    print("preview:")
    for line in result.text.splitlines()[:PREVIEW_LINES]:
        print(f"  {line[:100]}")
    return 0


if __name__ == "__main__":
    sys.exit(run(main))
