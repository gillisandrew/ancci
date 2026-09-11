import yaml

from ancci.schema import load

SOURCE = "https://platform.claude.com/docs/en/build-with-claude/prompt-caching"


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


def write(tmp_path, area, cards):
    path = tmp_path / f"{area}.yaml"
    path.write_text(yaml.safe_dump({"area": area, "cards": cards}))
    return path


def errors(problems):
    return [str(p) for p in problems if p.error]


def test_valid_card_loads(tmp_path):
    files, problems = load([write(tmp_path, "context", [card()])])
    assert errors(problems) == []
    assert files[0].cards[0].anki_tags() == ["agentic::context::caching", "definition"]


def test_cloze_needs_a_deletion(tmp_path):
    bad = card(id="context.x", style="cloze", front=None, back=None, text="no deletion here")
    _, problems = load([write(tmp_path, "context", [bad])])
    assert any("{{c1::" in e for e in errors(problems))


def test_basic_card_rejects_cloze_fields(tmp_path):
    _, problems = load([write(tmp_path, "context", [card(text="{{c1::x}}")])])
    assert any("front/back" in e for e in errors(problems))


def test_reverse_that_leaks_the_term_is_rejected(tmp_path):
    leaky = card(reverse=True, front="Compaction", back="`Compaction` summarises old turns.")
    _, problems = load([write(tmp_path, "context", [leaky])])
    assert any("leak" in e for e in errors(problems))


def test_reverse_only_on_definitions(tmp_path):
    _, problems = load([write(tmp_path, "context", [card(style="tradeoff", reverse=True)])])
    assert any("reverse is only allowed" in e for e in errors(problems))


def test_sources_must_be_allowlisted(tmp_path):
    for url in ("https://medium.com/some-post", "https://github.com/someone/repo", "http://platform.claude.com/x"):
        _, problems = load([write(tmp_path, "context", [card(sources=[url])])])
        assert errors(problems), url
    _, problems = load([write(tmp_path, "context", [card(sources=["https://github.com/anthropics/claude-cookbooks"])])])
    assert errors(problems) == []


def test_id_prefix_and_file_name_must_match_area(tmp_path):
    _, problems = load([write(tmp_path, "context", [card(id="tools.prompt-caching")])])
    assert any("must start with 'context.'" in e for e in errors(problems))


def test_duplicate_ids_across_files(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    first = write(tmp_path / "a", "context", [card()])
    second = write(tmp_path / "b", "context", [card()])
    _, problems = load([first, second])
    assert any("duplicate id" in e for e in errors(problems))


def test_long_answers_warn_but_do_not_fail(tmp_path):
    _, problems = load([write(tmp_path, "context", [card(back="x" * 800)])])
    assert errors(problems) == []
    assert any("atomic" in str(p) for p in problems)


def test_unknown_keys_are_errors(tmp_path):
    _, problems = load([write(tmp_path, "context", [card(answer="typo")])])
    assert errors(problems)
