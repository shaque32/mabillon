"""Claims (/claims) and Add a claim (/claim/new).

This page's own CSS, scoped to its markup (see ui/css/__init__.py): `.pg-claims` wraps the claims
overview and `.pg-newclaim` wraps Add a claim. The claim page's side ledger (`_ledger`, compact)
sits outside both wrappers and keeps the shared look in ui/theme.py.

The overview reads like the site's hero ledger: a claim's name in a narrow left column, the
claim, one status at the right, and under it where it sits, the one thing it needs from the expert
and its gap topics as small tags.
"""

CSS = """
/* The queue. One headline with its one action, the counts as plain numbers, the next claim
   up, then the groups as ruled rows. */
.pg-claims .overview-head { display: flex; flex-wrap: wrap; align-items: center;
  justify-content: space-between; gap: var(--s3) var(--s6); }
.pg-claims .overview-head h1 { margin: 0; }
.pg-claims .head-acts { display: inline-flex; align-items: center; gap: var(--s4); }
.pg-claims .tiles { display: flex; flex-wrap: wrap; gap: var(--s4) var(--s7);
  margin: var(--s5) 0 var(--s7); }
.pg-claims .tile { display: grid; gap: 0; color: var(--ink); text-decoration: none; }
.pg-claims .tile .n { grid-row: 1; font: 600 var(--t5)/var(--l5) var(--sans);
  font-variant-numeric: tabular-nums; }
.pg-claims .tile .name { grid-row: 2; display: flex; align-items: center; gap: var(--s2);
  font-size: var(--t1); line-height: var(--l1); color: var(--muted); }
.pg-claims .tile .name::before { content: ""; width: var(--dot); height: var(--dot);
  border-radius: 50%; border: 2px solid var(--muted); }
.pg-claims .tile.t-you .name::before { background: var(--accent); border-color: var(--accent);
  border-radius: 0; }
.pg-claims .tile.t-sup .name::before { background: var(--ink); border-color: var(--ink); }
.pg-claims .tile.t-con .name::before { background: var(--signal); border-color: var(--signal); }
/* the counts take their finding's color; unproven and not audited stay ink */
.pg-claims .tile.t-you .n { color: var(--accent); }
.pg-claims .tile.t-con .n { color: var(--signal); }
/* The Supported count and its heading stand for every claim under them, so they are green only
   when every one of those claims earned it. One claim whose support rests on the AI reviewer
   (its row carries v-supai; every claim is listed under its verdict) turns the count, its mark
   and the heading's mark back to ink, for a mixed group as for an AI-only one. */
.pg-claims:not(:has(.verdict.v-supai)) .tile.t-sup .name::before,
.pg-claims:not(:has(.verdict.v-supai)) section#sup .ghead h2::before {
  background: var(--support); border-color: var(--support); }
.pg-claims:not(:has(.verdict.v-supai)) a.tile.t-sup .n { color: var(--support); }
.pg-claims a.tile:hover .name { color: var(--ink); }
.pg-claims .tile.empty .n { color: var(--muted); }

/* next up: the claim in the large size, each thing to do on its own short line */
.pg-claims .nextup { margin: 0 0 var(--s7); }
.pg-claims .nextup .head { display: flex; flex-wrap: wrap; justify-content: space-between;
  gap: var(--s1) var(--s3); }
.pg-claims .nextup .meta a { color: inherit; }
.pg-claims .nextup blockquote.claimtext { margin: var(--s2) 0 var(--s3); }
.pg-claims .nextup .todo { margin: 0 0 var(--s4); }
.pg-claims .nextup .todo p { margin: 0 0 var(--s1); }
.pg-claims .nextup .gap { margin-top: var(--s1); font-size: var(--t1); line-height: var(--l1);
  color: var(--muted); }
.pg-claims .nextup .gap b { color: var(--ink); margin-right: var(--s2); }

/* groups: a heading behind its finding's mark, and its count */
.pg-claims section.group .ghead h2 { display: inline-flex; align-items: center; gap: var(--s2); }
.pg-claims section.group .ghead h2::before { content: ""; flex: none; width: var(--dot);
  height: var(--dot); border-radius: 50%; border: 2px solid var(--muted); }
.pg-claims section#you .ghead h2::before { background: var(--accent);
  border-color: var(--accent); border-radius: 0; }
.pg-claims section#sup .ghead h2::before { background: var(--ink); border-color: var(--ink); }
.pg-claims section#con .ghead h2::before { background: var(--signal);
  border-color: var(--signal); }
.pg-claims details.fold > summary { color: var(--muted); }

/* a claim row: name | claim | status, then small lines under the claim */
.pg-claims .ledger .row { display: grid; grid-template-columns: 4em minmax(0, 1fr) auto;
  align-items: baseline; gap: 0 var(--s4); }
.pg-claims .ledger .cid { grid-column: 1; font-weight: 600; font-variant-numeric: tabular-nums;
  overflow-wrap: anywhere; }
.pg-claims .ledger .cid a { color: var(--ink); text-decoration: none; }
.pg-claims .ledger .cid a::after { content: ""; position: absolute; inset: 0; }
.pg-claims .ledger .cid a:focus-visible { outline: none; }
.pg-claims .ledger li:has(.cid a:focus-visible) { outline: 2px solid var(--accent);
  outline-offset: 2px; }
.pg-claims .ledger .text { grid-column: 2; max-width: 80ch; text-wrap: pretty; }
.pg-claims .ledger .verdict { grid-column: 3; justify-self: end; }
.pg-claims .ledger .sub { grid-column: 2 / -1; max-width: 80ch; font-size: var(--t1);
  line-height: var(--l1); color: var(--muted); }
.pg-claims .ledger .sub .meta { display: block; }
.pg-claims .ledger .needs { margin-top: var(--s1); color: var(--ink); }
/* gap topics: one plain line under the claim; the claim page says each in full */
.pg-claims .ledger .gap { display: inline; color: var(--ink); }
.pg-claims .ledger .sub > :not(.gap) + .gap::before { content: ""; display: block;
  margin-top: var(--s1); }
.pg-claims .ledger .gap + .gap::before { content: " · "; color: var(--muted); }
/* a claim listed under its verdict that also waits on the expert: the one filled tag */
.pg-claims .ledger .gap.you { display: inline-block; color: var(--paper); }
.pg-claims .ledger .gap.you + .gap::before { margin-left: var(--s1); }

@media (max-width: 600px) {
  .pg-claims .tiles { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--s4) var(--s5); }
  .pg-claims .ledger .row { grid-template-columns: minmax(0, 1fr) auto; }
  .pg-claims .ledger .cid { grid-column: 1; grid-row: 1; }
  .pg-claims .ledger .verdict { grid-column: 2; grid-row: 1; }
  .pg-claims .ledger .text, .pg-claims .ledger .sub { grid-column: 1 / -1; }
  .pg-claims .ledger .text { margin-top: var(--s1); }
}

/* add a claim: one form at a readable width */
.pg-newclaim form.box { max-width: 46rem; }
.pg-newclaim form.box p { margin: 0 0 var(--s4); }
.pg-newclaim .para-list { max-height: 22rem; overflow-y: auto; margin: 0 0 var(--s4);
  border-top: 1px solid var(--ink); border-bottom: 1px solid var(--ink); }
.pg-newclaim fieldset.paras { margin: 0; }
.pg-newclaim fieldset.paras legend { padding: var(--s2) 0; margin: 0;
  font: 600 var(--t2)/var(--l2) var(--sans); }
.pg-newclaim label.para-pick { display: grid; grid-template-columns: auto minmax(0, 1fr);
  gap: 0 var(--s3); margin: 0; padding: var(--s2) 0; border-top: 1px solid var(--line); }
.pg-newclaim label.para-pick input { grid-row: 1 / span 2; }
.pg-newclaim p.act { display: flex; flex-wrap: wrap; align-items: center;
  gap: var(--s2) var(--s4); margin: var(--s1) 0 0; }
.pg-newclaim p.act .muted { font-size: var(--t1); line-height: var(--l1); }
"""
