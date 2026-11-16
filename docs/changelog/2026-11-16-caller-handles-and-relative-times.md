## 2026-11-16: Call claims naming the other side by handle get a caller check; claims that time one act from another get no borrowed range
- Changed: three filler fixes (`core/audit/assumption_filler.py`, FILLER_VERSION 10), found on a
  public development phone on 2026-11-16.
  - Caller (`call_form`, `_caller_params`). A call's clause may end with the call's own app
    ("SUBJECT-1 called \"Marc R.\" on Telegram", "via WhatsApp", "on the WhatsApp app"); other
    words, or another app's name, still leave the caller unread. A time row that names the
    other side by a handle (a display name the checks resolve) now gets a caller row too, when
    the caller is the person on the other side and the handle is the very one the clause
    writes for that side (a time row whose handle is another party gets no caller row, Greptile
    on #261); the row keeps the handle. Before, both shapes
    kept no caller, so a claim with the direction reversed showed only the passing time check.
  - Relative times (`_RELATIVE_TIME_RE`, read in `_stated` and `_window`). A claim that times
    one act from another ("about six minutes later", "an hour earlier", "afterward", "within a
    minute of receiving it") gives no row a range from its stated time, from code or from the
    model. Before, the one stated time could be given to the other act, or to an edge it does
    not cover. These claims now go untested instead (fail closed).
  - What a message refers to (`_OTHER_ACT_RE`, `_times_what_it_refers_to`, read in `_stated`
    and `_window`). "refers to", "referred" and "referring" join the acts whose stated time
    code does not give to a quoted message. When the words after the refer word hold a date, a
    day or a clock time ("was referring to the picture X sent at about 8:10 p.m."), no row gets
    a range from the claim's stated time, from code or from the model (Greptile on #261). A
    refer clause with no time ("referring to the search") keeps the claim's date as the
    message's.
- Where: PR #261
- Verified: new tests in `tests/test_fill_calls.py` (the app after a call's clause, other
  words or another app, four relative-time wordings, the refer forms, a caller row's handle
  that is or is not the clause's side, a message said to refer to a timed act, and which
  refer clauses lend a time). The filler, window, quote, caller, check and axiom tests pass
  locally (1,180). A replay of stored model answers on the development phone (no model call;
  results in project files only) moved one false claim from all checks passing to a failed
  caller check, and five claims that time one act from another, or what a message refers to,
  to untested. `make check` runs on GitHub CI.
- Open: a call claim whose caller is the side named only by a handle still gets no caller row
  (`sent_by` names persons or accounts only, set in the frozen `core/contracts.py`). The
  relative-time guard is blunt: a claim with "later" anywhere loses every range, including one
  that is right. A record whose fields disagree (a message logged as sent whose stated sender
  is another account) still leaves the sender check inconclusive, by design.
- Affects: verdicts (more CONTRADICTED from the caller check on reversed calls; fewer tested
  claims where one act is timed from another); customer-facing claims: none. No privacy or
  network change.
- Status doc: pending: header "Other versions": filler 10. Section 2, step 5 (Assumptions):
  add "a claim that times one act from another (\"six minutes later\"), or times what a
  message refers to, gets no time range from its stated time".
