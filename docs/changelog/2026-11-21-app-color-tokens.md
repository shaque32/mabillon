## 2026-11-21: App color: navy accent, green for earned support, red against (#276)
- Changed: Arsh said (2026-11-21) the five-color app (#266) fixed spacing and text but lost its
  character, and asked for some color back: green for good claims, red for contested, nothing
  loud. The token block in `ui/theme.py` goes from 5 colors to 11, all taken from the site's
  own palette (`site/styles.css`): the four neutrals stay (ink, muted, paper, line); three hues
  each get one job and one pale wash: accent navy #1d3557 / #e4eaf2, support green #2f5d43 /
  #e6eee8, signal red #9a3a2c (unchanged) / #f4e5e1; and a highlighter #f3e3a6 for quoted
  words. The spacing scale, the type scale, the one radius token, the hairlines and every word
  on screen are unchanged. One component gains box styling from those tokens: the claim page's
  verdict takes padding, a 1px border and the standard radius (its plate, below). One markup
  change: the case page's list of counts carries the class `ai-support` when a supported claim
  rests on the AI reviewer.
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
  stays muted; unproven, not tested and "Support found: do you agree?" take no green. The
  Supported count and heading stand for a whole group, so one claim under them that rests on the
  AI reviewer turns their marks and the count back to ink, on Claims and on the case page, for
  a mixed group as for an AI-only one. Accept is navy, never green, because it accepts what the
  item shows, for or against the claim. A pressed choice button (Confirm or Reject on an
  identity link) keeps its pale navy look under the pointer.
- Where: PR #276
- Verified: `tests/test_design_system.py` now pins the 11 tokens and adds two tests. One
  computes WCAG contrast for every text color on paper, on the quiet fill and on its own wash,
  for ink and muted on every wash and the highlighter, and for every rule that sets a text
  color and a fill together, and fails under 4.5:1 (lowest pairs: muted on line 4.90, signal on
  line 4.99, support on line 5.44, signal on its wash 5.68). The other fails if any rule gives
  the support green to a selector outside a short allow-list, to v-supai, v-await, v-unp,
  v-nt, a stance or AI-reviewed tag, if a Supported count or heading takes green without its
  AI guard, or if the ai_reviewed override on "Records found" goes missing; each was checked to
  fail on a planted bad rule. `tests/test_demo.py` checks the case page marks its counts
  `ai-support` when a supported claim rests on the AI reviewer and not otherwise. Cloud
  container, 2026-11-21: the design-system test 10 passed; 178 tests selected by `-k "design or
  review_screen or demo or report_consistency or ui or theme or pages or smoke"` passed; ruff
  clean. Full `make check` on GitHub CI (numbers in the PR). Looked at by hand on the synthetic
  demo case (case01, scripted labels, no model call): all 19 app pages at 1440 and 390 px,
  before and after. In a headless Chromium on that case, computed styles confirmed the
  Supported count, its mark and the heading's mark are green when every supported claim earned
  it and ink once one row is AI-reviewed, the same on the case page, and that a pressed primary
  button keeps navy text on its pale navy fill under hover.
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
