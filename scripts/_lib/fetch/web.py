"""Reading a web page, and the HTML-to-Markdown conversion the EPUB reader borrows.

Documentation generators put a code block's language on a wrapper element, and the
converter only reads it off `<pre>` or `<code>`. Measured against html-to-markdown 3.12.4:

    <code class="language-yaml">      -> ```yaml
    <code class="lang-yaml">          -> ```yaml
    <pre class="language-yaml">       -> ```yaml
    <code class="highlight-yaml">     -> ```      (not understood)
    <div class="highlight-yaml"><pre> -> ```      (ancestors are not consulted)

So the pre-pass copies the language down onto the element that counts, and rewrites
Sphinx's `highlight-` spelling into the `language-` one. Without it every fence in a docs
site arrives untagged, which loses the one piece of context a code card needs.
"""

import re
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from html_to_markdown import convert
from html_to_markdown.options import ConversionOptions

from ..sources import UrlSource
from .types import Fetched, FetchError

# Chrome and Safari both send something like this; an honest one is better than a fake one.
USER_AGENT = "ancci/0.1 (+https://github.com/gillisandrew/ancci)"

LANG_CLASS = re.compile(r"^(?:language|lang|highlight)-([\w+#.-]+)$")
# Page furniture that carries no content and only adds noise to a research note.
FURNITURE = ("script", "style", "nav", "header", "footer", "aside", "noscript", "form")
UNDERSTOOD = ("language-", "lang-")


def _language_near(element) -> str | None:
    """The language named on this element or the closest ancestor that names one."""
    for node in (element, *element.parents):
        for name in node.get("class", ()) or ():
            if match := LANG_CLASS.match(name):
                return match.group(1)
    return None


def strip_line_anchors(soup: BeautifulSoup) -> int:
    """Remove the per-line anchors documentation generators put inside code blocks.

    MkDocs Material emits `<a id="__codelineno-0-1" href="#__codelineno-0-1"></a>` before
    every line, which converts to a `[](#__codelineno-0-1)` prefix on that line — measured
    at 136 of them in a single page on docs.astral.sh, ruining every code block.

    An anchor with no text is a link target, so it goes entirely. One with text is a real
    link and is kept as its text, since Markdown code blocks cannot hold links anyway.
    """
    removed = 0
    for pre in soup.find_all("pre"):
        for anchor in pre.find_all("a"):
            anchor.unwrap() if anchor.get_text(strip=True) else anchor.decompose()
            removed += 1
    return removed


def tag_code_languages(soup: BeautifulSoup) -> int:
    """Put each code block's language where the converter will actually look for it."""
    tagged = 0
    for pre in soup.find_all("pre"):
        target = pre.find("code") or pre
        classes = list(target.get("class", ()) or ())
        if any(c.startswith(UNDERSTOOD) for c in classes):
            continue
        if language := _language_near(pre):
            target["class"] = [*classes, f"language-{language}"]
            tagged += 1
    return tagged


def to_markdown(html: str) -> tuple[str, str | None]:
    """Convert a document, returning the Markdown and the title if the page declares one."""
    soup = BeautifulSoup(html, "html.parser")
    for element in soup.find_all(FURNITURE):
        element.decompose()
    strip_line_anchors(soup)
    tag_code_languages(soup)

    title = None
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    elif h1 := soup.find("h1"):
        title = h1.get_text(strip=True)

    # Without this, a page's <meta> tags are prepended to the text as a YAML block, which
    # is noise in every research note written from it.
    options = ConversionOptions(extract_metadata=False)
    # convert() hands back a result object; the Markdown is on .content. Never str() it.
    return convert(str(soup), options).content.strip(), title


def fetch(spec: str, cache: Path) -> Fetched:
    try:
        response = httpx.get(
            spec, timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise FetchError(f"could not fetch {spec}: {exc}") from exc

    text, title = to_markdown(response.text)
    if not text:
        raise FetchError(f"nothing readable at {spec}")
    title = title or spec
    return Fetched(
        text=f"# {title}\n\n{text}",
        citation=UrlSource(url=str(response.url)),
        title=title,
        notes={"fetched_from": str(response.url)},
    )
