---
name: add-source
description: Fetches a source into a deck - a web page, YouTube video, PDF, EPUB or text file - and distils it into a research note the author skill can write cards from. Use when someone says "add this source", "read this page", "ingest this video", "pull in these docs" or pastes a link to study from.
disable-model-invocation: true
argument-hint: "<url | path>"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash("${CLAUDE_PLUGIN_ROOT}/scripts/add-source.py" *), Bash("${CLAUDE_PLUGIN_ROOT}/scripts/validate.py" *)
---

# Add a source to a deck

`$ARGUMENTS` is what to read. The kind is worked out from its shape — you never say which.

## 1. Fetch it

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/add-source.py" [--deck <deck>] <source>
```

The script prints the kind, a title, the cache path, the `sources:` block to cite, and a
preview. The extracted text is cached under `.ancci/` and **is not committed** — it is
often large and always noisy. Read it from the cache path it prints.

Useful flags: `--pages` limits a long PDF, `--language` picks a caption track, `--refresh`
re-fetches something already cached.

Each source type has its own failure modes and its own way of being cited well. Read the
one that applies before writing the note:

- **`references/web.md`** — docs sites, code fences, and pages that need a browser
- **`references/video.md`** — transcripts, timestamps, and auto-caption hazards
- **`references/repo.md`** — reading a repository yourself, and citing the commit
- **`references/pdf.md`** — inferred headings, page citations, and scanned documents

## 2. Distil it into a research note

Write `research/<slug>.md` in the deck. This is the file that gets committed, and it is
what the author skill reads — so it must carry everything a card will need and nothing it
will not.

```markdown
# <title>

Fetched <date>. <one line on what this source is and why it is in this deck.>

## Sources

- <the citation block the script printed>

## Notes

- Fact, stated plainly, in the words the source uses for it.
- Another fact. Quote directly when the exact wording carries the meaning.
```

Rules that make a note worth having:

- **Facts, not summary.** A card needs something specific enough to test. "Discusses
  caching" is useless; "the cache prefix must match exactly, so a timestamp at the top of a
  system prompt invalidates it every request" is a card.
- **Keep the source's own terms.** If you paraphrase a term of art into something friendlier,
  the card will test the wrong words.
- **Record where each fact came from** — a heading, a page, a `[t=]` marker — so a card can
  cite a place rather than a whole document.
- **Never add what the source does not say.** Your own inference does not belong in a note
  that later becomes a card with a citation on it.
- If the material does not suit the deck — wrong audience, wrong scope, too thin — say so
  rather than writing a note nobody should author from.

## 3. Hand off

Report what was fetched, where the note is, and roughly how many cards it looks worth.
Then say that the author skill turns it into cards; do not start writing cards here.
