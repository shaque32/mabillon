## 2026-11-21: App color: navy accent, green for earned support, red against (#276)
- Changed: Arsh said (2026-11-21) the five-color app (#266) fixed spacing and text but lost its
  character, and asked for some color back: green for good claims, red for contested, nothing
  loud. The token block in `ui/theme.py` goes from 5 colors to 11. The four neutrals stay
  as #266 set them (ink, muted, paper, line). Three hues each get one job and one pale wash:
  accent navy #1d3557 / #e4eaf2, support green #2f5d43 / #e6eee8, signal red #9a3a2c
  (unchanged) / #f4e5e1; and a highlighter #f3e3a6 for quoted words. The three hues, the green
  and red washes and the highlighter are the site's own values (`site/styles.css`: --accent,
  --sup, --sup-bg, --con, --con-bg, --hl); the navy wash #e4eaf2 is new here, made to sit
  beside those two washes (the site has none for its accent), and the hairline #dedad0 is the
  app's own from #266, not the site's. The spacing scale, the type scale, the one radius token, the hairlines and every word
  on screen are unchanged. One component gains box styling from those tokens: the claim page's
  verdict takes padding, a 1px border and the standard radius (its plate, below). Two markup
  changes, both classes the green rules hang on: the Claims page and the case page's list of
  counts carry `sup-earned` or `sup-confirmed` when every supported claim earned its green
  (below), and a verdict that waits on a re-run carries `v-stale`.
  What the examiner sees. Navy is "yours to act on, and where you are": the main button and
  Accept, links, focus rings, checked boxes, the open page in the sidebar, the open claim in the
  side ledger, the "Needs you" tag and count, "Support found: do you agree?", the phone's own
  messages in a conversation and the outline of the cited record. Green is "for the claim as
  stated, and an expert, counsel or the code checks stand behind it": Supported
  (expert-confirmed) is a solid green mark with green words; Supported by code checks or by
  counsel keeps its ring, now green; the Supported count and heading; "Records found" on an
  assumption; "Matches" and "inside the stated time" on the Timeline. Red is unchanged in
  meaning (against the claim as stated, and errors) and now also colors the Contradicted count
  and heading. On the claim page the verdict sits on a plate that follows its mark: a wash
  where the mark is solid (expert-confirmed support, contradicted), an outline in the finding's
  color where the mark is a ring, a hairline for unproven.
  What green never reaches: "Supported (AI-reviewed)" keeps the plain ink ring and ink words; a
  model's "supports" stance label stays ink; an assumption covered only at the ai_reviewed tier
  stays muted; unproven, not tested and "Support found: do you agree?" take no green. A
  Supported verdict that is not current (an evidence, wording, stipulation, person or identity
  decision came after the run and nobody overrode the verdict; the same test as the "Not
  current" line) keeps its words and mark shape but goes back to ink on a plain hairline plate
  until the audit runs again; an expert's override is never stale. A contradicted verdict that
  is not current keeps its red words, as before this PR, and also sits on the plain plate.
  The Supported count and heading stand for a whole group, so they follow its weakest claim, on
  Claims and on the case page: a solid green mark only when an expert confirmed every supported
  claim; a green ring when every one rests on an expert, counsel or the code checks; an ink
  ring when there is no supported claim, or when one rests on the AI reviewer or is not
  current. On Claims the Supported count takes the same green as its mark and is ink with the
  ink ring; on the case page every count stays ink, Contradicted included, and only the marks
  carry color. The page states which with a class (`_support_mark` in `ui/pages.py`), so
  a page that sets none shows no green. Accept is navy, never green, because it accepts what the
  item shows, for or against the claim. A pressed choice button (Confirm or Reject on an
  identity link) keeps its pale navy look under the pointer.
- Where: PR #276
- Verified: `tests/test_design_system.py` now pins the 11 tokens and adds two tests. One
  computes WCAG contrast for all 30 pairs of the five text colors on the six fills (paper, the
  quiet fill, the three washes and the highlighter) and for every rule that sets a text color
  and a fill together, and fails under 4.5:1 (lowest pairs: muted on line 4.90, signal on line
  4.99). The other fails if any rule gives
  the support green to a selector outside a short allow-list, to v-supai, v-await, v-unp,
  v-nt, v-stale, a stance or AI-reviewed tag, if a verdict's green rule lacks its
  `:not(.v-stale)`, if a Supported count or heading takes green without `sup-earned` or
  `sup-confirmed` (or the solid mark without `sup-confirmed`), or if the ai_reviewed override
  on "Records found" goes missing; five planted bad rules each made it fail. `tests/test_demo.py` checks on the demo case that Claims and the case page
  carry `sup-earned` (it holds expert-confirmed and code-checked support), that a group of
  expert-confirmed claims alone gets `sup-confirmed` and counsel-reviewed ones never do, that
  one AI-reviewed claim removes the class, and that after an identity decision made after the
  run both pages lose it and the claim page's verdict carries `v-stale`. Cloud
  container, 2026-11-21: `tests/test_design_system.py` and `tests/test_demo.py` 42 passed
  after the review fixes; on the first commit 178 tests selected by `-k "design or
  review_screen or demo or report_consistency or ui or theme or pages or smoke"` passed; ruff
  clean. Full `make check` on GitHub CI (numbers in the PR). Looked at by hand on the synthetic
  demo case (case01, scripted labels, no model call): all 19 app pages at 1440 and 390 px,
  before and after. In a headless Chromium on that case, computed styles confirmed the
  Supported count and marks as served are a green count and green rings (the case holds
  code-checked support), solid green with `sup-confirmed`, and an ink count and ink rings with
  no class; on the case page the mark does the same and the count is ink throughout; that a verdict given `v-stale` turns to ink words, an
  ink mark and the hairline plate; that each group heading's text and its count share a
  baseline; and that a pressed primary button keeps navy text on its pale navy fill under
  hover. The stale look was checked by adding the class in the browser, not by making a
  decision in the demo case.
- Open: no examiner or lawyer has seen the colors yet; Safari and Windows browsers and an
  encrypted case's screens were not looked at by hand; "Supported (AI-reviewed)", "Supported
  (reviewed by counsel)" and "Support found: do you agree?" do not occur in the demo case, so
  those marks were checked from the CSS only; color-blind simulation was not run (every state
  keeps its words and its mark shape, so none rests on hue); the exported report keeps its own
  colors and REPORT_VERSION.
- Affects: none (look of the local screen; no verdict, rule, label, report or privacy change)
- Status doc: pending: in section 8 ("Implemented features"), in the list of merged PRs, after
  "app look (#222, #226)" (and after "app design system on one token block (#266)" once that
  pending edit is applied) add "app color tokens: navy accent, green only for earned support
  (#276)".
