## 2026-11-25: Site drops "local by default"; new data headline (#278)
- Changed: the site still said "Local by default. Cloud AI only when your case allows it and you
  opt in", untrue since #254 (cloud AI, Claude Opus through Anthropic, is the recommended choice
  at setup for an ordinary case). Arsh asked for it dropped and a new line (2026-11-25), and
  approved the wording 08:07Z in the project thread, and the review-fix wording 08:42Z
  (keeping "Mabillon runs no server" on the privacy page). `site/index.html`: the "Your data"
  section's headline is now "Nothing goes out the door unlogged" with a subline on what leaves
  (text one question at a time, each request logged first) and what stays (extraction files, case database); the
  diagram, its screen-reader label and the columns (Your files / Cloud AI, recommended / On this
  computer) say the same; the example app window names Claude Opus instead of "Local model,
  offline"; the re-check bundle line says "on their own computer" instead of "offline". The site
  avoids the app's label "Fast", which visitors do not know. `site/privacy.html` (Arsh-signed):
  new intro sentence and "The software, in short" paragraph, effective date 25 November 2026.
- Where: PR #278
- Verified: wording checked against `core/casework/cloud.py` (FAST_EXPLAINED, ATTESTATION,
  CSAM_NOTE), `docs/SECURITY_PRIVACY.md` sections 3 and 5, and the hash-chained request log
  (`cloud.sent` before each send). The site claims no Mabillon zero-retention agreement (none is
  signed yet); it says the key must belong to an organization with zero retention in writing,
  as the attestation does. Rendered at 1440 and 390 px; `tests/test_site_assets.py` passes.
- Open: the example window's "Rules 0.4.0" (rules are 0.6.0) and the Supported column's "Only
  after you accept the evidence behind it" (untrue since rules 0.5.0) were offered and left out
  (not approved in this round). README.md, docs/ONE_PAGER.md, docs/PILOT_ONBOARDING.md,
  docs/install.md and docs/install-mac.md still say local by default or offline by default.
  `core/casework/cloud.py` FAST_EXPLAINED says a member list goes out "for a group chat", but
  `core/audit/context.py` sends one for a message in any chat (the record's own chat only, at most
  20 accounts plus a count of the rest; calls and contacts get none). The site says "each chat's
  member list". FAST_EXPLAINED is Arsh-approved app text, so that fix needs his sign-off.
- Affects: customer-facing claims (public site and privacy page)
- Status doc: pending: in the safe-claims table, row 6, replace the status cell's last sentence
  "Cloud stays off until the expert attests per case, so "local by default" stays true." with
  "Since #254 cloud AI is the recommended choice at setup, so "local by default" is no longer
  true." and replace the safe-wording cell with ""Nothing goes out the door unlogged": with cloud
  AI, text goes out one question at a time (the government's document paragraph by paragraph,
  the records each claim is tested against, the messages around them, the case's app names and,
  for a message, the member list of its own chat, up to 20 accounts), each request logged first, and the extraction
  files and case database stay on the computer (site, 2026-11-25)". In the paragraph after the
  table, replace ""files never leave your machine" or any hosted-model wording, because plan C is
  not built (section 5) and its customer wording still needs Arsh's sign-off;" with "any
  Mabillon-hosted-model wording, because plan C is not built (section 5) and its customer wording
  still needs Arsh's sign-off; any claim that Mabillon holds a signed zero-retention agreement
  (none is signed yet);".
