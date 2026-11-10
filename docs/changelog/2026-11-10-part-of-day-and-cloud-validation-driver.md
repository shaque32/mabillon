## 2026-11-10: A part of the day is never widened to the whole day; the validation driver can run on the cloud model
- Changed: `stated_windows` in `core/audit/assumption_filler.py` no longer reads a whole-day date
  written with a part of the day ("in the early hours of November 2, 2025", "on the evening
  of", "late on", "on the night of", "overnight", "toward the end of", "in the small hours of",
  "after dark", "after work", "first thing", or "that evening" after the date). Before, code
  read such a date as the whole day, so any record that day passed a record_time check the
  claim had narrowed. Now the date is not read, the filler keeps no code-made window for it, and
  the claim cannot reach checked on that window. Found on synthetic case05 C05 by the agents
  thread. Windows tied to an expert-entered event ("in the hour before the SHOP BURGLARY") go
  through `event_windows` and are unchanged. FILLER_VERSION goes from 5 to 6. Separately,
  `eval/validation/hickman_run.py` gains `--cloud MODEL`, `--effort` and `--max-usd`: the
  public-phone validation driver can run assumption filling and stance labels on the hosted
  model (eval only, using the key in `MABILLON_ANTHROPIC_API_KEY`), counts token spend against
  a cap, and pauses with a resumable exit (code 3) when the cap is reached or the account runs
  out of credit.
- Where: branch claude/project-thread-ds0ify (PR to follow)
- Verified: new tests in `tests/test_affidavit_wording.py` (thirteen part-of-day phrasings
  return no window, including one where a plain date elsewhere in the claim would otherwise
  read; a minute time and a quoted "early" still read) and `tests/test_validation_run.py`
  (spend cap and out-of-credit pause); `make check` on 2026-11-10, cloud container.
- Open: the word list is a fixed set; a part of the day written another way ("around
  closing time on January 9, 2026") still reads as the whole day unless another guard catches
  it. The cloud driver path in `hickman_run.py` is eval tooling only: the product's assumption
  filler still has no cloud path in `core/`.
- Affects: verdict path (fewer claims can reach checked when they name a part of a day; fail
  closed). No privacy, network or customer-facing change in `core/`.
- Status doc: no change
