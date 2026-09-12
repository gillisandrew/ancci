"""One-way sync: card files -> Anki. The repo always wins, except for user-owned state
(review history, the Feedback field, and tags outside the ones the sync manages)."""

import html
import re
from dataclasses import dataclass, field
from itertools import batched

from . import render
from .anki import AnkiError
from .config import Deck, DeckConfig
from .notetypes import css_for, note_types
from .schema import ORPHAN_TAG, Card, CardFile


def managed_tags(config: DeckConfig) -> set[str]:
    """Tags the sync owns. Everything else on a note belongs to the user."""
    return {*config.styles, *config.tags, ORPHAN_TAG}


def is_managed_tag(tag: str, config: DeckConfig) -> bool:
    return tag.startswith(f"{config.tag_root}::") or tag in managed_tags(config)


def note_type_for(card: Card, deck: Deck) -> str:
    names = deck.config.note_types
    return names.cloze if card.is_cloze else names.basic


@dataclass
class Note:
    note_id: int
    model: str
    fields: dict[str, str]
    tags: list[str]
    cards: list[int]


@dataclass
class Plan:
    adds: list[Card] = field(default_factory=list)
    updates: list[tuple[Note, Card]] = field(default_factory=list)
    unchanged: int = 0
    orphans: list[Note] = field(default_factory=list)
    revives: list[Note] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


def desired_tags(card: Card, config: DeckConfig, note: Note | None = None) -> list[str]:
    kept = [t for t in note.tags if not is_managed_tag(t, config)] if note else []
    return sorted({*card.anki_tags(config), *kept})


def ensure_setup(anki, deck: Deck) -> None:
    anki.invoke("createDeck", deck=deck.config.name)
    css = css_for(deck)
    existing = set(anki.invoke("modelNames"))
    for nt in note_types(deck):
        templates = {name: {"Front": front, "Back": back} for name, (front, back) in nt.templates.items()}
        if nt.name not in existing:
            anki.invoke(
                "createModel",
                modelName=nt.name,
                inOrderFields=list(nt.fields),
                css=css,
                isCloze=nt.is_cloze,
                cardTemplates=[{"Name": name, **sides} for name, sides in templates.items()],
            )
            continue
        have = anki.invoke("modelFieldNames", modelName=nt.name)
        for index, name in enumerate(nt.fields):
            if name not in have:
                anki.invoke("modelFieldAdd", modelName=nt.name, fieldName=name, index=index)
        anki.invoke("updateModelTemplates", model={"name": nt.name, "templates": templates})
        anki.invoke("updateModelStyling", model={"name": nt.name, "css": css})


def fetch_notes(anki, deck: Deck) -> dict[str, Note]:
    basic, cloze = note_types(deck)
    note_ids = anki.invoke("findNotes", query=f'"note:{basic.name}" or "note:{cloze.name}"')
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


def plan(files: list[CardFile], notes: dict[str, Note], areas: set[str], deck: Deck) -> Plan:
    """Diff the repo against Anki. Orphan detection only covers `areas`, so syncing one
    area never suspends another area's cards."""
    config = deck.config
    result = Plan()
    wanted: set[str] = set()
    for card_file in files:
        for card in card_file.cards:
            wanted.add(card.id)
            note = notes.get(card.id)
            if note is None:
                result.adds.append(card)
                continue
            if note.model != note_type_for(card, deck):
                result.conflicts.append(
                    f"{card.id}: is a {note.model} note in Anki but a {card.style} card in the repo; give it a new id"
                )
                continue
            if ORPHAN_TAG in note.tags:
                result.revives.append(note)
            new_fields = render.fields(card)
            stale_fields = any(note.fields.get(name) != value for name, value in new_fields.items())
            if stale_fields or set(note.tags) != set(desired_tags(card, config, note)):
                result.updates.append((note, card))
            else:
                result.unchanged += 1
    for card_id, note in notes.items():
        if card_id not in wanted and card_id.split(".", 1)[0] in areas and ORPHAN_TAG not in note.tags:
            result.orphans.append(note)
    return result


