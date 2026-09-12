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
not said which, ask. Each deck has its own types and voice, so cards written for the wrong
one are wrong cards.

## Read the deck first

Never write a card before reading, in this order:

1. **`deck.yaml`** — the types this deck has, what it may cite, and usually
   all the prose there is: `audience` (what the reader already knows, so a card never
   explains it), `scope` (what belongs on a card) and `avoid` (what does not). A type not
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

## Card types

**Which keys a card may carry comes from its type, and the deck declares its types.** Read
`deck.yaml` before writing anything:

- `types:` lists type names using the default shape — `front` and `back` required, `code`
  and `reverse` optional.
- `card_types:` declares types with their own contract: `requires`, `optional`, `cloze`,
  and `fields` for extra Anki fields of the deck's own.
- ancci itself ships only `basic` and `cloze`. Every other name you see is the deck's.

A card naming a type the deck does not have is an error, not a suggestion. A key the type
does not list is an error too — so do not reach for `code` on a type that never allowed it.

## Card fields

```yaml
area: extraction              # matches the file name with its NN- prefix stripped
cards:
  - id: extraction.bloom      # <area>.<kebab-slug>, permanent once synced
    type: technique           # a type the deck declares
    topic: pour-over          # kebab-case; becomes <tag_root>::<area>::<topic>
    front: |                  # whichever keys this type requires and allows
    back: |
    text: |                   # cloze types, with {{c1::...}}
    extra: |
    code: |                   # fenced, shown on the back
    reverse: false            # only where the type allows it; back must not contain front
    fields:                   # only fields this type declares
      Phonetic: "[pɑ̃tut]"
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

- **Length is your judgement, and nothing checks it.** The validator has no opinion on how
  long an answer is — it only knows whether a card is valid. An answer that will not fit is
  almost always two cards rather than one card to cram, and the deck's `AUTHORING.md` says
  what its house style expects.
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

Errors must be fixed; there are no warnings. Nothing checks how long an answer is — a card
that sprawls is usually testing two facts, so split it rather than cram it. Report the
count, and mention that the sync skill pushes the cards into Anki when they are ready.
