---
name: new-deck
description: Scaffolds a new ancci deck - deck.yaml, AUTHORING.md, cards/ and research/ - after settling what the deck is about, who is studying it and what card styles it needs. Use when someone says "start a new deck", "make a deck about X", "set up a deck" or "scaffold a deck".
disable-model-invocation: true
argument-hint: "[subject]"
allowed-tools: Read, Write, Edit, Glob, Bash("${CLAUDE_PLUGIN_ROOT}/scripts/validate.py" *)
---

# Start a new deck

Create a deck directory that ancci can validate and sync. The subject is `$ARGUMENTS` if
given; otherwise ask for it first.

A deck is a directory containing `deck.yaml`, and a repository normally holds several side
by side. See what is already there before choosing a name and a place:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/decks.py"
```

The new deck goes beside them, as a sibling directory at the same root.

## Settle these before writing anything

Ask as one short round, with your recommendation for each. Do not ask what the files
should be called or where they go if the answer is obvious from the surrounding repo.

1. **Subject and scope** — what belongs on a card, and what is explicitly out.
2. **Audience** — what the reader already knows, so cards never explain it. This is the
   single most useful line in the whole config; a deck for a beginner and a deck for a
   practitioner share no cards.
3. **Card types** — ancci ships only `basic` and `cloze`; every other name is the deck's
   own. Propose type names that fit the material (a language deck might want `conjugation`;
   a cooking deck `technique`, `ratio`) and list them under `styles:`, which gives each the
   default shape: `front` and `back` required, `code` and `reverse` optional.

   A type needing more than that goes under `card_types:` instead, where it declares its own
   `requires`, `optional`, `cloze`, and `fields` — extra Anki fields the deck adds, such as a
   phonetic transcription. Do not reach for this unless the material actually needs it; most
   decks never do.
4. **Sources** — which publishers this deck may cite, if it should be restricted at all.
   Leave `hosts` out entirely to accept any https URL.
5. **Anki deck name** — what it will be called in their collection.

## Then write

```
<deck>/
  deck.yaml
  cards/          (empty; the author skill fills it)
  research/       (empty; source notes land here)
```

One file. `deck.yaml` carries the machine-checkable settings — `name`, `tag_root`,
`styles`, `tags`, `limits`, `sources`, and `note_types` if the defaults (`<name> Basic` /
`<name> Cloze`) are not wanted — plus the three lines of prose that change what a good card
looks like:

```yaml
audience: makes coffee daily, owns a grinder and a scale
scope: why a variable moves the cup, not one café's recipe
avoid: equipment prices, model numbers
```

Keep those to a line each. They are read by the author skill on every run, so vague ones
("people interested in the topic") do nothing. See
`${CLAUDE_PLUGIN_ROOT}/example-deck/deck.yaml` for a worked example that also overrides the
default styles.

**Do not write an AUTHORING.md.** Universal card craft lives in the author skill, and house
style belongs in a root `ancci.yaml` shared by every deck in the repository. Only add a
per-deck `AUTHORING.md` when three lines genuinely will not do — a deck with unusual card
shapes, or conventions that need explaining. It overrides everything else when present.

## Finish by proving it loads

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/validate.py" --deck <name>
```

An empty deck validates as `0 cards in 0 files`. Report that, and say what to do next:
add source notes to `research/`, then run the author skill.
