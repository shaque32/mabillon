## 2026-11-16: The validation run driver takes two phones and LEAPP packages
- Changed: `eval/validation/hickman_run.py` (setup 4). Each `--phone SOURCE_ID=PACKAGE` imports
  one phone into the same case, with the importer `core/ingest/pick.py` picks for the file (a
  UFDR, or a zip of one iLEAPP or ALEAPP output once the LEAPP importer is merged). The
  affidavit header (`--definitions`) gains `phones`: each source id's name in the document and
  the SUBJECT-<n> who used it (a stipulation), with an optional zone. Two phones need it. A
  phone's user cannot also be defined by a number, so records of that number on the other phone
  stay unlinked (fail closed). `--phone-sha256` checks each package file's hash on import. The
  zone the header gives is used only when the package records none. A package that records
  another zone stops the build, and so does a LEAPP phone whose tables hold more than one zone,
  since one given zone would misread part of its times. The same zone as the package's is
  accepted and not given again. `--ufdr` keeps working for one phone as before. run.json lists
  each phone's importer, file hash and recorded zone. Why: validation v5 is a two-phone case
  read through LEAPP, and without a zone every stated window on a LEAPP phone is refused.
- Where: PR from branch claude/project-thread-ds0ify, on main after #263 and #264
- Verified: `tests/test_validation_run.py` (two synthetic case01 phones: names, owners, people,
  hash refusal, resume refusal, header refusals, flag mixes; a two-phone LEAPP case where one
  phone records its zone, one takes the given zone, and one with two zones stops the build).
  With #264 on main the LEAPP test always runs (its skip guard is gone); the file's 32 tests
  pass locally on main c93e97d plus this change, cloud container, 2026-11-17. `make check` runs
  on GitHub CI.
- Open: not yet run end to end on a development LEAPP output (gate G2 of the v5 readiness
  list). Third-party chat apps and app calls on LEAPP come in the importer's follow-up PR.
- Affects: the validation run driver only. No verdict, capability, privacy or network change,
  and no customer-facing claim.
- Status doc: no change
