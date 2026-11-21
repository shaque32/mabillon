"""Timeline (/timeline) and Gaps (/gaps).

This page's own CSS, scoped to its markup (see ui/css/__init__.py). Both pages render the
report's own fragments (core/report/timeline.py); the report keeps its look, and only the screen
is styled here, under .pg-timeline and .pg-gaps. App pages do not load the report's stylesheet,
so every rule these fragments need on screen is in this module or in ui/theme.py.

Timeline: the stated times read as one ledger (rows split by hairlines, not a stack of cards),
each row the document's words, the phone records on a quiet rail, and one status.
Gaps: one panel per phone, the day strip on top and its quiet stretches below it.
"""

CSS = """
/* Timeline and Gaps. The page head is the lede, then the explanation and the settings folded
   side by side. Both pages show fragments of the report (core/report/timeline.py). */
.pg-gaps > .caveat { margin: 0 0 var(--s1); font-weight: 600; }
.pg-timeline > .tl-summary { margin: 0 0 var(--s2); color: var(--muted); }
.tl-folds { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--s1) var(--s5);
  margin: var(--s2) 0 0; }
.tl-folds > details, .tl-folds > details.case-settings { margin: 0; }
.tl-folds > details[open] { flex-basis: 100%; }
.tl-folds > details > summary { color: var(--muted); }
.tl-folds > details > summary:hover, .tl-folds > details[open] > summary { color: var(--ink); }
.tl-folds > details.more > p { margin: 0 0 var(--s1); color: var(--muted); }
.tl-folds form.settings { max-width: 720px; }
.pg-timeline h2 .n, .pg-gaps h2 .n { margin-left: var(--s1); font-weight: 400;
  color: var(--muted); font-variant-numeric: tabular-nums; }

/* Timeline: one ruled row per stated time: what the document says, what the phones hold, and
   the result at the right */
.tl { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--ink); }
.tl > li { display: grid; gap: var(--s2) var(--s6); margin: 0; max-width: none;
  padding: var(--s4) 0; border-bottom: 1px solid var(--line);
  grid-template-columns: minmax(0, 5fr) minmax(0, 7fr) 120px; }
.tl > li:target { outline: 0; background: var(--accent-wash); }
.tl .meta { font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.tl .said { margin: var(--s1) 0; font-weight: 600; }
.tl details { margin: 0 0 var(--s1); }
.tl details > summary { font-size: var(--t1); line-height: var(--l1); color: var(--muted); }
.tl details > summary:hover, .tl details[open] > summary { color: var(--ink); }
.tl li > div > details > .q { display: block; max-width: 72ch; padding: 0 0 0 var(--s3);
  border-left: 1px solid var(--muted); }
.tl .recs { display: grid; gap: var(--s1); align-content: start; }
.tl .recs ul { list-style: none; margin: var(--s1) 0 0; padding: 0; }
.tl .recs li { margin: 0 0 var(--s2); padding: 0 0 0 var(--s3); max-width: none;
  font-size: var(--t1); line-height: var(--l1); border-left: 1px solid var(--line); }
.tl .recs li:last-child { margin-bottom: 0; }
.tl .st { display: flex; flex-direction: column; align-items: flex-end; gap: var(--s1); }
.tl .notes { grid-column: 1 / -1; list-style: none; margin: 0; padding: 0;
  font-size: var(--t1); line-height: var(--l1); color: var(--muted); }
.tl .notes li { max-width: none; }
.d-ok { color: var(--support); }
.d-flag { color: var(--signal); font-weight: 600; }

/* Gaps: per phone, the day strip, then its quiet stretches as ruled rows */
.strips { margin: 0 0 var(--s4); padding: var(--s3) 0; overflow-x: auto;
  border-top: 1px solid var(--ink); border-bottom: 1px solid var(--line); }
.strips > div:first-child { margin: 0 0 var(--s2); font-size: var(--t1); line-height: var(--l1);
  color: var(--muted); }
/* The phone's name is the heading just above; screen readers still hear it here. */
.pg-gaps .strips > div:first-child > strong { position: absolute; width: 1px; height: 1px;
  overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
.strip { display: grid; grid-template-columns: 112px minmax(0, 1fr) 72px; gap: var(--s3);
  align-items: end; margin: var(--s1) 0; min-width: 520px; font-size: var(--t1);
  line-height: var(--l1); }
.bars { display: flex; align-items: flex-end; gap: 0; height: 40px; }
.bars span { flex: 1; min-height: 0; background: var(--muted);
  border-left: 1px solid var(--paper); }
.bars span.z { background: transparent; }
.bars span.g { background: var(--line); }
.axis { display: flex; justify-content: space-between; font-size: var(--t1);
  line-height: var(--l1); color: var(--muted); }
.pg-gaps .gap { margin: 0; padding: var(--s4) 0; border-bottom: 1px solid var(--line); }
.pg-gaps .gap .stmt { margin: var(--s1) 0 var(--s2); font-weight: 600; max-width: 84ch; }
.pg-gaps .gap dl { display: grid; grid-template-columns: 104px minmax(0, 1fr);
  gap: var(--s1) var(--s5); margin: 0; }
.pg-gaps .gap dt { color: var(--muted); }
.pg-gaps .gap dd { margin: 0; max-width: 84ch; overflow-wrap: anywhere; }
.pg-gaps .gap dd ul { margin: var(--s1) 0 0; padding-left: var(--s4); font-size: var(--t1);
  line-height: var(--l1); color: var(--muted); }
.pg-gaps .gap dd li { margin: 0; }
/* The page intro states the not-found caveat once; the row keeps its own Searched line. */
.pg-gaps .gap > .meta:last-child { display: none; }
.pg-gaps > details { margin: var(--s2) 0; }
.pg-gaps > details > summary { color: var(--muted); }

@media (max-width: 760px) {
  .tl > li { grid-template-columns: minmax(0, 1fr); }
  .tl .st { order: -1; flex-direction: row; align-items: baseline; gap: var(--s2); }
}
@media (max-width: 600px) {
  .pg-gaps .gap dl { grid-template-columns: minmax(0, 1fr); gap: 0; }
  .pg-gaps .gap dd { margin-bottom: var(--s2); }
}
"""
