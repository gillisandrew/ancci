"""What a card cites.

A source is a web page, a local file, a place in a repository, or a moment in a video.
A bare string is shorthand for a URL, which is what every card written before this module
existed used — so those files keep parsing, and keep rendering byte-for-byte the same.
"""

import html
from pathlib import PurePosixPath
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

from .config import SourceRules


class UrlSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["url"] = "url"
    url: str


class FileSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["file"] = "file"
    path: str
    # Where in the file, when that is worth recording: a page, a heading, a line range.
    at: str | None = None


class RepoSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["repo"] = "repo"
    repo: str
    # A branch moves; pin what was actually read.
    ref: str
    path: str | None = None


class VideoSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["video"] = "video"
    url: str
    # Seconds from the start, so a citation points at the moment rather than the video.
    t: int | None = None


Source = UrlSource | FileSource | RepoSource | VideoSource

SourceField = Field(min_length=1)


def coerce(value: object) -> object:
    """Bare string -> URL source. Anything else is left for pydantic to validate."""
    return {"type": "url", "url": value} if isinstance(value, str) else value


def check(source: Source, rules: SourceRules) -> str | None:
    """Allowlist enforcement, which applies to URLs only: a path is not a publisher."""
    if not isinstance(source, (UrlSource, VideoSource)):
        return None
    parsed = urlparse(source.url)
    if rules.require_https and parsed.scheme != "https":
        return f"source must be https: {source.url}"
    if rules.hosts is None:
        return None
    if parsed.hostname not in rules.hosts:
        return f"source is not on the allowlist: {source.url}"
    if parsed.hostname == "github.com" and rules.github_orgs:
        org = PurePosixPath(parsed.path).parts[1:2]
        if not org or org[0] not in rules.github_orgs:
            return f"GitHub sources must be under {sorted(rules.github_orgs)}: {source.url}"
    return None


def _url_label(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.hostname}{parsed.path.rstrip('/')}"


def link(source: Source) -> str:
    """One rendered citation. URL sources render exactly as they always have."""
    if isinstance(source, UrlSource):
        return f'<a href="{html.escape(source.url)}">{html.escape(_url_label(source.url))}</a>'
    if isinstance(source, VideoSource):
        url = f"{source.url}{'&' if '?' in source.url else '?'}t={source.t}" if source.t else source.url
        label = _url_label(source.url) + (f" @{source.t}s" if source.t else "")
        return f'<a href="{html.escape(url)}">{html.escape(label)}</a>'
    if isinstance(source, RepoSource):
        label = f"{source.repo}@{source.ref[:7]}"
        if source.path:
            label += f" {source.path}"
        return html.escape(label)
    label = source.path + (f" ({source.at})" if source.at else "")
    return html.escape(label)
