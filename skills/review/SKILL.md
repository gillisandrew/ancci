---
name: review
description: Gathers the cards flagged while studying an ancci deck - flags, leeches and Feedback notes - helps fix them in the YAML, then clears the flags. Use when someone says "review my cards", "gather card feedback", "what did I flag", "fix the bad cards" or "check my deck feedback".
allowed-tools: Read, Write, Edit, Glob, Grep, Bash("${CLAUDE_PLUGIN_ROOT}/scripts/report.py" *), Bash("${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py" *), Bash("${CLAUDE_PLUGIN_ROOT}/scripts/validate.py" *), Bash("${CLAUDE_PLUGIN_ROOT}/scripts/sync.py" *)
---

# Close the feedback loop

While studying, a card gets flagged and sometimes a note typed into its Feedback field.
This skill turns that into fixed cards.

Anki must be running with AnkiConnect.

## Which deck

A session often sits at the root of a repository holding several decks. List them, then
pass `--deck <name>` to every command below:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/decks.py"
```

Inside a single deck, `--deck` can be omitted. If more than one is listed and the user has
not said which, ask.

## 1. Gather

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/report.py" --deck <name>
```

Each line is a card id, why it needs attention (flag colour, `leech`, `feedback`) and the
feedback text. `Nothing flagged.` means there is nothing to do — say so and stop.

## 2. Diagnose against the deck's own rules

For each card, read it in `cards/` and check it against `AUTHORING.md` and `deck.yaml`
before proposing anything. Most complaints are one of:

- **The front doesn't say what to recall** — a topic heading rather than a question. This
  is the most common one, and the fix is a front whose answer is the verdict line.
- **Two facts on one card** — the give-away is "and also", or a back over the deck's limit.
- **The answer format slipped** — no bold verdict line, or bullets that restate the front.
- **The card is right and the reader was wrong** — say so plainly rather than inventing a
  change. Sometimes the fix is that the card is fine.

A `leech` with no feedback usually means the card is hard to recall rather than wrong:
consider splitting it, not rewording it.

Report what you found and what you propose, then wait. Do not rewrite cards unasked.

## 3. Fix, then clear

Edit the YAML. **If a card's meaning changes, give it a new id and delete the old one** —
the sync suspends the old note and tags it `orphaned`, preserving its history. A wording
fix keeps the id.

Then validate, sync, and only then clear the flags:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/validate.py" --deck <name>
"${CLAUDE_PLUGIN_ROOT}/scripts/sync.py" --deck <name> --dry-run
"${CLAUDE_PLUGIN_ROOT}/scripts/sync.py" --deck <name>
"${CLAUDE_PLUGIN_ROOT}/scripts/resolve.py" --deck <name> <card-id>...
```

`resolve` clears the Feedback field and every flag on those cards. It deliberately leaves
the `leech` tag and all review history alone — a leech stays a leech until the reason it
became one is fixed.

Clear only the cards you actually dealt with.
