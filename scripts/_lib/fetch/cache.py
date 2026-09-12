"""Where fetched material is kept.

Raw extraction is cached inside the deck at `.ancci/cache/`, and never committed: a repo
clone or a forty-page PDF makes a large, noisy diff and says nothing a reviewer wants to
read. What gets committed is the distilled research note beside it.

Keeping the cache in the deck rather than somewhere global means it is obvious what it
belongs to, and deleting the deck deletes it.
"""

import hashlib
from pathlib import Path

CACHE_DIR = ".ancci/cache"
GITIGNORE = ".ancci/\n"


def cache_dir(deck_root: Path) -> Path:
    """The deck's cache, created on demand and kept out of git."""
    path = deck_root / CACHE_DIR
    path.mkdir(parents=True, exist_ok=True)
    ignore = deck_root / ".gitignore"
    existing = ignore.read_text() if ignore.is_file() else ""
    if ".ancci/" not in existing:
        ignore.write_text(existing + ("" if existing.endswith("\n") or not existing else "\n") + GITIGNORE)
    return path


def key(spec: str) -> str:
    """A stable, filename-safe name for whatever was asked for."""
    return hashlib.sha256(spec.encode()).hexdigest()[:16]


def cached_text(deck_root: Path, spec: str) -> Path:
    return cache_dir(deck_root) / f"{key(spec)}.md"
