"""Audit log (/log).

This page's own CSS, scoped to its markup (see ui/css/__init__.py). A long technical table made
scannable: the chain status as one line with a dot, the flags tool as one quiet panel, the
filters as a row of segmented links, then the entries with the sequence number, time and action
on one line each and the payload folded to a short monospace preview. On a phone each entry
stacks into a few short lines instead of squeezing five columns.
"""

CSS = """
/* The audit log: the chain's state, the flags tool, then the entries as a ruled table. */
.pg-log p.chain.ok { display: flex; align-items: baseline; gap: var(--s2);
  margin: var(--s1) 0 0; font-weight: 600; }
.pg-log p.chain.ok::before { content: ""; flex: none; width: var(--dot); height: var(--dot);
  border-radius: 50%; background: var(--ink); }
.pg-log .flash.chain { margin: var(--s1) 0 var(--s2); }
.pg-log p.chainmeta { margin: 0 0 0 var(--s4); max-width: none; font-size: var(--t1);
  line-height: var(--l1); color: var(--muted); }

/* The flags tool: count and how to flag, then the download on one line with its note */
.pg-log .logflags > p { margin: 0 0 var(--s3); color: var(--muted); }
.pg-log .logflags > p strong { color: var(--ink); }
.pg-log form.flagform { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s2); }
.pg-log form.flagform input[type=text] { width: 260px; min-width: 0; }
.pg-log form.flagform p.muted { flex-basis: 100%; margin: 0; font-size: var(--t1);
  line-height: var(--l1); }

/* Filters: plain links; the current choice is bold and not a link */
.pg-log .logbar { display: flex; flex-wrap: wrap; align-items: baseline;
  gap: var(--s2) var(--s5); margin: 0 0 var(--s2); }
.pg-log .seg { display: inline-flex; align-items: baseline; gap: var(--s3); }
.pg-log .seg .seglabel { color: var(--muted); }
.pg-log .seg .on { font-weight: 600; }
.pg-log .logbar > .muted { font-size: var(--t1); line-height: var(--l1); }

/* Entries: number, time and action never wrap; ids and payloads are the only monospace */
.pg-log .logtable th:first-child, .pg-log .logtable td:first-child { width: 1%;
  text-align: right; white-space: nowrap; color: var(--muted); }
.pg-log .logtable td.when { width: 1%; }
.pg-log .logtable td:nth-child(3) { width: 22%; }
.pg-log .logtable .kind { color: var(--muted); }
.pg-log .logtable td:nth-child(4) { width: 1%; white-space: nowrap; font-weight: 600; }
.pg-log .logtable td.payload > .mono { display: block; }
.pg-log .logtable td.payload details { margin: var(--s1) 0 0; }
.pg-log .logtable td.payload summary { font-size: var(--t1); line-height: var(--l1);
  color: var(--muted); }
.pg-log .logtable td.payload details .mono { display: block; margin: var(--s1) 0;
  padding: 0 0 0 var(--s3); border-left: 1px solid var(--muted); }

@media (max-width: 600px) {
  .pg-log p.chainmeta { margin-left: 0; }
  .pg-log form.flagform input[type=text] { width: 100%; }
  .pg-log table.logtable { display: block; overflow: visible; }
  .pg-log .logtable thead { position: absolute; width: 1px; height: 1px; overflow: hidden;
    clip-path: inset(50%); white-space: nowrap; }
  .pg-log .logtable tbody { display: block; }
  .pg-log .logtable tr { display: grid; grid-template-columns: auto minmax(0, 1fr);
    column-gap: var(--s3); padding: var(--s2) 0; border-bottom: 1px solid var(--line); }
  .pg-log .logtable td, .pg-log .logtable td:nth-child(n) { display: block; width: auto;
    padding: 0; border: 0; text-align: left; }
  .pg-log .logtable td:nth-child(1) { grid-area: 1 / 1; }
  .pg-log .logtable td.when { grid-area: 1 / 2; }
  .pg-log .logtable td:nth-child(4) { grid-area: 2 / 1 / 3 / 3; white-space: normal; }
  .pg-log .logtable td:nth-child(3) { grid-area: 3 / 1 / 4 / 3; color: var(--muted); }
  .pg-log .logtable td.payload { grid-area: 4 / 1 / 5 / 3; margin-top: var(--s1); }
}
"""
