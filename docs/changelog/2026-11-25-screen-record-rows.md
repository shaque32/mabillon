## 2026-11-25: Review screen: a record reads as one row, exported values one fold away (#277)
- Changed: Arsh said (2026-11-24) the review screen feels "noisy and crowded with all the
  sources and rough text". The audit that followed found the main cause: every record printed
  its full citation every time it appeared ("...; UTC 2026-03-10T15:15:03Z, as printed 3/10/2026
  3:15:03 PM(UTC+0)", then "From item1.xlsx, Chats sheet, spreadsheet row 946 (Excel's row
  number, not the report's # column)"). This is the first of four screen PRs (plan:
  `baker/plans/app-noise.md` in the project files). Screen only: no file under `core/` changes,
  so the report, the audit log, the stance prompt and `verify-bundle` are untouched and
  REPORT_VERSION stays 0.41.0.
  - New `ui/records.py`: one record in reading words (who, when, where in the file), and one
    table for many records. The time is the same phone-local time the screen already showed
    (`core/enrich/local_time.py` format_local), written "Mar 10, 2026, 11:16:44 AM EDT"; the
    full value with its UTC offset is the hover title, and the note said once above the rows
    names in full the zone of the phones those rows are from ("America/New_York"), so a short
    zone name is not ambiguous; when the phones differ in zone, each is named with its file, as
    the rows name files (the phone's label and the file name cited as the source's text). The
    same note says, in view, that an Excel row is the spreadsheet's own row number, not the
    report's # column, and it is left out where no row gives a time or an Excel row. A time
    shown in UTC still says "device zone unknown" in view, its table's time column is headed
    "Time (UTC)" and the note says UTC. A value the source printed that was not read as a time
    prints as stored, with "date not read" in the date cell so it does not read as the day of
    the row above; "no date" is for a record the source gives no time for at all (a contact, a
    message with no time). An attachment has no time of its own: its row shows its message's
    time and says so, and the fold gives that message's exported line (UTC and as printed). A
    message whose stored time is not a time, or is too near year 1 or 9999 to move into the
    phone's zone, keeps its row, sender and direction and reads "time unknown"; a case made
    before messages kept the sender text as printed still gets its rows.
  - Claim page, the records a failed check cites: a table (date once per run of rows, the
    phone's local time, sender, the message or record text, the Excel row linked to the message
    in its conversation) in place of the list of full citations. Above it, once: the assumption,
    the tier, the app and the thread when every message shares them ("Observed Telegram messages
    in thread @northstar"), the file and sheet, and that the time is derived from UTC and the
    phone's time zone. That line is taken over every record the heading counts, also when the
    table draws only the first 12; when a cited id is not among the case's records, or is an
    account's or a thread's (which is in the case but is not a record), the line says how many
    of each and claims no shared tier, file or thread, and an account or thread row says what it
    is in place of "record not found". Each Excel row link carries a title saying it opens the
    message in its conversation. Messages from more than one thread each say their thread under
    the message. Under it, one fold, "Exported values for these N records": each record's line
    exactly as the report prints it (`record_line`: UTC and the time as printed) with its record
    id, and the note on what an Excel row number is.
  - Evidence card: one line (sender, thread, time, file, sheet and Excel row) in place of the
    "As exported" line and the "From ..." line. When the messages are drawn above it, the line
    leaves the time out. The Evidence section, the labeled-irrelevant list and the evidence
    item's own page say once how to read the times and the Excel rows, the messages drawn around
    each record included. The evidence item's own page now shows a forwarded or quoted copy's
    caution as the claim page does (it did not pass the lookup before this PR). The card's fold,
    now "Exported values and model note", holds the report's record line, the full source
    sentence from #223 ("spreadsheet row N (Excel's row number, not the report's # column)"),
    the ids and the model note. A forwarded or quoted copy's caution stays in view on the card.
  - "Labeled irrelevant" rows: the quote, the short record line and the link to the item's own
    page, where the exported values are. The list now says the items' tier, once above the rows
    when they share it (it showed none before this PR).
  - Message in its conversation (`/selection/context`, `/exhibit/match`), and each related
    thread: five columns (Date, Phone's local time, From, Message, Excel row) in place of eight.
    The tier is said once above the rows; a table whose rows differ in tier or file gets the
    column back. A direction that does not follow from whose account sent the message is said in
    the From cell, so none is lost; an unknown direction reads "direction unknown", as the
    bubbles say it. The report's own eight-column table (`context_table`: UTC, local time, as
    printed, sender, direction, message, tier, source) is on the page unchanged, in the fold
    "Exported values for these N messages". The header gives the thread's first and last day on
    the phone's calendar, as the rows do; the two UTC times the report's header gives lead the
    fold. The match page's fixed line ends at "Messages are observed." and leaves the times to
    the note above the rows, which knows whether they are local or UTC.
  - A one-line record (an evidence card, a labeled-irrelevant row) adds the account's name,
    worded as the account's: "5551234 (account name @alex92)", "7001001 (account name Dan P,
    this phone)". The tables give the account only. The name is kept once per account and no
    importer stores the sender text per message yet, so the source can print another name on a
    later message (a changed handle); a table row says only what the message's own row gives.
  - Message bubbles on the claim and evidence pages use the same time format.
- Where: PR #277 (branch `claude/project-thread-4qhfdg`).
- Verified: `tests/test_screen_records.py` (49 tests, synthetic demo case, cloud container,
  2026-11-25): the time format and its fallbacks; times said as UTC, and headed so, where the
  phone's zone is unknown; the note naming only the zones of the phones its rows are from, and
  left out when no row has a time or an Excel row; an attachment's time, said to be its
  message's, with that message's exported line in the fold, and a message or call whose stored
  time is not a time (it keeps its sender); the Evidence note speaking for the messages drawn
  around a record; a forwarded copy's caution on the item's own page; the direction and
  display-name rules (a message with no sender account always says its direction); a tier or
  file column returning when rows differ; the app and thread named above a cited table whose
  rows leave them off; a cited list longer than the table described over every record it counts;
  and, on the claim, evidence and conversation pages, that every record's report line, record
  id, spreadsheet-row sentence and the report's conversation table are still on the same page
  inside a fold. The pinned strings in `tests/test_start_case.py`, `tests/test_flags.py`,
  `tests/test_first_read_fixes.py`, `tests/test_restore_case01.py` and both
  screen-against-report tests in `tests/test_report_consistency.py` pass unchanged. Checked by
  eye in the running demo at 1440 px and 390 px. On the demo case the cited-records block of C04
  goes from 20 lines of citation to a 10-row table, and each decided evidence card loses two
  wrapped lines.
- Open: for an account or a thread a failed check cites (`acct:`, `thr:` ids, the same_account
  check) the report, and so the fold under the screen's table, still prints "record not found"
  (`record_line` in `core/`), and the screen's row gives it no tier; both need a report change
  and a decision on the tier an account carries. A message dated too near year 1 or 9999 to move
  into the phone's zone still fails the pages that read it through `core/` (the conversation
  page when it is in the window shown, the evidence item page's context, a claim page through
  the selection audit or the Why lines), as before this PR; `format_local`'s callers in `core/`
  need the guard in a follow-up. Three more screen PRs (evidence as table rows, Timeline and
  Gaps, the Case page record block with the Audit log and Activity). The Selection page's own
  bubbles and its "nearby" table are report fragments and keep the long format until the report
  is decided. The report itself is not trimmed: that needs a REPORT_VERSION bump and Arsh's
  go-ahead. Not tested on a real export: sender and place wording was only seen on the synthetic
  Excel reports.
- Affects: the review screen's wording and layout only. No capability, verdict path, model,
  privacy or customer-facing claim.
- Status doc: no change
