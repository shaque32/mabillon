## 2026-11-10: Every model job runs on the case's model (#PRNUM)
- Changed: Arsh asked on 2026-11-10 to send every job to Opus by default ("yeah send to opus by
  defult", approved with no API spend). Following the CLAUDE.md rule signed 2026-11-09 (#250),
  a case that opted in to cloud AI now runs every model job on the cloud model: stance labels,
  the AI reviewer, assumption filling, claim proposal and the testability step. Before, only
  stance labels went to the cloud and the other jobs stayed on the local model. One helper
  (`open_cloud_run` and `open_job_run` in `core/audit/_local_model.py`) gives every job the
  safeguards stance already had: each request is written to the case's audit log before it is
  sent (`cloud.sent`), a sticky failure pauses the audit (`CloudPaused`) instead of mixing in
  local answers, and an unusable stored answer is asked again rather than reused. Each job keeps
  its signed prompt; nothing new is sent beyond the text those prompts name. A cloud case needs
  no local model: the app skips the local model check before a cloud audit, proposes claims on
  the cloud model (app and `mabillon claims`), and estimates time at the cloud rate for every
  call. A cloud choice that arrives without its settings stops the audit
  (`ComponentsMissing`) rather than putting part of the case on the local model. The report's
  versions row reads "Case's model". Cloud stays opt-in per case; making it the default choice
  at setup, with the attestation and setup text Arsh approved on 2026-11-10, is the next PR.
- Where: branch claude/project-thread-fujfti
- Verified: make check (see PR). New tests in `tests/test_cloud.py`, on stand-in models with
  no network: every job opens its run on the cloud model; the AI reviewer and the assumption
  filler log each request before sending and pause on a sticky failure; `real_components` puts
  stance, filling and review on the cloud model for an allowed case; a cloud choice without
  settings never falls back to the local model. No API calls were made for this change.
- Open: only stance has a signed cloud gate (`PROBE_PASSED`, Opus 5.5 medium, stance v1.2).
  Opus on the other jobs was measured on synthetic data only: every job on case01 for $4.59
  (2026-11-08), and the signed reviewer trap set at 0/37 traps accepted (2026-11-10, cloud
  container). No real-export accuracy is measured for the cloud on any job. Zero retention
  still needs Anthropic's written agreement, which needs the company to exist.
  `docs/SECURITY_PRIVACY.md` still says only stance questions go to the cloud; it is a customer
  privacy doc, so its update is a separate PR for Arsh to sign before this ships to anyone.
- Affects: capabilities, privacy (more job types send their filled-in prompts to Anthropic in an
  opted-in case), performance (a cloud case no longer waits on the local model)
- Status doc: pending: in the models table, change the Claude Opus 5.5 row's job to "Every model
  job (claim proposal, assumption filling, stance labels with the cloud prompt v1.2, AI review,
  testability step) for cases the expert opted in; stance gated by `PROBE_PASSED`" and add
  "(#PRNUM)" to its Where; in the Qwen3-14B row change "(every case not opted in to cloud)" to
  apply to every job, not only stance labels. In "What Opus does", replace "It is the stance
  labeler" with "It runs every model job of an opted-in case (#PRNUM)", and say each job sends
  only the text its signed prompt names. In "Failure handling", say the pause and the
  `cloud.sent` log cover every job, and that a cloud case needs no local model.
