"""The study feedback loop: find cards you marked while studying, and clear them once fixed."""

import html
import re

from .config import Deck
from .notes import fetch_notes
from .schema import ORPHAN_TAG

_FLAGS = {1: "red", 2: "orange", 3: "green", 4: "blue", 5: "pink", 6: "turquoise", 7: "purple"}


def _strip_html(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())


def _suspended_by_reviewer(deck: Deck) -> str:
    """Suspended cards, less the ones the sync suspended itself when it orphaned them."""
    return f'"deck:{deck.config.name}" is:suspended -tag:{ORPHAN_TAG}'


def report(anki, deck: Deck) -> str:
    """Cards needing attention: flagged, suspended, leeches, or with text in the Feedback field."""
    query = f'"deck:{deck.config.name}"'
    reasons: dict[int, set[str]] = {}
    card_queries = [(f"{colour} flag", f"{query} flag:{flag}") for flag, colour in _FLAGS.items()]
    card_queries.append(("suspended", _suspended_by_reviewer(deck)))
    for label, q in card_queries:
        card_ids = anki.invoke("findCards", query=q)
        if card_ids:
            for info in anki.invoke("cardsInfo", cards=card_ids):
                reasons.setdefault(info["note"], set()).add(label)
    for label, q in (("leech", f"{query} tag:leech"), ("feedback", f'{query} "Feedback:_*"')):
        for note_id in anki.invoke("findNotes", query=q):
            reasons.setdefault(note_id, set()).add(label)
    if not reasons:
        return "Nothing flagged."
    lines = []
    infos = anki.invoke("notesInfo", notes=list(reasons))
    for info in sorted(infos, key=lambda i: i["fields"]["ID"]["value"]):
        values = {name: f["value"] for name, f in info["fields"].items()}
        lines.append(f"- {values.get('ID') or info['noteId']} ({', '.join(sorted(reasons[info['noteId']]))})")
        if values.get("Feedback"):
            lines.append(f"  feedback: {_strip_html(values['Feedback'])}")
    return "\n".join(lines)


def resolve(anki, deck: Deck, card_ids: list[str], everything: bool = False) -> tuple[list[str], list[str]]:
    """Clear the Feedback field and every flag on cards whose feedback has been acted on,
    and unsuspend them so they come back into study.

    Only undoes what the reviewer set for our benefit. Review history and the leech tag
    are Anki's own; a leech stays a leech until you fix why it is one. An orphaned note
    stays suspended: that suspension is the sync's, and means the card left the repo.
    """
    notes = fetch_notes(anki, deck)
    errors = [f"unknown card id: {card_id}" for card_id in card_ids if card_id not in notes]
    suspended = set(anki.invoke("findCards", query=_suspended_by_reviewer(deck)))
    if everything:
        marked = suspended | set(anki.invoke("findCards", query=f'"deck:{deck.config.name}" -flag:0'))
        targets = [note for note in notes.values() if note.fields.get("Feedback") or marked.intersection(note.cards)]
    else:
        targets = [notes[card_id] for card_id in card_ids if card_id in notes]

    actions, labels = [], []
    for note in sorted(targets, key=lambda n: n.fields["ID"]):
        if note.fields.get("Feedback"):
            actions.append(
                {"action": "updateNoteFields", "params": {"note": {"id": note.note_id, "fields": {"Feedback": ""}}}}
            )
            labels.append(note.fields["ID"])
        for card in note.cards:
            actions.append(
                {"action": "setSpecificValueOfCard", "params": {"card": card, "keys": ["flags"], "newValues": [0]}}
            )
            labels.append(note.fields["ID"])
        if ORPHAN_TAG not in note.tags and suspended.intersection(note.cards):
            actions.append({"action": "unsuspend", "params": {"cards": sorted(suspended.intersection(note.cards))}})
            labels.append(note.fields["ID"])
    for label, (result, err) in zip(labels, anki.multi(actions) if actions else []):
        # setSpecificValueOfCard reports failure inside its result, not as an error.
        if err:
            errors.append(f"{label}: {err}")
        elif isinstance(result, list) and result and result[0] is False:
            errors.append(f"{label}: {result[1] if len(result) > 1 else 'could not clear flag'}")
    return sorted({note.fields["ID"] for note in targets}), errors
