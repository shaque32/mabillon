## 2026-11-21: LEAPP importer reads a LAVA database over 2 GiB and the Android 14 zone (#274)
- Changed: Importer `leapp` 0.3.0 (`core/ingest/leapp.py`, doc `docs/ingest/leapp.md`). Two
  generic format bugs, both found at v5 gate C2 on the held-out public test packages, before any
  claim was written (aggregates only: `/mnt/project-files/baker/validation/v5/C2_RESULT.md`).
  The fix was built from ALEAPP's public source and synthetic tests only; nothing in the held-out
  packages was opened for it. (1) Large databases: `read_lava` loaded the LAVA database with
  `sqlite3.deserialize`, which SQLite refuses above about 2 GiB (one allocation), so a public
  iOS 17 phone's 5.58 GB database could not be imported on any machine. A database up to
  2,000,000,000 bytes is still read into memory and never written out; a larger one (or a
  smaller one the computer lacks memory to load) is streamed to a new owner-only temporary
  folder, opened read-only (`mode=ro&immutable=1`) and removed, best effort, when the import ends
  or fails (`Lava.close`); on Linux it then tries to remove the name at once (macOS untested; a failed
  removal leaves the named copy until the import ends), and the next large import tries, best
  effort, to remove this user's copies older than six hours that a stopped import left.
  `docs/encryption.md` lists the copy under "Not covered". A database is refused when its temporary
  disk lacks its size plus 512 MiB, and the size ceiling rises from 8 GiB to 64 GiB. The
  coverage record says how it was read (`leapp.database_read_from`). (2) Android 14 zone:
  `ZONE_SOURCES` read the Android zone only from ALEAPP `get_battery_usage_v4`; Android 14 keeps
  it in `battery-usage-db-v9`, which ALEAPP writes as `get_battery_usage_v9`
  (`battery_usage_v9.py` at the pinned ed1b63d: `Timestamp`, `Timezone`), now read the same way.
  A phone holding both gets a zone only when every zone in both agrees, as before.
- Where: PR #274
- Verified: `tests/test_leapp.py` 133 passed (18 new): the import through a temporary copy
  (forced by setting the memory limit to 0, with the in-memory loader made to fail) stores the
  same rows and coverage as the in-memory import on the synthetic iOS and Android outputs; the
  copy is read-only, gone once open on Linux and gone after close; a database at the limit stays
  in memory; no room on disk, a non-database and an unknown tool each leave no copy; an encrypted
  case's copy reads through; a memory failure falls back to the copy; a stale copy is swept and
  a fresh one kept; a zip member that cannot be opened leaves no copy; a copy SQLite cannot open
  is reported as the temporary folder's problem. Synthetic `get_battery_usage_v9` (ALEAPP's headers) sets the zone,
  and v4 and v9 must agree. Local check (cloud container, 2026-11-21): a synthetic 2.30 GB LAVA
  database raises MemoryError through `deserialize` and imports through the new path in 3.0 s at
  37 MB peak memory, leaving no temporary file. CI `make check` (ubuntu-latest, 2026-11-21, head
  f2445f4): `ruff` clean, 5,101 tests passed (7 skipped); eval: case01 model-free
  accuracy 1.00 with 0 false supported (unreviewed 0.70, report only), hostile mode PASS (0 of 7
  structural claims supported), case02 aggregate 0.90 with 0 false supported (report only).
- Open: the temporary copy is the plain database, also in an encrypted case (the case's own
  copy of the zip stays encrypted; the examiner's original zip is plain on the same machine).
  Unlinked blocks are not wiped. Every removal is best effort: a copy left by a stopped import stays
  until a large import more than six hours later removes it, or for good if none can; a copy
  the system will not let the import remove at its end stays too. Not yet tested on macOS or Windows. Not yet
  run on the held-out iOS 17 or Android 14 packages (the validation thread does that). ALEAPP's
  v9 module notes name a sample row count for the public Pixel 7a phone; only its headers were
  used. Format support stays unverified.
- Affects: capabilities (LAVA databases over 2 GiB import; Android 14 phones get their zone);
  privacy (a database over 2 GB is written to a temporary file during import, removed at the end, best effort)
- Status doc: pending: in "Importers (main)", the LEAPP line's version becomes `leapp` 0.3.0 and
  gains "; a LAVA database over 2 GB is read from a temporary plain copy, removed (best effort) when the import ends;
  the Android zone is read from ALEAPP battery usage v4 and v9". If the #264 or #268 edit is not
  applied yet, apply it first with this version.
