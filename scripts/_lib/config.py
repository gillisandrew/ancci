"""Deck configuration.

The tool ships defaults; a deck overrides what it needs in `deck.yaml`, and a repo of
several decks can share house style in a root `ancci.yaml` that each deck inherits.

A deck is a directory containing `deck.yaml`. Commands find it by walking up from the
working directory, so you can run them from anywhere inside a deck.

What a card may look like is a property of the deck. A **card type** is a contract: which
built-in keys a card must and may carry, whether it is cloze, which Anki note type it lands
in, and which extra fields it adds.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from .errors import ConfigError

DECK_CONFIG = "deck.yaml"
ROOT_CONFIG = "ancci.yaml"

# The keys a card may carry beyond its identity and provenance. A type says which of these
# it requires and which it merely allows; anything unlisted is forbidden.
BUILTIN_KEYS = ("front", "back", "text", "extra", "code", "reverse")

# Names the sync owns. A deck declaring one of these would either collide with a field the
# renderer writes, or with `Feedback`, which is yours and which sync must never touch.
RESERVED_FIELDS = frozenset(
    {"ID", "Front", "Back", "Text", "Extra", "Code", "Sources", "Verified", "Reverse", "Feedback"}
)

__all__ = [
    "BUILTIN_KEYS",
    "DECK_CONFIG",
    "RESERVED_FIELDS",
    "ROOT_CONFIG",
    "SHIPPED_TYPES",
    "CardType",
    "ConfigError",
    "Deck",
    "DeckConfig",
    "SourceRules",
    "area_of",
    "find_deck",
    "find_decks",
    "load_deck",
    "resolve_deck",
]


class SourceRules(BaseModel):
    """What a deck is willing to cite. Applies to URLs; a path is not a publisher."""

    model_config = ConfigDict(extra="forbid")

    # None means any host is acceptable; a list restricts URL sources to those hosts.
    hosts: list[str] | None = None
    github_orgs: list[str] = []
    require_https: bool = True


class CardType(BaseModel):
    """What a card of this type must look like, and where it lands in Anki."""

    model_config = ConfigDict(extra="forbid")

    # Which entry in the deck's `note_types:` this type's cards are created on.
    note_type: str = "basic"
    cloze: bool = False
    requires: list[str] = []
    optional: list[str] = []
    # Extra Anki fields this type adds, beyond the ones ancci writes itself. This is how a
    # card carries audio, an image, or anything else the built-in keys do not cover.
    fields: list[str] = []

    @model_validator(mode="after")
    def _coherent(self) -> "CardType":
        named = [*self.requires, *self.optional]
        for key in named:
            if key not in BUILTIN_KEYS and key not in self.fields:
                raise ValueError(f"{key!r} is neither a built-in key nor a field this type declares")
        for name in self.fields:
            if name in RESERVED_FIELDS:
                raise ValueError(f"field {name!r} is reserved; ancci writes it")
        if self.cloze and "reverse" in named:
            raise ValueError("a cloze type cannot accept `reverse`: its note type has no Reverse field")
        if self.cloze and "text" not in named:
            raise ValueError("a cloze type must accept `text`")
        return self

    def missing(self, present: set[str]) -> list[str]:
        return sorted(k for k in self.requires if k not in present)

    def forbidden(self, present: set[str]) -> list[str]:
        allowed = {*self.requires, *self.optional}
        return sorted(k for k in present if k not in allowed)


# The two shapes every deck always has. Everything else a deck names itself.
SHIPPED_TYPES: dict[str, CardType] = {
    "basic": CardType(note_type="basic", requires=["front", "back"], optional=["code", "reverse"]),
    "cloze": CardType(note_type="cloze", cloze=True, requires=["text"], optional=["extra", "code"]),
}


class DeckConfig(BaseModel):
    """Everything the validator and the sync need to know about one deck."""

    model_config = ConfigDict(extra="forbid")

    name: str
    tag_root: str

    # The only prose most decks need. What the reader already knows, what belongs on a
    # card, and what does not — the three things that change what a good card looks like.
    # A deck wanting more than three lines drops an AUTHORING.md beside deck.yaml instead.
    audience: str | None = None
    scope: str | None = None
    avoid: str | None = None

    # Key -> Anki model name. Note types are global in Anki, so each deck names its own.
    # Open: a deck may add more than the two defaults.
    note_types: dict[str, str] | None = None

    # Bare type names using the shipped `basic` contract. A name matching a shipped type
    # resolves to that type instead — without which a deck listing `cloze` here would route
    # its cloze cards onto the basic note type, which Anki cannot do in place.
    types: list[str] = []
    # Types declaring their own contract. These override anything above.
    card_types: dict[str, CardType] = {}

    # Extra tags a card may carry beyond its type and topic. Deck vocabulary, not universal.
    tags: list[str] = ["beta", "migration"]
    sources: SourceRules = SourceRules()
    # A stylesheet of this deck's own, relative to the deck. Restyling is all a deck needs;
    # the card templates themselves are the tool's.
    css: str | None = None

    @model_validator(mode="after")
    def _defaults(self) -> "DeckConfig":
        if self.note_types is None:
            self.note_types = {"basic": f"{self.name} Basic", "cloze": f"{self.name} Cloze"}
        for key in ("basic", "cloze"):
            self.note_types.setdefault(key, f"{self.name} {key.title()}")
        for name, card_type in self.card_types.items():
            if card_type.note_type not in self.note_types:
                raise ValueError(
                    f"card type {name!r} lands on note type {card_type.note_type!r}, "
                    f"which this deck does not declare"
                )
        return self

    def card_type_map(self) -> dict[str, CardType]:
        """Every card type this deck has: the shipped floor, its bare names, its own."""
        resolved = dict(SHIPPED_TYPES)
        for name in self.types:
            # A shipped name keeps its shipped contract; anything else gets `basic`.
            resolved.setdefault(name, SHIPPED_TYPES["basic"])
        resolved.update(self.card_types)
        return resolved

    def fields_for(self, note_type_key: str) -> list[str]:
        """The deck-declared fields landing on one note type, in declaration order."""
        seen: list[str] = []
        for card_type in self.card_type_map().values():
            if card_type.note_type != note_type_key:
                continue
            for name in card_type.fields:
                if name not in seen:
                    seen.append(name)
        return seen


class Deck:
    """A loaded deck: its config plus where on disk it lives."""

    def __init__(self, config: DeckConfig, root: Path):
        self.config = config
        self.root = root

    @property
    def cards_dir(self) -> Path:
        return self.root / "cards"

    @property
    def research_dir(self) -> Path:
        return self.root / "research"

    def card_files(self) -> list[Path]:
        """Card files in study order: the NN- filename prefix orders them, nothing else."""
        return sorted(p for p in self.cards_dir.glob("*.y*ml") if p.suffix in (".yaml", ".yml"))


def area_of(path: Path) -> str:
    """`cards/01-patterns.yaml` -> `patterns`. The prefix orders files and means nothing else."""
    stem = path.stem
    head, sep, rest = stem.partition("-")
    return rest if sep and head.isdigit() else stem


def _merge(base: dict, override: dict) -> dict:
    """Shallow-merge per key, one level deep for nested tables, override winning."""
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = {**out[key], **value}
        else:
            out[key] = value
    return out


def find_decks(start: Path | None = None) -> list["Deck"]:
    """Every deck at or just below `start`, in name order."""
    start = (start or Path.cwd()).resolve()
    if (start / DECK_CONFIG).is_file():
        return [load_deck(start)]
    return [load_deck(path.parent) for path in sorted(start.glob(f"*/{DECK_CONFIG}"))]


def resolve_deck(spec: str | None = None, start: Path | None = None) -> "Deck":
    """A deck named by path, by name, or by where you are standing."""
    start = (start or Path.cwd()).resolve()
    if spec is None:
        return find_deck(start)
    path = Path(spec).expanduser()
    if (path / DECK_CONFIG).is_file():
        return load_deck(path)
    if (start / spec / DECK_CONFIG).is_file():
        return load_deck(start / spec)
    names = ", ".join(deck.root.name for deck in find_decks(start))
    raise ConfigError(f"no deck {spec!r} here. Decks found: {names or '(none)'}")


def find_deck(start: Path | None = None) -> "Deck":
    """Walk up from `start` looking for a deck. Raises ConfigError naming nearby decks."""
    start = (start or Path.cwd()).resolve()
    for directory in (start, *start.parents):
        if (directory / DECK_CONFIG).is_file():
            return load_deck(directory)
    raise ConfigError(_no_deck_message(start))


def _no_deck_message(start: Path) -> str:
    """Never guess which deck was meant; say what is here instead."""
    nearby = sorted(p.parent.name for p in start.glob(f"*/{DECK_CONFIG}"))
    if nearby:
        return f"no {DECK_CONFIG} here. Decks found: {', '.join(nearby)}. cd into one, or pass --deck"
    return f"no {DECK_CONFIG} in {start} or any parent directory"


def load_deck(root: Path) -> "Deck":
    """Load a deck's config, inheriting from a root ancci.yaml if one sits above it."""
    config_path = root / DECK_CONFIG
    if not config_path.is_file():
        raise ConfigError(f"no {DECK_CONFIG} in {root}")
    try:
        raw = yaml.safe_load(config_path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"{config_path}: invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{config_path}: expected a mapping")

    try:
        config = DeckConfig.model_validate(_merge(_shared_config(root), raw))
    except Exception as exc:
        raise ConfigError(f"{config_path}: {exc}") from exc
    return Deck(config, root)


def _shared_config(deck_root: Path) -> dict:
    """House style from the nearest ancci.yaml above the deck, if any."""
    for directory in deck_root.parents:
        shared = directory / ROOT_CONFIG
        if shared.is_file():
            try:
                raw = yaml.safe_load(shared.read_text()) or {}
            except yaml.YAMLError as exc:
                raise ConfigError(f"{shared}: invalid YAML: {exc}") from exc
            if not isinstance(raw, dict):
                raise ConfigError(f"{shared}: expected a mapping")
            return raw
    return {}
