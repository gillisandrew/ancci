"""Deck configuration.

The tool ships defaults; a deck overrides what it needs in `deck.yaml`, and a repo of
several decks can share house style in a root `ancci.yaml` that each deck inherits.

A deck is a directory containing `deck.yaml`. Commands find it by walking up from the
working directory, so you can run them from anywhere inside a deck.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

DECK_CONFIG = "deck.yaml"
ROOT_CONFIG = "ancci.yaml"

DEFAULT_STYLES = ("definition", "cloze", "footgun", "tradeoff", "pattern")


class ConfigError(Exception):
    """Raised when a deck's configuration is missing or unusable."""


class Limits(BaseModel):
    """Answer-shape warnings. These never fail a build; they flag cards to condense."""

    model_config = ConfigDict(extra="forbid")

    back_chars: int = 220
    front_chars: int = 200
    bullets: int = 3
    cloze_deletions: int = 3


class SourceRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # None means any host is acceptable; a list restricts URL sources to those hosts.
    hosts: list[str] | None = None
    github_orgs: list[str] = []
    require_https: bool = True


class NoteTypes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    basic: str
    cloze: str


class DeckConfig(BaseModel):
    """Everything the validator and the sync need to know about one deck."""

    model_config = ConfigDict(extra="forbid")

    name: str
    tag_root: str
    note_types: NoteTypes | None = None
    styles: list[str] = list(DEFAULT_STYLES)
    # Extra tags a card may carry beyond its style and topic. Deck vocabulary, not universal.
    tags: list[str] = ["beta", "migration"]
    limits: Limits = Limits()
    sources: SourceRules = SourceRules()
    # Directory of Anki templates/CSS overriding the shipped ones, relative to the deck root.
    templates: str | None = None

    @model_validator(mode="after")
    def _default_note_types(self) -> "DeckConfig":
        # Note types are global in Anki, so they are named per deck to keep decks isolated.
        if self.note_types is None:
            self.note_types = NoteTypes(basic=f"{self.name} Basic", cloze=f"{self.name} Cloze")
        return self

    @property
    def cloze_style(self) -> str:
        return "cloze" if "cloze" in self.styles else ""


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
        found = sorted(p for p in self.cards_dir.glob("*.y*ml") if p.suffix in (".yaml", ".yml"))
        return found


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


def find_deck(start: Path | None = None) -> Deck:
    """Walk up from `start` looking for a deck. Raises ConfigError naming nearby decks."""
    start = (start or Path.cwd()).resolve()
    for directory in (start, *start.parents):
        config_path = directory / DECK_CONFIG
        if config_path.is_file():
            return load_deck(directory)
    raise ConfigError(_no_deck_message(start))


def _no_deck_message(start: Path) -> str:
    """Never guess which deck was meant; say what is here instead."""
    nearby = sorted(p.parent.name for p in start.glob(f"*/{DECK_CONFIG}"))
    if nearby:
        return f"no {DECK_CONFIG} here. Decks found: {', '.join(nearby)}. cd into one, or pass --deck"
    return f"no {DECK_CONFIG} in {start} or any parent directory"


def load_deck(root: Path) -> Deck:
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

    shared = _shared_config(root)
    try:
        config = DeckConfig.model_validate(_merge(shared, raw))
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
