## 2026-11-17: A Timeline row's summary cites the message it names, so its words never stop the report
- Changed: `core/timeline/check.py` and `core/report/timeline.py`. A "Differs" or "Order differs"
  row names the nearest tied record in its summary ("The nearest, the message "...", is 2 days
  before it"). Those words are the document's quote of the evidence, but the summary printed them
  as the tool's own text, so the report's forbidden-word check refused the whole report when the
  quote held one of its words. The validation dry run hit this on a development LEAPP phone
  whose nearest message read "I deleted it.". The row now records the record it names
  (`TimelineRow.named`), and the renderer cites that record's words (`link_label` with `q`),
  as it already cites document text and phone labels. Tool-authored text is still checked.
- Where: PR #267 (branch claude/project-thread-ds0ify)
- Verified: `tests/test_timeline_case01.py::test_a_quoted_message_s_own_words_never_stop_the_report`
  plants the word in case01's paragraph 8 (a "Differs" row) and paragraph 9 (an "Order differs"
  row); it fails on main and passes with this change. Timeline, report, invariant and UI tests
  pass locally (69). The two-phone dry run on development LEAPP output (Android 13 and iOS 15,
  stand-in components, no model call, cloud container, 2026-11-17) now writes its report, and
  verify-bundle passes on its bundle with nothing failed.
- Open: none known. Other summaries that quote source text were not swept beyond this file.
- Affects: the report and the review screen's Timeline page only. No verdict, privacy or network
  change, and no customer-facing claim.
- Status doc: no change
