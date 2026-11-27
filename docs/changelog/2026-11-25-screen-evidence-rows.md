## 2026-11-25: Claim page: a decided evidence item reads as one row, with one Details fold (#280)
- Changed: second of the four screen PRs from the noise audit (plan: `baker/plans/app-noise.md`
  in the project files; the first was #277). Screen only: no file under `core/` changes, so the
  report, the audit log, the stance prompt and `verify-bundle` are untouched and REPORT_VERSION
  stays 0.41.0.
  - Claim page, "Evidence the expert already decided": each item is one row (`decided_row` in
    `ui/pages.py`). On the left its stance and its tier; beside them the quote and the short
    record line from #277 (sender, thread, the phone's local time, file, sheet and Excel row).
    One fold, "Details", holds everything else the card had: the messages around the record,
    the form to change the decision, the values as exported (the report's record line, the full
    source sentence, the ids), the model's note, the link to the item's own page and the label
    flag. Before, each decided card showed its review in full and four folds and a link side by
    side. Nothing is dropped; the row is the card's content, folded.
  - A row the expert dismissed says "dismissed by an expert" under its stance and tier, so a
    dismissed "supports" never reads as standing support once the review line is out of view.
    An accepted row's tier already says "confirmed: accepted by an expert". A message's
    quote that is part of that message is marked "Quoted:" on the row, also when the message is
    alone in its thread; a call's or an attachment's quote that is its whole text is not.
  - When every item of the decided group carries the same review, the group says it once above
    the rows ("Review, all 12: ...") and each row keeps it in its fold. A group whose reviews
    differ keeps the review in view on every row (and then not a second time in the fold).
  - The same record decided under more than one assumption is drawn once. A later row says
    "The same message as the item above (quote), judged here for this assumption" ("call" or
    "attachment" for those records, on this row and on an open card), links up to it, and keeps
    its own stance, tier, review and fold with the exported values; the messages around it are
    in the first row's fold only.
  - Stays in view on a row, never folded: the tier, "flagged by you", "needs expert review" and
    the challenge mark; a withheld rationale with its acknowledge form; a forwarded or quoted
    copy's caution.
  - Not changed: an open item (not yet decided, or decided only by the AI reviewer or counsel)
    keeps the full card with its decision form in view, and so does the evidence item's own
    page. At 600 px and under, a row's stance and tier sit above the quote.
  - Also in this PR, three wording fixes from the last review pass on #277, which merged before
    they were pushed: an attachment whose message the source gives no time at all no longer says
    its row shows that message's time; a failed check that cites only accounts or threads says they are
    not records (and "The cited id is ..." for one); a source that is not an Excel report heads
    its last column "Place in the file". This PR's own review added to the second: such a list
    is headed "Accounts or threads the failed check cites", its column "Cited id", it has no
    empty Tier or place column, and it gets no "Exported values" fold; in a mixed list the fold
    counts only the records and says what an account's or thread's id is in place of the
    report's "record not found", the line above says "the message is from ..." for one message,
    and the paragraph over the block says "What that check cites is the evidence" when no cited
    id is a record. An
    attachment whose message's printed time was not read still says the value shown is that
    message's.
  - `docs/review-screen.md` and `docs/flags.md` name the claim page's links as it prints them
    ("Messages around it"; "Flag this label" is in Details on a decided item).
- Where: PR #280 (branch `claude/project-thread-4qhfdg`).
- Verified: `tests/test_screen_records.py` (60 tests, synthetic demo case, cloud container,
  2026-11-25; main has 51 after #277). New: every decided item on C03 is one row with stance,
  tier and Excel row in view and the review, the reopen form, the report's record line, the
  spreadsheet-row sentence, the record id, the model note and the own-page link inside its fold;
  a review all 12 rows share is said once and not on the rows; each row prints its review
  exactly once; a quote that is part of its message is marked "Quoted:" and a call's or
  attachment's whole text is not (C09, C20); on C16 the three
  dismissed rows say "dismissed by an expert"; a message decided
  under several assumptions is drawn once with its conversation, the other rows point up to it
  and each keeps its exported values; a call decided twice is called a call (C09); a source that is not an Excel report; a list of accounts
  and threads alone (heading, column, no fold) and a mixed list's fold. The open-card test now
  runs on C16's undecided items. `tests/test_review_screen.py`,
  `tests/test_restore_case01.py`, `tests/test_flags.py`, `tests/test_first_read_fixes.py` and
  `tests/test_start_case.py` pass unchanged. Checked by eye in the running demo at 1440 px and
  390 px, with no sideways scroll at either. On the demo case the C03 claim page goes from
  3,343 px to 2,491 px tall at 1440 px wide, and C16 from 2,746 px to 2,486 px.
- Open: the report itself still prints "record not found" for an account or thread a failed
  check cites (`record_line` in `core/`), and the screen gives such an id no tier; both need a
  report change and a decision on the tier an account carries. The rows of one thread still each name the thread and the file; one heading per thread
  would shorten them further and was left for after pilots say whether they miss it. Two more
  screen PRs (Timeline and Gaps; the Case page record block with the Audit log and Activity).
  The report itself is not trimmed: that needs a REPORT_VERSION bump and Arsh's go-ahead. Not
  tested on a real export.
- Affects: the review screen's wording and layout only. No capability, verdict path, model,
  privacy or customer-facing claim.
- Status doc: no change
