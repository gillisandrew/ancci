# ancci

Author Anki decks as YAML and sync them one way into Anki through
[AnkiConnect](https://git.sr.ht/~foosoft/anki-connect). What a card may look like, what it
may cite and what it lands on in Anki are all properties of the deck, not of this tool.

Decks live in their own repositories. This one holds only the tooling.

## Install

```
/plugin marketplace add gillisandrew/ancci
/plugin install ancci@ancci
```

| skill | what it does |
|---|---|
| `/ancci:new-deck` | scaffolds a deck after settling subject, audience and card styles |
| `/ancci:add-source` | reads a page, video, PDF, EPUB or file into a research note |
| `/ancci:author` | writes cards from a deck's research notes, sample batch first |
| `/ancci:review` | gathers what you flagged while studying, helps fix it, clears the flags |
| `/ancci:sync` | validates and pushes a deck into Anki, dry run first |

`new-deck` and `author` only run when you ask for them by name; `review` and `sync` can
also be triggered by asking in plain English.

The scripts need no installation of their own: each declares its dependencies inline and is
run by [uv](https://docs.astral.sh/uv/), which builds an isolated environment on first use.
uv 0.6.3 or newer is required.

## What a deck is

A directory containing `deck.yaml`. Commands find it by walking up from the working
directory, so run them from inside the deck you mean.

```
my-deck/
  deck.yaml              what it is called, how its cards are shaped, who reads them
  cards/NN-<area>.yaml   the cards; the NN- prefix orders areas and means nothing else
  research/<area>.md     source notes each area was written from
  AUTHORING.md           optional; only when three lines of prose will not do
```

The `NN-` prefix is ordering metadata only. `cards/01-patterns.yaml` is the `patterns`
area, its cards are `patterns.*`, and renumbering the file never touches a card.

## deck.yaml

```yaml
name: Agentic AI            # the Anki deck
tag_root: agentic           # cards are tagged <tag_root>::<area>::<topic>

# The only prose most decks need. One line each; vague ones do nothing.
audience: experienced programmers new to agentic AI
scope: current practice only, GA and beta features
avoid: exact prices, rate limits, model ids

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

### Replacing the card templates

`templates:` points at a directory of your own. Ship any subset of these; whatever you
leave out keeps the template ancci ships.

```
<deck>/templates/
  basic.front.html          basic.back.html
  basic-reverse.front.html  basic-reverse.back.html   # the "Name it" card
  cloze.front.html          cloze.back.html
  cards.css
```

They are Anki templates, so `{{Front}}`, `{{Back}}`, `{{cloze:Text}}`, `{{Code}}`,
`{{Sources}}`, `{{Verified}}` and `{{Feedback}}` are the fields available. An empty file is
an error rather than a blank card side.

Reach for this only when CSS genuinely cannot do it — `cards.css` alone restyles a deck
completely, and it cannot break the fields a card depends on.

A repo holding several decks can put shared house style in a root `ancci.yaml` using the
same keys; each deck inherits it and overrides only what differs.

Guidance sits in three layers, so a deck stays light:

| layer | lives in | covers |
|---|---|---|
| universal | the `author` skill | how to write a good card at all |
| house style | root `ancci.yaml`, and a root `AUTHORING.md` if you want prose | your voice across every deck |
| this deck | `audience` / `scope` / `avoid` in `deck.yaml` | who reads it and what belongs on a card |

A deck that genuinely needs more keeps its own `AUTHORING.md`, which overrides the rest.

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

The skills above are the usual way in. Each script also stands alone — run it from inside
a deck, or point it at one with `--deck`:

```sh
scripts/decks.py                     # list the decks here, with card counts
scripts/add-source.py <url|path>     # fetch a source into the deck's cache
scripts/validate.py                  # schema + answer-shape checks, no Anki needed
scripts/sync.py --dry-run -v         # show what would change
scripts/sync.py                      # the whole deck
scripts/sync.py tools                # one area
scripts/report.py                    # flagged cards, leeches, Feedback notes
scripts/resolve.py <card-id>         # clear Feedback and flags once fixed
scripts/sync.py --deck path/to/deck  # a deck other than the one you are standing in
```

Only `sync`, `report` and `resolve` ever contact Anki; `validate.py` deliberately depends on
nothing that could reach it.

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
