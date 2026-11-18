## 2026-11-18: The validation run stops before any model call when a phone's call log cannot be read (#269)
- Changed: `eval/validation/hickman_run.py` (`call_log_check`, gate G5b of the validation v5
  readiness list in project files; not pilot gate 5b). After each phone's import, the build
  checks the phone's own call log, found by the importer's artifact keys (`NATIVE_CALL_KEYS`:
  `get_calllog` or `callHistory`, now public in `core/ingest/leapp.py`), not by table name.
  The LEAPP coverage's `not_imported` entries now carry their artifact key and, for a table that
  failed to read, whether it may hold records (`may_hold_records`). That flag, and the importer's
  own test of whether an unread artifact may hold records, now reads a table that is there for a
  row even when the manifest counts 0, and reads a manifest count below 0 as unknown. Only the table's own rows (`TABLE/rowid=N`) are
  counted, and package text in a log line is kept on one line. The build stops before the audit, so no
  model call is made, in these cases:
  - The table has rows but no phone call from it can be read as the caller check reads one: a
    readable time, and the other party stored on the side its direction names (the callee of an
    outgoing call, the caller of an incoming or missed one). This happens when every row was
    placed by another app, or had no direction, no other party or no usable time. The message
    lists the table's import flags.
  - The table has such calls but the phone has no account of its own in the case (no line or
    handle the import tied to its device), so the caller check could not put its owner on any
    call.
  - The table may hold records the import could not read at all (listed under `not_imported`;
    an entry with neither a count nor a row check fails closed, one known empty passes; a
    table whose row probe SQLite cannot answer counts as possibly holding records).
  - The case holds no LEAPP coverage record for the phone, and the build recorded it as read
    by the LEAPP importer or did not record its importer. A phone whose importer is not recorded
    but whose LEAPP coverage is there is checked as usual.
  The messages say that claims about the phone's calls would go untested; calls of another app
  are checked apart.
  Calls of a provider app in the same table, such as FaceTime on iOS, are not phone calls, so
  they neither hide an unreadable call log nor stop a phone that has only those calls.
  Otherwise the run logs how many rows are phone calls a check can read. A resume runs the same
  check on the stored case, so a case built before this change never resumes into an audit of
  such a phone. Before that check, a resume stops unless the case.db holds the very imports
  `built.ok` records (each phone's stored SHA-256), and unless it is the very case that build
  made: each build writes a random build id into the case's audit log and into `built.ok`, so a
  case.db from any other build (other claims, claim ids, claim types or zones, even of the same
  package) is refused, and so is a `built.ok` that records no build id. This is driver setup 6
  (setup 5 existed only on this PR's branch); a case built by an earlier setup is not resumed and
  is built again with a new `--out`. A resume whose case.db is gone stops with a message. A resume
  of a case imported before unread entries kept their artifact key stops too, since an unread
  call log cannot be ruled out; the driver does not rebuild it, and the operator runs again with a new `--out`.
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
  - A refused call log with a row stops the build when the manifest counts 0; one with no row
    passes.
  - A call log whose only phone call has no readable time stops the build; the same call with a
    time passes.
  - On a stored case: an unread entry with no count stops unless known empty, an entry with no
    key asks for a rebuild, another table's calls do not count (with foreign keys on), a call
    with no time, or with no other party on the side its direction names, does not count, and
    one with the callee but no line of the phone does while the phone has an account of its own
    elsewhere, and stops when it has none; a phone with no LEAPP coverage record
    stops when it was read by LEAPP or its importer was not recorded, and a line break in a table name stays escaped. A resume logs the readable count as a
    build does.
  - A resume whose case.db holds another import under the same phone name stops, and so does
    one whose case.db is another build of the same package that differs only in a claim's text,
    only in a claim id, or only in the zone given, and one whose build recorded no build id.
  - A timed call on a phone with no line of its own stops the build.
  - `tests/test_leapp.py`: an artifact whose table holds a row may hold records even when the
    manifest counts 0, a negative manifest count reads as unknown, and a table whose row probe
    fails may hold records.
  The file's 58 tests pass locally (cloud container, 2026-11-18). On the G2 development case
  (Android 13 and iOS 15 LEAPP output, #268 96cc425 + #267), neither phone is stopped, on build
  or resume: 66 of 108 and 13 of 22 call log rows are phone calls a check can read (4 missed
  calls on Android 13 name no caller), and the stored coverage is unchanged. `make check` runs on GitHub CI.
- Open: a call log where only a few rows are readable passes and is only logged; no share is
  set as a stop. Only LEAPP coverage names these tables, so a UFDR phone is never checked here.
  The v5 phones themselves are not opened before the run, so whether they would be stopped is
  not known.
- Affects: the validation driver (`eval/`) and, in the LEAPP importer, one constant made public,
  an artifact key and `may_hold_records` added to each `not_imported` coverage entry, and a
  manifest count of 0 no longer taken on trust when the table holds a row, nor a negative one at
  all. The verdict rules do not change, but the coverage that feeds them can: when such a table
  of an app holds rows Mabillon did not read (for example a refused native-message table with
  rows and a count of 0), that app is no longer counted as read in full, so an exact count or
  absence check on it that would have passed becomes inconclusive. This is the safer reading
  and did not change the coverage of the G2 development phones.
  No capability, privacy or network change, and no customer-facing claim.
- Status doc: no change
