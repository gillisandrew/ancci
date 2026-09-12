import yaml

from _lib.config import Deck, DeckConfig
from _lib.schema import load

SOURCE = "https://platform.claude.com/docs/en/build-with-claude/prompt-caching"

CONFIG = {
    "name": "Test Deck",
    "tag_root": "test",
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
        "style": "definition",
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
    return [str(p) for p in problems if p.error]


def test_valid_card_loads(tmp_path):
    files, problems = load([write(tmp_path, "context", [card()])], deck(tmp_path))
    assert errors(problems) == []
    assert files[0].cards[0].anki_tags(deck(tmp_path).config) == ["test::context::caching", "definition"]


def test_order_prefix_is_stripped_from_the_area(tmp_path):
    # 01-context.yaml is the `context` area; the number only orders the files.
    _, problems = load([write(tmp_path, "01-context", [card()], area="context")], deck(tmp_path))
    assert errors(problems) == []


def test_area_must_still_match_the_rest_of_the_file_name(tmp_path):
    _, problems = load([write(tmp_path, "01-tools", [card()], area="context")], deck(tmp_path))
    assert any("must match the file name" in e for e in errors(problems))


def test_bare_string_source_is_read_as_a_url(tmp_path):
    files, problems = load([write(tmp_path, "context", [card()])], deck(tmp_path))
    assert errors(problems) == []
    assert files[0].cards[0].sources[0].type == "url"


def test_typed_sources_load(tmp_path):
    cards = [
        card(id="context.a", sources=[{"type": "file", "path": "notes/talk.pdf", "at": "p. 4"}]),
        card(id="context.b", sources=[{"type": "repo", "repo": "anthropics/claude-code", "ref": "abc1234"}]),
        card(id="context.c", sources=[{"type": "video", "url": "https://www.youtube.com/watch?v=x", "t": 372}]),
    ]
    hosts = [*CONFIG["sources"]["hosts"], "www.youtube.com"]
    watching = deck(tmp_path, sources={**CONFIG["sources"], "hosts": hosts})
    _, problems = load([write(tmp_path, "context", cards)], watching)
    assert errors(problems) == []


def test_a_video_is_a_publisher_so_the_allowlist_applies(tmp_path):
    # A path is not a publisher, but a video is: it is fetched from a host like any page.
    video = card(sources=[{"type": "video", "url": "https://www.youtube.com/watch?v=x", "t": 372}])
    _, problems = load([write(tmp_path, "context", [video])], deck(tmp_path))
    assert any("not on the allowlist" in e for e in errors(problems))


def test_local_sources_skip_the_host_allowlist(tmp_path):
    # A path is not a publisher; the allowlist only governs URLs.
    bad_host = card(sources=[{"type": "file", "path": "/somewhere/medium-export.md"}])
    _, problems = load([write(tmp_path, "context", [bad_host])], deck(tmp_path))
    assert errors(problems) == []


def test_unknown_style_is_an_error(tmp_path):
    _, problems = load([write(tmp_path, "context", [card(style="conjugation")])], deck(tmp_path))
    assert any("unknown style" in e for e in errors(problems))


def test_deck_can_define_its_own_styles(tmp_path):
    own = deck(tmp_path, styles=["conjugation", "cloze"])
    _, problems = load([write(tmp_path, "context", [card(style="conjugation")])], own)
    assert errors(problems) == []


def test_unknown_tag_is_an_error(tmp_path):
    _, problems = load([write(tmp_path, "context", [card(tags=["spicy"])])], deck(tmp_path))
    assert any("unknown tag" in e for e in errors(problems))


def test_cloze_needs_a_deletion(tmp_path):
    bad = card(id="context.x", style="cloze", front=None, back=None, text="no deletion here")
    _, problems = load([write(tmp_path, "context", [bad])], deck(tmp_path))
    assert any("{{c1::" in e for e in errors(problems))


def test_basic_card_rejects_cloze_fields(tmp_path):
    _, problems = load([write(tmp_path, "context", [card(text="{{c1::x}}")])], deck(tmp_path))
    assert any("front/back" in e for e in errors(problems))


def test_reverse_that_leaks_the_term_is_rejected(tmp_path):
    leaky = card(reverse=True, front="Compaction", back="`Compaction` summarises old turns.")
    _, problems = load([write(tmp_path, "context", [leaky])], deck(tmp_path))
    assert any("leak" in e for e in errors(problems))


def test_reverse_only_on_definitions(tmp_path):
    _, problems = load([write(tmp_path, "context", [card(style="tradeoff", reverse=True)])], deck(tmp_path))
    assert any("reverse is only allowed" in e for e in errors(problems))


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


def test_long_answers_warn_but_do_not_fail(tmp_path):
    cards = [card(back="x" * 301), card(id="context.q", front="y" * 201)]
    _, problems = load([write(tmp_path, "context", cards)], deck(tmp_path))
    assert errors(problems) == []
    assert any("condense to bold verdict" in str(p) for p in problems)
    assert any("condense the question" in str(p) for p in problems)


def test_limits_come_from_the_deck(tmp_path):
    generous = deck(tmp_path, limits={"back_chars": 400})
    _, problems = load([write(tmp_path, "context", [card(back="x" * 301)])], generous)
    assert problems == []


def test_more_than_three_bullets_warns(tmp_path):
    back = "**Verdict**\n\n- a\n- b\n- c\n- d\n"
    _, problems = load([write(tmp_path, "context", [card(back=back)])], deck(tmp_path))
    assert any("4 bullets" in str(p) for p in problems)


def test_unknown_keys_are_errors(tmp_path):
    _, problems = load([write(tmp_path, "context", [card(answer="typo")])], deck(tmp_path))
    assert errors(problems)
