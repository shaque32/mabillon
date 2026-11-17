"""Set up and run (/setup, /run).

This page's own CSS, scoped to its markup (see ui/css/__init__.py).
"""

CSS = """
/* Set up's tables: words stay whole (a cell wraps only between words), controls sit on one
   row, and the claims table's wording column takes the room. */
table.tidy td { overflow-wrap: break-word; }
table.tidy td.nowrap { white-space: nowrap; }
table.tidy td .mono { white-space: nowrap; word-break: normal; overflow-wrap: normal; }
table.tidy td.controls { width: 1%; white-space: nowrap; }
table.tidy .row-actions { display: flex; flex-wrap: nowrap; gap: var(--s2); align-items: center; }
table.tidy .row-actions form.inline { display: flex; gap: var(--s2); align-items: center; }
table.tidy .row-actions input[type=text] { min-width: 0; width: 170px; }
table.tidy .row-actions button { margin: 0; }
table.tidy td.controls details { margin: var(--s1) 0 0; }
table.claim-order td.brief { white-space: nowrap; }
table.claim-order td .where, table.claim-order td .kind { font-size: var(--t1);
  line-height: var(--l1); color: var(--muted); }
table.claim-order td .where::before { content: "\\A"; white-space: pre; }
table.claim-order td .kind::before { content: " \\B7  "; white-space: pre; }
table.claim-order td.brief:nth-child(3) { font-size: var(--t1); line-height: var(--l1);
  color: var(--muted); white-space: normal; min-width: 96px; }
table.claim-order td.decide { width: 1%; white-space: nowrap; overflow-wrap: normal; }
table.claim-order .claim-actions { display: inline-flex; flex-wrap: nowrap; gap: var(--s1);
  align-items: center; vertical-align: middle; }
table.claim-order .claim-actions form.inline { display: flex; gap: var(--s1); }
table.claim-order .claim-actions button { margin: 0; }
/* Quiet controls on every row: the arrows and Remove show a fill only on hover or focus */
table.claim-order .claim-actions button:not([value=accepted]) { background: transparent;
  border-color: transparent; font-weight: 400; color: var(--muted); }
table.claim-order .claim-actions button:not([value=accepted]):hover,
table.claim-order .claim-actions button:not([value=accepted]):focus-visible {
  background: var(--line); color: var(--ink); }
table.claim-order .claim-actions button[name=delta] { padding: 0 var(--s2); }
/* Remove stays apart from the reorder buttons, so a slip on Down does not land on it */
table.claim-order .claim-actions form:last-child { margin-left: var(--s3); }
table.claim-order td.decide details { display: inline-block; vertical-align: middle;
  margin: 0 0 0 var(--s3); white-space: normal; }
table.claim-order td.decide details[open] { display: block; margin: var(--s2) 0 0; }
table.claim-order td.decide details > summary { white-space: nowrap; color: var(--muted);
  font-size: var(--t1); line-height: var(--l1); }
table.claim-order td.decide textarea { width: 100%; min-width: 260px; margin: var(--s1) 0; }

/* Set up and run: the five steps as one line of links (numbered: the order matters), one row
   of actions per step, long text folded away */
ol.steps { list-style: none; display: flex; flex-wrap: wrap; gap: var(--s2) var(--s5);
  margin: 0 0 var(--s2); padding: var(--s2) 0; border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line); }
ol.steps li { margin: 0; }
ol.steps a { display: inline-flex; align-items: baseline; gap: var(--s2);
  text-decoration: none; color: var(--muted); }
ol.steps a:hover { color: var(--ink); }
ol.steps .n { font-variant-numeric: tabular-nums; }
ol.steps .n::after { content: "."; }
ol.steps .state { font-size: var(--t1); line-height: var(--l1); }
ol.steps .todo a { color: var(--ink); font-weight: 600; }
form.plain > p.muted { font-size: var(--t1); line-height: var(--l1); }
table.files .coverage { margin-top: var(--s1); font-size: var(--t1); line-height: var(--l1);
  color: var(--muted); }
table.files .coverage ul { margin: var(--s1) 0 0; padding-left: var(--s4); }
table.files .rec-note { display: block; white-space: normal; max-width: 14rem;
  font-size: var(--t1); line-height: var(--l1); }
table.hashes td.hash { white-space: normal; overflow-wrap: anywhere; }
details.add-files { margin: var(--s1) 0 var(--s2); }
.uploads { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: var(--s5); }
.uploads form.box { margin: 0; }
.uploads form.box p .muted { display: block; margin-top: var(--s1); font-size: var(--t1);
  line-height: var(--l1); }
.removed ul { list-style: none; display: flex; flex-wrap: wrap; gap: var(--s2);
  margin: 0 0 var(--s3); padding: 0; }
.removed li { display: inline-flex; align-items: center; gap: var(--s2); margin: 0; }
ul.ready { list-style: none; margin: 0 0 var(--s3); padding: 0; }
ul.ready li { margin: 0 0 var(--s1); padding-left: var(--s4);
  text-indent: calc(-1 * var(--s4)); color: var(--muted); }
ul.ready li::before { content: ""; display: inline-block; width: var(--dot);
  height: var(--dot); margin-right: var(--s2); border-radius: 50%;
  border: 2px solid var(--muted); }
ul.ready li.ok::before { background: var(--muted); }
ul.ready li.todo { color: var(--ink); }
ul.ready li.todo::before { border-color: var(--ink); }
.checks { display: grid; gap: var(--s2); margin: 0 0 var(--s3); }
.checks label { display: flex; align-items: flex-start; gap: var(--s2); margin: 0;
  max-width: 88ch; cursor: pointer; }
details.options { margin: 0 0 var(--s3); }
details.options > summary { color: var(--muted); }

/* On a phone the set-up tables stack: each row is a short block, its cells one under another,
   and the header row stays for screen readers only. */
@media (max-width: 600px) {
  table.tidy, table.tidy tbody { display: block; overflow: visible; }
  table.tidy thead { position: absolute; width: 1px; height: 1px; overflow: hidden;
    clip-path: inset(50%); }
  table.tidy tbody tr { display: grid; grid-template-columns: auto minmax(0, 1fr);
    gap: var(--s1) var(--s3); padding: var(--s3) 0; border-bottom: 1px solid var(--line); }
  table.tidy tbody td { display: block; grid-column: 1 / -1; width: auto; padding: 0;
    border: 0; white-space: normal; overflow-wrap: anywhere; }
  table.tidy td .mono { white-space: normal; overflow-wrap: anywhere; }
  table.claim-order tbody td:nth-child(1) { grid-column: 1; }
  table.claim-order tbody td:nth-child(2) { grid-column: 2; }
  table.claim-order td .where::before { content: "  "; }
  table.claim-order td.brief:nth-child(3) { min-width: 0; }
  table.claim-order td.decide { width: auto; white-space: normal; }
  table.tidy .row-actions, table.tidy .row-actions form.inline { flex-wrap: wrap; }
  table.tidy .row-actions input[type=text] { flex: 1 1 160px; width: auto; }
  table.files .rec-note { max-width: none; }
}
"""
