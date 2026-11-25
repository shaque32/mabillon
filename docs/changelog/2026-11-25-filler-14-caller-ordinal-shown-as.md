## 2026-11-25: Filler 14: who placed "a second call", and a side named "the party displayed as" (#279)
- Changed: found by the v5 pre-run replay (stored Opus answers replayed through the real
  `hickman_run` driver on tag `validation-v5`, development phones only, no model calls; files in
  `baker/validation/v5/pre-run-replay/`, project files). A false call claim whose direction is
  wrong, whose time check passes and whose caller code does not read is held open only by an
  expert-only event, which a stance "supports" label could close (v5 bar 4's worst case).
  - Assumption filler 13 to 14 (`core/audit/assumption_filler.py`). A call's noun phrase may
    hold an ordinal right after its article ("placed a second Signal call to", "received a
    third call from"), and the caller row is read for that call. Filler 13 refused it because
    the ordinal states an earlier call no check reads; that word now keeps the claim's core
    event (the unread-words guard also reads "second" before an app and "call"), so the claim
    still never rests on its checks alone.
  - The other side may be named by what the log shows for it: "to the party displayed as
    "X"", also "contact", "caller", "number", "user" or "account", "displayed" or "shown as".
    Only for an account side, never a person or a phone. "displayed as" is plain naming, as it
    already was everywhere else, so the clause reads as 'to "X"' does; "shown" is a word no
    check reads and keeps the core event. A handle side that placed the call still gets no
    caller: a caller row names persons or accounts, and code never decides which account a
    handle is.
  - "a second" before a call is an ordinal, not a tested length ("a second WhatsApp call that
    lasted two minutes" kept no event because its "a second" was read as a length).
- Where: PR #279
- Verified: `tests/test_fill_calls.py` (ordinal forms read with the event kept, on the call log
  and on an app; an ordinal anywhere but after the article refused; "displayed as" and "shown
  as" read for an account side, refused for a person, for a handle that placed the call and
  for other descriptors; an ordinal beside a tested length keeps the event, which fails
  without the fix). The filler test files: 1,245 passed. Free replay of stored answers
  (no spend), Android 13 v4 (150 claims) and iOS 15 dev (106): one claim changes, iOS 15 C07
  (gold contradicted), which gains a caller row that stays inconclusive (calls both ways in
  the window), so it is held open by a check, not only by the event. Bars 1 to 3 unchanged on
  both: 0 false Supported, 0 false Contradicted. v5 bar 4 as replayed 0 of 50 and 0 of 37;
  worst case 1 of 50 (D023) and 1 of 37 (D27), was 1 and 2. `make eval`: see the PR
  description. Cloud container, Linux x86_64, 2026-11-25.
- Open: development phones only. D27 ("received ... from the party displayed as") stays: the
  caller is a handle side. D023 stays: its key reads "about 2:08" as the failed 2:08 attempt,
  while the signed 8-minute "about" finds the connected 2:14 call. The time range must still
  name both parties for any caller row (iOS 15 D14 reads the form, gets none). This changes
  the code frozen at tag `validation-v5`: v5 needs a new tag and a redone freeze addendum.
- Affects: capabilities (which call claims code can test)
- Status doc: pending: section 2 table, step 5 (Assumptions): add "Filler 14 reads who placed
  a call written with an ordinal ('a second Signal call', the ordinal keeping a core event) or
  with the other side named by what the log shows ('the party displayed as "X"', an account
  side only) (#279)." Header "Other versions": assumption filler 14.
