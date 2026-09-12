# PDFs

Extracted with pdfplumber, with metadata from pypdf. Both MIT — the faster tools in this
space are AGPL, which a published MIT plugin cannot depend on.

## Headings are inferred, not read

A PDF has no heading levels. It has text at sizes. So the most common font size on the page
is taken as body text, and runs meaningfully larger are promoted:

- ≥ 1.45× body → `#`
- ≥ 1.20× body → `##`

This is a heuristic and it is wrong sometimes — a pull quote becomes a heading, a small
section title stays body text. **Do not trust the heading structure as if it were real.**
Read the surrounding text to work out what a section is actually about.

## Cite the page

Every page is marked in the extracted text:

```
<!-- page 7 -->
```

Use it, because the inferred structure is not citable but a page number always is:

```yaml
sources:
  - type: file
    path: ~/papers/attention.pdf
    at: "p. 7"
```

Record the page for each fact as you take the note — going back to find it later means
re-reading the document.

## Long documents

`--pages N` reads only the first N pages. Useful for a book when a chapter is all you want.
If you used it, say so in the research note: someone authoring later should know the
material was only partly read.

## Scans will not work

If a PDF is images of text, extraction returns nothing and the error says it may need OCR.
There is no OCR here. Say so and ask for a text-bearing copy — do not guess at contents
from the filename or from what such a document usually contains.
