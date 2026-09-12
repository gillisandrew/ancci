---
name: sync
description: Validates an ancci deck and pushes it into Anki over AnkiConnect, showing the dry run first. Use when someone says "sync my deck", "push cards to Anki", "update Anki", "validate my deck" or "check the cards are valid".
argument-hint: "[area]"
allowed-tools: Read, Glob, Bash("${CLAUDE_PLUGIN_ROOT}/scripts/validate.py" *), Bash("${CLAUDE_PLUGIN_ROOT}/scripts/sync.py" *)
---

# Validate and sync a deck

`$ARGUMENTS` names a single area if given; otherwise the whole deck.

Anki must be running with AnkiConnect installed.

## Which deck

A session often sits at the root of a repository holding several decks. Never guess which
one is meant:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/decks.py"
```

Pass `--deck <name>` to every command below. Inside a single deck it can be omitted. If
more than one deck is listed and the user has not said which, ask before touching Anki —
syncing the wrong deck orphans cards in it.

## Always dry run first

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/validate.py" --deck <name> [area]
"${CLAUDE_PLUGIN_ROOT}/scripts/sync.py" --deck <name> [area] --dry-run -v
```

Read the summary line before writing anything:

```
would: add 3, update 12, orphan 0, revive 0; 438 unchanged
```

- **Unexpected `add`s** usually mean a card id changed. That is not a rename — it creates a
  new note and orphans the old one, losing its review history. Check before proceeding.
- **Unexpected `orphan`s** mean cards vanished from the repo. Syncing one area only orphans
  that area's cards.
- **A large `update` count after a tooling change** means rendering shifted. Worth
  understanding rather than pushing.

If the numbers are surprising, stop and explain them. Do not push to make them go away.

## Then sync

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/sync.py" --deck <name> [area]
```

Validation errors block a sync; warnings do not.

## What it will and will not touch

- Notes are matched on the `ID` field, so changed cards are updated in place and **review
  history is kept**.
- A removed card is suspended and tagged `orphaned`, never deleted. Putting it back revives
  it.
- The repo wins for card content and its own tags. Your tags — including `leech` — and the
  `Feedback` field are left alone.
- AnkiConnect cannot update a note that is open in Anki's Browse editor. If a sync fails
  with an editor error, tell the user to close that window and retry.
