## 2026-11-21: Filler 13: owner identity with nothing to test, "connected" beside a call length (#PR)
- Changed: the assumption filler (version 12 to 13, `core/audit/assumption_filler.py`) now
  refuses a model's person_identity that names no account and no handle, only people who each
  own a phone by confirmed stipulation ("The account belongs to SUBJECT-1"). No check or
  reviewer could test it, and as a core assumption it kept true call claims unproven (v4
  Android 13 D077). A person who owns no phone keeps the row. "connected" is now read beside a
  call length a row tests (a tested length is never below one second), as "answered" already
  was, and a call "that was answered (or connected) and lasted ..." gets its code-made caller
  row. Found by a coverage recount that replays stored filler answers with no model calls
  (`baker/validation/coverage-recount/recount.py`, project files).
- Where: branch claude/project-thread-8xaz0s
- Verified: `tests/test_fill_calls.py` (5 new tests: the owner row refused and the claim then
  SUPPORTED on its checks, kept when it names an account or a non-owner; caller read after
  "answered/connected and lasted"; reversed caller CONTRADICTED; another length not
  SUPPORTED; "connected" without a length unread). Filler, testability and replay test files:
  1,352 passed locally. Free replay of stored answers (development data, no spend), Android 13
  v4 pass 1 (150 claims) and iOS 15 dev (106): 0 false Supported, 0 false Contradicted before
  and after. Code-checked stays 39 and 39. One claim gains a code verdict before stance labels
  (A13 D077 SUPPORTED, gold supported); with the run's stored labels it stays unproven
  (a "complicates" label). iOS 15 C06 gains a caller row (inconclusive: a copy of the call
  with no length). Full `make check` on CI.
- Open: gains are small on v4's claims: most unproven claims have several blockers. Measured
  on development phones only; the v5 claim set decides v5 coverage.
- Affects: capabilities (which call claims code can test)
- Status doc: pending: section 2 table, step 5 (Assumptions): add "Filler 13 refuses a
  person_identity naming no account or handle when every person it names owns a phone by
  confirmed stipulation, reads "connected" beside a tested call length, and reads a call
  'that was answered (or connected) and lasted ...' for its caller row (#PR)." Header
  "Other versions": assumption filler 13.
