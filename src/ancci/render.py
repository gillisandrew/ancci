"""Render card Markdown into the HTML stored in Anki fields."""

import html
from urllib.parse import urlparse

from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

from .schema import Card

LEXER_ALIASES = {"pseudo": "python", "pseudocode": "python"}


def _highlight(code: str, lang: str, _attrs: str) -> str:
    try:
        lexer = get_lexer_by_name(LEXER_ALIASES.get(lang, lang))
    except ClassNotFound:
        return ""  # markdown-it falls back to escaped plain text
    return highlight(code, lexer, HtmlFormatter(nowrap=True))


# html=False: raw tags in card text (e.g. <thinking>) are shown literally, not interpreted.
_md = MarkdownIt("commonmark", {"html": False, "highlight": _highlight}).enable(["table", "strikethrough"])


def markdown(text: str | None) -> str:
    return _md.render(text).strip() if text else ""


def sources_html(urls: list[str]) -> str:
    links = []
    for url in urls:
        parsed = urlparse(url)
        label = f"{parsed.hostname}{parsed.path.rstrip('/')}"
        links.append(f'<a href="{html.escape(url)}">{html.escape(label)}</a>')
    return " · ".join(links)


def fields(card: Card) -> dict[str, str]:
    """Every field the sync owns. The user-owned Feedback field is deliberately absent."""
    common = {
        "ID": card.id,
        "Code": markdown(card.code),
        "Sources": sources_html(card.sources),
        "Verified": card.verified.isoformat(),
    }
    if card.is_cloze:
        return {**common, "Text": markdown(card.text), "Extra": markdown(card.extra)}
    return {**common, "Front": markdown(card.front), "Back": markdown(card.back), "Reverse": "y" if card.reverse else ""}
