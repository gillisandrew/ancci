# Deck-defined card types and fields

Status: **designed, not built.** This records the configuration settled on, and why.

## Goal

Today `ancci` ships two fixed note types with fixed field lists. A deck can invent style
names, but every non-cloze style collapses onto one hardcoded `front`/`back` shape, and the
Anki fields are module constants. A deck cannot add a field of its own.

Make card types and their fields a property of the deck, the way styles, limits and sources
already are. The immediate want is a phonetic-transcription field on a French vocabulary
deck — but that field should fall out of the general mechanism as ordinary configuration.

## The configuration

A card type is a **contract**: which built-in keys a card must and may carry, whether it is
cloze, which Anki note type it lands in, and which extra fields it adds.

```yaml
# deck.yaml
note_types:                     # open mapping of key -> Anki model name
  basic: Quebec French Basic
  cloze: Quebec French Cloze
  audio: Quebec French Audio    # a deck may add more

styles: [definition, faux-ami, registre]   # bare names: the basic contract

card_types:
  oral:
    note_type: audio
    cloze: true
    requires: [text]
    optional: [extra, code]
    fields: [Audio, Phonetic]
    
limits:
  front: {chars: 200}           # per field
  Phonetic: {chars: 40}
  back_chars: 220               # the old four still work
```

A card names its type, and carries deck fields nested:

```yaml
- id: vocabulaire.pantoute
  type: definition              # `style:` is still accepted and means the same thing
  topic: quotidien
  front: "« J'exagère pas pantoute ! » — que veut dire *pantoute* ?"
  back: "**Pas du tout, aucunement.**"
  fields:
    Phonetic: "[pɑ̃tut]"
  sources: [https://usito.usherbrooke.ca/définitions/pantoute]
  verified: 2026-09-12
```

### What the tool ships

Exactly two contracts, always available to every deck:

| type | requires | optional | note type | cloze |
|---|---|---|---|---|
| `basic` | `front`, `back` | `code`, `reverse` | `basic` | no |
| `cloze` | `text` | `extra`, `code` | `cloze` | yes |

A deck's `styles:` / `card_types:` **extends** that floor rather than replacing it. A bare
name in `styles:` gets the basic contract — **unless it matches a shipped name**, which
resolves to that shipped type. That exception is load-bearing: without it a deck listing
`cloze` bare would route its cloze cards onto the basic note type, which Anki cannot do in
place, re-adding every one of them and losing its review history.

Keys not listed in `requires` or `optional` are forbidden, which is what replaces the
hardcoded cloze-versus-front/back branch. A card naming an undeclared type is an error.

### Fields

Deck fields are **optional by default**; a type may name one in `requires` to demand it.
They nest under `fields:` on a card so that `Card` keeps `extra="forbid"` for its own keys —
a misspelled `sourcse:` stays an error instead of silently becoming a deck field.

These names are reserved and a deck may not declare them: `ID`, `Front`, `Back`, `Text`,
`Extra`, `Code`, `Sources`, `Verified`, `Reverse`, `Feedback`.

New fields are inserted **before `Feedback`**, so the field you type into stays last in the
Anki editor. `modelFieldReposition` is a first-class AnkiConnect action, so this is a
supported operation rather than a risk.

### Removing or renaming a field: refused

`modelFieldRemove` destroys that field's content on every note, and there is no undo. So
when a deck's declared fields no longer cover what its Anki note type has, **validation
fails**, naming the field and the two ways out: declare a new card type, or remove the field
by hand in Anki if that is genuinely what you want. Sync never calls `modelFieldRemove`. A
rename is a remove plus an add, so it is refused for the same reason.

### Rendering

Card types that share a note type share its templates. A deck field renders through a
conditional section — `{{#Phonetic}}<div class="ipa">{{Phonetic}}</div>{{/Phonetic}}` — which
is how `{{#Code}}` and `{{#Feedback}}` already work, so it needs no new mechanism. A type
that needs genuinely different HTML declares its own note type and ships templates for it.

`reverse` is no longer special-cased to `definition`: it is an ordinary optional key. A type
whose note type has no `Reverse` field may not accept it, and validation says so rather than
silently dropping it.

### Limits

Per field, keyed by field name. The existing `front_chars`, `back_chars`, `bullets` and
`cloze_deletions` keep working and mean what they mean now. A limit naming a field the type
does not have is simply not checked — never a crash, and never a silent end to checking the
built-ins.

## Note lookup

`fetch_notes()` queried `"note:<basic>" or "note:<cloze>"`. It must now query **every model
in `note_types:`**. This is the single most dangerous edit in the change: a deck declaring a
third note type without this generalisation makes its notes invisible to sync, so every one
is re-added as a duplicate and orphan detection silently stops seeing them.

## Compatibility

Two real decks exist. `agentic-ai` uses all five shipped names, including reverse cards;
`quebec-french` declares its own. Both carry live review history, and both must sync with
**zero diff** — `add 0, update 0, orphan 0` — before any deck adopts the new configuration.
Check that against the decks as they are, not against counts written here.

Three properties make that achievable:

- **Type names are today's style names**, so `anki_tags()` produces byte-identical tags.
- **`style:` stays a silent alias for `type:`**, so no card file is edited.
- **Types group onto the existing note types**, so no note changes model and nothing re-adds.

`quebec-french` already declares its styles and needs no edit. `agentic-ai` declares none —
it inherits `DEFAULT_STYLES` — so it gains one line, which is a no-op under today's code and
required once the plugin ships.

## Rollout

1. Add `styles: [definition, cloze, footgun, tradeoff, pattern]` to `agentic-ai/deck.yaml`.
   Changes nothing today; prevents a window where a pulled plugin meets an unedited deck.
2. One plugin PR, gated on `sync.py --dry-run` reporting `0, 0, 0` on both decks.
3. `./release.py 0.4.0`.

## Out of scope

**Orphan scoping is by area, derived from files on disk.** In `sync.py`, `areas` comes from
the card files present, so deleting a card file drops its area from that set and its notes
are never orphaned — they linger in Anki unmanaged. This is a real bug and a separate one.
Fixing it here would legitimately orphan notes and confound the zero-diff acceptance test.

## Tests to add

- A deck-declared type with a custom field round-tripping to Anki fields.
- A card naming an undeclared type failing validation.
- Required, optional and forbidden keys enforced per type.
- A bare `cloze` in `styles:` resolving to the shipped cloze type, not to basic.
- The default config still producing exactly `BASIC_FIELDS` and `CLOZE_FIELDS`.
- A removed field refusing with a clear message.
- `reverse` on a type whose note type has no `Reverse` field being rejected.

## Documentation to update

- `README.md` — the `deck.yaml` reference block is the user-facing spec.
- `skills/author/SKILL.md` — its "Card fields" block lists card keys verbatim and tells the
  agent an undeclared type is an error. It must describe how a deck's own types and fields
  are discovered, since the agent reads `deck.yaml` before writing any card.
- `skills/new-deck/SKILL.md` — mention the capability without forcing it.
- Note that a deck inventing types documents them in its own `AUTHORING.md`.
