## 2026-11-10: Testability go/no-go bar 1 counts a claim only when no sheet row is left out (eval only) (#258)
- Changed: bar 1 (`eval/run_pipeline.py`, `both_passes`) now counts a claim only when its core
  assumptions, from the first pass or an accepted repair, name nothing the signed sheet does not
  and leave none of its core rows out (`left_out`). A row is covered when one assumption of the
  same template names at least the row's people and its time window, row by row, so a writer
  named only in a time range does not cover a sender row. A meaning row needs only its template,
  since its people and time range only point to the message. Until now a set that named only
  part of what the sheet names counted as matching. The claims that name nothing extra but
  leave a row out are counted beside the bar, for information
  (`naming_nothing_extra_but_leaving_a_sheet_row_out`). Phones, accounts, apps, handles and
  quoted words are not required, because the sheet writes the ones it looked up and the filler
  finds its own. The step's per-try sheet check is unchanged. It still accepts a try that names
  nothing extra, so bar 3 keeps scoring what such a repair does to a verdict. Why: in the
  2026-11-10 Opus recheck on spent case05, C04's repair tested only that the BURNER's account
  sent the message. It left out that SUBJECT-1 used the BURNER and the day, still counted
  toward bar 1, and went false supported.
- Where: PR #258
- Verified: unit tests (`left_out` names each uncovered row and compares row by row, a meaning
  row needs only its template, and `both_passes` counts a full set but counts case01's C16
  without its authorship row and C05 without its day only beside the bar) and make check.
  Stored case05 runs replayed through `both_passes` (development data, never evidence), old
  count then new: 14B run of record (Mac, 2026-11-03) 14 to 7 of 48; DeepSeek V4.1 Flash 32k
  (hosted, 2026-11-07) 20 to 13; Kimi K3.1 Pro (hosted, 2026-11-07) 21 to 16; Opus 5.5 (hosted,
  2026-11-10) 19 to 16; Opus 5.5 recheck on main after #255 (2026-11-10) 20 to 15.
- Open: Arsh approved this change on 2026-11-10 at 21:56Z, at ed58af2. The row-by-row
  comparison (Greptile on #258) came after and needs his approval too; it gives the same
  replay numbers. The filler gap that let C04's one-row set through is a separate fix in the
  validation thread (#257). Bar 5 must still be restated for hosted Opus before case06.
- Affects: none for the product (eval scoring only; the step stays off by default).
- Status doc: no change
