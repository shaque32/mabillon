"""Cases (/cases), the enter-your-name form and the error page.

This page's own CSS, scoped to its markup (see ui/css/__init__.py). Every value comes from the
tokens in ui/theme.py.

The cases page is the first screen after install: a ruled list of cases (still a <table>, which
packaging/smoke_ui.py selects on), the cases folder as one muted line, then the form to make a
case, whose "Make the case" is the page's one solid button. The two passphrase fields recede
when "Encrypt this case" is unchecked (CSS :has(), no script; the server still checks them).
"""

CSS = """
/* Cases: each row is the case name, one small line of facts and its action at the right. Still
   a <table>; the header row stays for screen readers and is hidden on screen. */
.pg-cases, main:has(> .pg-cases) > .banner { max-width: 880px; }
.pg-cases table.caselist, .pg-cases .caselist tbody { display: block; }
.pg-cases table.caselist { margin: 0 0 var(--s3); border-top: 1px solid var(--line); }
.pg-cases .caselist thead { position: absolute; width: 1px; height: 1px; overflow: hidden;
  clip-path: inset(50%); }
.pg-cases .caselist tbody tr { display: grid; align-items: center; gap: var(--s1) var(--s4);
  grid-template-columns: auto auto minmax(0, 1fr) auto; padding: var(--s3) 0;
  border-bottom: 1px solid var(--line); }
.pg-cases .caselist td { display: block; padding: 0; border: 0; overflow-wrap: normal; }
.pg-cases .caselist td.name { grid-column: 1 / 4; font: 600 var(--t3)/var(--l3) var(--sans); }
.pg-cases .caselist td.name .mono { display: block; overflow-wrap: anywhere; }
.pg-cases .caselist td.state, .pg-cases .caselist td.lock { grid-row: 2; font-size: var(--t1);
  line-height: var(--l1); color: var(--muted); }
.pg-cases .caselist td.state { grid-column: 1; }
.pg-cases .caselist td.lock { grid-column: 2; white-space: nowrap; }
.pg-cases .caselist td.go { grid-column: 4; grid-row: 1 / span 2; white-space: nowrap; }
.pg-cases .unlock { display: inline-flex; align-items: center; gap: var(--s2); }
.pg-cases .unlock input[type=password] { min-width: 0; width: 220px; }
.pg-cases p.empty { margin: 0 0 var(--s3); padding: var(--s3) 0; color: var(--muted);
  border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.pg-cases p.where { margin: 0; max-width: none; font-size: var(--t1); line-height: var(--l1);
  color: var(--muted); }

/* Making a new case */
.pg-cases section.newcase label:has(> input.wide) { max-width: 520px; }
.pg-cases section.newcase p { margin: 0 0 var(--s4); }
.pg-cases section.newcase label:has(> input[type=checkbox]) { margin: 0; }
.pg-cases .pass { margin: 0 0 var(--s5); padding-left: var(--s5); }
.pg-cases .pass .passfields { display: flex; flex-wrap: wrap; gap: var(--s2);
  margin-bottom: var(--s2); }
.pg-cases .pass .passfields input { flex: 1 1 200px; max-width: 256px; min-width: 0; }
.pg-cases .pass p.muted { margin: 0; font-size: var(--t1); line-height: var(--l1); }
/* Receding, never hidden: a hidden field keeps its minlength check and would block the submit */
.pg-cases form.box:has(input[name=encrypt]:not(:checked)) .pass input { border-color: var(--line); }

/* The enter-your-name form, here, on the case page and on the set-up page: one line */
form.nameform { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s2) var(--s4);
  margin: 0 0 var(--s5); }
form.nameform p { margin: 0; color: var(--muted); }
form.nameform p strong { color: var(--ink); }
form.nameform .row { display: flex; flex: 1 1 320px; align-items: center; gap: var(--s2); }
form.nameform .row input { flex: 0 1 280px; min-width: 0; }
form.nameform .row button { margin: 0; }

/* The error page: what went wrong, and one way back */
.pg-error { max-width: 560px; padding-top: var(--s7); }
.pg-error h1 { font: 400 var(--t1)/var(--l1) var(--sans); color: var(--muted);
  margin: 0 0 var(--s2); font-variant-numeric: tabular-nums; }
.pg-error p.lede { font: 600 var(--t4)/var(--l4) var(--sans); color: var(--ink);
  margin: 0 0 var(--s5); }
.pg-error p.lede::first-letter { text-transform: uppercase; }
.pg-error .actions { display: flex; flex-wrap: wrap; align-items: center;
  gap: var(--s2) var(--s5); margin: 0; }

@media (max-width: 600px) {
  .pg-cases .caselist tbody tr { grid-template-columns: minmax(0, 1fr) auto; }
  .pg-cases .caselist td.name { grid-column: 1 / -1; }
  .pg-cases .caselist td.state { grid-column: 1; grid-row: 2; }
  .pg-cases .caselist td.lock { grid-column: 1; grid-row: 3; }
  .pg-cases .caselist td.go { grid-column: 2; grid-row: 2 / span 2; }
  .pg-cases .caselist tr:has(.unlock) td.go { grid-column: 1 / -1; grid-row: 4;
    margin-top: var(--s2); }
  .pg-cases .unlock { display: flex; width: 100%; }
  .pg-cases .unlock input[type=password] { flex: 1; width: auto; }
  .pg-cases .pass { padding-left: 0; }
  .pg-cases .pass .passfields input { max-width: none; }
  .pg-error { padding-top: var(--s5); }
}
"""
