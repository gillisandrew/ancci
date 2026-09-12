# Card authoring guide — Coffee Brewing

Every deck keeps one of these. `deck.yaml` holds the rules a validator can check; this
file holds the ones only a reader can. The authoring skill reads both.

## Audience and scope

- The reader already makes coffee daily and owns a grinder and a scale. Never explain
  what a burr grinder is, or that coffee is ground before brewing.
- Cards are about **why** a variable moves the cup, not about one café's recipe.
- Numbers appear only when they are a useful starting point a reader can adjust from
  (a brew ratio, a bloom time). Never equipment prices or model numbers.

## Styles

| style | front | back |
|---|---|---|
| `definition` | the term, or a symptom to diagnose | one line, or a bold verdict plus ≤2 bullets |
| `cloze` | — | `text` with ≤3 deletions; optional `extra` |
| `technique` | "Why do X?" or a symptom | bold cause or instruction, then ≤3 bullets |
| `ratio` | what is being measured | bold the ratio itself, then the variants |

`footgun` and `pattern` are ancci defaults this deck does not use — they suit software.

## Answer format

- **Line 1 is the verdict in bold**, ≤10 words, and it answers the question.
- Then 0–3 bullets, ≤8 words each, one fact apiece.
- Keep every qualifier that changes truth (*by mass*, *filter*, *espresso*).
- Tag a card `disputed` when practitioners genuinely disagree, and say so on the back.
