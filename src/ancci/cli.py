"""ancci: validate card files, sync them into Anki, and report flagged cards."""

import argparse
import sys
from pathlib import Path

from .anki import DEFAULT_URL, AnkiConnect, AnkiError
from .schema import AREAS, CardFile, load
from .sync import report, sync

CARDS_DIR = Path("cards")


def _resolve(targets: list[str]) -> list[Path]:
    if targets:
        return [Path(t) if t.endswith((".yaml", ".yml")) else CARDS_DIR / f"{t}.yaml" for t in targets]
    order = {area: i for i, area in enumerate(AREAS)}
    return sorted(CARDS_DIR.glob("*.yaml"), key=lambda p: (order.get(p.stem, len(order)), p.stem))


def _load(targets: list[str]) -> tuple[list[CardFile], int]:
    paths = _resolve(targets)
    missing = [p for p in paths if not p.exists()]
    for path in missing:
        print(f"{path}: error: no such file", file=sys.stderr)
    files, problems = load([p for p in paths if p.exists()])
    for problem in problems:
        print(problem, file=sys.stderr)
    errors = len(missing) + sum(p.error for p in problems)
    total = sum(len(f.cards) for f in files)
    print(f"{total} cards in {len(files)} files: {errors} errors, {len(problems) - sum(p.error for p in problems)} warnings")
    return files, errors


def _validate(args) -> int:
    _, errors = _load(args.targets)
    return 1 if errors else 0


def _sync(args) -> int:
    files, errors = _load(args.targets)
    if errors:
        return 1
    # With no targets every area is in scope, so deleting a whole area file orphans its cards too.
    areas = {f.area for f in files} if args.targets else set(AREAS)
    result, apply_errors = sync(AnkiConnect(args.url), files, areas, dry_run=args.dry_run)
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
    print(report(AnkiConnect(args.url)))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ancci", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="check card files without touching Anki")
    validate.add_argument("targets", nargs="*", help="area names or YAML paths (default: everything in cards/)")
    validate.set_defaults(run=_validate)

    sync_cmd = sub.add_parser("sync", help="push card files into Anki (repo wins)")
    sync_cmd.add_argument("targets", nargs="*", help="area names or YAML paths (default: everything in cards/)")
    sync_cmd.add_argument("--dry-run", action="store_true", help="show what would change without writing")
    sync_cmd.add_argument("-v", "--verbose", action="store_true", help="with --dry-run, list affected card ids")
    sync_cmd.add_argument("--url", default=DEFAULT_URL)
    sync_cmd.set_defaults(run=_sync)

    report_cmd = sub.add_parser("report", help="list flagged cards, leeches and Feedback notes")
    report_cmd.add_argument("--url", default=DEFAULT_URL)
    report_cmd.set_defaults(run=_report)

    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except AnkiError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
