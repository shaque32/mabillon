## 2026-11-25: Site privacy section shortened, Supported card fixed, docs drop local-first (#281)
- Changed: Arsh (2026-11-25 19:53Z) found the site's data section too long, since the demo
  covers the details, and asked that the site not name the AI provider or talk about keys.
  `site/index.html`: the "Nothing goes out the door unlogged" subline and its three columns are
  cut to a line or two each; the diagram box, its screen-reader label and the example window say
  "cloud AI provider" or "AI provider" instead of Claude Opus and Anthropic; "On this computer"
  says the audit runs locally and nothing is sent. The Supported column no longer says "Only
  after you accept the evidence behind it" (untrue since rules 0.5.0 added the "checked" basis);
  it now says supported comes from your acceptance or, for a message, timing or count claim,
  from passing every code check against the phone records, never from an AI label alone
  (scoped after review; pending Arsh's pick on the decision card). Step 4 says no AI label
  makes a claim supported. The example window shows Rules 0.6.0. The docs drop "local-first",
  "local by default" and "offline by default": README.md line 3, docs/ONE_PAGER.md "Where your
  data goes", the docs/PILOT_ONBOARDING.md intro, and the opening of docs/install.md and
  docs/install-mac.md now say files and the case database stay on the computer, the place the AI
  runs is chosen per case at setup, and cloud AI is recommended for an ordinary case. They keep
  naming Claude Opus and Anthropic, since examiners set up an Anthropic key. The one-pager and onboarding now say the case's AI proposes claims (not "a local
  model"), and the Mac guide says a cloud case needs internet while it proposes claims too. The "Offline
  computer" sections describe a machine without internet and stay. Arsh approved all of this
  wording 2026-11-25 19:58Z in the project thread.
- Where: PR #281
- Verified: Supported wording checked against `core/audit/rules.py` (RULE_VERSION 0.6.0; rule
  3c' checked basis, code checks only, for communication, timing and count claims; ai_accepted
  never supports). Docs wording checked against `core/casework/cloud.py` (attestation, minor
  rule) and `core/llm/cloud.py` (examiner's own key, one request at a time, logged first). No
  Mabillon zero-retention claim. Site rendered at 1280 and 390 px.
- Open: `site/privacy.html` still names Claude Opus and Anthropic (a privacy notice names who
  receives the text). Cloud AI still needs the examiner's own Anthropic key; a key from
  Mabillon's organization waits on its zero-retention agreement, which is not signed.
- Affects: customer-facing claims (public site, README, pilot and install docs)
- Status doc: no change
