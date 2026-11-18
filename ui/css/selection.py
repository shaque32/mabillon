"""Selection (/selection, /selection/context).

This page's own CSS, scoped to its markup (see ui/css/__init__.py). Every value comes from the
tokens in ui/theme.py. Both pages show fragments of the report (core/report/selection.py,
paired.py, restore.py); the app styles them here, and the exported report keeps its own look.
"""

CSS = """
.pg-context p.picked { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s2); }
.pg-context > p:not([class]) { color: var(--muted); }

/* the opening: one paragraph, the definitions and the coverage notice folded, then what was
   found as ruled rows */
.pg-selection details.terms { margin: 0 0 var(--s4); }
.pg-selection details.terms > p { color: var(--muted); }
.pg-selection > ul { list-style: none; padding: 0; margin: var(--s1) 0 var(--s2);
  max-width: 860px; border-top: 1px solid var(--line); }
.pg-selection > ul > li { margin: 0; max-width: none; padding: var(--s2) 0;
  border-bottom: 1px solid var(--line); }

/* section headings read as headings, not small labels */
.pg-selection > h3.eyebrow, .pg-selection > h3#paired-audit {
  font: 600 var(--t3)/var(--l3) var(--sans); margin: var(--s8) 0 var(--s2); }
.pg-selection > h4 { margin: var(--s6) 0 var(--s2); }

/* one paragraph, exhibit or tag set */
.sel-unit { margin: var(--s6) 0 var(--s7); }
.sel-unit > h3 { display: flex; flex-wrap: wrap; align-items: baseline;
  gap: var(--s1) var(--s3); font: 600 var(--t3)/var(--l3) var(--sans); margin: 0 0 var(--s2);
  padding-top: var(--s4); border-top: 1px solid var(--ink); }
.sel-unit > h3 .muted { font: 400 var(--t1)/var(--l1) var(--sans); }
.sel-unit > blockquote { margin: var(--s2) 0 var(--s3); }
ul.sel-quotes { list-style: none; padding: 0; margin: var(--s2) 0 var(--s3); }
ul.sel-quotes li { margin: 0 0 var(--s2); color: var(--muted); }
.sel-claims { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--s1) var(--s4);
  margin: var(--s2) 0; font-size: var(--t1); line-height: var(--l1); color: var(--muted); }
.sel-claims .verdict { font-size: var(--t1); line-height: var(--l1); }

/* a passage: the summary, the exchange as a conversation, then what else is near */
.sel-passage { margin: var(--s4) 0; }
.sel-passage .where { margin-bottom: var(--s1); overflow-wrap: anywhere; }
.sel-passage ul.sum { margin: var(--s1) 0 0; }
.sel-passage ul.sum li { margin: 0; }
.sel-passage > .foot > p { margin: var(--s2) 0 0; }
.sel-passage .sel-passage { margin: var(--s4) 0 0; padding-top: var(--s3);
  border-top: 1px solid var(--line); }
.sel-convo { display: flex; flex-direction: column; gap: var(--s1); margin: var(--s3) 0;
  padding: var(--s3) 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }

/* messages. Received ones are filled, sent ones outlined and set right, as on the claim page.
   A quoted message takes an ink edge; one the document left out takes a dashed signal edge.
   The tag names each state, so none rests on the edge alone. Messages outside the exchange
   recede to muted text. */
.bub { max-width: 76%; align-self: flex-start; padding: var(--s1) var(--s3);
  border: 1px solid var(--line); border-radius: var(--radius); background: var(--line);
  overflow-wrap: anywhere; }
.bub.out { align-self: flex-end; background: var(--paper); }
.bub.dim .body { color: var(--muted); }
.bub.pick { border-color: var(--ink); outline: 1px solid var(--ink); }
.bub.left { border: 1px dashed var(--signal); }
.bub .who2, .bub .att { font-size: var(--t1); line-height: var(--l1); color: var(--muted); }
.bub .t { display: flex; flex-wrap: wrap; justify-content: flex-end; align-items: baseline;
  gap: 0 var(--s2); font-size: var(--t1); line-height: var(--l1); color: var(--muted);
  font-variant-numeric: tabular-nums; }
.bub:not(.out) .t { justify-content: flex-start; }
.divider { align-self: center; padding: var(--s1) 0; font-size: var(--t1);
  line-height: var(--l1); color: var(--muted); text-align: center; }

/* the paired check: a ruled section */
.pair { margin: var(--s5) 0; padding: var(--s4) 0 0; border-top: 1px solid var(--line); }
.pair h4 { margin: var(--s1) 0; }
.pair > h4:not(:first-child) { margin-top: var(--s5); }
.pair > h4 + p.where { margin-bottom: var(--s3); }
.pair-claim { border-top: 1px solid var(--line); padding: var(--s3) 0 var(--s1); }
.pair-claim tr.thr td { font-weight: 600; background: var(--line); }
.pair td.mono { word-break: normal; overflow-wrap: break-word; white-space: nowrap; }
.pg-selection p.letter-link { margin-top: var(--s6); }
@media (max-width: 600px) {
  .bub { max-width: 92%; }
}
"""
