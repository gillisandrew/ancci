from pathlib import Path

from _lib.config import Deck, DeckConfig
from _lib.review import resolve
from _lib.schema import ORPHAN_TAG, CardFile
from _lib.sync import sync

SOURCE = "https://platform.claude.com/docs/en/build-with-claude/prompt-caching"

DECK = Deck(DeckConfig.model_validate({"name": "Test Deck", "tag_root": "test"}), Path("/tmp/deck"))


class FakeAnki:
    """In-memory stand-in for the AnkiConnect actions the sync uses."""

    def __init__(self):
        self.models: dict[str, list[str]] = {}
        self.notes: dict[int, dict] = {}
        self.suspended: set[int] = set()
        self.flags: dict[int, int] = {}
        self.last_find_query = ""

    def invoke(self, action, **params):
        return getattr(self, action)(**params)

    def multi(self, actions):
        out = []
        for action in actions:
            try:
                out.append((self.invoke(action["action"], **action["params"]), None))
            except Exception as exc:
                out.append((None, str(exc)))
        return out

    def createDeck(self, deck):
        return 1

    def modelNames(self):
        return list(self.models)

    def createModel(self, modelName, inOrderFields, **_):
        self.models[modelName] = list(inOrderFields)

    def modelFieldNames(self, modelName):
        return self.models[modelName]

    def modelFieldAdd(self, modelName, fieldName, index):
        self.models[modelName].insert(index, fieldName)

    def updateModelTemplates(self, model):
        pass

    def updateModelStyling(self, model):
        pass

    def findNotes(self, query):
        self.last_find_query = query
        return list(self.notes)

    def notesInfo(self, notes):
        return [
            {
                "noteId": nid,
                "modelName": self.notes[nid]["model"],
                "tags": list(self.notes[nid]["tags"]),
                "fields": {k: {"value": v, "order": 0} for k, v in self.notes[nid]["fields"].items()},
                "cards": [nid * 10],
            }
            for nid in notes
        ]

    def addNote(self, note):
        nid = len(self.notes) + 1
        fields = {name: "" for name in self.models[note["modelName"]]} | note["fields"]
        self.notes[nid] = {"model": note["modelName"], "fields": fields, "tags": list(note["tags"])}
        return nid

    def updateNote(self, note):
        self.notes[note["id"]]["fields"].update(note["fields"])
        self.notes[note["id"]]["tags"] = list(note["tags"])

    def suspend(self, cards):
        self.suspended |= set(cards)

    def unsuspend(self, cards):
        self.suspended -= set(cards)

    def addTags(self, notes, tags):
        for nid in notes:
            self.notes[nid]["tags"] += tags.split()

    def findCards(self, query):
        if "is:suspended" in query:
            return [card for card in self.suspended if ORPHAN_TAG not in self.notes[card // 10]["tags"]]
        return [card for card, flag in self.flags.items() if flag]

    def updateNoteFields(self, note):
        self.notes[note["id"]]["fields"].update(note["fields"])

    def setSpecificValueOfCard(self, card, keys, newValues):
        for key, value in zip(keys, newValues):
            if key == "flags":
                self.flags[card] = value
        return [True]

    def note_by_id(self, card_id):
        return next(n for n in self.notes.values() if n["fields"]["ID"] == card_id)


def card(card_id, **overrides):
    base = {
        "id": card_id,
        "type": "footgun",
        "topic": "caching",
        "front": "Why is the cache hit rate zero?",
        "back": "A timestamp at the top of the system prompt changes the prefix every request.",
        "sources": [SOURCE],
        "verified": "2026-09-11",
    }
    return {**base, **overrides}


def cards_file(area, *cards):
    return CardFile.model_validate({"area": area, "cards": list(cards)})


def test_first_sync_adds_and_second_is_a_no_op():
    anki = FakeAnki()
    files = [
        cards_file("context", card("context.a"), card("context.b", type="cloze", front=None, back=None, text="{{c1::x}}"))
    ]
    result, errors = sync(anki, DECK, files, {"context"})
    assert (len(result.adds), errors) == (2, [])
    # Note types are named by the deck, not baked into the tool.
    assert anki.note_by_id("context.b")["model"] == "Test Deck Cloze"
    assert anki.note_by_id("context.a")["model"] == "Test Deck Basic"

    result, _ = sync(anki, DECK, files, {"context"})
    assert (len(result.adds), len(result.updates), result.unchanged) == (0, 0, 2)


def test_edit_updates_but_keeps_user_tags_and_feedback():
    anki = FakeAnki()
    sync(anki, DECK, [cards_file("context", card("context.a"))], {"context"})
    note = anki.note_by_id("context.a")
    note["tags"].append("leech")
    note["fields"]["Feedback"] = "this is wrong"

    edited = [cards_file("context", card("context.a", back="Corrected.", tags=["beta"]))]
    result, _ = sync(anki, DECK, edited, {"context"})
    assert len(result.updates) == 1
    assert note["fields"]["Back"] == "<p>Corrected.</p>"
    assert note["fields"]["Feedback"] == "this is wrong"
    assert sorted(note["tags"]) == ["beta", "footgun", "leech", "test::context::caching"]


def test_removed_card_is_suspended_then_revived():
    anki = FakeAnki()
    sync(anki, DECK, [cards_file("context", card("context.a"), card("context.b"))], {"context"})

    result, _ = sync(anki, DECK, [cards_file("context", card("context.a"))], {"context"})
    orphan = anki.note_by_id("context.b")
    assert len(result.orphans) == 1
    assert ORPHAN_TAG in orphan["tags"]
    assert anki.suspended

    result, _ = sync(anki, DECK, [cards_file("context", card("context.a"), card("context.b"))], {"context"})
    assert len(result.revives) == 1
    assert ORPHAN_TAG not in orphan["tags"]
    assert not anki.suspended


def test_syncing_one_area_never_orphans_another():
    anki = FakeAnki()
    both = [cards_file("context", card("context.a")), cards_file("tools", card("tools.a", topic="tool-choice"))]
    sync(anki, DECK, both, {"context", "tools"})
    result, _ = sync(anki, DECK, [cards_file("context", card("context.a"))], {"context"})
    assert result.orphans == []


def test_changing_card_type_is_a_conflict_not_an_update():
    anki = FakeAnki()
    sync(anki, DECK, [cards_file("context", card("context.a"))], {"context"})
    cloze = card("context.a", type="cloze", front=None, back=None, text="{{c1::x}}")
    result, _ = sync(anki, DECK, [cards_file("context", cloze)], {"context"})
    assert result.conflicts and not result.updates


def test_resolve_clears_feedback_and_flags_but_leaves_the_leech_tag():
    anki = FakeAnki()
    sync(anki, DECK, [cards_file("context", card("context.a"))], {"context"})
    note = anki.note_by_id("context.a")
    note["fields"]["Feedback"] = "this is wrong"
    note["tags"].append("leech")
    anki.flags[10] = 1

    cleared, errors = resolve(anki, DECK, ["context.a"])
    assert (cleared, errors) == (["context.a"], [])
    assert note["fields"]["Feedback"] == ""
    assert anki.flags[10] == 0
    assert "leech" in note["tags"]


def test_resolve_unsuspends_a_card_suspended_while_studying():
    anki = FakeAnki()
    sync(anki, DECK, [cards_file("context", card("context.a"))], {"context"})
    anki.flags[10] = 1
    anki.suspended.add(10)

    cleared, errors = resolve(anki, DECK, ["context.a"])
    assert (cleared, errors) == (["context.a"], [])
    assert (anki.flags[10], anki.suspended) == (0, set())


def test_resolve_leaves_an_orphan_suspended():
    """A card whose meaning changed moves to a new id; the old note must stay out of study."""
    anki = FakeAnki()
    sync(anki, DECK, [cards_file("context", card("context.a"))], {"context"})
    anki.flags[10] = 1
    anki.suspended.add(10)
    sync(anki, DECK, [cards_file("context", card("context.b"))], {"context"})

    cleared, errors = resolve(anki, DECK, ["context.a"])
    assert (cleared, errors) == (["context.a"], [])
    assert (anki.flags[10], 10 in anki.suspended) == (0, True)


def test_resolve_all_covers_flagged_suspended_and_feedback_cards():
    anki = FakeAnki()
    sync(anki, DECK, [cards_file("context", card("context.a"), card("context.b"))], {"context"})
    anki.note_by_id("context.a")["fields"]["Feedback"] = "this is wrong"
    anki.flags[20] = 2
    sync(anki, DECK, [cards_file("context", card("context.a"), card("context.b"), card("context.c"))], {"context"})
    anki.suspended.add(30)

    cleared, errors = resolve(anki, DECK, [], everything=True)
    assert (cleared, errors) == (["context.a", "context.b", "context.c"], [])
    assert (anki.flags[20], anki.suspended) == (0, set())


def french_deck():
    """A deck declaring a type of its own, with a field of its own."""
    config = DeckConfig.model_validate(
        {
            "name": "Test Deck",
            "tag_root": "test",
            "card_types": {
                "vocab": {"requires": ["front", "back"], "optional": ["Phonetic"], "fields": ["Phonetic"]}
            },
        }
    )
    return Deck(config, Path("/tmp/deck"))


def test_a_declared_field_reaches_the_note_type_and_the_note():
    anki = FakeAnki()
    deck = french_deck()
    entry = card("context.a", type="vocab", fields={"Phonetic": "[pɑ̃tut]"})
    result, errors = sync(anki, deck, [cards_file("context", entry)], {"context"})

    assert (len(result.adds), errors) == (1, [])
    # the field exists on the model, before Feedback
    assert anki.models["Test Deck Basic"][-2:] == ["Phonetic", "Feedback"]
    # and the note carries its value
    assert "pɑ̃tut" in anki.note_by_id("context.a")["fields"]["Phonetic"]


def test_removing_a_declared_field_refuses_rather_than_destroying():
    anki = FakeAnki()
    deck = french_deck()
    sync(anki, deck, [cards_file("context", card("context.a", type="vocab"))], {"context"})
    assert "Phonetic" in anki.models["Test Deck Basic"]

    # The deck stops declaring the field. Anki still has it, full of content.
    plain = Deck(DeckConfig.model_validate({"name": "Test Deck", "tag_root": "test"}), Path("/tmp/deck"))
    result, _ = sync(anki, plain, [cards_file("context", card("context.a"))], {"context"})

    assert any("Phonetic" in c and "will not" in c for c in result.conflicts)
    # nothing was removed
    assert "Phonetic" in anki.models["Test Deck Basic"]


def test_note_lookup_covers_every_declared_model():
    """The most dangerous spot: a model missing from the query makes its notes invisible,
    so every one is re-added as a duplicate and orphan detection stops seeing them."""
    anki = FakeAnki()
    config = DeckConfig.model_validate(
        {
            "name": "Test Deck",
            "tag_root": "test",
            "note_types": {"basic": "T Basic", "cloze": "T Cloze", "audio": "T Audio"},
            "card_types": {"oral": {"note_type": "audio", "requires": ["front", "back"]}},
        }
    )
    sync(anki, Deck(config, Path("/tmp/deck")), [cards_file("context", card("context.a"))], {"context"})
    assert 'note:T Audio' in anki.last_find_query
    assert 'note:T Basic' in anki.last_find_query


def test_resolve_reports_an_unknown_card_id():
    anki = FakeAnki()
    sync(anki, DECK, [cards_file("context", card("context.a"))], {"context"})
    cleared, errors = resolve(anki, DECK, ["context.nope"])
    assert (cleared, errors) == ([], ["unknown card id: context.nope"])
