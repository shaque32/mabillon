## 2026-11-10: Fast recommended at setup, and every case must choose where its AI runs (#254)
- Changed: CLAUDE.md (signed 2026-11-09, #250) makes cloud AI the default choice for an
  ordinary case. Step 4 of Set up and run now asks where the case's AI runs: "Fast: Opus
  through Anthropic" (recommended) or "On this computer". Nothing is pre-chosen and the
  attestation is never pre-ticked, since it is the expert's own statement, made each time Fast
  is chosen. The app proposes claims and starts the audit only once a choice is made
  (`cases.where_ai_runs`, a new readiness item), so no case drifts to either side by accident. A
  case that chose Fast but whose cloud model cannot run (no key, or a model not in
  `PROBE_PASSED`) waits with the reason instead of running on the local model. Fast needs the
  attestation ticked, and a case marked as possibly containing CSAM can only choose this
  computer. The attestation (`core/casework/cloud.py` ATTESTATION) and the setup explanation
  (FAST_EXPLAINED) are the texts Arsh approved on 2026-11-10 07:27Z. A case attested under the
  earlier text reads as not chosen and must choose again (there are no real cases yet). The
  header pill reads "Fast: Opus" or "On this computer"; it no longer says "Offline", which
  CLAUDE.md forbids. Step 4 shows the choice before the local model, which only a case on this
  computer needs. The command line (`mabillon claims`, `mabillon audit`) still runs a case
  with no choice on the local model, as before.
- Where: PR #254
- Verified: make check (see PR). New tests in `tests/test_cloud.py`: a new case has nothing
  chosen or ticked; Fast without the attestation, Fast on a CSAM case and a form with no side
  are refused and save nothing; claim proposal and the audit wait for the choice; Fast with no
  key waits instead of running locally; an old-text attestation must choose again; the page
  never says "Offline". No API calls.
- Open: `docs/SECURITY_PRIVACY.md` and other customer privacy text still describe the old
  opt-in and stance-only cloud; they need Arsh's sign-off before this ships to anyone. Zero
  retention needs Anthropic's written agreement, which needs the company to exist. The CLI
  default stays local.
- Affects: capabilities, privacy (cloud is now the recommended choice), customer-facing claims
  (setup text, attestation)
- Status doc: pending: in "When Opus is used", replace "Opt-in per case, local by default (Arsh
  chose "Opt-in cloud", 2026-10-15 07:10Z)" with "Chosen per case at setup: Fast (Opus,
  recommended, per CLAUDE.md signed 2026-11-09) or on this computer; nothing is pre-chosen and
  the app proposes claims and audits only once the expert chooses". PRODUCT_STATUS quotes no
  attestation text; `docs/SECURITY_PRIVACY.md` line 150 does, and changes only with Arsh's
  sign-off.
