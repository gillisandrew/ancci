"""ancci: validate card files, sync them into Anki, and report flagged cards."""

import argparse
import sys
from pathlib import Path

from .anki import DEFAULT_URL, AnkiConnect, AnkiError
from .config import ConfigError, Deck, area_of, find_deck, load_deck
from .schema import CardFile, load
from .sync import report, resolve, sync


def _deck(args) -> Deck:
    """The deck named by --deck, else the one containing the working directory."""
    return load_deck(Path(args.deck)) if args.deck else find_deck()


def _paths(deck: Deck, targets: list[str]) -> tuple[list[Path], list[str]]:
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


def _load(deck: Deck, targets: list[str]) -> tuple[list[CardFile], int]:
    paths, missing = _paths(deck, targets)
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


def _validate(args) -> int:
    _, errors = _load(_deck(args), args.targets)
    return 1 if errors else 0


def _sync(args) -> int:
    deck = _deck(args)
    files, errors = _load(deck, args.targets)
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


def _report(args) -> int:
    print(report(AnkiConnect(args.url), _deck(args)))
    return 0


def _resolve(args) -> int:
    if not args.targets and not args.all:
        print("error: name the card ids to clear, or pass --all", file=sys.stderr)
        return 2
    cleared, errors = resolve(AnkiConnect(args.url), _deck(args), args.targets, everything=args.all)
    for card_id in cleared:
        print(f"cleared {card_id}")
    print(f"{len(cleared)} cards cleared")
    for message in errors:
        print(f"error: {message}", file=sys.stderr)
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ancci", description=__doc__)
    parser.add_argument("--deck", help="deck directory (default: the deck containing the working directory)")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="check card files without touching Anki")
    validate.add_argument("targets", nargs="*", help="area names or YAML paths (default: the whole deck)")
    validate.set_defaults(run=_validate)

    sync_cmd = sub.add_parser("sync", help="push card files into Anki (repo wins)")
    sync_cmd.add_argument("targets", nargs="*", help="area names or YAML paths (default: the whole deck)")
    sync_cmd.add_argument("--dry-run", action="store_true", help="show what would change without writing")
    sync_cmd.add_argument("-v", "--verbose", action="store_true", help="with --dry-run, list affected card ids")
    sync_cmd.add_argument("--url", default=DEFAULT_URL)
    sync_cmd.set_defaults(run=_sync)

    report_cmd = sub.add_parser("report", help="list flagged cards, leeches and Feedback notes")
    report_cmd.add_argument("--url", default=DEFAULT_URL)
    report_cmd.set_defaults(run=_report)

    resolve_cmd = sub.add_parser("resolve", help="clear Feedback and flags on cards you have since fixed")
    resolve_cmd.add_argument("targets", nargs="*", help="card ids, as printed by report")
    resolve_cmd.add_argument("--all", action="store_true", help="every flagged or Feedback card in the deck")
    resolve_cmd.add_argument("--url", default=DEFAULT_URL)
    resolve_cmd.set_defaults(run=_resolve)

    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except AnkiError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