def apply(anki, result: Plan, deck: Deck) -> list[str]:
    config = deck.config
    errors = []
    for chunk in batched(result.adds, 100):
        actions = [
            {
                "action": "addNote",
                "params": {
                    "note": {
                        "deckName": config.name,
                        "modelName": note_type_for(card, deck),
                        "fields": render.fields(card),
                        "tags": card.anki_tags(config),
                        "options": {"allowDuplicate": False},
                    }
                },
            }
            for card in chunk
        ]
        errors += [f"add {card.id}: {err}" for card, (_, err) in zip(chunk, anki.multi(actions)) if err]
    for chunk in batched(result.updates, 100):
        actions = [
            {
                "action": "updateNote",
                "params": {
                    "note": {"id": note.note_id, "fields": render.fields(card), "tags": desired_tags(card, config, note)}
                },
            }
            for note, card in chunk
        ]
        errors += [f"update {card.id}: {err}" for (_, card), (_, err) in zip(chunk, anki.multi(actions)) if err]
    if result.revives:
        anki.invoke("unsuspend", cards=[c for note in result.revives for c in note.cards])
    if result.orphans:
        anki.invoke("suspend", cards=[c for note in result.orphans for c in note.cards])
        anki.invoke("addTags", notes=[note.note_id for note in result.orphans], tags=ORPHAN_TAG)
    return errors


def sync(anki, deck: Deck, files: list[CardFile], areas: set[str], dry_run: bool = False) -> tuple[Plan, list[str]]:
    if not dry_run:
        ensure_setup(anki, deck)
    result = plan(files, fetch_notes(anki, deck), areas, deck)
    return result, ([] if dry_run else apply(anki, result, deck))


_FLAGS = {1: "red", 2: "orange", 3: "green", 4: "blue", 5: "pink", 6: "turquoise", 7: "purple"}


def _strip_html(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())


def report(anki, deck: Deck) -> str:
    """Cards needing attention: flagged, leeches, or with text in the Feedback field."""
    query = f'"deck:{deck.config.name}"'
    reasons: dict[int, set[str]] = {}
    for flag, colour in _FLAGS.items():
        card_ids = anki.invoke("findCards", query=f"{query} flag:{flag}")
        if card_ids:
            for info in anki.invoke("cardsInfo", cards=card_ids):
                reasons.setdefault(info["note"], set()).add(f"{colour} flag")
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
    """Clear the Feedback field and every flag on cards whose feedback has been acted on.

    Only clears what the reviewer set for our benefit. Review history and the leech tag
    are Anki's own; a leech stays a leech until you fix why it is one.
    """
    notes = fetch_notes(anki, deck)
    errors = [f"unknown card id: {card_id}" for card_id in card_ids if card_id not in notes]
    if everything:
        flagged = set(anki.invoke("findCards", query=f'"deck:{deck.config.name}" -flag:0'))
        targets = [note for note in notes.values() if note.fields.get("Feedback") or flagged.intersection(note.cards)]
    else:
        targets = [notes[card_id] for card_id in card_ids if card_id in notes]

    actions, labels = [], []
    for note in sorted(targets, key=lambda n: n.fields["ID"]):
        if note.fields.get("Feedback"):
            actions.append({"action": "updateNoteFields", "params": {"note": {"id": note.note_id, "fields": {"Feedback": ""}}}})
            labels.append(note.fields["ID"])
        for card in note.cards:
            actions.append({"action": "setSpecificValueOfCard", "params": {"card": card, "keys": ["flags"], "newValues": [0]}})
            labels.append(note.fields["ID"])
    for label, (result, err) in zip(labels, anki.multi(actions) if actions else []):
        # setSpecificValueOfCard reports failure inside its result, not as an error.
        if err:
            errors.append(f"{label}: {err}")
        elif isinstance(result, list) and result and result[0] is False:
            errors.append(f"{label}: {result[1] if len(result) > 1 else 'could not clear flag'}")
    return sorted({note.fields["ID"] for note in targets}), errors
