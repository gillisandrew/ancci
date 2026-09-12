#!/usr/bin/env -S uv run --script --no-config
# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic>=2.8", "pyyaml>=6.0"]
# ///
"""Check a deck's card files. Touches nothing and needs no Anki."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _lib.cli import deck_argument, deck_from, load_files, run, target_arguments  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(prog="ancci validate", description=__doc__)
    deck_argument(parser)
    target_arguments(parser)
    args = parser.parse_args()
    _, errors = load_files(deck_from(args), args.targets)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(run(main))
