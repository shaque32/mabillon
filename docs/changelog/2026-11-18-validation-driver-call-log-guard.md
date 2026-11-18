## 2026-11-18: The validation run stops before any model call when a phone's call log cannot be read (#269)
- Changed: `eval/validation/hickman_run.py` (`call_log_check`, gate G5b of the validation v5
  readiness list in project files; not pilot gate 5b). After each phone's import, the build
  checks the phone's own call log, found by the importer's artifact keys (`NATIVE_CALL_KEYS`:
  `get_calllog` or `callHistory`, now public in `core/ingest/leapp.py`, matched in any ASCII
  case and stored under that spelling, as is every other key Mabillon reads), not by table
  name. A LEAPP output that lists no phone call log entry at all, read or not, stops the run
  before any model call.
  The LEAPP coverage's `not_imported` entries now carry their artifact key and whether they may
  hold records (`may_hold_records`). That flag, and the importer's
  own test of whether an unread artifact may hold records, now reads a table that is there for a
  row even when the manifest counts 0, takes a manifest count only as a JSON integer of 0 or more (a negative number, a bool, or a number such as 1.0 or 0.0 reads as unknown), and finds a table whatever the ASCII case of its manifest name, as SQLite does; the importer then reads and cites the table as the database spells it, so a locator always names the LAVA table. An entry with no artifact key (a key of only spaces, or one that is not text such as a list, counts as none) takes its key from the table name: a table name that matches a key Mabillon knows (any phone call log key, or a key it reads for this LEAPP) in any ASCII case takes that key's canonical spelling, any other keeps the database's spelling, and the locator always keeps the database's spelling. It refuses a manifest in which two entries Mabillon reads name one table that is in the database (in any ASCII case), which would store each of its rows twice; entries it never reads, or entries naming a table the database does not hold, may share a name. An entry that names no table is no longer skipped without a trace: it is listed under `not_imported` (no table, its key, `may_hold_records` true unless its count is the integer 0; one of a key Mabillon reads is marked as a failed read, so the coverage shows it as not read rather than as an artifact Mabillon does not read), so a call log or app listed that way that may hold records is not counted as read in full; one counted 0 is not. The run's check stops only on such an entry of the call log, or one with no key at all; an app's entry alone does not stop it. An unread entry of a key Mabillon reads for a chat app marks that app as not read in full whatever its category says (before, only the category's first word was compared with the app's name). Neither development manifest (Android 13, iOS 15) has such entries. A call length the row states but its reader cannot read (on the phone's own call log, not whole seconds; on any path that takes the length, more digits than Python reads or past SQLite's integer range) is stored as unknown and flagged `duration_not_readable` at its row, and the coverage summary lists those rows for the examiner. A chat app's call length with a fraction of a second (such as `83.9`) is read, as before, and stored truncated to whole seconds without the flag. A Telegram call notice of an outcome other than hung up keeps no length and is flagged `call_not_incoming_outgoing_or_missed` instead, whatever length it states, so no `duration_not_readable` flag does not mean no length was stated. Only the table's own rows (`TABLE/rowid=N`) are
  counted, and package text in a log line is kept on one line. The build stops before the audit, so no
  model call is made, in these cases:
  - The table has rows but no phone call from it can be read as the caller check reads one: a
    time the caller check's own parser reads (a stored value it cannot parse does not count), and the other party stored on the side its direction names (the callee of an
    outgoing call, the caller of an incoming or missed one; the directions come from the caller
    check's own sets in `core/audit/checks/caller.py`). This happens when every row was
    placed by another app, or had no direction, no other party or no usable time, or when the
    only calls are of an app Mabillon does not know as a call provider (an iOS phone provider
    written another way would read so). The message lists the table's import flags.
  - The table has such calls but the phone has no account of its own in the case (no line or
    handle the import tied to its device), so the caller check could not put its owner on any
    call.
  - The table may hold records the import could not read at all (listed under `not_imported`;
    an entry with neither a count nor a row check fails closed, one known empty passes; a
    table whose row probe SQLite cannot answer counts as possibly holding records).
  - The manifest counts more records in the call log than its table gave rows to read.
  - The manifest lists an entry with neither an artifact key (none, or only spaces) nor a
    table that may hold records, so it cannot be ruled out as the call log (the message names the manifest
    problem, since a rebuild would list it again); one counted 0 passes.
  - The case holds no LEAPP coverage record for the phone, and the build recorded it as read
    by the LEAPP importer or did not record its importer. A phone whose importer is not recorded
    but whose LEAPP coverage is there is checked as usual.
  The messages say that claims about the phone's calls would go untested; calls of another app
  are checked apart.
  FaceTime calls in the same table are not phone calls, so they neither hide an unreadable
  call log nor stop a phone that has only those calls; calls of any other app with no phone
  call beside them stop the run. Fewer calls stored than rows read stops the run whatever
  else the log holds, readable phone calls included (the importer stores one call per row, so
  a call may be gone).
  Otherwise the run logs how many rows are phone calls a check can read. A resume runs the same
  check on the stored case, so a case built before this change never resumes into an audit of
  such a phone; on resume the phone's accounts count only while its device has one confirmed
  owner. Before that check, a resume stops unless the case.db holds the very imports
  `built.ok` records (each phone's stored SHA-256), and unless it is the very case that build
  made: each build writes a random build id into the case's audit log (on the connection that
  built it) and into `built.ok`, so a
  case.db from any other build (other claims, claim ids, claim types or zones, even of the same
  package) is refused, and so is a `built.ok` that records no build id. The audit itself checks
  the build id, each phone's confirmed owner and each phone's call log (gate G5b) again when it
  opens case.db, against the build record the run checked or wrote (not built.ok read again), so
  a case.db swapped (with or without its built.ok), an owner withdrawn, or call rows made
  unreadable after those checks is refused too. The audit
  reads its stipulations and calls in its own reads after that check, so once every claim is
  saved, and before the pipeline stores the run as completed, the driver runs the same owner
  and call log checks once more on the same connection (from the pipeline's progress callback,
  no change to `core/pipeline.py`). The check holds the write lock, and the pipeline's
  completed write joins that transaction, so nothing changes between the check and that write.
  An owner or call log change in place at that moment, or a check that itself fails (such as on
  a database locked by another writer), stores the run as stopped (with the reason in its note
  and a halt entry in the audit log), so `pipeline.last_run` and the scorer never take it as the
  case's completed audit, while its finished claims stay reusable. If even that stopped write
  fails, or the check is interrupted (Ctrl+C), the run stays running, which `pipeline.last_run`
  never takes either, and the driver's next audit on that case marks it stopped before it starts
  (as the app does when it opens a case or starts an audit). A case with no claim to audit is
  refused before the run (the pipeline would never call the check), and if its claims are
  removed after that check but before the pipeline reads them (the pipeline itself still stores
  an empty run as completed; `core/pipeline.py` is unchanged), the driver marks that run stopped
  at once and exits. If that stopped write fails too, the empty run stays completed in case.db,
  but the driver still exits without an audited.db, report or results.zip for that attempt,
  and the scorer refuses a bare case.db (it takes only a results.zip whose run.json names the
  last completed audit in the zip's own case.db).
  After that, the same check runs again in the read
  transaction of the copy below, and a change made after the run completed still marks it
  stopped; a failure there that also fails the stopped write leaves a run that passed the final
  check. The scorer (`eval/validation/score_hickman.py`, version unchanged, no measure changed)
  also now scores only a results.zip, and only when the case's last completed audit is the one
  the zip's run.json names and the build id stamped in its case.db is the one run.json names
  (run.json now records it; a zip made before build ids, such as the v4 runs, has neither and
  is checked by its run id alone, and one with only one of the two is refused); a case.db on
  its own is refused. The scorer scores into a temporary copy and replaces `scored.db`,
  `score.json` and `score.md` only once scoring succeeds, so a refused zip leaves an earlier
  score in place. The final check tests that the
  case still passes the gates, not that it equals what the audit read: a change made and
  reversed while the audit ran, or one that leaves the gates passing (such as a call time moved
  to another readable time), is not detected, and model calls made before a refusal are still
  spent. Closing these needs the pipeline to read in a snapshot the driver holds, a hook in
  `core/pipeline.py` not made here; the driver owns its output directory through `run.lock`,
  and nothing else is meant to write to case.db during a run.
  Otherwise the audit copies the case on that same connection, in the same read transaction as
  the check, to `audited.db`, and the
  report and `results.zip` are made from that copy, not from case.db read again by path, so they
  hold the audited build whatever case.db holds by then; the zip is written under a temporary
  name and published only once complete, never without the audited case, and an earlier
  attempt's `results.zip` is removed as the attempt starts, before any check can refuse it.
  One invocation at a time owns the output directory: it creates `run.lock` exclusively
  before its first write there and removes it when it ends, even if writing its PID fails, and a second invocation stops
  while the lock exists (a run killed outright leaves the file, and the message says to
  delete it). The resume and the audit open case.db without ever
  creating it, so a case.db moved away stops the run instead of leaving an empty file, and the
  run decides once whether it builds or resumes, so a `built.ok` that vanishes mid-run never
  starts a build. It also stops unless
  every resumed phone's device still has exactly one confirmed owner (counted by person, so two
  owners of one name are two), named as `built.ok` records it and the very person the build
  stipulated (`person:<device>:owner`, not another person of that name): an owner withdrawn or changed
  since the build stops the resume, whatever the phone's call log holds. This is driver setup 6
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
  - An iOS call history of FaceTime calls only passes; on a stored case, calls of an app not
    known as a call provider and no phone call stop the check, and so does a history with fewer
    calls stored than rows read, with or without a readable phone call beside them. A stored call time the caller check cannot parse is not a
    readable time.
  - A call log entry with no table name stops the build (`no table named`); an entry with
    neither a key nor a table stops it as a manifest problem when it may hold records and
    passes when counted 0 (a key of only spaces counts as none).
  - The audit stops when built.ok's build id is not the one case.db holds, or is missing, and
    when a phone's call log no longer passes gate G5b or the phone's owner stipulation was
    withdrawn, after the resume's checks or while the audit ran (the run is stored as stopped, `pipeline.last_run` keeps the earlier completed
    run, and no `audited.db` is left); a final check that fails while the write that stores the
    run as stopped fails too leaves the run running, never completed, with its finished claims
    kept; through `main()` too, with the audit itself refusing
    before any run; a case.db moved away is never recreated; another build's case.db put at
    case.db while the report reads it, or before the zip, never reaches `report.html` or
    `results.zip` (the other build's claim text is absent from the report); an owner withdrawn
    by another connection between the final check and the copy never reaches the shipped copy,
    under the default rollback journal and under WAL (where the withdrawal commits);
    a zip that fails to write, or lacks the audited case, is never published; a failed attempt
    leaves no earlier `results.zip`, and neither does a resume refused by its checks; a second
    run on a held output directory stops without touching it; a `built.ok` removed mid-resume
    never starts a build.
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
    elsewhere, and stops when it has none, or on resume when its owner stipulation was withdrawn; a phone with no LEAPP coverage record
    stops when it was read by LEAPP or its importer was not recorded, and a line break in a table name stays escaped. A resume logs the readable count as a
    build does.
  - On a stored case, an unread call log entry keyed in other case (`GET_CALLLOG`) stops the
    check, and so does a call log the manifest counts records in whose table gave no row, or
    fewer rows than the count.
  - A resume stops when its phone's confirmed device owner was changed to another person,
    withdrawn, joined by a second confirmed owner of the same name, or moved to another person
    of the same name since the build.
  - A build stops on a real `get_calllog` table with no row whose manifest counts 3 records.
  - A resume whose case.db holds another import under the same phone name stops, and so does
    one whose case.db is another build of the same package that differs only in a claim's text,
    only in a claim id, or only in the zone given, and one whose build recorded no build id.
  - A timed call on a phone with no line of its own stops the build.
  - `tests/test_leapp.py`: an artifact whose table holds a row may hold records even when the
    manifest counts 0, a negative manifest count reads as unknown (and a count of False or 0.0 is not taken as empty), a table whose row probe
    fails may hold records, a manifest table name in other case still finds its table and is
    read under the database's spelling, also as its key when it has none (tables whose names
    differ in non-ASCII letters stay distinct, each read from its own rows), a manifest naming
    one table twice among the entries it reads, in the same or other case, is refused, while
    entries it never reads may share a table; an entry with no table is listed as not imported
    and holds records unless its count is the integer 0 (a call log so listed is not read in
    full), and a call log key in other case is read as the call log (a key
    that is not text is not), and the import stores its calls under that key. A call duration
    that is not a decimal number (such as `²`), has more digits than Python reads, or is past
    SQLite's integer range is stored as unknown, on Android and iOS (an iOS duration of 5000
    digits too, and an app call duration that `int()` refuses is unknown, never a rounded float), instead of stopping the
    import; each such row is flagged `duration_not_readable` and the coverage summary lists it.
    So is a Telegram call notice whose checked length is past SQLite's range or has more digits
    than `int()` reads (before, the second stopped the import).
    An unread entry of Telegram's message key under a category that does not name Telegram
    keeps Telegram from being read in full, unless its count is 0.
  The file's 94 tests pass (with `tests/test_leapp.py`, 207; `tests/test_validation_score.py`'s 30 pass too) locally (cloud container, 2026-11-18). On the G2 development case
  (Android 13 and iOS 15 LEAPP output, #268 96cc425 + #267), neither phone is stopped, on build
  or resume: 66 of 108 and 13 of 22 call log rows are phone calls a check can read (4 missed
  calls on Android 13 name no caller), and the stored coverage is unchanged. `make check` runs on GitHub CI.
- Open: a call log where only a few rows are readable passes and is only logged; no share is
  set as a stop. Only LEAPP coverage names these tables, so a UFDR phone is never checked here.
  The v5 phones themselves are not opened before the run, so whether they would be stopped is
  not known. The caller check itself (`core/audit/checks/_common.py` `_ts`) still raises on a
  stored call time it cannot parse, so such a row beside readable ones fails the audit loudly
  (the pipeline marks the run failed and sets no verdict for the claim that failed; verdicts
  of claims finished before it stay in the case) rather than reading as inconclusive; that
  shared parser is used by every check and is not changed here. The importers store only
  parsed UTC times.
- Affects: the validation driver and scorer (`eval/`) and, in the LEAPP importer, one constant made public,
  an artifact key and `may_hold_records` added to each `not_imported` coverage entry, and a
  manifest count of 0 no longer taken on trust when the table holds a row, nor a negative one at
  all; a manifest entry with no table is listed as not imported instead of skipped, two read
  entries naming one table the database holds are refused; a key Mabillon reads in other ASCII case is read under its own spelling, a tableless entry of such a key is shown as a failed read (an attention item when it may hold records; a failed read of an entry the LEAPP output counts empty is an info line, without saying claims are untested), and a call duration that is
  not a decimal number or is past SQLite's integer range is stored as unknown instead of
  stopping the import. The verdict rules do not change, but the coverage that feeds them can: when such a table
  of an app holds rows Mabillon did not read (for example a refused native-message table with
  rows and a count of 0), that app is no longer counted as read in full, so an exact count or
  absence check on it that would have passed becomes inconclusive. This is the safer reading
  and did not change the coverage of the G2 development phones.
  No privacy or network change, and no customer-facing claim.
- Status doc: pending: section 9 (Known limitations), LEAPP import: add "A LEAPP manifest in
  which two entries Mabillon reads name one table (in any ASCII case) is refused. An entry
  that names no table is listed as not imported and, unless its count is 0, makes its app (or
  the call log) not read in full. A call duration Mabillon cannot read is stored as unknown and
  flagged in the coverage." (#269)
