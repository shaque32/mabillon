## 2026-11-10: Testability go/no-go bar 1 counts a claim only when no sheet row is left out (eval only)
- Changed: bar 1 (`eval/run_pipeline.py`, `both_passes`) now counts a claim only when its core
  assumptions, from the first pass or an accepted repair, name nothing the signed sheet does not
  and leave out none of the sheet's templates, people or time windows for it (`left_out`). Until
  now a set that named only part of what the sheet names counted as matching. The claims that
  name nothing extra but leave a row out are counted beside the bar, for information
  (`naming_nothing_extra_but_leaving_a_sheet_row_out`). Phones, accounts, apps, handles and quoted words
  are not required, because the sheet writes the ones it looked up and the filler finds its own.
  The step's per-try sheet check is unchanged. It still accepts a try that names nothing extra,
  so bar 3 keeps scoring what such a repair does to a verdict. Why: in the 2026-11-10 Opus
  recheck on spent case05, C04's repair tested only that the BURNER's account sent the message.
  It left out that SUBJECT-1 used the BURNER and the day, still counted toward bar 1, and went
  false supported.
- Where: branch claude/project-thread-6i2msb-strict-coverage
- Verified: unit tests (`left_out` names each missing template, person and window; `both_passes`
  counts a full set, and counts case01's C16 tested without its authorship row and C05 without its
  day only beside the bar) and make check. Stored case05 runs replayed through `both_passes`
  (development data, never evidence), old count then new: 14B run of record (Mac, 2026-11-03)
  14 to 7 of 48; DeepSeek V4.1 Flash 32k (hosted, 2026-11-07) 20 to 13; Kimi K3.1 Pro (hosted,
  2026-11-07) 21 to 16; Opus 5.5 (hosted, 2026-11-10) 19 to 16; Opus 5.5 recheck on main after
  #255 (2026-11-10) 20 to 15.
- Open: the bar text Arsh signed on 2026-11-08 already says "match the sheet's rows". This makes
  the scorer do that, and it needs his sign-off before merge. The filler gap that let C04's
  one-row set through is a separate fix in the validation thread. Bar 5 must still be restated
  for hosted Opus before case06.
- Affects: none for the product (eval scoring only; the step stays off by default).
- Status doc: no change
