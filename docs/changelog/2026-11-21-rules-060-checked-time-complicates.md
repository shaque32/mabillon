## 2026-11-21: rules 0.6.0, rule 3d': a checked time is not blocked by a model "complicates" (#275)
- Changed: `core/audit/rules.py` 0.5.0 -> 0.6.0, signed by Arsh 2026-11-21 ("approve" on the
  PROPOSED_CHANGES.md entry in the coverage thread), with two amendments from the CodeRabbit and
  Claude reviews of #275, each approved by Arsh. A "complicates" label no longer blocks
  SUPPORTED when all of these hold: rule 3c' carries the claim (code checks alone), no expert or
  counsel accepted a supporting item on an observed record of a core assumption, it has a core identity assumption (which passed its
  checks), and the label is open (no reviewer accepted it) and sits on a core time assumption
  whose checks all passed and named their records. The reasons list it for the expert ("Rule
  3d': ...", shown on the claim page as a plain line), and it is never cited as support. Every
  other "complicates" still blocks: one a reviewer accepted, one on identity or on a non-core
  assumption, one on a time whose check is inconclusive or names no records, and one on a claim
  checks cannot carry or that lacks a core identity assumption. Every unconfirmed "contradicts"
  still blocks. `core/audit/invariants.py` now refuses a checked SUPPORTED that leaves any other
  label open. Why: on the A13 dev phone, true claims whose checks all passed stayed UNPROVEN on
  labels about a neighbouring reply or a counterparty name the check had already resolved.
  Identity labels keep blocking because they are the only guard against someone else using an
  account on filler-made sender and caller assumptions. Not caught: a record saying the device
  clock was wrong; the flag stays listed.
- Where: PR #275
- Verified: free replay of stored v4 labels and filler answers (no model call, cloud container,
  2026-11-21, recount tool in baker/validation/coverage-recount): A13 SUPPORTED with stored labels
  3 -> 6 (D077, D093, D122), 0 false Supported, 0 false Contradicted; D064 and D133 stay
  UNPROVEN on their sender labels; iOS 15 unchanged, 0 false. New contract tests in
  tests/contract/test_rules_060.py, invariant and report-line tests. Eval and full suite: see the
  PR body.
- Open: dev data only, and correlated (the filler was developed on these phones); the v5
  held-out run is the real test. Synthetic and public data, not real-case validation.
- Affects: capabilities (a verdict path); customer-facing claims (more claims can show
  "Supported by the records (code checks)" with a model flag listed)
- Status doc: pending: Header "Rule version" line: 0.6.0 on main (add "0.6.0 #275"). Section 4
  bullet "Verdicts come from code or the expert": "rules 0.6.0". Section 4 "Opus's influence on
  verdicts": add a sub-bullet after the first: "A 'complicates' label blocks SUPPORTED except one nobody
  reviewed on a core time assumption whose checks all passed and named records, with every
  non-dismissed 'complicates' on that time unreviewed, on a code-checked claim with a core
  identity assumption and no accepted support on an observed record; that one is listed for the expert (rule 3d', rules 0.6.0, #275)." Pipeline table row 11: "applies rules 0.6.0 (0.5.0 #228, 0.6.0 #275)".
  Outcome table heading: "(rules 0.6.0)", and in the code-checked Supported row add "a model's
  'complicates' nobody reviewed, on a core time assumption whose checks all passed and named
  records, with every non-dismissed 'complicates' on that time unreviewed, in a claim with a
  core identity assumption and no accepted support on an observed record, is listed and does not block (rule 3d', #275); any other
  open label blocks". Claims table rows 1 and 8: `RULE_VERSION = "0.6.0"`.
