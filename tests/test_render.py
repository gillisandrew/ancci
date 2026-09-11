from ancci.notetypes import CSS
from ancci.render import markdown


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
