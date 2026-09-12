"""Shared plumbing for the entry scripts.

Deliberately imports nothing that talks to Anki or renders Markdown, so a script that only
validates card files does not pay for a syntax highlighter.
"""

import argparse
import sys
from pathlib import Path

from .config import Deck, area_of, find_deck, load_deck
from .errors import AnkiError, ConfigError
from .schema import CardFile, load


def deck_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--deck", help="deck directory (default: the deck containing the working directory)")


def target_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("targets", nargs="*", help="area names or YAML paths (default: the whole deck)")


def deck_from(args) -> Deck:
    """The deck named by --deck, else the one containing the working directory."""
    return load_deck(Path(args.deck)) if args.deck else find_deck()


def paths_for(deck: Deck, targets: list[str]) -> tuple[list[Path], list[str]]:
    """Resolve area names (or paths) to card files. Order comes from the NN- prefix."""
    files = deck.card_files()
    if not targets:
        return files, []
    by_area = {area_of(path): path for path in files}
    paths, missing = [], []
    for target in targets:
        if target.endswith((".yaml", ".yml")):
            path = Path(target)
            (paths if path.exists() else missing).append(path if path.exists() else target)
        elif target in by_area:
            paths.append(by_area[target])
        else:
            missing.append(target)
    return paths, missing


def load_files(deck: Deck, targets: list[str]) -> tuple[list[CardFile], int]:
    paths, missing = paths_for(deck, targets)
    for target in missing:
        print(f"error: no such area or file: {target}", file=sys.stderr)
    files, problems = load(paths, deck)
    for problem in problems:
        print(problem, file=sys.stderr)
    errors = len(missing) + sum(p.error for p in problems)
    warnings = len(problems) - sum(p.error for p in problems)
    total = sum(len(f.cards) for f in files)
    print(f"{total} cards in {len(files)} files: {errors} errors, {warnings} warnings")
    return files, errors


def run(main) -> int:
    """Turn the failures a user can actually cause into a message rather than a traceback."""
    try:
        return main()
    except (ConfigError, AnkiError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
