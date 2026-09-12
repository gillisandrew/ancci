"""Card file schema. The YAML files in a deck's cards/ directory are its source of truth.

What counts as a valid card is a property of the deck, not of the tool. Which keys a card
must carry, which it may carry, and which are forbidden all come from the card type it
names; the deck declares those types, and the tool ships two.
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
    # `style` is the older spelling and means exactly the same thing. Cards written before
    # types existed keep parsing, and nothing had to be rewritten to introduce them.
    type: str | None = None
    style: str | None = None
    topic: str
    front: str | None = None
    back: str | None = None
    text: str | None = None
    extra: str | None = None
    code: str | None = None
    reverse: bool = False
    # Anki fields this deck declared for itself, beyond the ones ancci writes.
    fields: dict[str, str] = {}
    tags: list[str] = []
    sources: list[Source] = Field(min_length=1)
    verified: date

    @property
    def area(self) -> str:
        return self.id.split(".", 1)[0]

    @property
    def kind(self) -> str:
        """The card type this card names, whichever spelling it used."""
        return self.type or self.style or ""

    def present_keys(self) -> set[str]:
        """Which built-in keys this card actually carries."""
        return {key for key in BUILTIN_KEYS if getattr(self, key)}

    def anki_tags(self, config: DeckConfig) -> list[str]:
        return [f"{config.tag_root}::{self.area}::{self.topic}", self.kind, *self.tags]

    @field_validator("sources", mode="before")
    @classmethod
    def _coerce_sources(cls, values: object) -> object:
        # A bare string is shorthand for a URL, which is how every card was written
        # before sources grew types.
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
        if self.type and self.style and self.type != self.style:
            raise ValueError(f"card names two types: type {self.type!r} and style {self.style!r}")
        if not self.kind:
            raise ValueError("card must name a type")
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

        types = config.types()
        card_type = types.get(self.kind)
        if card_type is None:
            known = ", ".join(sorted(types))
            return [*out, f"unknown type '{self.kind}'; this deck has {known}"]

        present = self.present_keys()
        if missing := card_type.missing(present):
            out.append(f"type '{self.kind}' requires {', '.join(missing)}")
        if forbidden := card_type.forbidden(present):
            out.append(f"type '{self.kind}' does not take {', '.join(forbidden)}")
        if card_type.cloze and self.text and not CLOZE_RE.search(self.text):
            out.append("cloze types need text containing {{c1::...}}")
        for name in self.fields:
            if name not in card_type.fields:
                declared = ", ".join(card_type.fields) or "(none)"
                out.append(f"type '{self.kind}' declares no field '{name}'; it has {declared}")
        return out

    def _value(self, name: str) -> str | None:
        return getattr(self, name, None) if name in BUILTIN_KEYS else self.fields.get(name)

    def warnings(self, config: DeckConfig) -> list[str]:
        limits = config.limits
        card_type = config.types().get(self.kind)
        if card_type is None:
            return []

        out = []
        if card_type.cloze:
            if self.text and len(set(CLOZE_RE.findall(self.text))) > limits.cloze_deletions:
                found = len(set(CLOZE_RE.findall(self.text)))
                out.append(f"{found} cloze deletions; split the card (max {limits.cloze_deletions})")
        else:
            if self.front:
                question = re.sub(r"```.*?```", "", self.front, flags=re.DOTALL)
                if len(question) > limits.front_chars:
                    out.append(
                        f"front is {len(question)} chars excluding code; "
                        f"condense the question (max {limits.front_chars})"
                    )
            if self.back:
                if len(self.back) > limits.back_chars:
                    out.append(
                        f"back is {len(self.back)} chars; "
                        f"condense to bold verdict + bullets (max {limits.back_chars})"
                    )
                bullets = sum(1 for line in self.back.splitlines() if re.match(r"\s*[-*] ", line))
                if bullets > limits.bullets:
                    out.append(f"back has {bullets} bullets (max {limits.bullets})")

        # Per-field limits. One naming a field this type does not have is simply not checked.
        for name, limit in limits.fields.items():
            value = self._value(name)
            if not value:
                continue
            if limit.chars and len(value) > limit.chars:
                out.append(f"{name} is {len(value)} chars (max {limit.chars})")
            if limit.bullets:
                bullets = sum(1 for line in value.splitlines() if re.match(r"\s*[-*] ", line))
                if bullets > limit.bullets:
                    out.append(f"{name} has {bullets} bullets (max {limit.bullets})")
            if limit.deletions and len(set(CLOZE_RE.findall(value))) > limit.deletions:
                out.append(f"{name} has more than {limit.deletions} cloze deletions")

        if self.code and self.code.count("\n") > 25:
            out.append("code block is over 25 lines")
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
    error: bool = True

    def __str__(self) -> str:
        level = "error" if self.error else "warning"
        return f"{self.path}:{self.where}: {level}: {self.message}"


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
            problems.extend(Problem(path, card.id, w, error=False) for w in card.warnings(config))
        files.append(card_file)
    return files, problems
