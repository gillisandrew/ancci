"""Offline tests for the acquirers' pure parts.

Nothing here touches the network. What is worth pinning is the logic we wrote ourselves:
how a source is recognised, how a docs site's code language is recovered, and how a
transcript is cut into citable windows.
"""

import pytest
from bs4 import BeautifulSoup

from _lib.fetch import detect
from _lib.fetch.types import FetchError, Fetched
from _lib.fetch.video import to_windows
from _lib.fetch.web import tag_code_languages, to_markdown
from _lib.sources import UrlSource


def test_detect_reads_the_shape_of_what_it_is_given(tmp_path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    notes = tmp_path / "notes.md"
    notes.write_text("hi")

    assert detect("https://example.com/docs/page") == "url"
    assert detect("https://www.youtube.com/watch?v=abc") == "video"
    assert detect("https://youtu.be/abc") == "video"
    assert detect(str(pdf)) == "pdf"
    assert detect(str(notes)) == "file"


def test_a_github_url_is_just_a_page():
    # There is no repository acquirer; a repo URL renders its README like any other page.
    assert detect("https://github.com/anthropics/claude-code") == "url"
    assert detect("https://github.com/anthropics/claude-code/blob/main/README.md") == "url"


def test_detect_refuses_what_it_cannot_place():
    with pytest.raises(FetchError):
        detect("./nothing-here")


def test_a_bare_repo_slug_says_to_clone_it():
    with pytest.raises(FetchError, match="clone it"):
        detect("anthropics/claude-code")


# Measured against html-to-markdown 3.12.4: it reads `language-`/`lang-` off <pre> or
# <code>, and consults no ancestor. Each case below is a real docs generator's markup.
@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ('<div class="highlight-python"><pre>print(1)</pre></div>', "```python"),
        ('<div class="language-yaml"><pre><code>a: 1</code></pre></div>', "```yaml"),
        ('<div class="highlight"><pre><code class="language-js">x</code></pre></div>', "```js"),
        ("<pre><code>plain</code></pre>", "```"),
    ],
)
def test_code_language_survives_conversion(html, expected):
    assert to_markdown(html)[0].splitlines()[0] == expected


def test_sphinx_wrapper_class_is_translated_not_just_copied():
    # `highlight-python` is not a spelling the converter understands; it must become
    # `language-python` on the element it actually reads.
    soup = BeautifulSoup('<div class="highlight-python"><pre>print(1)</pre></div>', "html.parser")
    assert tag_code_languages(soup) == 1
    assert "language-python" in soup.find("pre")["class"]


def test_an_explicit_language_is_left_alone():
    soup = BeautifulSoup('<div class="highlight-python"><pre><code class="language-js">x</code></pre></div>', "html.parser")
    assert tag_code_languages(soup) == 0


# The exact markup MkDocs Material ships: an anchor carrying an href before each line.
# An earlier fixture used an anchor without an href, which the converter drops by itself —
# so it passed while the real thing leaked on every line.
MKDOCS_LINE_ANCHOR = (
    '<div class="highlight"><pre><span></span><code>'
    '<a id="__codelineno-0-1" name="__codelineno-0-1" href="#__codelineno-0-1"></a>'
    'print("hi")\n</code></pre></div>'
)


def test_line_number_anchors_do_not_leak_into_code():
    text, _ = to_markdown(MKDOCS_LINE_ANCHOR)
    assert "__codelineno" not in text
    assert "[](" not in text
    assert 'print("hi")' in text


def test_a_link_with_text_inside_a_code_block_keeps_its_text():
    text, _ = to_markdown('<pre><code><a href="https://example.com">see this</a> matters</code></pre>')
    assert "see this matters" in text


def test_images_never_leak_a_data_uri():
    # An EPUB cover is a base64 SVG; converted naively it puts the whole encoded file in
    # the note. Alt text is the only part worth keeping.
    html = (
        '<p><img alt="A diagram" src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0i"></p>'
        '<p><img src="data:image/png;base64,iVBORw0KGgo="></p>'
    )
    text, _ = to_markdown(html)
    assert "base64" not in text
    assert "A diagram" in text


def test_page_furniture_is_dropped():
    html = "<nav>skip me</nav><p>keep me</p><script>alert(1)</script>"
    text, _ = to_markdown(html)
    assert "keep me" in text
    assert "skip me" not in text and "alert" not in text


def test_title_comes_from_the_page():
    assert to_markdown("<title>A Page</title><p>x</p>")[1] == "A Page"
    assert to_markdown("<h1>Fallback</h1><p>x</p>")[1] == "Fallback"


def test_transcript_windows_carry_a_citable_marker():
    cues = [(0, "one"), (10, "two"), (70, "three"), (130, "four")]
    blocks = to_windows(cues, window=60).split("\n\n")
    assert blocks[0] == "[t=0] one two"
    assert blocks[1] == "[t=70] three"
    assert blocks[2] == "[t=130] four"


def test_empty_transcript_is_an_error():
    with pytest.raises(FetchError):
        to_windows([])


def test_slug_is_filename_safe():
    fetched = Fetched(text="x", citation=UrlSource(url="https://example.com"), title="A Page: Part 2!")
    assert fetched.slug == "a-page-part-2"
