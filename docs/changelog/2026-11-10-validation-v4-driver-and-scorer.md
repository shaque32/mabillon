## 2026-11-10: Validation v4: the signed plan, a second phone's header in the run driver, scorer 1.4.0 with v4's bars
- Changed: the validation run driver (`eval/validation/hickman_run.py`) takes `--source-id` and
  `--definitions FILE`, the affidavit header a v4 claims writer hands over: each SUBJECT-<n> other
  than the phone's user, defined by a telephone number, and an optional `phone_time_zone`, given
  to the case as the examiner's statement (as `--phone-zone`; a different `--phone-zone` is
  refused). Any other key, SUBJECT-1, or a value that is not a number is refused before a case is
  built. A resume must name the same source id and header. Without the options the driver sets up
  iOS 15 exactly as before. The scorer (`eval/validation/score_hickman.py`) goes to 1.4.0: an R1
  card (the run before any review: false Supported with its basis, false Contradicted, by claim
  type, over all and over tested claims); `--repeat` compares pass 2's verdicts with pass 1's
  (same share, Supported/Contradicted flips, every difference); and a v4 bars table with each
  bar's pass line (bars 1 to 6 and bar 8's import counts; 7 and 8 stay their own commands).
  Measures 1 to 7 keep their definitions. The plan itself, `eval/validation/PREREGISTERED_v4.md`,
  is the text Arsh signed on 2026-11-10 at 19:13 UTC; its freeze record is filled in before the
  run. Eval tooling only: no product code, verdict path,
  model job or prompt changes.
- Where: branch v4/tooling (local), opens as a PR after the safety PR
- Verified: `tests/test_validation_run.py` (another phone's source id and header, resume
  refusals, header refusals, the header's zone) and `tests/test_validation_score.py` (the R1 card,
  the bars on the synthetic fixture, pass 2 compared, flips and missing verdicts), synthetic data
  only.
- Open: the scorer's v4 lines (bar 1 floor 100 not-supported claims, bar 4 at most 5%, bar 6
  at least 95%) are the signed plan's; the v4 run has not happened, so no v4 number exists yet.
- Affects: performance claims (how the v4 accuracy run is scored); no capability or privacy change
- Status doc: no change
