"""The review screen's design system: the tokens, the app chrome and every shared control.

One spacing scale, one type scale and eleven colors (TOKENS_CSS). Every rule in this file and in
ui/css/ draws from them, and tests/test_design_system.py fails on anything else: an off-scale
margin, a font size outside the scale, a color literal, a gradient or a shadow. Hierarchy comes
from size, weight and space; structure from hairlines, not boxes, with two framed exceptions: a
warning inside the page, and the claim page's verdict. The app's pages carry only this
stylesheet; the exported report keeps its own (core/report/html.py).

Color carries meaning, never decoration. Four neutrals hold the page. Three hues, the site's own
(site/styles.css), each with a pale wash: navy for what the expert can act on and where they are,
green for the claim as stated, red against it. Green is earned: only support an expert, counsel
or the code checks stand behind takes it, never a model's label or the AI reviewer's acceptance,
and the same test fails if a rule gives it to either. A highlighter marks quoted words.

IBM Plex Sans for all text, IBM Plex Mono only for ids and hashes, Instrument Serif only for the
wordmark. The fonts (SIL Open Font License) are vendored in ui/static/fonts and served by this
screen at /static/fonts/; the font stacks fall back to system fonts. The Mabillon mark is inline
SVG, so no image request is ever made.
"""

from __future__ import annotations

from pathlib import Path

FONT_DIR = Path(__file__).resolve().parent / "static" / "fonts"
FONT_FILES = frozenset(p.name for p in FONT_DIR.glob("*.woff2"))

_LATIN = (
    "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,"
    "U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD"
)
_CYRILLIC = "U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116"


def _face(family: str, file: str, weight: str, rng: str, style: str = "normal") -> str:
    return (
        f"@font-face {{ font-family: '{family}'; font-style: {style}; font-weight: {weight}; "
        f"font-display: swap; src: url('/static/fonts/{file}') format('woff2'); "
        f"unicode-range: {rng}; }}\n"
    )


FONT_CSS = (
    _face("IBM Plex Sans", "ibm-plex-sans-latin-wght-normal.woff2", "100 700", _LATIN)
    + _face("IBM Plex Sans", "ibm-plex-sans-cyrillic-wght-normal.woff2", "100 700", _CYRILLIC)
    + _face("Instrument Serif", "instrument-serif-latin-400-normal.woff2", "400", _LATIN)
    + _face("IBM Plex Mono", "ibm-plex-mono-latin-400-normal.woff2", "400", _LATIN)
    + _face("IBM Plex Mono", "ibm-plex-mono-cyrillic-400-normal.woff2", "400", _CYRILLIC)
)

# A ledger page split into "for" and "against". It takes the text color and the page color.
MARK = (
    "<svg class='mark' viewBox='0 0 24 24' width='24' height='24' aria-hidden='true' fill='none'>"
    "<rect class='mark-page' x='2.75' y='2.75' width='18.5' height='18.5' rx='4'/>"
    "<path class='mark-rule' d='M12 6.5v11M6.75 9h2.5M6.75 12h2.5M6.75 15h2.5M14.75 9h2.5"
    "M14.75 12h1.25' stroke-width='1.5' stroke-linecap='round'/></svg>"
)

