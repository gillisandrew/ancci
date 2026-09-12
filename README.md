# ancci

Author Anki decks as YAML and sync them one way into Anki through
[AnkiConnect](https://git.sr.ht/~foosoft/anki-connect). What a card may look like, what it
may cite and what it lands on in Anki are all properties of the deck, not of this tool.

Decks live in their own repositories. This one holds only the tooling.

## What a deck is

A directory containing `deck.yaml`. Commands find it by walking up from the working
directory, so run them from inside the deck you mean.

```
my-deck/
  deck.yaml              what this deck is called and how its cards are shaped
  AUTHORING.md           prose rules the authoring agent reads
  cards/NN-<area>.yaml   the cards; the NN- prefix orders areas and means nothing else
  research/<area>.md     source notes each area was written from
```

The `NN-` prefix is ordering metadata only. `cards/01-patterns.yaml` is the `patterns`
area, its cards are `patterns.*`, and renumbering the file never touches a card.

## deck.yaml

```yaml
name: Agentic AI            # the Anki deck
tag_root: agentic           # cards are tagged <tag_root>::<area>::<topic>

note_types:                 # optional; defaults to "<name> Basic" / "<name> Cloze"
  basic: Agentic Basic      # note types are global in Anki, so each deck names its own
  cloze: Agentic Cloze

styles: [definition, cloze, footgun, tradeoff, pattern]   # optional; this is the default
tags: [beta, migration]     # optional; extra tags a card may carry
templates: templates/       # optional; a directory of Anki templates and CSS of your own

limits:                     # optional; these only ever warn
  back_chars: 220
  front_chars: 200
  bullets: 3
  cloze_deletions: 3

sources:                    # optional; omit `hosts` to accept any URL
  hosts: [platform.claude.com, anthropic.com]
  github_orgs: [anthropics]
  require_https: true
```

A repo holding several decks can put shared house style in a root `ancci.yaml` using the
same keys; each deck inherits it and overrides only what differs.

## Sources

A card cites one or more sources. A bare string is a URL:

```yaml
sources:
  - https://platform.claude.com/docs/en/build-with-claude/prompt-caching
  - {type: file, path: notes/talk.pdf, at: "p. 4"}
  - {type: repo, repo: anthropics/claude-code, ref: abc1234, path: README.md}
  - {type: video, url: "https://www.youtube.com/watch?v=...", t: 372}
```

The host allowlist applies to `url` and `video` sources — anything fetched from a
publisher. Files and repositories are cited by path and ref instead.

## Usage

```sh
ancci validate            # schema + answer-shape checks, no Anki needed
ancci sync --dry-run -v   # show what would change
ancci sync                # the whole deck
ancci sync tools          # one area
ancci report              # flagged cards, leeches, Feedback notes
ancci resolve <card-id>   # clear Feedback and flags once fixed
ancci --deck path/to/deck sync    # a deck other than the one you are standing in
```

Run from a directory holding several decks and nothing else, and every command will tell
you which decks it found rather than guess at one.

## How the sync behaves

- Creates the deck and its note types, and keeps their templates and CSS up to date.
- Notes are matched on the `ID` field. Changed cards are updated in place, so review
  history is kept.
- A card removed from the repo is **suspended and tagged `orphaned`**, never deleted.
  Putting it back revives it. Syncing one area only orphans cards from that area.
- The repo wins for card content and the tags it manages (`<tag_root>::*`, style tags and
  the deck's extra tags). Your own tags — including Anki's `leech` — and the `Feedback`
  field are left alone.
- AnkiConnect cannot update a note open in the Browse window's editor; close it first.

## Development

```sh
uv run pytest
```
