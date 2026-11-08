## 2026-11-08: Testability go/no-go scored on both passes, and a party the claim names is no wrong person (eval only) (#PR)
- Changed: the go/no-go's coverage bar (`eval/run_pipeline.py`, `testability_go_no_go`) now
  reads: at least 40% of the claims the signed sheet makes testable (at least 15 such claims, or
  "insufficient") end the audit with core assumptions, from the first pass or a repair the
  examiner accepted, that match the sheet (`both_passes`). It was 40% of the refusals the step
  worked on; that share is still printed beside the bar, for information. The eval's sheet
  check is now `SHEET_CHECK_PARTIES` (`core/audit/testability.py`): a person the claim's own
  words name, given only as a party to a record (record_time, message_count or no_contact),
  never as a sender or the one the words refer to, is not counted as a person the sheet does not
  name. Both bar 1 and bar 2 (no try naming a different person, phone or window) use it. A
  stored try that says the old check (or none) still replays with the old one, so verify-bundle
  gives earlier runs the same result. Why: Arsh chose (2026-11-08 00:48Z, decision card) to
  score both passes together. On spent case05 a stronger first pass left the step fewer, harder
  claims (Kimi K3.1 Pro: 17 of 48), so the step-only bar failed or could not be scored even when
  more claims ended testable, and the exact sheet match counted a recipient the claim names
  (DeepSeek's C38) as a wrong person.
- Where: branch claude/project-thread-6i2msb-both-passes, held until Arsh approves the bar text.
- Verified: unit tests (the bar at, above and below 40%; too few testable claims is
  insufficient; a first pass that leaves the step nothing still gets a decision; the party
  exception covers only a claim-named party to a record; the old check still flags the same
  answer), a case01 run test (C12 kept by the first pass with REYES as a party, C01 converted
  by the step: 2 of 2), and make check. Replayed through `both_passes` on spent case05 runs
  (development data, never evidence): 14B run of record (Mac, 2026-11-03, prompt v1.0) 14 of 48
  (29%), DeepSeek V4.1 Flash at 32,000 tokens 20 of 48 (42%), Kimi K3.1 Pro 21 of 48 (44%)
  (hosted, 2026-11-07, prompt v1.2). Bar 2 on the same stored tries: 14B 2 (C14, the
  code-vs-case05-sheet window convention), DeepSeek 1 (C10, a real wrong window; C38 is now
  spared), Kimi 0.
- Open: a GO no longer needs the step itself to convert a set share; a strong first pass can
  carry bar 1, and the step's share is shown beside it. Bars 3 to 7 are unchanged. No go/no-go
  has run on a held-out case under this scoring; case06 is saved for the plan C model.
- Affects: none for the product (eval scoring and the eval-only sheet check; the step stays off
  by default, and the product's claim-only check is unchanged).
- Status doc: no change
