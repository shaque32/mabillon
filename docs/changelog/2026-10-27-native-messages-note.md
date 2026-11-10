## 2026-10-27: The report and claim page say Native Messages holds iMessages and SMS together (#155)
- Changed: iOS exports put iMessages and SMS in one app, "Native Messages", and Mabillon's
  records do not say which kind a message is. Since #150 a claim that says "texted" or
  "iMessage" can be set up on Native Messages, so an expert could read a record from it as the
  kind the claim names. Report 0.19.0 adds a note to every claim whose assumptions name such an
  app, or whose shown evidence or checks rest on a message from one: "Native Messages holds
  iMessages and SMS together. Its records do not say which kind a message is, so a record from
  Native Messages may be either, whatever word the claim uses." The claim page shows the same
  note (`core/report/html.py`, `mixed_app_note`; `ui/pages.py`).
  - Which apps hold more than one kind is one map, `WIDER_APPS` in
    `core/audit/assumption_filler.py`, which the filler's count and absence refusal (#150) and
    the note both read.
  - The assumption's text is unchanged: it is what the stance model reads
    (`core/audit/readable.py`), so the note is in the report and on screen only.
  - Display only: no verdict, check, rule, prompt, contract, schema, gold or scorer changes.
- Where: main (#155, merged 2026-10-28)
- Verified: new `tests/test_mixed_app_note.py`, 5 tests on synthetic case01:
  - the filler and the note read the same map, and every app in it is one an alias names;
  - case01 has no such app, so no claim gets the note;
  - with one of case01's threads renamed Native Messages after an audit, exactly the claims
    whose shown evidence or checks rest on a message in it get the note, the report passes the
    forbidden-word check, and the claim page shows the same note as the report;
  - an assumption naming Native Messages gets the note with no record, and one naming
    WhatsApp does not;
  - the app named twice in different case gets one note, and an empty app name none.
  - `make check` passes; its eval numbers are in the PR.
- Open: whether a UFDR or AXIOM export says per message whether it is an iMessage or an SMS
  is not checked on a real export; if one does, the importer could keep it and the note could
  go. The note says nothing about how the claim was set up (an alias or the app's own name).
- Affects: customer-facing claims (what the report says on such a claim)
- Status doc: applied 2026-11-08
