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
  app's own from #266, not the site's. The spacing scale, the type scale, the one radius
  token, the hairlines and every word on screen are unchanged. One component gains box styling
  from those tokens: the claim page's verdict takes padding, a 1px border and the standard
  radius (its plate, below). Three markup changes, all classes the green rules hang on: a
  Supported verdict that earned its green carries `v-earned`; the Claims page and the case
  page's list of counts carry `sup-earned` or `sup-confirmed` when every supported claim did;
  and a covered assumption nothing stands against carries `unopposed` (all below).
  What the examiner sees. Navy is "yours to act on, and where you are": the main button and
  Accept, links, focus rings, checked boxes, the open page in the sidebar, the open claim in the
  side ledger, the "Needs you" tag and count, "Support found: do you agree?", the phone's own
  messages in a conversation and the outline of the cited record. Green is "for the claim as
  stated, and an expert, counsel or the code checks stand behind it": Supported
  (expert-confirmed) is a solid green mark with green words; Supported by code checks or by
  counsel keeps its ring, now green; the Supported count and heading; "Records found" on an
  assumption covered at the observed, derived, counsel_reviewed or confirmed tier that nothing
  stands against; and on the
  Timeline the "Matches" status and, in a row with that status, "inside the stated time" and a
  time outside the stated one but within the examiner's own tolerance (the comparison the code
  makes on a record the sentence names; the words still say how far off).
  Red is unchanged in meaning (against the claim as stated, and errors) and now also colors the
  Contradicted count and heading on Claims. On the claim page the verdict sits on a plate that
  follows its mark: a wash where the mark is solid (expert-confirmed support, contradicted), an
  outline in the finding's color where the mark is a ring, a hairline for unproven.
  What green never reaches. The green on a verdict is opt-in: the stylesheet gives it only to
  a pill that carries `v-earned`, and one function writes that class (`_vcls` in `ui/pages.py`)
  when the verdict is Supported on an expert's, counsel's or the code checks' word and nothing
  it rests on changed after the run (`ClaimState.stale`: an expert's decision on one of its
  items or on an agent's failed check, an edit to the claim text, or any case-wide change
  `case_changed_after` in `core/review/status.py` counts: a stipulation, person, identity
  link, proposed links included, device name, device time zone, account name or defined
  event). So "Supported (AI-reviewed)" keeps the plain ink ring and ink
  words; a Supported verdict that is not current keeps its words and mark shape in ink on a
  plain hairline plate until the audit runs again; an expert's override to Supported is held to
  the same test, because the lines under it read "Not current" after such a change; and the
  Selection page's small claim pills, which are the report's own fragment
  (`core/report/selection.py`), stay ink for every Supported verdict. A model's "supports"
  stance label stays ink; "Records found" at any other tier (ai_reviewed, inferred, none)
  stays muted; unproven, not tested and "Support found: do you agree?" take no green.
  "Records found" also stays muted on an assumption something stands against: the rules cover
  an assumption on its passing checks or an accepted supporting item whatever stands against
  it (rule 2), so a covered assumption can be the one a record contradicts. The row carries
  `unopposed` (`_opposed` and `_must_be_true` in `ui/pages.py`) only when it has no failed
  check, cited by the verdict or not, and no contradicting or complicating item short of one
  an expert dismissed; an item only the AI reviewer dismissed still counts, and so does the
  open "complicates" label rule 3d' lets a code-checked Supported verdict carry (the verdict
  is green, that row is muted, and the label stays for the expert). The words on such a row are
  unchanged ("Records found (derived)", as before this PR). The second Claude review round
  found the earlier version showed those words in green under a Contradicted verdict. On the
  Timeline a record's time line is ink in every row whose status is not "Matches": under
  "No record tied" the report's fragment (`core/report/timeline.py`) puts the same class, and
  for a record inside the stated time the same words, on the records around the stated time,
  which nothing ties to the sentence, so the rule
  hangs on the row's status chip (`.tl > li:has(.chip.ok) .d-ok`). The Claude review of this
  PR found the first version colored those records green.
  The Supported count and heading stand for a whole group, so they follow its weakest claim, on
  Claims and on the case page: a solid green mark only when an expert confirmed every supported
  claim; a green ring when every one rests on an expert, counsel or the code checks; an ink
  ring when there is no supported claim, or when one rests on the AI reviewer or is not
  current. On Claims the Supported count takes the same green as its mark and is ink with the
  ink ring; on the case page every count stays ink, Contradicted included, and only the marks
  carry color. The page states which with a class (`_support_mark` in `ui/pages.py`), so
  a page that sets none shows no green. Red is not held to that test: a Contradicted verdict
  that is not current keeps its red words, mark, plate and count, as its words and mark did
  before this PR; "Not current" and "Needs you" say so in words. Accept is navy, never green,
  because it accepts what the item shows, for or against the claim. A pressed choice button
  (Confirm or Reject on an identity link) keeps its pale navy look under the pointer.