# The whole system. Nothing outside this block names a color, a size in px for type, or a
# spacing length.
TOKENS_CSS = """
:root {
  /* color: four neutrals, then three hues that each mean one thing, each with a pale wash for
     a fill behind its own text, and a highlighter */
  --ink: #141414;     /* text */
  --muted: #5f5a51;   /* secondary text, control edges, marks that mean "neither way" */
  --paper: #f7f5f0;   /* the one background */
  --line: #dedad0;    /* hairlines, quiet fills */
  --accent: #1d3557;  /* yours to act on, and where you are: the main action, links, focus,
                         the open page and row, what waits on you */
  --accent-wash: #e4eaf2;  /* its pale fill: the open page and row, and the phone's own side
                              of a conversation (sent messages, as a messaging app shows
                              them); the record under review takes the accent edge instead */
  --support: #2f5d43; /* for the claim as stated, once an expert, counsel or the code checks
                         stand behind it; never a model's label or the AI reviewer's */
  --support-wash: #e6eee8;
  --signal: #9a3a2c;  /* against the claim as stated, and errors; nothing else */
  --signal-wash: #f4e5e1;
  --quote: #f3e3a6;   /* the highlighter: words quoted from a record */
  /* space: margin, padding and gap take only these */
  --s1: 4px; --s2: 8px; --s3: 12px; --s4: 16px; --s5: 24px; --s6: 32px; --s7: 48px; --s8: 64px;
  /* type: size and its line height, in pairs */
  --t1: 12px; --l1: 16px;
  --t2: 14px; --l2: 20px;
  --t3: 16px; --l3: 24px;
  --t4: 20px; --l4: 28px;
  --t5: 28px; --l5: 36px;
  --sans: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial,
    sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, Menlo, Consolas, monospace;
  --wordmark: "Instrument Serif", Georgia, serif;
  /* shape and layout */
  --radius: 4px; --control: 32px; --dot: 8px; --sidebar: 224px; --measure: 68ch;
  --ease: cubic-bezier(.22, 1, .36, 1);
  color-scheme: light;
}
"""

