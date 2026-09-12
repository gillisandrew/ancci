#!/usr/bin/env -S uv run --script --no-config
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pydantic>=2.8",
#   "pyyaml>=6.0",
#   "markdown-it-py>=3.0",
#   "pygments>=2.18",
#   "requests>=2.32",
# ]
# ///
"""Push a deck's card files into Anki. The repo wins; your review history is left alone."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _lib.anki import DEFAULT_URL, AnkiConnect  # noqa: E402
from _lib.cli import deck_argument, deck_from, load_files, run, target_arguments  # noqa: E402
from _lib.config import area_of  # noqa: E402
from _lib.sync import sync  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(prog="ancci sync", description=__doc__)
    deck_argument(parser)
    target_arguments(parser)
    parser.add_argument("--dry-run", action="store_true", help="show what would change without writing")
    parser.add_argument("-v", "--verbose", action="store_true", help="with --dry-run, list affected card ids")
    parser.add_argument("--url", default=DEFAULT_URL)
    args = parser.parse_args()

    deck = deck_from(args)
    files, errors = load_files(deck, args.targets)
    if errors:
        return 1
    # With no targets every area is in scope, so deleting a whole area file orphans its cards too.
    areas = {f.area for f in files} if args.targets else {area_of(p) for p in deck.card_files()}
    result, apply_errors = sync(AnkiConnect(args.url), deck, files, areas, dry_run=args.dry_run)

    verb = "would" if args.dry_run else "did"
    print(
        f"{verb}: add {len(result.adds)}, update {len(result.updates)}, orphan {len(result.orphans)}, "
        f"revive {len(result.revives)}; {result.unchanged} unchanged"
    )
    if args.dry_run and args.verbose:
        for card in result.adds:
            print(f"  + {card.id}")
        for _, card in result.updates:
            print(f"  ~ {card.id}")
        for note in result.orphans:
            print(f"  - {note.fields['ID']}")
    for message in result.conflicts + apply_errors:
        print(f"error: {message}", file=sys.stderr)
    return 1 if result.conflicts or apply_errors else 0


if __name__ == "__main__":
    sys.exit(run(main))
