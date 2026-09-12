from _lib.config import Deck, DeckConfig
from _lib.notetypes import CSS, css_for, note_types
from _lib.render import markdown


def plain_deck(tmp_path, **overrides):
    config = DeckConfig.model_validate({"name": "T", "tag_root": "t", **overrides})
    return Deck(config, tmp_path)


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


def test_a_deck_gets_the_shipped_templates_and_css(tmp_path):
    deck = plain_deck(tmp_path)
    types = note_types(deck)
    assert "{{Front}}" in types["basic"].templates["Card 1"][0]
    assert "{{cloze:Text}}" in types["cloze"].templates["Cloze"][0]
    assert css_for(deck) == CSS


def test_a_deck_can_ship_its_own_stylesheet(tmp_path):
    # Restyling is all a deck needs; the card templates themselves are the tool's.
    (tmp_path / "cards.css").write_text(".card { color: red }")
    deck = plain_deck(tmp_path, css="cards.css")
    assert css_for(deck) == ".card { color: red }"


def test_a_missing_stylesheet_falls_back_rather_than_failing(tmp_path):
    deck = plain_deck(tmp_path, css="nonexistent.css")
    assert css_for(deck) == CSS
