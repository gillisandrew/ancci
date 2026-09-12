#!/usr/bin/env -S uv run --script --no-config
# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic>=2.8", "pyyaml>=6.0"]
# ///
"""List the decks here, so a session at the root of a repository can pick one."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _lib.cli import run  # noqa: E402
from _lib.config import area_of, find_decks  # noqa: E402
from _lib.schema import load  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(prog="ancci decks", description=__doc__)
    parser.add_argument("--at", help="where to look (default: the working directory)")
    args = parser.parse_args()

    root = Path(args.at).expanduser() if args.at else Path.cwd()
    decks = find_decks(root)
    if not decks:
        print(f"no decks in {root}")
        return 1

    for deck in decks:
        paths = deck.card_files()
        files, problems = load(paths, deck)
        cards = sum(len(f.cards) for f in files)
        errors = sum(p.error for p in problems)
        areas = ", ".join(area_of(p) for p in paths) or "(no cards yet)"
        flag = f"  [{errors} errors]" if errors else ""
        print(f"{deck.root.name}  ->  Anki deck {deck.config.name!r}{flag}")
        print(f"  {cards} cards in {len(paths)} areas: {areas}")
    print(f"\nPass --deck <name> to any command, e.g. --deck {decks[0].root.name}")
    return 0


if __name__ == "__main__":
    sys.exit(run(main))
