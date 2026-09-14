#!/usr/bin/env -S uv run --script --no-config
# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic>=2.8", "pyyaml>=6.0", "requests>=2.32"]
# ///
"""Clear Feedback and flags on cards you have since fixed, and unsuspend them. Leeches keep their tag."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _lib.anki import DEFAULT_URL, AnkiConnect  # noqa: E402
from _lib.cli import deck_argument, deck_from, run  # noqa: E402
from _lib.review import resolve  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(prog="ancci resolve", description=__doc__)
    deck_argument(parser)
    parser.add_argument("targets", nargs="*", help="card ids, as printed by report")
    parser.add_argument("--all", action="store_true", help="every flagged, suspended or Feedback card in the deck")
    parser.add_argument("--url", default=DEFAULT_URL)
    args = parser.parse_args()

    if not args.targets and not args.all:
        print("error: name the card ids to clear, or pass --all", file=sys.stderr)
        return 2
    cleared, errors = resolve(AnkiConnect(args.url), deck_from(args), args.targets, everything=args.all)
    for card_id in cleared:
        print(f"cleared {card_id}")
    print(f"{len(cleared)} cards cleared")
    for message in errors:
        print(f"error: {message}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(run(main))
