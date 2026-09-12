# Web pages

Fetched with httpx and converted to Markdown. Sphinx, MkDocs and Docusaurus all render on
the server, so a plain GET is enough and no browser is involved.

## Code fences often arrive without a language

The converter reads a language off `language-…` or `lang-…` on `<pre>` or `<code>`, and
consults no ancestor. A pre-pass copies the language down from a wrapper when one names it,
and rewrites Sphinx's `highlight-python` spelling into `language-python`.

**But many sites never name the language at all.** Measured on docs.astral.sh (MkDocs
Material): across 32 code blocks, the strings `language-`, `lang-`, `data-lang` and
`highlight-` appear **zero times** in the page. The only wrapper is a bare
`<div class="highlight">`, and the language survives solely as Pygments `<span>` colouring,
which carries no language name. Every fence on that page arrives as a bare ```` ``` ````.

So: **do not assume a fence's language came through.** If a code block matters to a card and
arrived untagged, work the language out from the surrounding prose and say so in the
research note. Never guess it on the card itself.

## Line-number anchors are stripped

MkDocs Material puts `<a id="__codelineno-0-1" href="#__codelineno-0-1"></a>` before every
line of every code block, which converts to a `[](#__codelineno-0-1)` prefix on each line —
136 of them in one page, before stripping. Anchors inside `<pre>` are removed; a link that
has text keeps its text.

If you ever see `[](#…)` inside a code block in a cached file, the stripping missed a
variant: report it rather than writing cards from mangled code.

## What else is removed

`script`, `style`, `nav`, `header`, `footer`, `aside`, `noscript` and `form`, plus the
page's `<meta>` block, which the converter otherwise prepends as YAML. Page furniture
otherwise dominates a note.

## When a page comes back thin or empty

Almost always JavaScript rendering: the content is not in the HTML. There is no browser
here, so the honest move is to say so and ask for another route — a docs export, the
underlying repository, or a different page. **Do not** fill the gap from memory of what the
page probably says.

## Citing

A web source cites as a bare URL, which is the shorthand the schema expects. Link to the
most specific anchor that supports the fact — `#section` deep links are better citations
than a page root, and the reader following it in a year will thank you.
