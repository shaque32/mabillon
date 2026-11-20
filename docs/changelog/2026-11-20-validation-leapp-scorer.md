## 2026-11-20: The validation scorer scores a LEAPP run of one or two phones (scorer 1.6.0)
- Changed: `eval/validation/score_hickman.py` scored only a UFDR run (one phone, keys by UFDR
  source index, bar 8 against `dump_ufdr.py`), so it could not score validation v5, whose
  phones are read from LEAPP output. A run whose run.json names only LEAPP phones is now scored
  with `--phone SOURCE_ID=ZIP` for each phone, the zip the run read (checked against the
  SHA-256 in run.json), instead of `--dump`; a run mixing LEAPP and UFDR phones is refused, and
  each path refuses the other's arguments. The new `eval/validation/score_leapp.py` reads each
  phone's LAVA output itself (sqlite3 and the manifest, through `dump_lava.py`, never through the
  importer):
  - Keys are `lava:<phone>:<table>:<rowid>`, which a key writer reads from the LAVA output with
    no Mabillon code. A key maps to the one record of that phone whose locator the key row (and,
    for a table the kinds file groups by dedupe columns, each row sharing them) could stand
    behind; none or several is listed with why, never matched to a near miss.
  - A Google Messages row the importer skipped as a copy maps to its SMS or MMS only when the
    scorer confirms the pair from the LAVA rows: same direction, same text (an ALEAPP MMS body
    that is a part's path is an attachment), an attachment on both sides or neither, at most 2
    seconds apart, and no SMS or MMS standing for two skipped rows. The rule is restated in the
    scorer from the importer's stated behaviour, not imported.
  - Bar 8 compares, per phone and per table the kinds file reads, Mabillon's records from that
    table (distinct locators in messages, calls and contacts) plus the confirmed skipped copies
    with the reader's count; it passes only when every table agrees, every skipped copy is
    confirmed and no record comes from a table the reader does not count. `score.md` shows
    the table per phone.
  - The kinds file moves into the repo as `eval/validation/lava_kinds.json` (the `--kinds`
    default), extended with the seven tables added since #264 (ALEAPP Telegram, iLEAPP
    Snapchat and five app call tables); a test pins that it names exactly the importer's
    tables. The UFDR path and every measure are unchanged; `score.json` gains `source`.
- Where: branch `claude/project-thread-ds0ify`, its own PR on main after #265 and #269 merged.
- Verified: `tests/test_score_leapp.py` (38 tests, cloud container, 2026-11-20): row-to-record
  mapping on both phones of one case (multi-row MMS, RCS and iOS attachment rows, a skipped
  copy, a table name in other case), every refusal reason, bar 8 passing and failing (a missing
  record, a record from an uncounted table, a wrong or shared pair, a skipped row not in the
  table), each pair field, the phone hash and set checks, and the whole scorer on a driver run.
  Each guard was mutated and a test failed, except the explicit "every skipped copy confirmed"
  term of bar 8, which a table count already fails on. On the G2 development pair (Android 13
  and iOS 15 LEAPP output, driver run52 on #269 2c9ffbc, fake model, no spend): all 1,043 rows
  of the counted tables map to a record, all 123 skipped Google Messages copies are confirmed,
  and every table matches on both phones (bar 8 PASS); a hand-made 8-key dry-run key scores end
  to end with only the planted bad key unmapped. Development data, not a validation result.
  `make check` runs on GitHub CI.
- Open: the key writer brief for v5 must cite keys in the `lava:` form. A chat app's unread
  tables are outside bar 8 by design (apps stay partial). The pair rule restates the importer's
  stated rule, so a defect shared by both would not show here; the counts are independent.
- Affects: the validation scorer (`eval/`) only. No capability, privacy, model or customer claim.
- Status doc: no change.
