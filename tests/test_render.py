import pytest

from _lib.config import ConfigError, Deck, DeckConfig
from _lib.notetypes import CSS, css_for, note_types
from _lib.render import markdown


def deck_with_templates(tmp_path, **files):
    (tmp_path / "tpl").mkdir()
    for name, body in files.items():
        (tmp_path / "tpl" / name).write_text(body)
    config = DeckConfig.model_validate({"name": "T", "tag_root": "t", "templates": "tpl"})
    return Deck(config, tmp_path)


def test_a_deck_without_templates_gets_the_shipped_ones(tmp_path):
    plain = Deck(DeckConfig.model_validate({"name": "T", "tag_root": "t"}), tmp_path)
    basic, cloze = note_types(plain)
    assert "{{Front}}" in basic.templates["Card 1"][0]
    assert "{{cloze:Text}}" in cloze.templates["Cloze"][0]
    assert css_for(plain) == CSS


def test_a_deck_can_replace_one_side_and_keep_the_rest(tmp_path):
    deck = deck_with_templates(tmp_path, **{"basic.front.html": "<h1>{{Front}}</h1>"})
    basic, cloze = note_types(deck)
    assert basic.templates["Card 1"][0] == "<h1>{{Front}}</h1>"
    # Everything it did not override is still the shipped template.
    assert "<hr id=" in basic.templates["Card 1"][1]
    assert "{{cloze:Text}}" in cloze.templates["Cloze"][0]


def test_cloze_and_reverse_templates_are_overridable(tmp_path):
    deck = deck_with_templates(
        tmp_path,
        **{"cloze.back.html": "<div>{{Extra}}</div>", "basic-reverse.front.html": "<p>{{Back}}</p>"},
    )
    basic, cloze = note_types(deck)
    assert cloze.templates["Cloze"][1] == "<div>{{Extra}}</div>"
    assert basic.templates["Card 2"][0] == "<p>{{Back}}</p>"


def test_an_empty_template_is_an_error_not_a_blank_card(tmp_path):
    deck = deck_with_templates(tmp_path, **{"basic.front.html": "   \n"})
    with pytest.raises(ConfigError, match="empty"):
        note_types(deck)


def test_a_deck_can_replace_the_css(tmp_path):
    deck = deck_with_templates(tmp_path, **{"cards.css": ".card { color: red }"})
    assert css_for(deck) == ".card { color: red }"


def test_raw_html_is_shown_literally():
    assert "&lt;thinking&gt;" in markdown("Wrap it in `<thinking>` or <thinking> tags")
    assert "<thinking>" not in markdown("Wrap it in <thinking> tags")


def test_pseudocode_is_highlighted_as_python():
    out = markdown("```pseudo\nfor block in response.content:\n    pass\n```")
    assert '<span class="k">for</span>' in out
    assert out.startswith("<pre><code")


def test_unknown_language_falls_back_to_plain_text():
    out = markdown("```nope\na < b\n```")
    assert "a &lt; b" in out


def test_cloze_markers_survive_markdown():
    assert "{{c1::<code>tool_choice</code>}}" in markdown("{{c1::`tool_choice`}}")


def test_css_has_light_and_dark_highlighting():
    assert ".card pre code .k" in CSS
    assert ".nightMode pre code .k" in CSS
