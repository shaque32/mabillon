"""Exhibits (/exhibits, /exhibit, /exhibit/match, /request-letter).

This page's own CSS, scoped to its markup (see ui/css/__init__.py). Every value comes from the
tokens in ui/theme.py. The exhibit and match pages show fragments of the report
(core/report/restore.py); the app styles them here, and the exported report keeps its own look.
"""


def context_table_css(scope: str) -> str:
    """The conversation table (core/report/restore.py context_table) under one page wrapper.

    Words break only at spaces, never mid-word; direction and tier never wrap; the columns the
    expert reads second (as printed, direction, tier, source) are small and muted. Columns:
    UTC, phone's local time, as printed, sender, direction, message, tier, source."""
    t = f"{scope} table.ctx"
    return f"""
{t} td {{ overflow-wrap: break-word; word-break: normal; }}
{t} td:nth-child(3), {t} td:nth-child(5), {t} td:nth-child(7) {{ color: var(--muted);
  font-size: var(--t1); line-height: var(--l1); }}
{t} td:nth-child(5), {t} td:nth-child(7) {{ white-space: nowrap; }}
{t} td:nth-child(6) {{ min-width: 26ch; }}
{t} td.mono {{ word-break: normal; overflow-wrap: break-word; }}
{t} tr.target td {{ font-weight: 400; }}
{t} tr.target td:nth-child(6) {{ font-weight: 600; }}
{scope} details.related {{ margin: var(--s5) 0 var(--s2); }}
"""


CSS = """
/* fragments of the report shown in the app: a highlighted span, a quoted piece, a pasted text */
.piece { font: 400 var(--t1)/var(--l1) var(--mono); background: var(--line);
  padding: 0 var(--s1); border-radius: var(--radius); white-space: pre-wrap; }
.nf { font-weight: 600; }
pre.letter, pre.exhibit-text { white-space: pre-wrap; overflow-wrap: anywhere;
  font: 400 var(--t1)/var(--l1) var(--mono); margin: var(--s3) 0 0; padding: var(--s4);
  border: 1px solid var(--line); border-radius: var(--radius); }

/* the group's shared bits: a quiet back link */
.pg-exhibit p.back, .pg-match p.back, .pg-context p.back { margin: 0 0 var(--s3);
  font-size: var(--t1); line-height: var(--l1); }
.pg-exhibit p.back a, .pg-match p.back a, .pg-context p.back a { color: var(--muted); }

/* Exhibits: the list, then one form with one main action */
.pg-exhibits table.exhibits td.n { white-space: nowrap; }
.pg-exhibits table.exhibits td.meta { color: var(--muted); font-size: var(--t1);
  line-height: var(--l1); }
.pg-exhibits form.box { max-width: 760px; }
.pg-exhibits form.box .fields { display: grid; gap: 0 var(--s4);
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.5fr); }
.pg-exhibits form.box .fields label { display: grid; margin: 0 0 var(--s3); }
.pg-exhibits form.box .fields input, .pg-exhibits form.box .fields select { width: 100%;
  min-width: 0; }
.pg-exhibits form.box .hint { font-weight: 400; color: var(--muted); }
.pg-exhibits fieldset.msgsplit label { display: flex; margin: 0 0 var(--s1); }
.pg-exhibits form.box fieldset.msgsplit .muted { font-size: var(--t1); line-height: var(--l1); }
@media (max-width: 640px) {
  .pg-exhibits form.box .fields { grid-template-columns: minmax(0, 1fr); }
}

/* One exhibit: the name is the page heading; each quoted message is a ruled section */
.pg-exhibit h1 { margin-bottom: var(--s1); }
.pg-exhibit .exhibit > h3 { display: none; }
.pg-exhibit .exhibit > p.muted { max-width: none; font-size: var(--t1);
  line-height: var(--l1); }
.pg-exhibit .exhibit > p:nth-of-type(2) { font-weight: 600; margin: var(--s3) 0 0; }
.pg-exhibit .exhibit > h4 { margin: var(--s6) 0 var(--s2); padding-top: var(--s5);
  border-top: 1px solid var(--line); }
.pg-exhibit .exhibit > blockquote { margin: 0 0 var(--s3); }
.pg-exhibit .item { border-top: 0; padding: 0 0 0 var(--s4); margin: var(--s2) 0; }
.pg-exhibit .item > p:first-child { max-width: none; margin: 0 0 var(--s2);
  font-size: var(--t1); line-height: var(--l1); color: var(--muted); }
.pg-exhibit .item > p:first-child .mono { overflow-wrap: anywhere; }
.pg-exhibit .item blockquote { margin: 0 0 var(--s2); }
.pg-exhibit .item ul { margin: 0; color: var(--muted); }
.pg-exhibit details.pasted { margin: var(--s6) 0 0; padding-top: var(--s5);
  border-top: 1px solid var(--line); }
.pg-exhibit .actions { display: flex; flex-wrap: wrap; align-items: center;
  gap: var(--s3) var(--s6); margin: var(--s5) 0 0; }
.pg-exhibit form.act { display: flex; flex-wrap: wrap; align-items: center;
  gap: var(--s1) var(--s3); font-size: var(--t1); line-height: var(--l1); color: var(--muted); }

/* A match in context: what the exhibit prints, how it matched, then the conversation */
.pg-match p.prints { margin: var(--s4) 0 var(--s1); }
.pg-match > blockquote { margin: 0 0 var(--s3); }
.pg-match ul.notes { margin: 0 0 var(--s3); color: var(--muted); }
.pg-match p.tiers, .pg-context p.tiers { margin: 0 0 var(--s5); font-size: var(--t1);
  line-height: var(--l1); }
.pg-match > p:not([class]) { color: var(--muted); }

/* The request letter: one sheet at a letter's measure, the download beside the heading */
.pg-letter .letter-head { display: flex; flex-wrap: wrap; align-items: flex-end;
  justify-content: space-between; gap: var(--s3) var(--s6); max-width: 840px; }
.pg-letter .letter-head > div { flex: 1 1 420px; }
.pg-letter .letter-head p { margin: 0; }
.pg-letter a.button { flex: none; }
.pg-letter pre.letter { max-width: 840px; margin: var(--s5) 0 0; padding: var(--s6);
  color: var(--ink); }
@media (max-width: 600px) {
  .pg-letter pre.letter { padding: var(--s4); }
  .pg-exhibits table.exhibits, .pg-exhibits table.exhibits tbody { display: block;
    overflow: visible; }
  .pg-exhibits table.exhibits thead { position: absolute; width: 1px; height: 1px;
    overflow: hidden; clip-path: inset(50%); }
  .pg-exhibits table.exhibits tbody tr { display: grid; gap: var(--s1) var(--s4);
    grid-template-columns: minmax(0, 1fr) auto; padding: var(--s3) 0;
    border-bottom: 1px solid var(--line); }
  .pg-exhibits table.exhibits tbody td { display: block; padding: 0; border: 0; }
  .pg-exhibits table.exhibits tbody td.meta { grid-column: 1 / -1; }
  .pg-exhibits form.box .fields { grid-template-columns: minmax(0, 1fr); }
}
""" + context_table_css(".pg-match")
