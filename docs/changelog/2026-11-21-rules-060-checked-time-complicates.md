## 2026-11-21: rules 0.6.0, rule 3d': a checked time is not blocked by a model "complicates" (#275)
- Changed: `core/audit/rules.py` 0.5.0 -> 0.6.0, signed by Arsh 2026-11-21 ("approve" on the
  PROPOSED_CHANGES.md entry in the coverage thread), with an amendment from CodeRabbit's review
  that Arsh also approved. When rule 3c' carries a claim (code checks alone), an open
  (unreviewed) model "complicates" label on a core time assumption whose checks all passed and
  named their records no longer blocks SUPPORTED. The reasons list it for the expert ("Rule 3d':
  ..."), on every decision, and it is never cited as support. A "complicates" that the AI
  reviewer, counsel or an expert accepted still blocks, as does one on identity, on a non-core
  assumption, on a time whose check is inconclusive or names no records, or on a claim checks
  cannot carry still blocks, as does every unconfirmed "contradicts". Why: on the A13 dev phone,
  true claims whose checks all passed stayed UNPROVEN on labels about a neighbouring reply or a
  counterparty name the check had already resolved. Identity labels keep blocking because they
  are the only guard against someone else using an account on filler-made sender and caller
  assumptions. Not caught: a record saying the device clock was wrong; the flag stays listed.
- Where: PR #275
- Verified: free replay of stored v4 labels and filler answers (no model call, cloud container,
  2026-11-21, recount tool in baker/validation/coverage-recount): A13 SUPPORTED with stored labels
  3 -> 6 (D077, D093, D122), 0 false Supported, 0 false Contradicted; D064 and D133 stay
  UNPROVEN on their sender labels; iOS 15 unchanged, 0 false. New tests
  tests/contract/test_rules_060.py (10 test functions). Eval and full suite: see the PR body.
- Open: dev data only, and correlated (the filler was developed on these phones); the v5
  held-out run is the real test. Synthetic and public data, not real-case validation.
- Affects: capabilities (a verdict path); customer-facing claims (more claims can show
  "Supported by the records (code checks)" with a model flag listed)
- Status doc: pending: Header "Rule version" line: 0.6.0 on main (add "0.6.0 #275"). Pipeline
  table row 11: "applies rules 0.6.0 (0.5.0 #228, 0.6.0 #275)". Outcome table heading: "(rules
  0.6.0)", and in the code-checked Supported row add "a model's open 'complicates' on a time the
  check computed is listed and does not block (rule 3d', #275)". Claims table rows 1 and 8:
  `RULE_VERSION = "0.6.0"`.
