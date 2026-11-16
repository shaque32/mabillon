"""Help (/help).

This page's own CSS, scoped to its markup (see ui/css/__init__.py).

Three sections divided by a hairline, prose kept under ~70 characters a line. The bug report's
full text is folded under "Exactly what the file holds": every byte stays on the page.
"""

CSS = """
/* Help: four ruled sections at a reading width. */
.pg-help { max-width: 760px; }
.pg-help section.hs { padding: var(--s5) 0 var(--s1); border-top: 1px solid var(--line); }
.pg-help h1 + section.hs { border-top: 0; padding-top: 0; }
.pg-help section.hs h2 { margin: 0 0 var(--s2); }
.pg-help section.hs li::marker { color: var(--muted); }
.pg-help section.words dl { display: grid; gap: var(--s1) var(--s5); margin: 0 0 var(--s3);
  grid-template-columns: minmax(0, 14rem) minmax(0, 1fr); }
.pg-help section.words dt { font-weight: 600; }
.pg-help section.words dd { margin: 0; color: var(--muted); }

/* the three steps of sending a bug report, numbered because the order matters */
.pg-help ol.howto { list-style: none; counter-reset: step; margin: var(--s4) 0 var(--s2);
  padding: 0; display: grid; gap: var(--s2); }
.pg-help ol.howto li { counter-increment: step; display: flex; align-items: center;
  flex-wrap: wrap; gap: var(--s1) var(--s2); margin: 0; min-height: var(--control); }
.pg-help ol.howto li::before { content: counter(step) "."; width: var(--s4);
  color: var(--muted); font-variant-numeric: tabular-nums; }

/* the report's text, folded */
.pg-help details.filetext { margin: var(--s2) 0 var(--s4); }
.pg-help pre.bugreport { margin: 0; max-height: 480px; overflow: auto; padding: var(--s3);
  font: 400 var(--t1)/var(--l1) var(--mono); border: 1px solid var(--line);
  border-radius: var(--radius); scrollbar-width: thin; }

/* what it does and does not, side by side when there is room */
.pg-help .dodont { display: grid; gap: 0 var(--s6);
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
.pg-help .dodont h3 { margin-top: var(--s3); }
.pg-help section.about p.muted { font-size: var(--t1); line-height: var(--l1); }

@media (max-width: 600px) {
  .pg-help section.words dl { grid-template-columns: minmax(0, 1fr); gap: 0; }
  .pg-help section.words dd { margin: 0 0 var(--s2); }
  .pg-help pre.bugreport { max-height: 360px; }
}
"""
