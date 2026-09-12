"""Card file schema. The YAML files in a deck's cards/ directory are its source of truth.

What counts as a valid card is a property of the deck, not of the tool. Which keys a card
must carry, which it may carry, and which are forbidden all come from the card type it
names; the deck declares those types, and the tool ships two.

A card is valid or it is not. How long an answer should be, how many bullets it wants — that
is a judgement, and it belongs to whoever writes the card, working from the deck's
AUTHORING.md. The validator has no opinion on it.
"""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .config import BUILTIN_KEYS, RESERVED_FIELDS, Deck, DeckConfig, area_of
from .sources import Source, check, coerce

ORPHAN_TAG = "orphaned"

SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
CLOZE_RE = re.compile(r"\{\{c(\d+)::")


def _plain(text: str) -> str:
    return re.sub(r"[`*_]", "", text).strip().lower()


class Card(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    topic: str
    front: str | None = None
    back: str | None = None
    text: str | None = None
    extra: str | None = None
    code: str | None = None
    reverse: bool = False
    # Anki fields this deck declared for itself: audio, an image, a phonetic transcription.
    fields: dict[str, str] = {}
    tags: list[str] = []
    sources: list[Source] = Field(min_length=1)
    verified: date

    @property
    def area(self) -> str:
        return self.id.split(".", 1)[0]

    def present_keys(self) -> set[str]:
        """Which built-in keys this card actually carries."""
        return {key for key in BUILTIN_KEYS if getattr(self, key)}

    def anki_tags(self, config: DeckConfig) -> list[str]:
        return [f"{config.tag_root}::{self.area}::{self.topic}", self.type, *self.tags]

    @field_validator("sources", mode="before")
    @classmethod
    def _coerce_sources(cls, values: object) -> object:
        # A bare string is shorthand for a URL, which is how most cards cite.
        return [coerce(v) for v in values] if isinstance(values, list) else values

    @field_validator("id")
    @classmethod
    def _id_shape(cls, value: str) -> str:
        if not re.fullmatch(rf"{SLUG}\.{SLUG}", value):
            raise ValueError("id must look like '<area>.<kebab-slug>'")
        return value

    @field_validator("topic")
    @classmethod
    def _topic_shape(cls, value: str) -> str:
        if not re.fullmatch(SLUG, value):
            raise ValueError("topic must be a kebab-case slug")
        return value

    @model_validator(mode="after")
    def _shape(self) -> "Card":
        """Only what can be judged without the deck. The rest lives in errors()."""
        if self.reverse and self.front and self.back and _plain(self.front) in _plain(self.back):
            raise ValueError("reversed card would leak the answer: back contains the front term")
        if self.code is not None and "```" not in self.code:
            raise ValueError("code must contain a fenced code block")
        for name in self.fields:
            if name in RESERVED_FIELDS:
                raise ValueError(f"field {name!r} is reserved; ancci writes it")
        return self

    def errors(self, config: DeckConfig) -> list[str]:
        """Checks that need the deck's config, so they cannot live on the model itself."""
        out = []
        # Type-independent first. A bad citation or an undeclared tag is wrong whatever the
        # type is, and reporting it now saves a second round trip once a typo'd type name
        # is fixed.
        for tag in self.tags:
            if tag not in config.tags:
                out.append(f"unknown tag '{tag}'; this deck uses {', '.join(config.tags) or '(none)'}")
        out += [problem for source in self.sources if (problem := check(source, config.sources))]

        types = config.card_type_map()
        card_type = types.get(self.type)
        if card_type is None:
            known = ", ".join(sorted(types))
            return [*out, f"unknown type '{self.type}'; this deck has {known}"]

        present = self.present_keys()
        if missing := card_type.missing(present):
            out.append(f"type '{self.type}' requires {', '.join(missing)}")
        if forbidden := card_type.forbidden(present):
            out.append(f"type '{self.type}' does not take {', '.join(forbidden)}")
        if card_type.cloze and self.text and not CLOZE_RE.search(self.text):
            out.append("cloze types need text containing {{c1::...}}")
        for name in self.fields:
            if name not in card_type.fields:
                declared = ", ".join(card_type.fields) or "(none)"
                out.append(f"type '{self.type}' declares no field '{name}'; it has {declared}")
        return out


class CardFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    area: str
    cards: list[Card]

    @field_validator("area")
    @classmethod
    def _area_shape(cls, value: str) -> str:
        if not re.fullmatch(SLUG, value):
            raise ValueError("area must be a kebab-case slug")
        return value


@dataclass(frozen=True)
class Problem:
    path: Path
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.where}: error: {self.message}"


def _where(raw: object, loc: tuple) -> str:
    if len(loc) >= 2 and loc[0] == "cards" and isinstance(loc[1], int):
        try:
            card_id = raw["cards"][loc[1]]["id"]
        except (KeyError, IndexError, TypeError):
            card_id = f"cards[{loc[1]}]"
        return ".".join([str(card_id), *map(str, loc[2:])])
    return ".".join(map(str, loc)) or "-"


def load(paths: list[Path], deck: Deck) -> tuple[list[CardFile], list[Problem]]:
    """Parse and validate card files against their deck, including cross-file checks."""
    config = deck.config
    files: list[CardFile] = []
    problems: list[Problem] = []
    seen: dict[str, Path] = {}
    for path in paths:
        try:
            raw = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            problems.append(Problem(path, "-", f"invalid YAML: {exc}"))
            continue
        try:
            card_file = CardFile.model_validate(raw)
        except ValidationError as exc:
            problems.extend(Problem(path, _where(raw, err["loc"]), err["msg"]) for err in exc.errors())
            continue
        # The NN- prefix orders files and is stripped; the area is the rest of the name.
        if card_file.area != area_of(path):
            problems.append(Problem(path, "area", f"area '{card_file.area}' must match the file name"))
        for card in card_file.cards:
            if card.area != card_file.area:
                problems.append(Problem(path, card.id, f"id must start with '{card_file.area}.'"))
            if card.id in seen:
                problems.append(Problem(path, card.id, f"duplicate id (also in {seen[card.id]})"))
            seen[card.id] = path
            problems.extend(Problem(path, card.id, e) for e in card.errors(config))
        files.append(card_file)
    return files, problems
