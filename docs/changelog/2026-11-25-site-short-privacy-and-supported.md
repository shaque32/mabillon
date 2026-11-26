## 2026-11-25: Site privacy section shortened, Supported card fixed, docs drop local-first (#281)
- Changed: Arsh (2026-11-25 19:53Z) found the site's data section too long, since the demo
  covers the details, and asked that the site not name the AI provider or talk about keys.
  `site/index.html`: the "Nothing goes out the door unlogged" subline and its three columns are
  cut to a line or two each; the diagram box, its screen-reader label and the example window say
  "cloud AI provider" or "AI provider" instead of Claude Opus and Anthropic; "On this computer"
  says the audit runs locally and nothing is sent. The Supported column no longer says "Only
  after you accept the evidence behind it" (untrue since rules 0.5.0 added the "checked" basis);
  it now reads, in Arsh's wording approved 2026-11-25 19:58Z and confirmed 21:47Z: "A claim is
  marked supported only when you accept the evidence, or when the phone records pass every code
  check. An AI label alone never makes it supported." The one-pager's Supported sentence is
  scoped to message, timing and count claims. Step 4 says no AI label
  makes a claim supported. The example window shows Rules 0.6.0. The docs drop "local-first",
  "local by default" and "offline by default": README.md line 3, docs/ONE_PAGER.md "Where your
  data goes", the docs/PILOT_ONBOARDING.md intro, and the opening of docs/install.md and
  docs/install-mac.md now say files and the case database stay on the computer, the place the AI
  runs is chosen per case at setup, and cloud AI is recommended for an ordinary case. They keep
  naming Claude Opus and Anthropic, since examiners set up an Anthropic key. The one-pager and onboarding now say the case's AI proposes claims (not "a local
  model"), and both install guides and the onboarding table say a cloud case needs internet while it proposes claims or is audited. The "Offline
  computer" sections describe a machine without internet and stay. Arsh approved the rest of this
  wording 2026-11-25 19:58Z in the project thread.
- Where: PR #281
- Verified: Supported wording checked against `core/audit/rules.py` (RULE_VERSION 0.6.0; rule
  3c' checked basis, code checks only, for communication, timing and count claims; ai_accepted
  never supports). Docs wording checked against `core/casework/cloud.py` (attestation, minor
  rule) and `core/llm/cloud.py` (examiner's own key, one request at a time, logged first). No
  Mabillon zero-retention claim. Site rendered at 1280 and 390 px.
- Open: the site's Supported line is broader than rule 3c': code checks alone make only a
  communication, timing or count claim supported (not an identity claim or an "exactly N"
  count), and an expert acceptance also needs no failed core check. Reviews flagged this; Arsh
  kept his wording as the owner's call (2026-11-25 21:47Z). The demo and the docs carry the
  scoped version. `site/privacy.html` still names Claude Opus and Anthropic (a privacy notice names who
  receives the text). Cloud AI still needs the examiner's own Anthropic key; a key from
  Mabillon's organization waits on its zero-retention agreement, which is not signed.
- Affects: customer-facing claims (public site, README, pilot and install docs)
- Status doc: pending: section 12, row 2, replace the safe-wording cell "Do not use.
  Replacement wording is Arsh's call (customer-facing)" with "Site (2026-11-25, Arsh's wording): "A claim is
  marked supported only when you accept the evidence, or when the phone records pass every code
  check. An AI label alone never makes it supported." Accurate scope: code checks alone cover
  only communication, timing and count claims (rule 3c'), and an acceptance needs no failed core
  check." Row 6, after the #278 edit,
  replace the safe-wording cell with ""Nothing goes out the door unlogged": your files stay on
  your computer; with cloud AI, questions go out one at a time, each logged before it is sent
  (site, 2026-11-25; the site no longer names the provider)".
