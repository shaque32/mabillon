"""Activity (/activity).

This page's own CSS, scoped to its markup (see ui/css/__init__.py). The intro reads at a
comfortable measure, what was seen sits on one line with the CSV download, the report switch is
one row (its state on the left, its button on the right), and the two tables are compact:
numbers right-aligned, times muted and unwrapped, claims never opened quieter than the rest.
On a phone the trail stacks each step into short lines.
"""

CSS = """
/* Activity: what was seen and the download, the report switch, then two ruled tables. */
.pg-activity details.howcounted { margin: var(--s1) 0 var(--s5); }
.pg-activity details.howcounted p { margin: var(--s2) 0 0 var(--s4); color: var(--muted); }
.pg-activity .actbar { display: flex; flex-wrap: wrap; align-items: center;
  justify-content: space-between; gap: var(--s2) var(--s5); margin: 0 0 var(--s3); }
.pg-activity .actbar p { margin: 0; }
.pg-activity .actbar .t { white-space: nowrap; font-variant-numeric: tabular-nums;
  color: var(--muted); }
.pg-activity form.reportswitch { display: flex; flex-wrap: wrap; align-items: center;
  justify-content: space-between; gap: var(--s2) var(--s5); margin: 0; padding: var(--s3) 0;
  border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.pg-activity form.reportswitch p { flex: 1 1 40ch; margin: 0; }
.pg-activity form.reportswitch button { flex: none; }

/* Tables */
.pg-activity th.n { text-align: right; }
.pg-activity .byclaim td:nth-child(2), .pg-activity .byclaim td:nth-child(n+5),
.pg-activity .byclaim td:last-child { text-align: right; }
.pg-activity .byclaim td:first-child { width: 1%; white-space: nowrap; font-weight: 600; }
.pg-activity .byclaim tr.unopened td { color: var(--muted); }
.pg-activity .trail td:first-child, .pg-activity .trail th:first-child { width: 1%;
  text-align: right; white-space: nowrap; color: var(--muted); }
.pg-activity .trail td.when { width: 1%; }
.pg-activity .trail td:nth-child(4) { white-space: nowrap; font-weight: 600; }
.pg-activity .trail td:last-child { width: 18ch; text-align: right; color: var(--muted); }
.pg-activity .trail td .mono { display: inline; }
.pg-activity .trailbar { display: flex; flex-wrap: wrap; align-items: baseline;
  gap: var(--s1) var(--s4); margin: 0 0 var(--s3); }

@media (max-width: 600px) {
  .pg-activity .byclaim td, .pg-activity .byclaim th { white-space: nowrap;
    overflow-wrap: normal; }
  .pg-activity table.trail { display: block; overflow: visible; }
  .pg-activity .trail thead { position: absolute; width: 1px; height: 1px; overflow: hidden;
    clip-path: inset(50%); white-space: nowrap; }
  .pg-activity .trail tbody { display: block; }
  .pg-activity .trail tr { display: grid; grid-template-columns: auto minmax(0, 1fr) auto;
    column-gap: var(--s3); padding: var(--s2) 0; border-bottom: 1px solid var(--line); }
  .pg-activity .trail td, .pg-activity .trail td:nth-child(n) { display: block; width: auto;
    padding: 0; border: 0; text-align: left; }
  .pg-activity .trail td:nth-child(1) { grid-area: 1 / 1; }
  .pg-activity .trail td.when { grid-area: 1 / 2; }
  .pg-activity .trail td:nth-child(6) { grid-area: 1 / 3; text-align: right; }
  .pg-activity .trail td:nth-child(4) { grid-area: 2 / 1 / 3 / 4; white-space: normal; }
  .pg-activity .trail td:nth-child(3) { grid-area: 3 / 1 / 4 / 4; color: var(--muted); }
  .pg-activity .trail td:nth-child(5) { grid-area: 4 / 1 / 5 / 4; }
  .pg-activity .trail td:nth-child(5):empty { display: none; }
}
"""
