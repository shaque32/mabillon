## 2026-11-21: The validation driver's coverage probe (PREREGISTERED_v5 gate C4)
- Changed: validation v4's paid pass reached 42 code-checked claims of 150, found only after
  paying for every stance label. The coverage tier of a claim (code-checked, check unsettled,
  expert only, not tested, as `score_hickman._check_tier` sets it) depends only on the filler's
  assumptions and the deterministic checks, never on stance labels. `eval/validation/hickman_run.py
  --coverage-probe` now builds the case the same way and runs the same filler and checks, but a
  stand-in labeler (`eval/validation/coverage_probe.py` ProbeLabeler, every candidate irrelevant,
  no model call) replaces the stance labeler, so a cloud probe pays only for the filler's calls
  (about 150 of v4's 2,203). It writes `DIR/probe.json` with the tiers counted in total, by claim
  kind and, for code-checked claims, by each phone a deciding check searched. No claim id,
  verdict or check result is printed, logged or kept, and the case (case.db, the audited copy,
  built.ok) is deleted once counted, so whoever runs the probe on held-out phones sees counts
  only. A probe's case never resumes as a run, nor a run's as a probe; with `--cloud` it needs
  `--max-usd`. The stand-in labeler's module is in `eval/`, so the run is marked fake and no
  scorer or report takes it.
- Where: local only, branch `probe` (stacked on #271); its own PR once #271 merges.
- Verified: `tests/test_coverage_probe.py` (7 tests, cloud container, 2026-11-21, stand-in
  components on synthetic case01): the probe's counts equal a full run's tiers on the same claims,
  tier for tier, as the scorer reads them; tiers and per-phone counts on crafted check rows; no
  claim id or verdict in the log, run.json, probe.json or output (mutation-checked: a log line
  with the claim id fails it); the resume guard both ways (mutation-checked); a later run in the
  same DIR leaves no probe.json. `tests/test_validation_run.py` and
  `tests/test_validation_score.py` pass unchanged. Not yet run with a real filler: the probe's
  cost and counts on the held-out phones are unmeasured.
- Open: the filler is not deterministic, so the probe's counts estimate a later pass's tiers
  rather than fix them (v4's two passes gave 42 and 40 code-checked). The probe needs Arsh's OK
  for its spend (estimate $2 to $4, cap $5, unverified until run).
- Affects: the validation driver (`eval/`) only. No capability, privacy, model or customer claim.
- Status doc: no change
