"""Case overview (/).

This page's own CSS, scoped to its markup (see ui/css/__init__.py): the notices (.ov-notices),
then the page body (.pg-overview). One column, as wide as the status strip, so the notices, the
status, the set-up rows and the record line up on one left and one right edge. The status strip
is the only box; the set-up and the record are hairline rows, like the site's .facts and .rows,
and the record is smaller and muted, so the run ids, versions and hashes stay present but quiet.
"""

CSS = """
/* The case page: its name, what waits on you, then the set-up and the record as ruled rows.
   The notices above are the shared one-line notices (ui/theme.py). */
.ov-notices, main:has(> .pg-overview) > .banner { max-width: 880px; }
.ov-notices { margin: 0 0 var(--s4); }
.ov-notices .banner details > p { margin-left: var(--s4); }
.pg-overview { max-width: 880px; }

/* what waits on you: the page's one solid button, then the counts in a row */
.pg-overview .casestatus { display: flex; flex-wrap: wrap; align-items: center;
  gap: var(--s3) var(--s6); margin: 0 0 var(--s5); }
.pg-overview .casestatus .findings { display: flex; flex-wrap: wrap; gap: var(--s2) var(--s5);
  list-style: none; padding: 0; margin: 0; }
.pg-overview .casestatus .findings li { margin: 0; }
.pg-overview .casestatus .findings a { display: inline-flex; align-items: center;
  gap: var(--s2); text-decoration: none; }
.pg-overview .casestatus .findings .name { display: inline-flex; align-items: center;
  gap: var(--s2); color: var(--muted); }
.pg-overview .casestatus .findings a:hover .name { color: var(--ink); }
.pg-overview .casestatus .findings .name::before { content: ""; width: var(--dot);
  height: var(--dot); border-radius: 50%; border: 2px solid var(--muted); }
.pg-overview .casestatus .findings .t-con::before { background: var(--signal);
  border-color: var(--signal); }
.pg-overview .casestatus .findings .t-sup::before { background: var(--ink);
  border-color: var(--ink); }
.pg-overview .casestatus .findings b { font-variant-numeric: tabular-nums; }
.pg-overview .casestatus .verdict { margin: 0; }
.pg-overview #withheld { margin: 0 0 var(--s4); }
.pg-overview #withheld ul { margin: var(--s1) 0 0; }

/* case setup and the record: hairline rows with the label on the left */
.pg-overview ul.setuplist li { display: grid; grid-template-columns: 240px minmax(0, 1fr);
  gap: 0 var(--s5); align-items: baseline; }
.pg-overview .ov-dev { min-width: 0; }
.pg-overview .ov-dev:not(:has(b)) { font-weight: 600; }
.pg-overview .ov-dev .src { display: block; font-size: var(--t1); line-height: var(--l1);
  color: var(--muted); font-weight: 400; }
.pg-overview .ov-who { min-width: 0; }
.pg-overview .ov-none { color: var(--muted); }
.pg-overview .ov-head { display: flex; align-items: baseline; justify-content: space-between;
  margin: var(--s7) 0 var(--s3); }
.pg-overview .ov-head h2 { margin: 0; }
.pg-overview dl.record { grid-template-columns: calc(240px + var(--s5)) minmax(0, 1fr); gap: 0;
  margin: 0; border-top: 1px solid var(--line); }
.pg-overview dl.record dt, .pg-overview dl.record dd { padding: var(--s2) 0; max-width: none;
  border-bottom: 1px solid var(--line); }

/* the folds under the record: chain of custody and the reviewer */
.pg-overview details.custody { margin: 0; padding: var(--s2) 0;
  border-bottom: 1px solid var(--line); }
.pg-overview details.custody[open] { overflow-x: auto; }
.pg-overview details.custody h2 { font: 600 var(--t2)/var(--l2) var(--sans);
  margin: var(--s4) 0 var(--s1); }
.pg-overview details.custody table { margin: 0 0 var(--s2); font-size: var(--t1);
  line-height: var(--l1); }
.pg-overview details.custody td { overflow-wrap: normal; }
.pg-overview details.custody td:nth-child(2), .pg-overview details.custody td:nth-child(3),
.pg-overview details.custody td:nth-child(4), .pg-overview details.custody td:nth-child(7) {
  white-space: nowrap; }
.pg-overview details.custody td.mono { min-width: 16ch; overflow-wrap: anywhere; }
.pg-overview details.custody form.box { display: flex; flex-wrap: wrap; gap: var(--s2);
  align-items: center; margin: var(--s2) 0 var(--s1); }
.pg-overview details.custody form.box input[type=text] { max-width: 280px; }

@media (max-width: 640px) {
  .pg-overview ul.setuplist li { grid-template-columns: minmax(0, 1fr); }
  .pg-overview dl.record { grid-template-columns: minmax(0, 1fr); }
  .pg-overview dl.record dt { border-bottom: 0; padding-bottom: 0; }
  .pg-overview dl.record dd { margin: 0; padding-top: 0; }
}
"""
