## 2026-11-25: Claim page: a decided evidence item reads as one row, with one Details fold (#280)
- Changed: second of the four screen PRs from the noise audit (plan: `baker/plans/app-noise.md`
  in the project files; the first was #277). Screen only: no file under `core/` changes, so the
  report, the audit log, the stance prompt and `verify-bundle` are untouched and REPORT_VERSION
  stays 0.41.0.
  - Claim page, "Evidence the expert already decided": each item is one row (`decided_row` in
    `ui/pages.py`). On the left its stance and its tier; beside them the quote and the short
    record line from #277 (sender, thread, the phone's local time, file, sheet and Excel row).
    One fold, "Details", holds everything else the card had: the messages around the record,
    the review, the form to change the decision, the values as exported (the report's record
    line, the full source sentence, the ids), the model's note, the link to the item's own page
    and the label flag. Before, each decided card showed its review in full and four folds and a
    link side by side. Nothing is dropped; the row is the card's content, folded.
  - When every item of the decided group carries the same review, the group says it once above
    the rows ("Review, all 12: ...") and each row leaves it to its fold. A group whose reviews
    differ keeps the review in view on every row.
  - The same message decided under more than one assumption is drawn once. A later row says
    "The same message as the item above (quote), judged here for this assumption", links up to
    it, and keeps its own stance, tier, review and fold with the exported values.
  - Stays in view on a row, never folded: the tier, "flagged by you", "needs expert review" and
    the challenge mark; a withheld rationale with its acknowledge form; a forwarded or quoted
    copy's caution.
  - Not changed: an open item (not yet decided, or decided only by the AI reviewer or counsel)
    keeps the full card with its decision form in view, and so does the evidence item's own
    page. At 600 px and under, a row's stance and tier sit above the quote.
  - Also in this PR, three wording fixes from the last review pass on #277, which merged before
    they were pushed: an attachment whose message has no readable time no longer says its row
    shows that message's time; a failed check that cites only accounts or threads says they are
    not records (and "The cited id is ..." for one); a source that is not an Excel report heads
    its last column "Place in the file".
- Where: PR #280 (branch `claude/project-thread-4qhfdg`).
- Verified: `tests/test_screen_records.py` (56 tests, synthetic demo case, cloud container,
  2026-11-25). New: every decided item on C03 is one row with stance, tier and Excel row in view
  and the review, the reopen form, the report's record line, the spreadsheet-row sentence, the
  record id, the model note and the own-page link inside its fold; a review all 12 rows share is
  said once and not on the rows; on C16 a message decided under several assumptions is drawn
  once, the other rows point up to it and each keeps its exported values. The open-card test
  now runs on C16's undecided items. `tests/test_review_screen.py`,
  `tests/test_restore_case01.py`, `tests/test_flags.py`, `tests/test_first_read_fixes.py` and
  `tests/test_start_case.py` pass unchanged. Checked by eye in the running demo at 1440 px and
  390 px, with no sideways scroll at either. On the demo case the C03 claim page goes from
  3,343 px to 2,491 px tall at 1440 px wide, and C16 from 2,746 px to 2,486 px.
- Open: the rows of one thread still each name the thread and the file; one heading per thread
  would shorten them further and was left for after pilots say whether they miss it. Two more
  screen PRs (Timeline and Gaps; the Case page record block with the Audit log and Activity).
  The report itself is not trimmed: that needs a REPORT_VERSION bump and Arsh's go-ahead. Not
  tested on a real export.
- Affects: the review screen's wording and layout only. No capability, verdict path, model,
  privacy or customer-facing claim.
- Status doc: no change
