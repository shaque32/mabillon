## 2026-11-25: Site privacy section shortened; Supported card and step 4 fixed
- Changed: Arsh (2026-11-25 19:53Z) found the site's data section too long, since the demo
  covers the details, and asked that the site not name the AI provider or talk about keys.
  `site/index.html`: the "Nothing goes out the door unlogged" subline and its three columns are
  cut to a line or two each; the diagram box, its screen-reader label and the example window say
  "cloud AI provider" or "AI provider" instead of Claude Opus and Anthropic; "On this computer"
  says the audit runs locally and nothing is sent. The Supported column no longer says "Only
  after you accept the evidence behind it" (untrue since rules 0.5.0 added the "checked" basis);
  it now names acceptance or, for some claims, every code check passing, and never an AI label
  alone. Step 4 says no AI label makes a claim supported. The example window shows Rules 0.6.0.
  Wording held for Arsh's "approved" in the project thread.
- Where: branch claude/project-thread-j4v7t7 (draft PR)
- Verified: Supported wording checked against `core/audit/rules.py` (RULE_VERSION 0.6.0, rule
  3c' checked basis for communication, timing and count claims; ai_accepted never supports).
  No Mabillon zero-retention claim. Rendered at 1280 and 390 px.
- Open: `site/privacy.html` and the docs (README.md, docs/ONE_PAGER.md,
  docs/PILOT_ONBOARDING.md, docs/install.md, docs/install-mac.md) still name Claude Opus and
  Anthropic; the docs still say local or offline by default. Their wording is drafted and
  waiting on Arsh. Cloud AI still needs the examiner's own Anthropic key (`core/llm/cloud.py`).
- Affects: customer-facing claims (public site)
- Status doc: no change
