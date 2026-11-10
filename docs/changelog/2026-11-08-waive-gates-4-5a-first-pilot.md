## 2026-11-08: Gates 4 and 5a waived for the first pilot
- Changed: Arsh waived pilot gates 4 (forwarded and quoted messages) and 5a (UFDR import counts
  compared with Cellebrite Reader) in writing for the first pilot, in the project thread on
  2026-11-08 at 01:25Z ("just waive 4 and 5", then "waive"). Gate 5 counts as met only through 5a,
  and 5b was already after the first pilot, so "5" is read as 5a. `docs/PILOT_GATES.md` records
  both rows as "Not met; waived for the first pilot", with what the waiver leaves in place. A
  waived gate is not met: the count stays 15 of 19 (gate 11 was met on 2026-11-10), and the gates
  still open for the first pilot are 9 and 16. No code changes. Forwarded and quoted messages still fail closed (a claim
  resting on one stays Unproven with its warning), the UFDR importer keeps
  `FORMAT_SUPPORT = "unverified"`, and the pilot rule (only UFDR from Cellebrite Reader 7.48;
  every other format shows "Untested export format") still holds.
- Where: branch claude/project-thread-a2qum8
- Verified: docs only; `make check` run on this branch.
- Open: the separate author and forwarder fields, the second embedded level and the Reader-count
  comparison are still not done; nothing may say the UFDR import is checked against Cellebrite
  Reader's own counts. Arsh also decided that the first pilot waits for the cloud model path
  (on 2026-11-09 changed to Opus on Mabillon's zero-retention Anthropic account), which adds
  steps outside this file's gate list.
- Affects: customer-facing claims (pilot readiness); no capability, privacy or performance change.
- Status doc: pending: section 11, after the gate count sentence ("N of 19 met (...)"), add "Gates 4 and 5a are waived for
  the first pilot (Arsh, 2026-11-08); they stay not met, and the gates still open for the first
  pilot are 9 and 16."
