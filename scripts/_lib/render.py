"""Render card Markdown into the HTML stored in Anki fields."""

from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

from .config import DeckConfig
from .schema import Card
from .sources import Source, link

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


def sources_html(sources: list[Source]) -> str:
    return " · ".join(link(source) for source in sources)


def fields(card: Card, config: DeckConfig) -> dict[str, str]:
    """Every field the sync owns. The user-owned Feedback field is deliberately absent."""
    common = {
        "ID": card.id,
        "Code": markdown(card.code),
        "Sources": sources_html(card.sources),
        "Verified": card.verified.isoformat(),
    }
    # A deck's own fields are rendered like any other card text.
    own = {name: markdown(value) for name, value in card.fields.items()}

    card_type = config.card_type_map().get(card.type)
    if card_type is not None and card_type.cloze:
        return {**common, "Text": markdown(card.text), "Extra": markdown(card.extra), **own}
    return {
        **common,
        "Front": markdown(card.front),
        "Back": markdown(card.back),
        "Reverse": "y" if card.reverse else "",
        **own,
    }