- Where: PR #276
- Verified: `tests/test_design_system.py` now pins the 11 tokens and adds two tests. One
  computes WCAG contrast for all 30 pairs of the five text colors on the six fills (paper, the
  quiet fill, the three washes and the highlighter) and for every rule that sets a text color
  and a fill together, and fails under 4.5:1 (lowest pairs: muted on line 4.90, signal on line
  4.99). The other fails if any rule gives the support green to an element outside a short
  allow-list (matched at the end of the selector, so a condition on an ancestor or inside
  `:has()` cannot make another element green), to v-supai, v-await, v-unp, v-nt, a stance tag
  or the ai_reviewed or inferred tier; if a verdict class takes green without `v-earned`; if a
  Supported count or heading
  takes green without `sup-earned` or `sup-confirmed` (or a solid green mark without
  `sup-confirmed`, or without `v-sup` and `v-earned` together on a verdict, read from
  `background` and `background-color`); if "Records found" is green at a tier outside the four
  named or without `unopposed`; if a Timeline record line is green outside a "Matches" row; if
  a rule that sets the green negates anything with `:not()`; or
  if `v-earned`, `sup-earned`, `sup-confirmed` or `unopposed` is written anywhere but in one
  string each in `ui/pages.py` (read from the parsed source, so the quoting of the markup
  around it does not matter). Twenty planted faults (sixteen bad rules and four second
  writers of a class) each made it fail. `tests/test_demo.py` checks the markup those rules
  read, on the demo case and through the app: every current Supported verdict and nothing else
  carries `v-earned`; a
  change after the run of each of the three kinds removes it, for an expert's override too;
  an AI-reviewed verdict never has it and a counsel-reviewed one has it without the solid
  group mark; Claims and the case page carry `sup-earned` (the case holds expert-confirmed
  and code-checked support) and a group of expert-confirmed claims alone gets `sup-confirmed`;
  the Selection page serves its pills without the class; on the Timeline as served, every row
  that lists records around a moment reads "No record tied" and only "Matches" rows carry
  the chip the green hangs on; after an identity decision made after the run, Claims, the
  case page, the claim page and Selection serve no `v-earned` and no group class; and every
  covered assumption in the case as audited carries `unopposed`, which a planted contradicting
  item (accepted, open, AI-accepted or AI-dismissed), a planted complicating item (accepted or
  open) or a planted failed check on that
  assumption removes while the words stay, and only an expert's dismissal restores.
  `tests/test_report_consistency.py` still requires the screen and the report
  to show the same verdict classes for every claim through a review; it sets the screen's own
  `v-earned` aside for that compare and fails if the class sits on a verdict the report does
  not show as supported on an expert's, counsel's or the checks' word. Cloud container,
  2026-11-22: `tests/test_design_system.py` and
  `tests/test_demo.py` 43 passed and `tests/test_report_consistency.py` 21 passed after the
  review fixes; on the first commit 178 tests
  selected by `-k "design or review_screen or demo or report_consistency or ui or theme or
  pages or smoke"` passed; ruff clean. Full `make check` on GitHub CI (numbers in the PR).
  Looked at by hand on the synthetic demo case (case01, scripted labels, no model call): all
  19 app pages at 1440 and 390 px, before and after. In a headless Chromium on that case,
  computed styles confirmed: the Supported count and marks on Claims as served are a green
  count and green rings (the case holds code-checked support), solid green with
  `sup-confirmed`, and an ink count and ink rings with no class; on the case page the mark does
  the same and the count is ink throughout; a verdict with `v-earned` removed turns to ink
  words, an ink mark and the hairline plate while a Contradicted one is unchanged; the
  Selection page's Supported pills are ink and its Contradicted ones red; "Records found
  (derived)" is green and turns muted with `unopposed` removed; on the Timeline the 9 "inside the
  stated time" lines, all in "Matches" rows, are green, and the 6 within-tolerance lines in
  "No record tied" rows ("1 min before", "1 min after" or "2 min after the stated time") are
  ink; each group heading's text and its
  count share a baseline; a pressed
  primary button keeps navy text on its pale navy fill under hover; and a main button goes
  from navy to ink under the pointer, which reads as a change in a headless Chromium capture
  at 2x. The not-current look was
  checked by removing the class in the browser, not by making a decision in the demo case.
- Open: no examiner or lawyer has seen the colors yet; Safari and Windows browsers and an
  encrypted case's screens were not looked at by hand; "Supported (AI-reviewed)", "Supported
  (reviewed by counsel)" and "Support found: do you agree?" do not occur in the demo case, so
  those marks were checked from the CSS only; color-blind simulation was not run. Every verdict
  keeps its words and its mark shape, but two things now differ from their counterparts by hue
  alone: a Supported verdict that is not current (ink against green) and the Supported group's
  mark and count when one of its claims has not earned the green (ink against green). The
  words that carry the same fact are elsewhere on the page ("Not current" under the verdict,
  "Needs you" and "Supported (AI-reviewed)" on the row), not on the mark itself. An expert's
  override followed by a case-wide change (a stipulation, person or identity decision) shows
  ink without being listed under "Needs you", because the "Not current" listing leaves
  overrides out (unchanged here). A covered assumption something stands against still reads
  "Records found", now muted, not "Contradicted by the records": `_must_be_true` tests
  coverage first, as on main, and changing those words is left for its own change. No claim in the
  demo case has an opposed covered
  assumption, so that row was checked through planted items in the test and by removing the
  class in the browser. What counts as a
  change after the run reads expert review rows only (`core/review/status.py`,
  `decided_after_run`); the app has no screen where counsel withdraws an acceptance yet, and
  when one lands that test and this green must count counsel's rows too. The exported report
  keeps its own colors and REPORT_VERSION.
- Affects: none (look of the local screen; no verdict, rule, label, report or privacy change)
- Status doc: pending: in section 8 ("Implemented features"), in the list of merged PRs, after
  "app look (#222, #226)" (and after "app design system on one token block (#266)" once that
  pending edit is applied) add "app color tokens: navy accent, green only for earned support
  (#276)".
