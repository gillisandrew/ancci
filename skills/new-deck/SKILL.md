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
3. **Card styles** — the shipped default is `definition, cloze, footgun, tradeoff, pattern`.
   Those last two suit software. For anything else, propose styles that fit the material
   (a language deck might want `conjugation`; a cooking deck `technique`, `ratio`).
4. **Sources** — which publishers this deck may cite, if it should be restricted at all.
   Leave `hosts` out entirely to accept any https URL.
5. **Anki deck name** — what it will be called in their collection.

## Then write

```
<deck>/
  deck.yaml
  AUTHORING.md
  cards/          (empty; the author skill fills it)
  research/       (empty; source notes land here)
```

`deck.yaml` carries what a validator can check: `name`, `tag_root`, `styles`, `tags`,
`limits`, `sources`, and `note_types` if the defaults (`<name> Basic` / `<name> Cloze`)
are not wanted. See `${CLAUDE_PLUGIN_ROOT}/example-deck/deck.yaml` for a worked example
that overrides the default styles.

`AUTHORING.md` carries what only a reader can check: the audience, the scope boundaries,
what each style's front and back look like, and the answer format. Write it in the second
person, addressed to whoever writes cards next. `${CLAUDE_PLUGIN_ROOT}/example-deck/AUTHORING.md`
is a model to follow.

If several decks live in one repository and share house style, put the shared keys in a
root `ancci.yaml` instead and let each `deck.yaml` override only what differs.

## Finish by proving it loads

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/validate.py" --deck <name>
```

An empty deck validates as `0 cards in 0 files`. Report that, and say what to do next:
add source notes to `research/`, then run the author skill.
