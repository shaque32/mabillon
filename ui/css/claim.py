"""One claim (/claim) and one evidence item (/evidence).

This page's own CSS, scoped to its markup (see ui/css/__init__.py): `.pg-claim` wraps the claim
page's split (ledger and main column), `.pg-evidence` the evidence item page.

The claim reads like the site's walk panel (site/index.html `.walk`): the claim, its rows of
facts each with one tag and one small detail line, and one status. Forms sit flat inside their
card (no box in a box), with the reason field and its buttons on one line. Settled evidence,
the rules' working, the other explanations and the secondary forms fold; every word stays.
"""

CSS = """
/* ---- one claim: the ledger beside a readable main column. The order is the reading order:
   the claim, its verdict in the same large size, why, then what has to be true, then the
   evidence. Nothing is framed; hairlines part the sections. */
.split { display: grid; grid-template-columns: 272px minmax(0, 1fr); gap: var(--s7);
  align-items: start; }
aside.side { position: sticky; top: var(--s5); max-height: calc(100vh - var(--s7));
  overflow-y: auto; scrollbar-width: thin; }
aside.side .ledger .row { padding: var(--s2); }
aside.side .ledger .text { font-size: var(--t1); line-height: var(--l1); color: var(--muted);
  margin-top: var(--s1); display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow: hidden; }
aside.side .ledger .verdict { font-weight: 400; }
aside.side .ledger li.on { background: var(--accent-wash); }
aside.side .ledger li.on .text { color: var(--ink); }
.pg-claim .claim-main { min-width: 0; max-width: 820px; }
.pg-claim .claim-head { display: flex; justify-content: space-between; align-items: baseline;
  gap: var(--s3); flex-wrap: wrap; }
.pg-claim .claim-head h1 { font: 600 var(--t1)/var(--l1) var(--sans); margin: 0; }
.pg-claim .claim-head h1 .muted { font-weight: 400; }
blockquote.claimtext { font: 400 var(--t4)/var(--l4) var(--sans); border: 0; padding: 0;
  margin: var(--s2) 0 var(--s4); max-width: 60ch; text-wrap: pretty; }

/* the verdict: the page's answer, as large as the claim it answers, on a plate. The plate
   follows the mark: filled with its finding's wash where the mark is solid (support the expert
   confirmed, contradicted), an outline in the finding's color where the mark is a ring, and a
   hairline for unproven and for support that rests on the AI reviewer. */
.pg-claim #verdict { margin: 0 0 var(--s5); }
.pg-claim .vhead { margin: 0 0 var(--s3); }
.pg-claim .vhead h2 { position: absolute; width: 1px; height: 1px; overflow: hidden;
  clip-path: inset(50%); white-space: nowrap; margin: 0; }
.pg-claim #verdict .vhead .verdict { font: 600 var(--t4)/var(--l4) var(--sans);
  gap: var(--s3); white-space: normal; padding: var(--s2) var(--s4);
  border: 1px solid var(--line); border-radius: var(--radius); }
.pg-claim #verdict .vhead .v-sup { background: var(--support-wash);
  border-color: var(--support-wash); }
.pg-claim #verdict .vhead .v-con { background: var(--signal-wash);
  border-color: var(--signal-wash); }
.pg-claim #verdict .vhead .v-supchk, .pg-claim #verdict .vhead .v-supcou {
  border-color: var(--support); }
.pg-claim #verdict .vhead .v-confirm { border-color: var(--signal); }
.pg-claim #verdict .vhead .v-await { border-color: var(--accent); }
.pg-claim #verdict .vhead .verdict::before { width: var(--s3); height: var(--s3); }
.pg-claim ul.needs { list-style: none; margin: 0 0 var(--s3); padding: 0; }
.pg-claim ul.needs li { margin: 0 0 var(--s1); }
.pg-claim #verdict .gap, .pg-claim #verdict .gap-detail { margin: var(--s2) 0;
  font-size: var(--t1); line-height: var(--l1); color: var(--muted); overflow-wrap: anywhere; }
.pg-claim #verdict .gap b { color: var(--ink); margin-right: var(--s2); }
.pg-claim ul.cited { margin: var(--s1) 0 var(--s4); }
.pg-claim #verdict details.fmt p.format-notice { margin-left: var(--s4); }
.pg-claim #verdict details.fmt > summary strong { font-weight: 400; }
.pg-claim #verdict ul.why-lines { margin: var(--s2) 0 0; }
.pg-claim #verdict details.why-tech { margin: var(--s2) 0 0 var(--s4); }
.pg-claim #verdict details.why-tech > summary, .pg-claim #verdict details.why-tech ul,
.pg-claim #verdict details.why-tech p { font-size: var(--t1); line-height: var(--l1);
  color: var(--muted); overflow-wrap: break-word; }
.pg-claim p.signoff { margin: var(--s3) 0 0; }
.pg-claim #verdict > .in.vacts { display: flex; flex-wrap: wrap; align-items: baseline;
  gap: var(--s2) var(--s5); margin-top: var(--s4); padding-top: var(--s3);
  border-top: 1px solid var(--line); }
.pg-claim .vacts > details { margin: 0; }
.pg-claim .vacts > details[open] { flex-basis: 100%; }
.pg-claim .vacts > details.flag > summary { color: var(--muted); }
.pg-claim .vacts form.box + form.box { margin-top: var(--s4); padding-top: var(--s4);
  border-top: 1px solid var(--line); }
.pg-claim .vacts details > p.muted { margin: var(--s3) 0 0; font-size: var(--t1);
  line-height: var(--l1); }

/* where the claim comes from: the printed paragraph and the selection notes, as small lines */
.pg-claim .claim-src { display: grid; gap: var(--s2); margin: 0 0 var(--s5); }
.pg-claim .claim-src details { margin: 0; }
.pg-claim .claim-src details > summary, .pg-claim .claim-src p.caution { color: var(--muted);
  font-size: var(--t1); line-height: var(--l1); }
.pg-claim .claim-src p.caution { margin: 0; padding: 0; border: 0; }

/* what has to be true: one row per part of the claim, its state at the right */
.pg-claim .truths .checklist { list-style: none; padding: 0; margin: 0;
  border-top: 1px solid var(--line); }
.pg-claim .checklist li { display: grid; grid-template-columns: minmax(0, 1fr) auto;
  gap: 0 var(--s4); align-items: baseline; margin: 0; max-width: none; padding: var(--s2) 0;
  border-bottom: 1px solid var(--line); }
.pg-claim .checklist .mark { display: none; }
.pg-claim .checklist .meta { margin-top: var(--s1); }
.pg-claim .checklist .said { font-size: var(--t1); line-height: var(--l1); color: var(--muted);
  white-space: nowrap; }
.pg-claim .checklist li.ok .said { color: var(--support); font-weight: 600; }
.pg-claim .checklist li.ok[data-tier=ai_reviewed] .said { color: var(--muted); font-weight: 400; }
.pg-claim .checklist li.con .said { color: var(--signal); font-weight: 600; }

/* other explanations: one line per lead, the records behind them folded */
.pg-claim details.alts-fold { margin: var(--s5) 0 var(--s2); }
.pg-claim details.alts-fold > summary { display: grid;
  grid-template-columns: auto minmax(0, 1fr); align-items: baseline; }
.pg-claim details.alts-fold > summary::before { align-self: center; }
.pg-claim .claim-main details.alts-fold h2 { margin: 0; }
.pg-claim .alt-titles { grid-column: 2; display: grid; margin: var(--s1) 0 0; }
.pg-claim .alt-titles span { font: 400 var(--t2)/var(--l2) var(--sans); color: var(--muted); }
.pg-claim details.alts-fold[open] .alt-titles { display: none; }
.alts { margin: var(--s1) 0 0; }
.alt { border-top: 1px solid var(--line); padding: var(--s3) 0; }
.alt h3, .alt h4 { margin: var(--s1) 0; }
.alt p { margin: var(--s1) 0; }
.alt .fam, .alt .meta, .alt .searched { font-size: var(--t1); line-height: var(--l1);
  color: var(--muted); overflow-wrap: anywhere; }
.alt ul { margin: var(--s1) 0; }

/* the evidence: each group a small heading, each item under the assumption it bears on */
.pg-claim h3.ev-group { margin: var(--s6) 0 0; }
.pg-claim h3.ev-group span { font-weight: 400; color: var(--muted); }
/* the hairline sits above the assumption line, so the line stays with the item it labels */
.pg-claim p.ev-asm { margin: var(--s3) 0 var(--s2); padding-top: var(--s3); max-width: none;
  border-top: 1px solid var(--line); font-size: var(--t1); line-height: var(--l1);
  color: var(--muted); }
.pg-claim p.ev-asm + .item { border-top: 0; padding-top: 0; }
.pg-claim p.warn strong { font-weight: 600; }
.pg-claim .holdings p { margin: 0 0 var(--s1); }
.pg-claim .holdings ul { margin: 0 0 var(--s4); }
.pg-claim .holdings li { overflow-wrap: anywhere; }

/* one piece of evidence: how it bears and where it comes from, the record, then the decision */
.pg-claim .item, .pg-evidence .item { padding: var(--s3) 0 var(--s4); }
.ev-tags { display: flex; flex-wrap: wrap; align-items: baseline; margin: 0 0 var(--s2); }
.ev-tags .badge:first-child { font-size: var(--t2); line-height: var(--l2); font-weight: 600;
  color: var(--ink); }
.ev-tags .badge.b-against:first-child { color: var(--signal); }
.item blockquote { margin: 0 0 var(--s2); }
.item p.quoted { margin: var(--s2) 0 var(--s1); }
p.ev-same, p.ev-rec, p.ev-src { margin: var(--s1) 0 0; max-width: 80ch; font-size: var(--t1);
  line-height: var(--l1); color: var(--muted); overflow-wrap: anywhere; }
p.ev-rec .ev-asx { font-weight: 600; }
p.ev-review { margin: var(--s3) 0 0; max-width: none; }
.ev-foot { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--s1) var(--s5);
  margin: var(--s2) 0 0; font-size: var(--t1); line-height: var(--l1); }
.ev-foot > details { margin: 0; }
.ev-foot > details[open] { flex-basis: 100%; }
.ev-foot summary { color: var(--muted); }
.ev-foot summary:hover { color: var(--ink); }
.ev-foot details p { margin: var(--s1) 0; }
.ev-foot .ev-around { margin-left: auto; }

/* a decision's form: the reason field and its buttons on one line */
.pg-claim form.box, .pg-evidence form.box { display: flex; flex-wrap: wrap; align-items: center;
  gap: var(--s2); margin: var(--s2) 0 0; }
.pg-claim form.box br, .pg-evidence form.box br { display: none; }
.pg-claim form.box input[type=text].wide, .pg-evidence form.box input[type=text].wide {
  flex: 1 1 260px; width: auto; min-width: 0; }
.pg-claim form.box textarea { flex: 1 1 100%; }
.pg-claim form.box button, .pg-evidence form.box button { margin: 0; }
.pg-claim form.box > .muted, .pg-claim form.box > p,
.pg-evidence form.box > .muted, .pg-evidence form.box > p { flex: 1 1 100%; margin: 0;
  font-size: var(--t1); line-height: var(--l1); }
.pg-claim form.box button + .muted, .pg-evidence form.box button + .muted { flex: 1 1 200px; }

/* the agent's proposal */
.pg-claim .claim-main section.agent h2 { display: flex; flex-wrap: wrap; align-items: baseline;
  gap: var(--s1) var(--s3); margin: 0 0 var(--s2); }
.pg-claim section.agent ul.proposed li { margin: 0 0 var(--s3); }

/* the rest of the claim, folded: irrelevant records, the rules' working, a missed record */
.pg-claim .claim-more { display: grid; gap: var(--s2); margin: var(--s6) 0 0;
  padding-top: var(--s4); border-top: 1px solid var(--line); }
.pg-claim .claim-more:empty { display: none; }
.pg-claim .claim-more > details { margin: 0; }
.pg-claim .claim-more > details > summary { color: var(--muted); }
.pg-claim .claim-more > details > summary:hover { color: var(--ink); }
.pg-claim #irrelevant ul { margin: 0; font-size: var(--t1); line-height: var(--l1); }
.pg-claim #irrelevant li { margin: 0 0 var(--s2); max-width: 80ch; }
.pg-claim details.working { overflow-x: auto; }

/* the claim's wording: accept or remove on one line, a new wording folded */
.pg-claim .claim-main section.wording h2 { margin: var(--s7) 0 var(--s1); }
.pg-claim form.wording-acts { margin: var(--s2) 0 var(--s3); }
.pg-claim form.wording-acts.done button[value=accepted] { color: var(--ink);
  background: var(--line); border-color: var(--line); }
.pg-claim form.wording-acts.done button[value=accepted]:hover { border-color: var(--ink); }

/* the side ledger keeps the open claim in view. A ledger link lands on that claim's row
   (#lg-<id>), which scrolls the ledger to it, a third of the way down; the window stays at
   the top of the new claim (the padding below is only set while a ledger row is the target).
   scroll-initial-target centres the open claim on any load, after a form or from the
   overview, where the browser supports it (Chrome, Edge). No script: the page's policy
   forbids it. */
.pg-claim aside.side .ledger { overflow: clip; } /* not a scroll box, so the aside is "nearest" */
.pg-claim aside.side .ledger li { scroll-margin-top: 30vh; outline: 0; }
.pg-claim aside.side .ledger li.on { scroll-initial-target: nearest; scroll-snap-align: center; }
/* where nothing scrolled the ledger (Safari after a form), the open claim's row still shows:
   it sticks to the ledger's top or bottom edge until the list is scrolled to it */
.pg-claim aside.side .ledger li.on { position: sticky; top: 0; bottom: 0; z-index: 1; }
html:has(.pg-claim aside.side .ledger li:target) { scroll-padding-top: 100vh; }

/* ---- one evidence item */
.pg-evidence { max-width: 820px; }
.pg-evidence p.ev-of { color: var(--muted); }
.pg-evidence h2 + p.muted { margin-bottom: var(--s3); }

@media (max-width: 960px) {
  .split { grid-template-columns: minmax(0, 1fr); gap: var(--s6); }
  aside.side { position: static; max-height: none; order: 2; }
  .pg-claim .claim-main { max-width: none; }
  /* the ledger sits below the claim here: opening a claim stays at the top of the page */
  .pg-claim aside.side .ledger li { scroll-margin-top: 100000px; }
  .pg-claim aside.side .ledger li.on { position: relative; }
}
@media (max-width: 600px) {
  .pg-claim .checklist li { grid-template-columns: minmax(0, 1fr); }
  .pg-claim .checklist .said { justify-self: start; margin-top: var(--s1); }
  .ev-foot .ev-around { margin-left: 0; }
}
"""
