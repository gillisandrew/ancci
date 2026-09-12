import yaml

from _lib.config import Deck, DeckConfig
from _lib.notetypes import BASIC_FIELDS, CLOZE_FIELDS, note_types
from _lib.render import fields as render_fields
from _lib.schema import load

SOURCE = "https://platform.claude.com/docs/en/build-with-claude/prompt-caching"

CONFIG = {
    "name": "Test Deck",
    "tag_root": "test",
    # The tool ships basic and cloze; every other name is the deck's own.
    "types": ["definition", "footgun", "tradeoff", "pattern"],
    "sources": {
        "hosts": ["platform.claude.com", "github.com"],
        "github_orgs": ["anthropics"],
    },
}


def deck(tmp_path, **overrides):
    return Deck(DeckConfig.model_validate({**CONFIG, **overrides}), tmp_path)


def card(**overrides):
    base = {
        "id": "context.prompt-caching",
        "type": "definition",
        "topic": "caching",
        "front": "Prompt caching",
        "back": "Reusing the processed prefix of a prompt across requests.",
        "sources": [SOURCE],
        "verified": "2026-09-11",
    }
    return {**base, **overrides}


def write(tmp_path, name, cards, area=None):
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.safe_dump({"area": area or name, "cards": cards}))
    return path


def errors(problems):
    return [str(p) for p in problems]


def test_valid_card_loads(tmp_path):
    files, problems = load([write(tmp_path, "context", [card()])], deck(tmp_path))
    assert errors(problems) == []
    assert files[0].cards[0].anki_tags(deck(tmp_path).config) == ["test::context::caching", "definition"]


def test_a_card_must_name_a_type(tmp_path):
    _, problems = load([write(tmp_path, "context", [card(type=None)])], deck(tmp_path))
    assert errors(problems)


def test_order_prefix_is_stripped_from_the_area(tmp_path):
    _, problems = load([write(tmp_path, "01-context", [card()], area="context")], deck(tmp_path))
    assert errors(problems) == []


def test_area_must_still_match_the_rest_of_the_file_name(tmp_path):
    _, problems = load([write(tmp_path, "01-tools", [card()], area="context")], deck(tmp_path))
    assert any("must match the file name" in e for e in errors(problems))


def test_bare_string_source_is_read_as_a_url(tmp_path):
    files, problems = load([write(tmp_path, "context", [card()])], deck(tmp_path))
    assert errors(problems) == []
    assert files[0].cards[0].sources[0].type == "url"


def test_local_sources_skip_the_host_allowlist(tmp_path):
    bad_host = card(sources=[{"type": "file", "path": "/somewhere/medium-export.md"}])
    _, problems = load([write(tmp_path, "context", [bad_host])], deck(tmp_path))
    assert errors(problems) == []


def test_sources_must_be_allowlisted(tmp_path):
    for url in ("https://medium.com/some-post", "https://github.com/someone/repo", "http://platform.claude.com/x"):
        _, problems = load([write(tmp_path, "context", [card(sources=[url])])], deck(tmp_path))
        assert errors(problems), url
    ok = card(sources=["https://github.com/anthropics/claude-cookbooks"])
    _, problems = load([write(tmp_path, "context", [ok])], deck(tmp_path))
    assert errors(problems) == []


def test_a_deck_without_a_host_allowlist_accepts_any_url(tmp_path):
    open_deck = deck(tmp_path, sources={})
    _, problems = load([write(tmp_path, "context", [card(sources=["https://medium.com/x"])])], open_deck)
    assert errors(problems) == []


# --- card types -------------------------------------------------------------------


def test_a_card_naming_an_undeclared_type_is_an_error(tmp_path):
    _, problems = load([write(tmp_path, "context", [card(type="conjugation")])], deck(tmp_path))
    assert any("unknown type 'conjugation'" in e for e in errors(problems))


def test_an_unknown_type_does_not_hide_a_bad_source(tmp_path):
    # errors() reports what it can judge without the type, so one typo does not mask a
    # bad citation until the next round trip.
    bad = card(type="conjugation", sources=["https://medium.com/x"], tags=["spicy"])
    _, problems = load([write(tmp_path, "context", [bad])], deck(tmp_path))
    reported = errors(problems)
    assert any("unknown type" in e for e in reported)
    assert any("allowlist" in e for e in reported)
    assert any("unknown tag" in e for e in reported)


def test_the_tool_ships_only_basic_and_cloze(tmp_path):
    bare = Deck(DeckConfig.model_validate({"name": "T", "tag_root": "t"}), tmp_path)
    assert sorted(bare.config.card_type_map()) == ["basic", "cloze"]


def test_a_bare_name_matching_a_shipped_type_keeps_that_type(tmp_path):
    # The guard that matters: a deck listing `cloze` bare must not get the basic contract,
    # or its cloze cards route onto the basic note type and Anki re-adds every one.
    listed = deck(tmp_path, types=["definition", "cloze"])
    resolved = listed.config.card_type_map()["cloze"]
    assert resolved.cloze is True
    assert resolved.note_type == "cloze"
    cloze_card = card(id="context.c", type="cloze", front=None, back=None, text="{{c1::x}}")
    _, problems = load([write(tmp_path, "context", [cloze_card])], listed)
    assert errors(problems) == []