THEME_CSS = (
    TOKENS_CSS
    + """
/* ---- base */
*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; scrollbar-color: var(--muted) var(--paper); }
body { margin: 0; padding: 0 0 0 var(--sidebar); font: 400 var(--t2)/var(--l2) var(--sans);
  color: var(--ink); background: var(--paper); accent-color: var(--accent);
  -webkit-font-smoothing: antialiased; }
::selection { background: var(--accent); color: var(--paper); }
main { max-width: 1120px; margin: 0; padding: var(--s6) var(--s7) var(--s8); }
main.wide { max-width: 1360px; }
p { margin: 0 0 var(--s3); }
main p, main li, main dd, main blockquote { max-width: var(--measure); text-wrap: pretty; }
ul, ol { margin: 0 0 var(--s3); padding-left: var(--s5); }
li { margin: 0 0 var(--s1); }

/* type: five sizes, two weights */
h1 { font: 600 var(--t4)/var(--l4) var(--sans); margin: 0 0 var(--s4); text-wrap: balance; }
h2 { font: 600 var(--t3)/var(--l3) var(--sans); margin: var(--s7) 0 var(--s3); }
h3, h4 { font: 600 var(--t2)/var(--l2) var(--sans); margin: var(--s5) 0 var(--s2); }
strong, b { font-weight: 600; }
h1 + p, .lede { color: var(--muted); }
.muted { color: var(--muted); }
small, .meta, .where { font-size: var(--t1); line-height: var(--l1); color: var(--muted); }
.mono, code { font: 400 var(--t1)/var(--l1) var(--mono); color: var(--muted);
  overflow-wrap: anywhere; }
.q { white-space: pre-wrap; }
/* visually hidden: kept for a screen reader and for tools that read the page */
.vh { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%);
  white-space: nowrap; }
a { color: var(--accent); text-decoration: underline 1px; text-underline-offset: 0.2em; }
a:hover { text-decoration-thickness: 2px; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
blockquote { margin: var(--s2) 0; padding: 0 0 0 var(--s3); border-left: 1px solid var(--muted); }
/* a quoted span: the highlighter and an ink underline, so it shows on every message bubble
   and without color */
mark { background: var(--quote); color: inherit; border-bottom: 1px solid var(--ink); }
hr { border: 0; border-top: 1px solid var(--line); margin: var(--s5) 0; }

/* ---- sidebar: the wordmark, the open case, the pages in groups; the footer holds where the
   model runs, the reviewer and Help */
header.top { position: fixed; inset: 0 auto 0 0; z-index: 5; width: var(--sidebar);
  display: flex; flex-direction: column; background: var(--paper);
  border-right: 1px solid var(--line); overflow-y: auto; scrollbar-width: thin; }
.bar { display: contents; }
.brand { display: flex; align-items: center; gap: var(--s2); text-decoration: none;
  color: var(--ink); padding: var(--s5) var(--s4) 0; }
.brand span { font: 400 var(--t4)/var(--l4) var(--wordmark); }
.mark-page { fill: var(--ink); }
.mark-rule { stroke: var(--paper); }
.casename { display: block; font: 600 var(--t2)/var(--l2) var(--sans); color: var(--ink);
  text-decoration: none; margin: var(--s5) var(--s2) 0; padding: var(--s1) var(--s2);
  border-radius: var(--radius); }
a.casename:hover, a.casename.on { background: var(--line); }
nav.tabs { order: 2; display: flex; flex-direction: column;
  padding: var(--s3) var(--s2) var(--s4); }
nav.tabs a { color: var(--ink); text-decoration: none; padding: var(--s1) var(--s2);
  border-radius: var(--radius); white-space: nowrap; }
nav.tabs a:hover { background: var(--line); }
nav.tabs a.on { font-weight: 600; background: var(--accent-wash); color: var(--accent); }
nav.tabs .sep { flex: none; height: var(--s4); }
.bar .right { order: 3; margin-top: auto; display: flex; flex-direction: column;
  align-items: flex-start; gap: var(--s1); padding: var(--s4); font-size: var(--t1);
  line-height: var(--l1); color: var(--muted); }
.pill { display: inline-flex; align-items: center; gap: var(--s2); color: var(--muted);
  text-decoration: none; }
.pill::before { content: ""; flex: none; width: var(--dot); height: var(--dot);
  border-radius: 50%; border: 2px solid var(--muted); }
a.pill::before { background: var(--muted); }
a.pill:hover { color: var(--ink); }
.who { color: var(--ink); font-weight: 600; }
.bar .right a.help { color: var(--muted); text-decoration: none; }
.bar .right a.help:hover { color: var(--ink); }

/* ---- notices. The page-top notices (demo case, untested format, verdicts out of date) are one
   small line each over a hairline; they stay on every page. A warning inside the page is a
   framed box, so a frame there always means "read this". The only other frame in the app is
   the claim page's verdict (its plate, ui/css/claim.py). */
.banner { margin: 0 0 var(--s4); padding: 0 0 var(--s2); border-bottom: 1px solid var(--line);
  font-size: var(--t1); line-height: var(--l1); }
.banner + .banner { margin-top: calc(-1 * var(--s2)); }
.banner p { margin: var(--s1) 0 0; color: var(--muted); }
.banner strong { font-weight: 600; }
.banner details > summary { font-size: var(--t1); line-height: var(--l1); }
.banner details > summary strong { font-weight: 400; }
.banner form { margin: var(--s2) 0 0; }
.banner .banner { margin: var(--s2) 0 0; padding: 0; border: 0; }
p.warn:not(.format-notice), .caution, .flash { max-width: var(--measure); margin: 0 0 var(--s4);
  padding: var(--s2) var(--s3); border: 1px solid var(--muted); border-radius: var(--radius); }
.flash.err { border-color: var(--signal); background: var(--signal-wash);
  color: var(--signal); }
.flash.toast { position: fixed; right: var(--s5); bottom: var(--s5); z-index: 10; margin: 0;
  max-width: min(420px, calc(100vw - var(--s7))); background: var(--ink); color: var(--paper);
  border-color: var(--ink); animation: toast-out 0.3s ease 7s forwards; }
.flash.toast.err { animation: none; background: var(--signal); border-color: var(--signal);
  color: var(--paper); }
@keyframes toast-out { to { opacity: 0; visibility: hidden; } }
p.format-notice { margin: var(--s1) 0; font-size: var(--t1); line-height: var(--l1); }
p.format-notice strong { font-weight: 600; }
.flash.recovery h2 { margin: 0 0 var(--s2); }
.recovery-key { font-size: var(--t3); line-height: var(--l3); color: var(--ink); }

/* coming back to the item a form acted on: mark it */
[id] { scroll-margin-top: var(--s5); }
:target { outline: 2px solid var(--accent); outline-offset: var(--s1); }
main:target, section:target, h2:target, h3:target, tr:target, details:target { outline: 0; }
tr:target td, tr.target td { background: var(--line); }
tr.target td { font-weight: 600; }

/* ---- tables: a ruled ledger. No frame and no fill; the header sits on an ink rule, rows on
   hairlines, and the first column starts at the page's text edge. */
table { border-collapse: collapse; width: 100%; margin: var(--s2) 0 var(--s5);
  font-variant-numeric: tabular-nums; }
th, td { padding: var(--s2) var(--s4) var(--s2) 0; text-align: left; vertical-align: top;
  border-bottom: 1px solid var(--line); overflow-wrap: anywhere; }
th:last-child, td:last-child { padding-right: 0; }
th { font: 400 var(--t1)/var(--l1) var(--sans); color: var(--muted); white-space: nowrap;
  border-bottom-color: var(--ink); vertical-align: bottom; }
td.when { white-space: nowrap; color: var(--muted); }
td .mono { display: inline-block; }
td p { margin: 0; }
td:has(> form.inline):not(:has(input[type=text])) { white-space: nowrap; }
td:has(> form.inline) details { white-space: normal; margin-top: var(--s1); }

/* ---- records as rows (ui/records.py): the date once per run of rows, the phone's local time,
   the sender, the message, then its row in the file, small and muted at the right edge. The
   row asked about is filled, so every row is inset by the same step and the fill does not
   touch its text. The values as exported fold under the table. */
table.recs { margin: var(--s2) 0; }
table.recs th:first-child, table.recs td:first-child { padding-left: var(--s2); }
table.recs td { overflow-wrap: break-word; word-break: normal; }
table.recs td.d { white-space: nowrap; color: var(--muted); }
table.recs td.t { white-space: nowrap; }
table.recs td.what { min-width: 26ch; }
table.recs td.src, table.recs td.tier { color: var(--muted); font-size: var(--t1);
  line-height: var(--l1); }
table.recs th:last-child, table.recs td.src { text-align: right; padding-right: var(--s2); }
table.recs td.src { white-space: nowrap; }
table.recs td.src .mono { white-space: normal; }
table.recs tr.target td { font-weight: 400; }
table.recs tr.target td.what { font-weight: 600; }
table.recs strong.warn { display: inline-block; margin-top: var(--s1); font-size: var(--t1);
  line-height: var(--l1); }
details.exported { margin: 0 0 var(--s5); }
details.exported > summary { color: var(--muted); font-size: var(--t1); line-height: var(--l1); }
details.exported > summary:hover { color: var(--ink); }
details.exported ol, details.exported > p { font-size: var(--t1); line-height: var(--l1);
  color: var(--muted); }
p.conv-head { margin: 0 0 var(--s1); }
p.conv-note, p.cited-note { margin: 0 0 var(--s1); max-width: none; font-size: var(--t1);
  line-height: var(--l1); }
p.cited-more { margin: 0 0 var(--s2); font-size: var(--t1); line-height: var(--l1); }

/* ---- forms: the label above its field, 32px controls, one focus ring */
form { margin: 0; }
form.inline { display: inline; }
form.box, form.plain { margin: var(--s3) 0 var(--s5); }
form.box > :last-child, form.plain > :last-child { margin-bottom: 0; }
fieldset { border: 0; margin: 0 0 var(--s3); padding: 0; min-width: 0; }
legend { padding: 0; margin: 0 0 var(--s1); font: 600 var(--t1)/var(--l1) var(--sans); }
label:has(> input[type=text], > input[type=password], > input[type=number], > select,
  > textarea, > .unit-input) { display: inline-grid; grid-template-columns: minmax(0, 1fr);
  gap: var(--s1); vertical-align: top; max-width: 100%; margin: 0 var(--s3) var(--s2) 0;
  font: 600 var(--t1)/var(--l1) var(--sans); }
/* a field with its button beside it: both sit on the field's bottom edge */
label:has(> input[type=text], > select):has(+ button) { vertical-align: bottom;
  margin-bottom: 0; }
label + button { vertical-align: bottom; margin-top: var(--s2); }
label:has(> textarea[name]), label:has(> input[type=text].wide) { display: grid;
  margin-right: 0; }
label:has(> input[type=checkbox], > input[type=radio]) { display: inline-flex;
  align-items: flex-start; gap: var(--s2); margin: 0 var(--s4) var(--s1) 0; cursor: pointer; }
input[type=text], input[type=password], input[type=number], input[type=search], select {
  height: var(--control); }
input[type=text], input[type=password], input[type=number], input[type=search],
input[type=file], textarea, select { font: 400 var(--t2)/var(--l2) var(--sans);
  color: var(--ink); background: var(--paper); border: 1px solid var(--muted);
  border-radius: var(--radius); padding: 0 var(--s2); margin: 0; max-width: 100%;
  caret-color: var(--accent); }
input[type=text], input[type=password] { min-width: min(280px, 100%); }
input[type=text].wide, textarea { width: 100%; }
textarea { display: block; padding: var(--s2); min-height: 96px; resize: vertical; }
input[type=file] { padding: var(--s2); border-style: dashed; }
input[type=file]::file-selector-button { font: 600 var(--t2)/var(--l2) var(--sans);
  color: var(--ink); background: var(--line); border: 0; border-radius: var(--radius);
  padding: var(--s1) var(--s3); margin-right: var(--s3); cursor: pointer; }
select { padding-right: var(--s1); cursor: pointer; }
input::placeholder, textarea::placeholder { color: var(--muted); opacity: 1; }
input:focus-visible, textarea:focus-visible, select:focus-visible {
  outline: 2px solid var(--accent); outline-offset: 1px; }
input:disabled, select:disabled, textarea:disabled { color: var(--muted);
  border-color: var(--line); cursor: not-allowed; }
/* Checkboxes and radios drawn in CSS (the page allows no images): a 16px box, accent when
   checked. Forced-colors mode gets the system control back. */
input[type=checkbox], input[type=radio] { appearance: none; -webkit-appearance: none;
  flex: none; display: inline-grid; place-content: center; width: 16px; height: 16px;
  margin: 0; translate: 0 2px; background: var(--paper);
  border: 1px solid var(--muted); border-radius: var(--radius); cursor: pointer; }
input[type=radio] { border-radius: 50%; }
input[type=checkbox]::before { content: ""; width: 8px; height: 4px;
  border: solid var(--paper); border-width: 0 0 2px 2px;
  transform: translateY(-1px) rotate(-45deg) scale(0); }
input[type=radio]::before { content: ""; width: 6px; height: 6px; border-radius: 50%;
  background: var(--paper); transform: scale(0); }
input[type=checkbox]:checked, input[type=radio]:checked { background: var(--accent);
  border-color: var(--accent); }
input[type=checkbox]:checked::before { transform: translateY(-1px) rotate(-45deg) scale(1); }
input[type=radio]:checked::before { transform: scale(1); }
@media (forced-colors: active) {
  input[type=checkbox], input[type=radio] { appearance: auto; -webkit-appearance: auto; }
  input[type=checkbox]::before, input[type=radio]::before { content: none; }
}
/* a number with its unit inside the field */
.unit-input { display: flex; align-items: center; height: var(--control); max-width: 200px;
  border: 1px solid var(--muted); border-radius: var(--radius); font-weight: 400; }
.unit-input:focus-within { outline: 2px solid var(--accent); outline-offset: 1px; }
.unit-input input[type=number] { flex: 1; min-width: 0; height: auto; border: 0; outline: 0;
  background: transparent; -moz-appearance: textfield; appearance: textfield; }
.unit-input input::-webkit-outer-spin-button,
.unit-input input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
.unit-input .unit { padding: 0 var(--s2) 0 var(--s1); font-size: var(--t2);
  line-height: var(--l2); color: var(--muted); }
form.settings { display: grid; gap: var(--s4); }
form.settings .settings-head h3 { margin: 0; }
form.settings .settings-head p { margin: 0; color: var(--muted); }
form.settings .fields { display: grid; gap: var(--s4) var(--s5); max-width: 640px;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
form.settings label.field { display: grid; align-content: start; gap: var(--s1); margin: 0; }
form.settings small { font-weight: 400; }
form.settings .actions { display: flex; }

/* ---- buttons: three ranks. Solid accent is the page's main action, and Accept on each open
   evidence item (the one decision that item waits for); every other button is a quiet fill;
   a link does the rest. Accept is never green: it accepts what the item shows, for the claim or
   against it. */
button, a.button, a.dl { display: inline-flex; align-items: center; justify-content: center;
  gap: var(--s1); min-height: var(--control); padding: 0 var(--s3); margin: 0;
  font: 600 var(--t2)/var(--l2) var(--sans); color: var(--ink); background: var(--line);
  border: 1px solid var(--line); border-radius: var(--radius); text-decoration: none;
  cursor: pointer; vertical-align: middle; white-space: nowrap;
  transition: border-color 0.15s var(--ease), background-color 0.15s var(--ease); }
button:hover, a.button:hover, a.dl:hover { border-color: var(--accent); }
button.primary, button[value=accepted], a.button.primary { background: var(--accent);
  border-color: var(--accent); color: var(--paper); }
button.primary:hover, button[value=accepted]:hover, a.button.primary:hover {
  background: var(--ink); border-color: var(--ink); }
button:disabled, button.primary:disabled { color: var(--muted); background: var(--paper);
  border-color: var(--line); cursor: not-allowed; }
/* the choice already made: it keeps this look under the pointer too, whatever its rank */
button[aria-pressed=true], button[aria-pressed=true]:hover,
button.primary[aria-pressed=true]:hover { background: var(--accent-wash);
  border-color: var(--accent); color: var(--accent); }
button + button, form.inline + form.inline button, button + a.button { margin-left: var(--s2); }
@media (prefers-reduced-motion: reduce) {
  button, a.button, a.dl, .flash.toast { transition: none; animation: none; }
}

/* ---- disclosures: a small drawn chevron that turns when open */
details { margin: var(--s2) 0; }
details > summary { list-style: none; cursor: pointer; }
details > summary::-webkit-details-marker { display: none; }
details > summary::before { content: ""; display: inline-block; width: 6px; height: 6px;
  margin: 0 var(--s2) 0 0; vertical-align: 0.15em; border: solid var(--muted);
  border-width: 0 1px 1px 0; transform: rotate(-45deg); }
details[open] > summary::before { transform: rotate(45deg); vertical-align: 0.25em; }
details > summary:hover::before { border-color: var(--ink); }
details[open] > summary { margin-bottom: var(--s2); }

/* ---- status words. A verdict is its signed words behind a mark. The color says which way:
   support green for the claim, signal against it, accent for support that waits on the
   expert's answer, muted for neither. The fill says how far it has gone: solid for support the
   expert confirmed and for contradicted; a ring for support by code checks or counsel, for a
   contradiction that waits on the expert's confirm, and for unproven; a dashed ring for not
   tested. So support the expert has not confirmed never wears the expert-confirmed mark, and
   support that rests on the AI reviewer (v-supai) takes no green at all: it keeps the plain ink
   ring. The green is opt-in: a Supported verdict takes it only with v-earned, which _vcls in
   ui/pages.py writes when an expert, counsel or the code checks stand behind the verdict and
   nothing it rests on changed after the run. Without it the words and mark are ink (solid for
   v-sup, a ring otherwise), so a pill built anywhere else, or a verdict that is not current,
   never shows green. The words always show, so no verdict rests on the mark or its color. */
.verdict { display: inline-flex; align-items: center; gap: var(--s2); font-weight: 600;
  white-space: nowrap; text-decoration: none; color: var(--ink); }
.verdict::before { content: ""; flex: none; width: var(--dot); height: var(--dot);
  border-radius: 50%; border: 2px solid var(--ink); }
.v-sup::before { background: var(--ink); }
.v-earned { color: var(--support); }
.v-earned::before { border-color: var(--support); }
.v-sup.v-earned::before { background: var(--support); }
.v-con, .v-confirm { color: var(--signal); }
.v-con::before { background: var(--signal); border-color: var(--signal); }
.v-confirm::before { border-color: var(--signal); }
.v-await { color: var(--accent); }
.v-await::before { border-color: var(--accent); }
.v-unp::before { border-color: var(--muted); }
.verdict.v-nt::before { border-style: dashed; border-width: 1px; }
/* every other tag is plain small text; a run of them is joined by a middle dot */
.badge, .stpill, .chip, .tag, .sel-n { font-size: var(--t1); line-height: var(--l1);
  color: var(--muted); white-space: nowrap; }
.badge + .badge::before, .stpill + .stpill::before, .badge + .stpill::before { content: "·";
  margin: 0 var(--s2); color: var(--muted); font-weight: 400; }
.b-against, .st-rejected.stpill, .chip.flag, .tag.left, .sel-n { color: var(--signal);
  font-weight: 600; }
.sel-n.none { color: var(--muted); font-weight: 400; }
.b-conf, .st-confirmed.stpill, .chip.ok, .tag.pick { color: var(--ink); font-weight: 600; }
/* the Timeline's "Matches": the records agree with the time the document states, by code */
.tl .chip.ok { color: var(--support); font-weight: 600; }
.stpill b { color: var(--ink); margin-left: var(--s1); }
/* a count of none is not a status: no weight and no signal */
.stpill.zero, .stpill.zero b { color: var(--muted); font-weight: 400; }
.counts { display: flex; flex-wrap: wrap; align-items: baseline; }
/* the one filled tag: this waits on you */
.gap.you { display: inline-block; padding: 0 var(--s1); border-radius: var(--radius);
  background: var(--accent); color: var(--paper); font-weight: 600; }

/* ---- a list of claims: one ruled row each */
.ledger { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--line); }
.ledger li { position: relative; margin: 0; max-width: none; border-bottom: 1px solid var(--line); }
.ledger li:hover { background: var(--line); }
.ledger .row { padding: var(--s3) 0; }
.ledger .head { display: flex; flex-wrap: wrap; align-items: baseline;
  justify-content: space-between; gap: var(--s1) var(--s3); }
.ledger .meta { font-size: var(--t1); line-height: var(--l1); color: var(--muted);
  font-variant-numeric: tabular-nums; }
.ledger .meta a { color: var(--ink); font-weight: 600; text-decoration: none; }
.ledger .meta a::after { content: ""; position: absolute; inset: 0; }
.ledger .verdict { font-size: var(--t1); line-height: var(--l1); }
.ledger .needs, .ledger .gap { font-size: var(--t1); line-height: var(--l1); color: var(--muted); }
section.group { margin: var(--s7) 0 0; }
.ghead { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--s1) var(--s3);
  margin: 0 0 var(--s2); }
.ghead h2 { margin: 0; }
.ghead .muted { font-size: var(--t1); line-height: var(--l1); }

/* ---- a conversation around a record. Received messages take the quiet fill; the phone's own
   take the accent wash and sit right; the record itself takes an accent edge. */
.thread { display: flex; flex-direction: column; gap: var(--s1); margin: var(--s2) 0; }
.msg { max-width: 72%; align-self: flex-start; padding: var(--s1) var(--s3);
  border: 1px solid var(--line); border-radius: var(--radius); background: var(--line);
  display: grid; grid-template-columns: minmax(0, 1fr) auto; column-gap: var(--s4); }
.msg.out { align-self: flex-end; background: var(--accent-wash);
  border-color: var(--accent-wash); }
.msg.target { border-color: var(--accent); outline: 1px solid var(--accent); }
.msg .who2 { grid-column: 1; font-size: var(--t1); line-height: var(--l1); color: var(--muted); }
.msg .t { grid-column: 2; grid-row: 1; font-size: var(--t1); line-height: var(--l1);
  color: var(--muted); white-space: nowrap; font-variant-numeric: tabular-nums; }
.msg .body { grid-column: 1 / -1; overflow-wrap: anywhere; }
.msg.cont .body { grid-column: 1; grid-row: 1; }
.msg .cited { margin-right: var(--s2); font-weight: 600; color: var(--accent); }

/* ---- an evidence item and other ruled blocks */
.item { padding: var(--s4) 0; border-top: 1px solid var(--line); }
.card { margin: var(--s5) 0; }
section.agent { margin: var(--s5) 0; padding: var(--s4) 0 0;
  border-top: 1px solid var(--line); }
section.agent ul.proposed { margin: var(--s2) 0 var(--s3); }
details.flag { margin-top: var(--s1); }
ul.flags form.inline button { margin-left: var(--s2); }
ul.setuplist { list-style: none; padding: 0; margin: 0 0 var(--s3);
  border-top: 1px solid var(--line); }
ul.setuplist li { margin: 0; max-width: none; padding: var(--s2) 0;
  border-bottom: 1px solid var(--line); }
dl.record { display: grid; grid-template-columns: max-content minmax(0, 1fr);
  gap: var(--s1) var(--s5); margin: 0 0 var(--s3); }
dl.record dt { color: var(--muted); }
dl.record dd { margin: 0; }
details.case-settings { margin: var(--s3) 0 var(--s5); }
.inline-actions { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s2) var(--s3);
  margin: 0 0 var(--s2); }
.inline-actions .muted { flex: 1 1 260px; font-size: var(--t1); line-height: var(--l1); }
.inline-actions button + button, .inline-actions button + a.button { margin-left: 0; }

/* ---- small screens: the sidebar becomes a top bar and tables scroll sideways */
@media (max-width: 960px) {
  body { padding-left: 0; }
  header.top { position: static; width: auto; border-right: 0;
    border-bottom: 1px solid var(--line); overflow: visible; }
  .brand { padding: var(--s3) var(--s4) 0; }
  .casename { margin: var(--s2) var(--s3) 0; }
  nav.tabs { flex-direction: row; flex-wrap: wrap; padding: var(--s2) var(--s3) var(--s3); }
  nav.tabs .sep { display: none; }
  .bar .right { order: 1; margin: 0; flex-direction: row; flex-wrap: wrap;
    gap: var(--s1) var(--s4); padding: var(--s1) var(--s4) 0; }
  main { padding: var(--s5) var(--s5) var(--s8); }
  .msg { max-width: 88%; }
}
@media (max-width: 600px) {
  main { padding: var(--s5) var(--s4) var(--s7); }
  table { display: block; overflow-x: auto; }
  th, td { overflow-wrap: normal; }
  .counts { gap: var(--s1) var(--s3); }
  .counts .stpill + .stpill::before { content: none; }
  .msg { grid-template-columns: minmax(0, 1fr); max-width: 92%; }
  .msg .t { grid-column: 1; grid-row: auto; white-space: normal; }
  input[type=text], input[type=password] { min-width: 0; width: 100%; }
  dl.record { grid-template-columns: minmax(0, 1fr); gap: 0; }
  dl.record dd { margin: 0 0 var(--s2); }
}
"""
)
