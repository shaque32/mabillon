## 2026-11-17: A Timeline row's summary cites the message it names, so its words never stop the report
- Changed: `core/timeline/check.py` and `core/report/timeline.py`. A "Differs" or "Order differs"
  row names the nearest tied record in its summary ("The nearest, the message "...", is 2 days
  before it"). Those words are the document's quote of the evidence, but the summary printed them
  as the tool's own text, so the report's forbidden-word check refused the whole report when the
  quote held one of its words. The validation dry run hit this on a development LEAPP phone
  whose nearest message read "I deleted it.". The row now carries its summary as segments
  (`TimelineRow.summary_parts`, from `label_parts`), and each printed-time note likewise
  (`note_parts`), marking which text is the source's; the renderer cites those segments
  where they stand, as it already cites document text and phone labels, with no search of the
  rendered text. A note's raw printed time is cited the same way. Report version 0.41.0, so a
  bundle made with 0.40.0 is verified with the commit that made it. Tool-authored text is
  still checked.
- Where: PR #267 (branch claude/project-thread-ds0ify)
- Verified: `tests/test_timeline_case01.py::test_a_quoted_message_s_own_words_never_stop_the_report`
  plants the word in case01's paragraph 8 (a "Differs" row) and paragraph 9 (an "Order differs"
  row), and a forbidden word in the raw time a note quotes; it fails on main and passes with this
  change. `test_a_raw_time_that_matches_the_note_s_own_words_is_cited_where_it_stands` cites a
  raw value that also occurs in the note's own words where the value stands. The tests matching report, timeline, html or validation
  pass locally (478, cloud container, 2026-11-17). The two-phone dry run on development LEAPP output (Android 13 and iOS 15,
  stand-in components, no model call, cloud container, 2026-11-17) now writes its report, and
  verify-bundle passes on its bundle with nothing failed.
- Open: none known. Other report sections that quote source text were not swept beyond the
  Timeline page.
- Affects: the report (version 0.41.0) and the review screen's Timeline page only. No verdict, privacy or network
  change, and no customer-facing claim.
- Status doc: no change
