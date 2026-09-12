---
name: author
description: Writes new cards for an ancci deck from its research notes, interviewing briefly, drafting a sample batch for approval, then authoring the rest. Use when someone says "write cards", "author cards for X", "add cards about Y", "draft cards from these notes" or "fill out the deck".
disable-model-invocation: true
argument-hint: "[area or topic]"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash("${CLAUDE_PLUGIN_ROOT}/scripts/validate.py" *)
---

# Author cards

Turn source notes into cards. `$ARGUMENTS` names the area or topic if given.

## Which deck

A session often sits at the root of a repository holding several decks. List them, then
pass `--deck <name>` to every command below:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/decks.py"
```

Inside a single deck, `--deck` can be omitted. If more than one is listed and the user has
not said which, ask. Each deck has its own styles and voice, so cards written for the wrong
one are wrong cards.

## Read the deck first

Never write a card before reading, in this order:

1. **`deck.yaml`** — the styles this deck uses, its limits, what it may cite, and usually
   all the prose there is: `audience` (what the reader already knows, so a card never
   explains it), `scope` (what belongs on a card) and `avoid` (what does not). A style not
   listed is an error, not a suggestion.
2. **A root `ancci.yaml` and `AUTHORING.md` above the deck**, if present — house style
   shared by every deck in the repository. The deck's own settings override them.
3. **The deck's own `AUTHORING.md`**, if it has one. Most decks do not; a deck that needs
   more than three lines of prose keeps one, and it wins over everything above.
4. **`research/<area>.md`** — the source notes. **Every fact on a card must be supported by
   something here.** If the notes do not support it, it does not go on a card; say so
   rather than reaching for what you already know.
5. An existing `cards/*.yaml`, if any. The cards are the deck's real style guide — match
   their voice exactly rather than inventing a new one.

## Card fields

```yaml
area: extraction              # matches the file name with its NN- prefix stripped
cards:
  - id: extraction.bloom      # <area>.<kebab-slug>, permanent once synced
    style: technique          # must be one the deck declares
    topic: pour-over          # kebab-case; becomes <tag_root>::<area>::<topic>
    front: |                  # every style except cloze
    back: |
    text: |                   # cloze only, with {{c1::...}}
    extra: |                  # cloze only, optional
    code: |                   # optional, fenced, shown on the back
    reverse: false            # definition only; the back must not contain the front
    tags: [beta]              # only tags the deck declares
    sources:                  # a bare string is a URL
      - https://example.com/page
      - {type: file, path: notes.pdf, at: "p. 4"}
    verified: 2026-09-12      # when you last checked the card against its sources
```

## Interview briefly, then draft a sample

Ask one short round — no more than four questions — covering scope for this batch, roughly
how many cards, and anything ambiguous in the notes. Recommend an answer for each.

Then **write about ten cards and stop.** Show them and ask for a verdict before going
further. A wrong read of the material costs ten cards to discover here and two hundred to
discover later. Wait for the answer; do not treat silence as approval.

## Writing rules that hold for every deck

- **One fact per card.** If the answer needs "and also", it is two cards.
- **Self-contained prompts.** A card is read months later with no context around it.
- **No guessable prompts.** No yes/no questions; no prompt whose wording gives away its
  answer.
- **The front must say what is being asked.** A noun phrase that could be answered three
  different ways is the most common way a card goes bad.
- Every card carries `sources` and a `verified` date. A bare string source is a URL; use
  the `file`, `repo` and `video` forms for anything else.
- Cards go in `cards/NN-<area>.yaml`, where `NN` orders areas for study and means nothing
  else. Ids are `<area>.<kebab-slug>` and **are permanent**: changing a card's id orphans
  its review history in Anki. If a card's meaning changes, give it a new id and delete the
  old one.

## Finish by validating

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/validate.py" --deck <name> <area>
```

Errors must be fixed. Warnings are the deck's answer-shape limits: a card over the limit is
usually testing two facts, so prefer splitting it over cramming it. Report the counts, and
mention that the sync skill pushes the cards into Anki when they are ready.
