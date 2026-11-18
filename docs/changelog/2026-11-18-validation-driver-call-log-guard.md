## 2026-11-18: The validation run stops before any model call when a phone's call log cannot be read (#269)
- Changed: `eval/validation/hickman_run.py` (`call_log_check`, gate G5b of the validation v5
  readiness list in project files; not pilot gate 5b). After each phone's import, the build
  checks the phone's own call log, found by the importer's artifact keys (`NATIVE_CALL_KEYS`:
  `get_calllog` or `callHistory`, now public in `core/ingest/leapp.py`), not by table name.
  The LEAPP coverage's `not_imported` entries now carry their artifact key too. The build stops before the audit, so no
  model call is made, in two cases:
  - The table has rows but no phone call from it was stored with a side. This happens when
    every row was placed by another app, or had no direction or no party. The message lists the
    table's import flags.
  - The table holds records the import could not read at all (listed under `not_imported`).
  Calls of a provider app in the same table, such as FaceTime on iOS, are not phone calls, so
  they neither hide an unreadable call log nor stop a phone that has only those calls.
  Otherwise the run logs how many rows are phone calls a check can read. A resume runs the same
  check on the stored case, so a case built before this change never resumes into an audit of
  such a phone. A resume whose case.db is gone stops with a message.
  Why: since #268, a call log row that names another app's package is stored with neither side.
  Only `com.android.phone` has been seen as the call log package. A phone that writes another
  value, as ALEAPP notes for Samsung samples, would import with no readable phone call, and
  every call claim on it would stay unproven after a paid run. Stopping a paid run is run
  policy, so the check sits in the driver and not in the importer (agreed with the importer
  thread).
- Where: PR #269 (branch claude/project-thread-ds0ify)
- Verified: `tests/test_validation_run.py` covers each case below. Each new test fails on the
  commit before its fix.
  - An Android call log whose rows were all placed by another package, or all have no
    direction, stops the build, and a case built without the check is refused on resume.
  - An Android call log with one phone-package row among other-app rows passes, on build and on
    resume, and so does a row naming no package.
  - An iOS call history whose phone calls have no direction stops the build even with a
    FaceTime call beside them.
  - An iOS call history of FaceTime calls only passes.
  - An unreadable call log table stops the build.
  - A resume with no case.db stops with a message.
  - A call log whose table is named other than its key is still checked, read or unread.
  The file's 50 tests pass locally (cloud container, 2026-11-18). On the G2 development case
  (Android 13 and iOS 15 LEAPP output, #268 96cc425 + #267), neither phone is stopped: 70 of 108
  and 13 of 22 call log rows are phone calls a check can read. `make check` runs on GitHub CI.
- Open: a call log where only a few rows are readable passes and is only logged; no share is
  set as a stop. Only LEAPP coverage names these tables, so a UFDR phone is never checked here.
  The v5 phones themselves are not opened before the run, so whether they would be stopped is
  not known.
- Affects: the validation driver (`eval/`) and, in the LEAPP importer, one constant made public and an artifact key added to each
  `not_imported` coverage entry.
  No product capability, verdict, privacy or network change, and no customer-facing claim.
- Status doc: no change
