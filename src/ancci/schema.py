"""Card file schema. The YAML files in cards/ are the source of truth for the deck."""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

# Rollout order: new cards are added to Anki, and therefore introduced, in this order.
AREAS = ("patterns", "api", "tools", "context", "agents", "claude-code", "mcp", "safety")
STYLES = ("definition", "cloze", "footgun", "tradeoff", "pattern")
EXTRA_TAGS = ("beta", "migration")
ORPHAN_TAG = "orphaned"
TAG_ROOT = "agentic"

SOURCE_HOSTS = {
    "platform.claude.com",
    "docs.claude.com",
    "docs.anthropic.com",
    "code.claude.com",
    "support.claude.com",
    "claude.com",
    "www.claude.com",
    "anthropic.com",
    "www.anthropic.com",
    "modelcontextprotocol.io",
    "blog.modelcontextprotocol.io",
    "github.com",
}
GITHUB_ORGS = {"anthropics", "modelcontextprotocol"}

SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
CLOZE_RE = re.compile(r"\{\{c(\d+)::")


def _plain(text: str) -> str:
    return re.sub(r"[`*_]", "", text).strip().lower()


class Card(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    style: Literal[STYLES]
    topic: str
    front: str | None = None
    back: str | None = None
    text: str | None = None
    extra: str | None = None
    code: str | None = None
    reverse: bool = False
    tags: list[Literal[EXTRA_TAGS]] = []
    sources: list[str] = Field(min_length=1)
    verified: date

    @property
    def area(self) -> str:
        return self.id.split(".", 1)[0]

    @property
    def is_cloze(self) -> bool:
        return self.style == "cloze"

    def anki_tags(self) -> list[str]:
        return [f"{TAG_ROOT}::{self.area}::{self.topic}", self.style, *self.tags]

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

    @field_validator("sources")
    @classmethod
    def _sources_allowed(cls, urls: list[str]) -> list[str]:
        for url in urls:
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.hostname not in SOURCE_HOSTS:
                raise ValueError(f"source is not on the allowlist: {url}")
            if parsed.hostname == "github.com" and parsed.path.strip("/").split("/")[0] not in GITHUB_ORGS:
                raise ValueError(f"GitHub sources must be under {sorted(GITHUB_ORGS)}: {url}")
        return urls

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

    def warnings(self) -> list[str]:
        out = []
        if self.is_cloze:
            deletions = len(set(CLOZE_RE.findall(self.text)))
            if deletions > 3:
                out.append(f"{deletions} cloze deletions; split the card (max 3)")
        else:
            if len(self.front) > 200:
                out.append(f"front is {len(self.front)} chars; condense the question (max 200)")
            if len(self.back) > 300:
                out.append(f"back is {len(self.back)} chars; condense to bold verdict + bullets (max 300)")
            bullets = sum(1 for line in self.back.splitlines() if re.match(r"\s*[-*] ", line))
            if bullets > 3:
                out.append(f"back has {bullets} bullets (max 3)")
        if self.code and self.code.count("\n") > 25:
            out.append("code block is over 25 lines")
        return out


class CardFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    area: Literal[AREAS]
    cards: list[Card]


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


def load(paths: list[Path]) -> tuple[list[CardFile], list[Problem]]:
    """Parse and validate card files, including cross-file checks (unique ids)."""
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
        if card_file.area != path.stem:
            problems.append(Problem(path, "area", f"area '{card_file.area}' must match the file name"))
        for card in card_file.cards:
            if card.area != card_file.area:
                problems.append(Problem(path, card.id, f"id must start with '{card_file.area}.'"))
            if card.id in seen:
                problems.append(Problem(path, card.id, f"duplicate id (also in {seen[card.id]})"))
            seen[card.id] = path
            problems.extend(Problem(path, card.id, w, error=False) for w in card.warnings())
        files.append(card_file)
    return files, problems
