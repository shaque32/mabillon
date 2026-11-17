"""Identities (/identities).

This page's own CSS, scoped to its markup (see ui/css/__init__.py). Every rule sits under
.pg-ids, the page's wrapper, so nothing here reaches another page (the claim page's
<aside class='side'> in particular). ui/theme.py holds only the shared controls and status
words; the page itself is here: one status bar, a person header with the name first, links
split by hairlines with their records for and against, and one decision line per link.
"""

CSS = """
/* Identities: the counts and the one page-wide action, names with no person yet, then each
   person and each link with its records for and against. */
.pg-ids > details.more { margin: 0 0 var(--s5); }
.pg-ids > details.more p { margin: var(--s2) 0 0; color: var(--muted); }
.pg-ids .idbar { display: flex; flex-wrap: wrap; align-items: center;
  justify-content: space-between; gap: var(--s3) var(--s5); padding: var(--s2) 0;
  border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.pg-ids .idbar .counts > .muted { margin-right: var(--s3); }
.pg-ids .idbar form.look { display: flex; align-items: center; flex-wrap: wrap;
  gap: var(--s2) var(--s3); margin: 0; }
.pg-ids .idbar form.look .muted { font-size: var(--t1); line-height: var(--l1); }
.pg-ids > .banner { margin: var(--s4) 0 0; }

/* Names with no person yet: name left, its actions on one line at the right */
.pg-ids ul.unplaced .head { align-items: center; }
.pg-ids ul.unplaced .head .text { font-weight: 600; }
.pg-ids ul.unplaced .acts { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s2); }
.pg-ids ul.unplaced .acts form.inline { display: inline-flex; align-items: center;
  gap: var(--s2); }
.pg-ids ul.unplaced .acts button { margin: 0; }
.pg-ids ul.unplaced .needs { margin-top: var(--s1); }
.pg-ids ul.unplaced li:hover { background: transparent; }

/* Add a person: field and button on one line under the names it belongs to */
.pg-ids form.addp, .pg-ids form.aliasf { display: grid; align-items: end;
  gap: var(--s1) var(--s2); margin: var(--s4) 0 0;
  grid-template-columns: minmax(0, 380px) auto minmax(0, 1fr); }
.pg-ids form.addp label, .pg-ids form.aliasf label { margin: 0; }
.pg-ids form.addp input[type=text], .pg-ids form.aliasf input[type=text] { width: 100%;
  min-width: 0; }
.pg-ids form.addp p.muted, .pg-ids form.aliasf .hint { grid-column: 1 / -1; margin: 0;
  font-size: var(--t1); line-height: var(--l1); }

/* A person: the name first, what they are in muted text under it, removal at the right */
.pg-ids section.person { margin: var(--s7) 0 0; }
.pg-ids .phead { display: flex; flex-wrap: wrap; align-items: flex-start;
  justify-content: space-between; gap: var(--s2) var(--s4); }
.pg-ids h2.pname { margin: 0; }
.pg-ids .pkind { margin: 0; color: var(--muted); }
.pg-ids .pclaims { margin: var(--s3) 0; max-width: 78ch; }
.pg-ids .pnote { margin: var(--s3) 0 0; }

/* An absence: one sentence, with what was searched one click under it */
.pg-ids details.absent { margin: var(--s4) 0 0; }
.pg-ids details.absent p { margin: var(--s2) 0 0 var(--s4); color: var(--muted); }
.pg-ids section.person .banner { margin: var(--s4) 0 0; }

/* A link: the pair and its two labels on one row, one muted meta line, the basis */
.pg-ids article.idlink { margin: var(--s4) 0 0; padding: var(--s4) 0 0;
  border-top: 1px solid var(--line); }
.pg-ids .idhead { display: flex; justify-content: space-between; align-items: baseline;
  gap: var(--s3); }
.pg-ids .idpair { margin: 0; font: 600 var(--t3)/var(--l3) var(--sans); }
.pg-ids .idpair .arrow { color: var(--muted); font-weight: 400; margin: 0 var(--s1); }
.pg-ids .idtags { display: inline-flex; flex: none; align-items: baseline; }
.pg-ids .idmeta { margin: 0 0 var(--s2); font-size: var(--t1); line-height: var(--l1);
  color: var(--muted); }
.pg-ids .idbasis { margin: 0; max-width: 80ch; }
.pg-ids article.idlink .caution { margin: var(--s3) 0 0; }
.pg-ids article.idlink .in > p.muted:last-child { margin: var(--s2) 0 0; font-size: var(--t1);
  line-height: var(--l1); }
.pg-ids article.idlink.st-rejected .idpair { color: var(--muted); }

/* Records for and against, side by side: the quote, one note line, the source */
.pg-ids .idgrid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 0 var(--s6); margin-top: var(--s3); }
.pg-ids .idgrid .side { margin: 0 0 var(--s1); font: 600 var(--t1)/var(--l1) var(--sans); }
.pg-ids .idgrid .side.against { color: var(--signal); }
.pg-ids .idgrid .side .n { color: var(--muted); font-weight: 400;
  font-variant-numeric: tabular-nums; }
.pg-ids ul.sig { list-style: none; padding: 0; margin: 0; }
.pg-ids ul.sig li { margin: 0; padding: var(--s2) 0; border-top: 1px solid var(--line); }
.pg-ids ul.sig .quote { font-weight: 600; }
.pg-ids ul.sig .ref { margin-top: var(--s1); font-size: var(--t1); line-height: var(--l1);
  color: var(--muted); overflow-wrap: anywhere; }
.pg-ids details.sigmore { margin: 0; border-top: 1px solid var(--line); padding-top: var(--s2); }
.pg-ids .idgrid > div > p.muted { margin: var(--s1) 0 0; }
/* A decided link folds its records; the summary says how many on each side */
.pg-ids details.idrec { margin: var(--s3) 0 0; }
.pg-ids article.idlink > .in:not(:first-child) { margin-top: var(--s3); }

/* The decision: the reason and the three choices on one line */
.pg-ids form.decide { display: flex; flex-wrap: wrap; align-items: flex-end;
  gap: var(--s2) var(--s3); margin: 0; }
.pg-ids form.decide label { flex: 1 1 320px; margin: 0; }
.pg-ids form.decide .choices { display: inline-flex; flex-wrap: wrap; gap: var(--s2); }
.pg-ids form.decide .choices button { margin: 0; }

/* Link an account yourself: selects shrink to the column instead of widening the page */
.pg-ids form.linkself .pick { display: flex; flex-wrap: wrap; gap: var(--s3) var(--s4);
  max-width: none; }
.pg-ids form.linkself .pick label { margin: 0; min-width: 0; max-width: 100%;
  grid-template-columns: minmax(0, 1fr); }
.pg-ids form.linkself .pick label:first-child { flex: 0 1 420px; }
.pg-ids form.linkself .pick label:last-child { flex: 0 1 220px; }
.pg-ids form.linkself input.wide { max-width: 664px; }
.pg-ids form.linkself select { width: 100%; }
.pg-ids form.linkself .go { display: flex; flex-wrap: wrap; align-items: center;
  gap: var(--s2) var(--s4); margin: 0; max-width: none; }
.pg-ids form.linkself .go .muted { font-size: var(--t1); line-height: var(--l1); }

@media (max-width: 600px) {
  .pg-ids .idhead { flex-wrap: wrap; }
  .pg-ids .idgrid { grid-template-columns: minmax(0, 1fr); gap: var(--s4) 0; }
  .pg-ids form.addp, .pg-ids form.aliasf { grid-template-columns: minmax(0, 1fr) auto; }
  .pg-ids form.decide label { flex-basis: 100%; }
}
"""
