#!/usr/bin/env -S uv run --script --no-config
# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic>=2.8", "pyyaml>=6.0", "requests>=2.32"]
# ///
"""List the cards you marked while studying: flagged, leeches, and Feedback notes."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _lib.anki import DEFAULT_URL, AnkiConnect  # noqa: E402
from _lib.cli import deck_argument, deck_from, run  # noqa: E402
from _lib.review import report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(prog="ancci report", description=__doc__)
    deck_argument(parser)
    parser.add_argument("--url", default=DEFAULT_URL)
    args = parser.parse_args()
    print(report(AnkiConnect(args.url), deck_from(args)))
    return 0


if __name__ == "__main__":
    sys.exit(run(main))
