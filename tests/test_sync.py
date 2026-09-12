from pathlib import Path

from ancci.config import Deck, DeckConfig
from ancci.schema import ORPHAN_TAG, CardFile
from ancci.sync import resolve, sync

SOURCE = "https://platform.claude.com/docs/en/build-with-claude/prompt-caching"

DECK = Deck(DeckConfig.model_validate({"name": "Test Deck", "tag_root": "test"}), Path("/tmp/deck"))


class FakeAnki:
    """In-memory stand-in for the AnkiConnect actions the sync uses."""

    def __init__(self):
        self.models: dict[str, list[str]] = {}
        self.notes: dict[int, dict] = {}
        self.suspended: set[int] = set()
        self.flags: dict[int, int] = {}

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
        "style": "footgun",
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
        cards_file("context", card("context.a"), card("context.b", style="cloze", front=None, back=None, text="{{c1::x}}"))
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


def test_changing_card_kind_is_a_conflict_not_an_update():
    anki = FakeAnki()
    sync(anki, DECK, [cards_file("context", card("context.a"))], {"context"})
    cloze = card("context.a", style="cloze", front=None, back=None, text="{{c1::x}}")
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


def test_resolve_all_covers_both_flagged_and_feedback_cards():
    anki = FakeAnki()
    sync(anki, DECK, [cards_file("context", card("context.a"), card("context.b"))], {"context"})
    anki.note_by_id("context.a")["fields"]["Feedback"] = "this is wrong"
    anki.flags[20] = 2

    cleared, errors = resolve(anki, DECK, [], everything=True)
    assert (cleared, errors) == (["context.a", "context.b"], [])
    assert anki.flags[20] == 0


def test_resolve_reports_an_unknown_card_id():
    anki = FakeAnki()
    sync(anki, DECK, [cards_file("context", card("context.a"))], {"context"})
    cleared, errors = resolve(anki, DECK, ["context.nope"])
    assert (cleared, errors) == ([], ["unknown card id: context.nope"])
