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
    scorer confirms the pair from the LAVA rows: same direction, same text with runs of white
    space read as one (an ALEAPP MMS body that is a part's path is an attachment), as many
    attachments on each side, the same other party (a received message's sender; a sent one's
    conversation name when it is a number or email, else the one number the phone's contacts
    give that name), at most 2 seconds apart, one text at most on the Google Messages side, and
    no SMS or MMS standing for two skipped rows. A multi-part MMS is read from all its part
    rows. The rule is restated in the scorer from the importer's stated behaviour, not imported.
  - Rows whose dedupe value is empty (NULL, "" or white space): the reader leaves NULL out and
    counts each distinct raw value, while the importer makes a record of each such row (one per
    row, or per Google Messages group with the value read stripped and NULL as empty). The scorer
    counts those rows again by the importer's rule and adds the difference to the reader's side,
    and a key on such a row maps as the importer grouped it. A pair's times are compared in whole
    seconds, as the importer does, with every part of an MMS inside the limit.
  - Each phone zip is copied once, and that copy is hashed and read. Its manifest and database
    are found as LAVA names them (either manifest name, the database the manifest names beside
    it), size-checked like the importer's, and the database is streamed out, not held in memory.
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
- Verified: `tests/test_score_leapp.py` (79 tests, cloud container, 2026-11-20): row-to-record
  mapping on both phones of one case (multi-row MMS, RCS and iOS attachment rows, a skipped
  copy, a table name in other case), every refusal reason, bar 8 passing and failing (a missing
  record, a record from an uncounted table, a wrong or shared pair, a skipped row not in the
  table, another party's SMS), each pair field (party, attachment count, white space, several
  texts, a multi-part MMS, whole seconds, a time that is not finite, the direction column), repeated empty dedupe values
  and a record lost among them, a skipped entry whose rows are not row ids, a key on a table the
  importer does not read, the zip's manifest and database as LAVA names them, the size limit, a
  path that is not a zip file, the phone hash and set checks, and the whole scorer on a
  driver run. Each guard was mutated and a test failed, except the explicit "every skipped copy
  confirmed" term of bar 8, which a table count already fails on. On the G2 development pair
  (Android 13 and iOS 15 LEAPP output, driver run60 on main 975e37e, Linux cloud container,
  2026-11-20, fake model, no spend): all 1,043 rows of the counted tables map to a record, all
  123 skipped Google Messages copies are confirmed with the party and attachment checks, and
  every table matches on both phones with no empty-key rows (bar 8 PASS); a hand-made 8-key
  dry-run key scores end to end with only the planted bad key unmapped. Development data, not a
  validation result. `make check` runs on GitHub CI.
- Open: the key writer brief for v5 must cite keys in the `lava:` form. A chat app's unread
  tables are outside bar 8 by design (apps stay partial). The pair rule restates the importer's
  stated rule, so a defect shared by both would not show here; the counts are independent. The
  scorer's party match is a little looser than the importer's (a number matches the same
  number after up to three more leading digits, marked as a country code or not), so it guards
  against another party but not against a country-code mix-up. A dedupe value with padding
  around it (" 5" beside "5") is two values to the reader and one to the importer, so it can
  make a correct table FAIL (never PASS); none occurs on the development pair.
- Affects: the validation scorer (`eval/`) only. No capability, privacy, model or customer claim.
- Status doc: no change
