"""Reading notes back out of Anki.

Kept apart from the sync so that looking at what is already in a collection costs neither
a Markdown renderer nor a syntax highlighter.
"""

from dataclasses import dataclass
from itertools import batched

from .anki import AnkiError
from .config import Deck


@dataclass
class Note:
    note_id: int
    model: str
    fields: dict[str, str]
    tags: list[str]
    cards: list[int]


def fetch_notes(anki, deck: Deck) -> dict[str, Note]:
    """Every note belonging to this deck's note types, keyed by the card id it carries."""
    names = deck.config.note_types
    note_ids = anki.invoke("findNotes", query=f'"note:{names.basic}" or "note:{names.cloze}"')
    notes: dict[str, Note] = {}
    for chunk in batched(note_ids, 500):
        for info in anki.invoke("notesInfo", notes=list(chunk)):
            values = {name: f["value"] for name, f in info["fields"].items()}
            card_id = values.get("ID", "")
            if not card_id:
                continue
            if card_id in notes:
                raise AnkiError(f"two notes share ID {card_id!r}; delete one in Anki and re-run")
            notes[card_id] = Note(info["noteId"], info["modelName"], values, info["tags"], info["cards"])
    return notes
