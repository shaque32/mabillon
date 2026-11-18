## 2026-11-18: The validation run stops before any model call when a phone's call log cannot be read
- Changed: `eval/validation/hickman_run.py` (`unreadable_call_log`, gate G5b of the v5
  readiness list). After each phone's import, the build checks the phone's own call log
  (`get_calllog` or `callHistory`, as a LEAPP import's coverage names it). When the table has
  rows but no call from it was stored with a side, the build stops before the audit, so no model
  call is made. A resume runs the same check on the stored case, so a case built before this
  change never resumes into an audit of such a phone. This happens when every row was placed by another app
  (`call_placed_by_another_app`) or has no direction. Why: since #268 a call log row that names
  another app's package is stored with neither side. Only `com.android.phone` has been seen as
  the call log package. A phone that writes another value, as ALEAPP notes for Samsung samples,
  would import with no readable phone call, and every call claim on it would stay unproven
  after a paid run. Stopping a paid run is run policy, so the check sits in the driver and not
  in the importer (agreed with the importer thread).
- Where: PR #269 (branch claude/project-thread-ds0ify)
- Verified: `tests/test_validation_run.py::test_a_call_log_no_check_can_read_stops_the_build_before_any_model_call`
  covers four cases. Every row placed by another package stops the build, and so does every row
  of no direction; both fail on main. A case built without the check is refused on resume. One phone-package row among other-app
  rows passes, and so does a row naming no package, on build and on resume. The file's 44 tests pass locally (cloud container, 2026-11-18).
  On the G2 development case (Android 13 and iOS 15 LEAPP output, #268 96cc425 + #267) neither
  phone is stopped. `make check` runs on GitHub CI.
- Open: only LEAPP coverage names these tables, so a UFDR phone is never checked here. The v5
  phones themselves are not opened before the run, so whether they would be stopped is not
  known.
- Affects: the validation driver only (`eval/`). No product capability, verdict, privacy or
  network change, and no customer-facing claim.
- Status doc: no change
