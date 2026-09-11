from ancci.schema import ORPHAN_TAG, CardFile
from ancci.sync import sync

SOURCE = "https://platform.claude.com/docs/en/build-with-claude/prompt-caching"


class FakeAnki:
    """In-memory stand-in for the AnkiConnect actions the sync uses."""

    def __init__(self):
        self.models: dict[str, list[str]] = {}
        self.notes: dict[int, dict] = {}
        self.suspended: set[int] = set()

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


def deck(area, *cards):
    return CardFile.model_validate({"area": area, "cards": list(cards)})


def test_first_sync_adds_and_second_is_a_no_op():
    anki = FakeAnki()
    files = [deck("context", card("context.a"), card("context.b", style="cloze", front=None, back=None, text="{{c1::x}}"))]
    result, errors = sync(anki, files, {"context"})
    assert (len(result.adds), errors) == (2, [])
    assert anki.note_by_id("context.b")["model"] == "Agentic Cloze"

    result, _ = sync(anki, files, {"context"})
    assert (len(result.adds), len(result.updates), result.unchanged) == (0, 0, 2)


def test_edit_updates_but_keeps_user_tags_and_feedback():
    anki = FakeAnki()
    sync(anki, [deck("context", card("context.a"))], {"context"})
    note = anki.note_by_id("context.a")
    note["tags"].append("leech")
    note["fields"]["Feedback"] = "this is wrong"

    result, _ = sync(anki, [deck("context", card("context.a", back="Corrected.", tags=["beta"]))], {"context"})
    assert len(result.updates) == 1
    assert note["fields"]["Back"] == "<p>Corrected.</p>"
    assert note["fields"]["Feedback"] == "this is wrong"
    assert sorted(note["tags"]) == ["agentic::context::caching", "beta", "footgun", "leech"]


def test_removed_card_is_suspended_then_revived():
    anki = FakeAnki()
    sync(anki, [deck("context", card("context.a"), card("context.b"))], {"context"})

    result, _ = sync(anki, [deck("context", card("context.a"))], {"context"})
    orphan = anki.note_by_id("context.b")
    assert len(result.orphans) == 1
    assert ORPHAN_TAG in orphan["tags"]
    assert anki.suspended

    result, _ = sync(anki, [deck("context", card("context.a"), card("context.b"))], {"context"})
    assert len(result.revives) == 1
    assert ORPHAN_TAG not in orphan["tags"]
    assert not anki.suspended


def test_syncing_one_area_never_orphans_another():
    anki = FakeAnki()
    sync(anki, [deck("context", card("context.a")), deck("tools", card("tools.a", topic="tool-choice"))], {"context", "tools"})
    result, _ = sync(anki, [deck("context", card("context.a"))], {"context"})
    assert result.orphans == []


def test_changing_card_kind_is_a_conflict_not_an_update():
    anki = FakeAnki()
    sync(anki, [deck("context", card("context.a"))], {"context"})
    cloze = card("context.a", style="cloze", front=None, back=None, text="{{c1::x}}")
    result, _ = sync(anki, [deck("context", cloze)], {"context"})
    assert result.conflicts and not result.updates
