## 2026-11-21: The validation driver's coverage probe (PREREGISTERED_v5 gate C4) (#272)
- Changed: validation v4's paid pass reached 42 code-checked claims of 150, a number found only
  after paying for every stance label. A claim's coverage tier (code-checked, check unsettled,
  expert only or not tested, as `score_hickman._check_tier` sets it) depends only on the filler's
  assumptions and the deterministic checks, never on stance labels. `eval/validation/hickman_run.py
  --coverage-probe` now builds the case the same way and runs the same filler and checks. A
  stand-in labeler (`eval/validation/coverage_probe.py` ProbeLabeler: every candidate irrelevant,
  no model call) is built in place of the stance labeler, so no stance model or prompt is loaded,
  and a cloud probe pays only for the filler's calls (about 150 of v4's 2,203).
  - It writes `DIR/probe.json`: the tiers in total and by claim kind, and the code-checked claims
    by each phone whose records a deciding check rests on. Every phone is listed, 0 included, and
    claims no phone can be named for are counted apart.
  - No claim id, verdict or check result is printed, logged or kept. Once the counts are written,
    the case is deleted: built.ok first, then case.db, the audited copy and the affidavit, which
    holds the claims' text.
  - A probe that pauses or stops keeps its case, so that a resume reuses the filler's paid
    answers. Until it finishes, nobody opens DIR's other files.
  - A probe's case never resumes as a run, nor a run's as a probe, and with `--cloud` the probe
    needs `--max-usd`.
  - A fresh case after a probe moves the earlier case's record into
    run.json's `earlier_cases`, so its spend cap starts at zero and nothing spent is dropped. A run
    rebuilt after a run keeps counting its spend.
  - The stand-in labeler's module is in `eval/`, so the run is marked fake and no scorer or report
    takes it.
  - `--max-usd` now holds before each request for every cloud run of the driver, probe or pass:
    a request is sent only if the spend so far plus the most it can cost (its whole request
    body at one token per byte, 4,096 tokens for what the API adds, and its whole output
    allowance) stays within the cap. Before, the cap was checked against the spend so far, so
    the last request could end above it. The 4,096-token margin is not measured, so the cap is
    an estimate, not a guarantee. run.json now keeps the spend unrounded, so a resume never
    starts its cap from a spend rounded down. A request that times out or loses its
    connection may still be charged, so its most is counted as spent (`uncertain_usd`) and
    never given back.
  - A probe never starts in a DIR that holds a run's record: its run.json, progress.log and
    report hold claims and verdicts, and its results are not the probe's to delete. The driver
    refuses it under DIR's lock, before touching DIR.
  - Every attempt now deletes an earlier attempt's report.html, as it already deleted
    results.zip, so a probe in a used DIR leaves no claims or verdicts.
  - The PR also adds the signed v5 plan as `eval/validation/PREREGISTERED_v5.md`, with its dated
    corrections and clarifications.
- Where: PR #272 (branch `claude/project-thread-ds0ify`).
- Verified: `tests/test_coverage_probe.py`, 14 tests, and the two cap tests in
  `tests/test_validation_run.py`, cloud container, 2026-11-21, stand-in
  components on synthetic case01. Six checks were mutation-checked: each test fails with its fix
  removed.
  - The probe's counts equal a full run's tiers on the same claims, tier for tier, as the scorer
    reads them.
  - Tiers and per-phone counts on crafted check rows: a check that searched two sources but
    rests on one phone's record counts for that phone only (mutation-checked).
  - No claim id or verdict in the log, run.json, probe.json or the output (mutation-checked).
  - The resume guard works both ways (mutation-checked).
  - A later run in the same DIR leaves no probe.json.
  - The spend baseline: a fresh probe starts at zero, and a rebuilt run keeps its spend (both
    mutation-checked).
  - A cloud probe builds no stance labeler (mutation-checked).
  - `tests/test_validation_run.py` and `tests/test_validation_score.py` pass unchanged.
  - Dev pair, free: a `--fake` probe ran on the A13 and iOS 15 LEAPP zips over 150 claims. A probe
    with v4's stored filler answers on the A13 LEAPP zip gave 13 code-checked. Most claims were
    untested because they name apps the LEAPP importer does not read. That run is approximate: the
    prompts' app list differed, and the scratch tool is not in the repo.
- Open: the filler is not deterministic, so the probe's counts estimate a later pass's tiers
  rather than fix them (v4's two passes gave 42 and 40 code-checked). The held-out probe's cost
  is unmeasured (estimate $2 to $4, cap $5). Arsh OK'd the first attempt on 2026-11-21.
- Affects: the validation driver (`eval/`) only. No capability, privacy, model or customer claim.
- Status doc: no change
