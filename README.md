# ancci

An Anki deck on agentic AI in the Anthropic ecosystem: Claude API, tool use, context and cost, Agent SDK and Managed Agents, Claude Code, MCP, Anthropic's published patterns, and safety. Aimed at experienced programmers, current practice only, and every card cites an Anthropic (or MCP) source.

The YAML in `cards/` is the source of truth. `ancci sync` pushes it one way into Anki through [AnkiConnect](https://git.sr.ht/~foosoft/anki-connect).

## Layout

| path | what |
|---|---|
| `cards/<area>.yaml` | the cards, one file per area |
| `research/<area>.md` | source notes each area's cards were written from (URLs, fetch dates, quotes) |
| `AUTHORING.md` | card rules and the YAML schema |
| `src/ancci/` | validation, rendering and sync |

Areas, in the order they are introduced: `patterns`, `api`, `tools`, `context`, `agents`, `claude-code`, `mcp`, `safety`.

## Usage

Anki must be running with AnkiConnect installed.

```sh
uv run ancci validate            # schema + atomicity checks, no Anki needed
uv run ancci sync --dry-run -v   # show what would change
uv run ancci sync                # everything in cards/
uv run ancci sync tools          # one area
uv run ancci report              # flagged cards, leeches, Feedback notes
uv run pytest
```

## How the sync behaves

- Creates the `Agentic AI` deck and the `Agentic Basic` / `Agentic Cloze` note types, and keeps their templates and CSS up to date.
- Notes are matched on the `ID` field. Changed cards are updated in place, so review history is kept.
- A card removed from the repo is **suspended and tagged `orphaned`**, never deleted. Putting it back revives it. Syncing a single area only orphans cards from that area.
- The repo wins for card content and for the tags it manages (`agentic::*`, style tags, `beta`, `migration`). Your own tags (including Anki's `leech`) and the `Feedback` field are left alone.
- AnkiConnect cannot update a note that is open in the Browse window's editor; close it before syncing.

## Reporting a bad card

While studying, flag the card (any colour) and optionally type what's wrong into its **Feedback** field (Edit → Feedback). `uv run ancci report` lists everything flagged, every leech, and every Feedback note, ready to be fixed in the YAML.