def test_required_and_forbidden_keys_come_from_the_type(tmp_path):
    missing_back = card(back=None)
    _, problems = load([write(tmp_path, "context", [missing_back])], deck(tmp_path))
    assert any("requires back" in e for e in errors(problems))

    has_text = card(text="{{c1::x}}")
    _, problems = load([write(tmp_path, "context", [has_text])], deck(tmp_path))
    assert any("does not take text" in e for e in errors(problems))


def test_a_deck_can_declare_a_type_with_its_own_field(tmp_path):
    # This is how a card carries audio, an image, or a phonetic transcription.
    french = deck(
        tmp_path,
        types=[],
        card_types={"vocab": {"requires": ["front", "back"], "optional": ["Phonetic"], "fields": ["Phonetic"]}},
    )
    entry = card(type="vocab", fields={"Phonetic": "[pɑ̃tut]"})
    files, problems = load([write(tmp_path, "context", [entry])], french)
    assert errors(problems) == []
    rendered = render_fields(files[0].cards[0], french.config)
    assert "Phonetic" in rendered and "pɑ̃tut" in rendered["Phonetic"]


def test_a_field_the_type_never_declared_is_an_error(tmp_path):
    french = deck(tmp_path, types=[], card_types={"vocab": {"requires": ["front", "back"]}})
    entry = card(type="vocab", fields={"Phonetic": "[x]"})
    _, problems = load([write(tmp_path, "context", [entry])], french)
    assert any("declares no field 'Phonetic'" in e for e in errors(problems))


def test_a_reserved_field_name_is_rejected(tmp_path):
    entry = card(fields={"Feedback": "mine"})
    _, problems = load([write(tmp_path, "context", [entry])], deck(tmp_path))
    assert any("reserved" in e for e in errors(problems))


def test_the_default_note_types_are_unchanged(tmp_path):
    bare = Deck(DeckConfig.model_validate({"name": "T", "tag_root": "t"}), tmp_path)
    built = note_types(bare)
    assert built["basic"].fields == BASIC_FIELDS
    assert built["cloze"].fields == CLOZE_FIELDS


def test_a_declared_field_lands_before_feedback(tmp_path):
    french = Deck(
        DeckConfig.model_validate(
            {
                "name": "T",
                "tag_root": "t",
                "card_types": {"vocab": {"requires": ["front", "back"], "fields": ["Phonetic"]}},
            }
        ),
        tmp_path,
    )
    fields = note_types(french)["basic"].fields
    assert fields[-2:] == ("Phonetic", "Feedback")


def test_reverse_on_a_cloze_type_is_rejected(tmp_path):
    # The cloze note type has no Reverse field and no second template, so a reverse cloze
    # card would be silently dropped rather than fail.
    import pytest
    from pydantic import ValidationError

    from _lib.config import CardType

    with pytest.raises(ValidationError, match="Reverse"):
        CardType(note_type="cloze", cloze=True, requires=["text"], optional=["reverse"])


# --- shape ------------------------------------------------------------------------


def test_cloze_needs_a_deletion(tmp_path):
    listed = deck(tmp_path, types=["cloze"])
    bad = card(id="context.x", type="cloze", front=None, back=None, text="no deletion here")
    _, problems = load([write(tmp_path, "context", [bad])], listed)
    assert any("{{c1::" in e for e in errors(problems))


def test_reverse_that_leaks_the_term_is_rejected(tmp_path):
    leaky = card(reverse=True, front="Compaction", back="`Compaction` summarises old turns.")
    _, problems = load([write(tmp_path, "context", [leaky])], deck(tmp_path))
    assert any("leak" in e for e in errors(problems))


def test_unknown_tag_is_an_error(tmp_path):
    _, problems = load([write(tmp_path, "context", [card(tags=["spicy"])])], deck(tmp_path))
    assert any("unknown tag" in e for e in errors(problems))


def test_id_prefix_and_file_name_must_match_area(tmp_path):
    _, problems = load([write(tmp_path, "context", [card(id="tools.prompt-caching")])], deck(tmp_path))
    assert any("must start with 'context.'" in e for e in errors(problems))


def test_duplicate_ids_across_files(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    first = write(tmp_path / "a", "context", [card()])
    second = write(tmp_path / "b", "context", [card()])
    _, problems = load([first, second], deck(tmp_path))
    assert any("duplicate id" in e for e in errors(problems))


def test_length_is_never_checked(tmp_path):
    # How long is too long is a judgement, and it belongs to whoever writes the card.
    cards = [card(back="x" * 900), card(id="context.q", front="y" * 900)]
    _, problems = load([write(tmp_path, "context", cards)], deck(tmp_path))
    assert problems == []


def test_unknown_keys_are_errors(tmp_path):
    _, problems = load([write(tmp_path, "context", [card(answer="typo")])], deck(tmp_path))
    assert errors(problems)
