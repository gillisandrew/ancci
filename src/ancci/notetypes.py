"""The deck and note types the sync creates and keeps up to date in Anki."""

from dataclasses import dataclass

from pygments.formatters import HtmlFormatter

DECK = "Agentic AI"


@dataclass(frozen=True)
class NoteType:
    name: str
    fields: tuple[str, ...]
    templates: dict[str, tuple[str, str]]  # template name -> (front, back)
    is_cloze: bool


_BACK_MATTER = """
{{#Code}}<div class="code">{{Code}}</div>{{/Code}}
<div class="provenance">{{Sources}}<span class="verified">verified {{Verified}}</span></div>
{{#Feedback}}<div class="feedback">{{Feedback}}</div>{{/Feedback}}"""

BASIC = NoteType(
    name="Agentic Basic",
    fields=("ID", "Front", "Back", "Code", "Sources", "Verified", "Reverse", "Feedback"),
    templates={
        "Card 1": (
            '<div class="prompt">{{Front}}</div>',
            '<div class="prompt">{{Front}}</div>\n<hr id="answer">\n<div class="answer">{{Back}}</div>'
            + _BACK_MATTER,
        ),
        "Card 2": (
            '{{#Reverse}}<div class="kicker">Name it</div><div class="prompt">{{Back}}</div>{{/Reverse}}',
            '<div class="kicker">Name it</div><div class="prompt">{{Back}}</div>\n<hr id="answer">\n'
            '<div class="answer">{{Front}}</div>' + _BACK_MATTER,
        ),
    },
    is_cloze=False,
)

CLOZE = NoteType(
    name="Agentic Cloze",
    fields=("ID", "Text", "Extra", "Code", "Sources", "Verified", "Feedback"),
    templates={
        "Cloze": (
            '<div class="prompt">{{cloze:Text}}</div>',
            '<div class="prompt">{{cloze:Text}}</div>\n'
            '{{#Extra}}<hr id="answer"><div class="answer">{{Extra}}</div>{{/Extra}}' + _BACK_MATTER,
        ),
    },
    is_cloze=True,
)

NOTE_TYPES = (BASIC, CLOZE)

_BASE_CSS = """
.card {
  --fg: #1f1e1b; --muted: #74716a; --bg: #fbfaf7; --panel: #f1efe9;
  --rule: #dedbd2; --accent: #a1461a; --link: #2f5f8a;
  font-family: ui-sans-serif, -apple-system, "Segoe UI", system-ui, sans-serif;
  font-size: 19px; line-height: 1.5; text-align: left;
  color: var(--fg); background: var(--bg);
}
.card.nightMode, .nightMode .card, .night_mode .card {
  --fg: #e9e6df; --muted: #9b978d; --bg: #1c1b19; --panel: #292825;
  --rule: #3a3833; --accent: #f0a06b; --link: #8fb8e0;
}
.prompt, .answer, .code, .provenance, .feedback, .kicker, hr#answer {
  max-width: 42rem; margin-left: auto; margin-right: auto;
}
.prompt > :first-child, .answer > :first-child { margin-top: 0; }
.prompt > :last-child, .answer > :last-child { margin-bottom: 0; }
.kicker { font-size: .72em; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); margin-bottom: .5em; }
hr#answer { border: 0; border-top: 1px solid var(--rule); margin-top: 1.1em; margin-bottom: 1.1em; }
.cloze { color: var(--accent); font-weight: 600; }
code { font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; font-size: .86em;
       background: var(--panel); padding: .08em .3em; border-radius: 4px; }
pre { background: var(--panel); padding: .75em 1em; border-radius: 6px; overflow-x: auto; line-height: 1.4; }
.code { margin-top: 1em; }
table { border-collapse: collapse; }
th, td { border: 1px solid var(--rule); padding: .25em .6em; }
.provenance { margin-top: 1.4em; font-size: .7em; color: var(--muted); }
.provenance a { color: var(--link); text-decoration: none; }
.verified { white-space: nowrap; margin-left: .6em; }
.feedback { margin-top: 1em; font-size: .8em; border-left: 3px solid var(--accent); padding-left: .6em; color: var(--muted); }
"""

# Pygments colour rules must follow the base CSS; the dark rules come last so they win in night mode.
CSS = "\n".join(
    [
        _BASE_CSS,
        HtmlFormatter(style="default").get_style_defs(".card pre code"),
        HtmlFormatter(style="github-dark").get_style_defs([".nightMode pre code", ".night_mode pre code"]),
        ".card pre code, .nightMode pre code, .night_mode pre code { background: transparent; padding: 0; font-size: .82em; }",
    ]
)
