"""Card file schema. The YAML files in a deck's cards/ directory are its source of truth.

What counts as a valid card is a property of the deck, not of the tool: its styles, its
answer-shape limits, what it may cite and what tags it uses all come from its config.
"""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .config import Deck, DeckConfig, area_of
from .sources import Source, check, coerce

ORPHAN_TAG = "orphaned"

SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
CLOZE_RE = re.compile(r"\{\{c(\d+)::")


def _plain(text: str) -> str:
    return re.sub(r"[`*_]", "", text).strip().lower()


class Card(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    style: str
    topic: str
    front: str | None = None
    back: str | None = None
    text: str | None = None
    extra: str | None = None
    code: str | None = None
    reverse: bool = False
    tags: list[str] = []
    sources: list[Source] = Field(min_length=1)
    verified: date

    @property
    def area(self) -> str:
        return self.id.split(".", 1)[0]

    @property
    def is_cloze(self) -> bool:
        return self.style == "cloze"

    def anki_tags(self, config: DeckConfig) -> list[str]:
        return [f"{config.tag_root}::{self.area}::{self.topic}", self.style, *self.tags]

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
        if self.is_cloze:
            if self.front or self.back:
                raise ValueError("cloze cards use text/extra, not front/back")
            if not self.text or not CLOZE_RE.search(self.text):
                raise ValueError("cloze cards need text containing {{c1::...}}")
        else:
            if self.text or self.extra:
                raise ValueError(f"{self.style} cards use front/back, not text/extra")
            if not self.front or not self.back:
                raise ValueError(f"{self.style} cards need both front and back")
        if self.reverse:
            if self.style != "definition":
                raise ValueError("reverse is only allowed on definition cards")
            if _plain(self.front) in _plain(self.back):
                raise ValueError("reversed card would leak the answer: back contains the front term")
        if self.code is not None and "```" not in self.code:
            raise ValueError("code must contain a fenced code block")
        return self

    def errors(self, config: DeckConfig) -> list[str]:
        """Checks that need the deck's config, so they cannot live on the model itself."""
        out = []
        if self.style not in config.styles:
            out.append(f"unknown style '{self.style}'; this deck uses {', '.join(config.styles)}")
        for tag in self.tags:
            if tag not in config.tags:
                out.append(f"unknown tag '{tag}'; this deck uses {', '.join(config.tags) or '(none)'}")
        out += [problem for source in self.sources if (problem := check(source, config.sources))]
        return out

    def warnings(self, config: DeckConfig) -> list[str]:
        limits = config.limits
        out = []
        if self.is_cloze:
            deletions = len(set(CLOZE_RE.findall(self.text)))
            if deletions > limits.cloze_deletions:
                out.append(f"{deletions} cloze deletions; split the card (max {limits.cloze_deletions})")
        else:
            question = re.sub(r"```.*?```", "", self.front, flags=re.DOTALL)  # pattern snippets don't count
            if len(question) > limits.front_chars:
                out.append(
                    f"front is {len(question)} chars excluding code; condense the question (max {limits.front_chars})"
                )
            if len(self.back) > limits.back_chars:
                out.append(
                    f"back is {len(self.back)} chars; condense to bold verdict + bullets (max {limits.back_chars})"
                )
            bullets = sum(1 for line in self.back.splitlines() if re.match(r"\s*[-*] ", line))
            if bullets > limits.bullets:
                out.append(f"back has {bullets} bullets (max {limits.bullets})")
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
