## 2026-11-16: App look rebuilt on one design system: 5 colors, one spacing scale, one type scale (#266)
- Changed: Arsh asked (2026-11-16) for the app to be run on a case with claims, every page
  screenshotted, the 5 biggest hierarchy and density problems listed, and the UI rebuilt on a
  spacing scale, a type scale and at most 5 color tokens with no gradients, checked at 1440 and
  390 px. `ui/theme.py` and every stylesheet in `ui/css/` are rewritten on one token block
  (`TOKENS_CSS`): spacing 4, 8, 12, 16, 24, 32, 48, 64; type 12/16, 14/20, 16/24, 20/28, 28/36
  in weights 400 and 600; colors ink #141414, muted #5f5a51, paper #f7f5f0, line #dedad0,
  signal #9a3a2c; one 4px radius; no gradients, shadows or opacity shades; hairlines instead of
  cards. Counted in the stylesheet before and after: font sizes 17 to 5, spacing values 35 to 8,
  colors about 28 to 5, radii 12 to 1, shadows 52 to 0, gradients 2 to 0.
  What the examiner sees: a claim's verdict is the 20px line directly under the claim text (the
  "Paragraph as printed" fold moves below it); verdicts are the signed words plus a mark. The
  mark's color says which way (ink for the claim, signal red against it, muted for neither) and
  its fill says how far it has gone: solid for support the expert confirmed and for
  contradicted; a ring for support by code checks, counsel or the AI reviewer, for a
  contradiction that waits on the expert's confirm, and for unproven; a dashed ring for not
  tested. So Supported no longer has a green, support the expert has not confirmed never wears
  the expert-confirmed mark, and red means only "against the claim as stated" and errors; stance,
  tier and review tags are plain small text and the one filled tag
  is "Needs you"; a frame means a warning; the solid button is the page's main action, and Accept on
  each open evidence item (as before). At 390 px the Set up
  tables and the Exhibits list stack, the claim counts sit two by two, and no app page scrolls
  sideways (before, Add a claim ran 487 px wide and the Files table broke to one word per line).
  App pages no longer load the report's stylesheets (core/report/*); the exported report keeps
  its own look and REPORT_VERSION, and the /report preview in the app still shows it that way.
  Fix: Set up read "This case was audited on True." because a local variable shadowed the audit
  date; it shows the date again.
  Kept on purpose: every verdict word, review-state name, provenance tier and source line; the
  demo and untested-format notices; the picked-message and "This record" outlines.
- Where: PR #266
- Verified: new `tests/test_design_system.py` (fails on any color, spacing, type size, radius,
  gradient or shadow from outside the tokens, on a font size paired with another step's line
  height, and on a style attribute anywhere under `ui/` except the bare error page in
  `ui/server.py`); ruff on `ui/` and the test; in the
  cloud container on 2026-11-16 the 41 test files that import `ui` ran 1159 passed, 2 skipped,
  25 failed (2026-11-17, after the review fixes), all 25 being encryption tests
  that need `sqlcipher3`, which that container lacks;
  full `make check` on GitHub CI (numbers in the PR). Looked at by hand on the synthetic demo
  case (case01, scripted labels, no model call): all 19 app pages at 1440 and 390 px, plus the
  agent-proposal claim, a claim with alternatives, an evidence item, both context pages and the
  error page. A review on 2026-11-17 found ten things, fixed in the same PR: an identity link's
  tier and status ran together; the conversation table lost its no-wrap times and its row
  inset; zero counts on Identities took status colors; the four supported kinds shared one
  mark; and five smaller code and wording points. An identity link card and a forwarded-copy
  label are not in the demo case, so those two rules were checked on a pasted card only.
  Contrast computed for the token pairs: muted on paper 6.28, signal on paper 6.39,
  ink on line 13.2. Screenshots in the project files, baker/app-design-system/.
- Open: Safari and Windows browsers were not looked at by hand (CI jobs only); the screens of an
  encrypted case were not looked at (no sqlcipher3 in the container); the exported report is
  not on these tokens (optional follow-up, needs a REPORT_VERSION bump); with five colors,
  Supported and Unproven differ by mark and words, not hue, and support by code checks differs
  from unproven by the ring's color and the words, which no examiner has tried.
- Affects: none (look of the local screen and one wrong date line; no verdict, rule, label,
  report or privacy change)
- Status doc: pending: in section 8 ("Implemented features"), in the list of merged PRs that
  reads "app look (#222, #226)", add "app design system on one token block (#266)" after it.
