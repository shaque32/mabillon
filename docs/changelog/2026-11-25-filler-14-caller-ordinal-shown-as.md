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
    event, so the claim still never rests on its checks alone. The caller row itself adds that
    event (the one the unread-words guard would add), so it never depends on how the guard
    reads the wording; with no event allowed, the ordinal gets no caller row.
  - The other side may be named by what the log shows for it: "to the party displayed as
    "X"", also "contact", "caller", "number", "user" or "account", "displayed" or "shown as".
    Only for an account side, never a person or a phone. With a quoted name, "displayed as"
    is plain naming, as it already was everywhere else, so the clause reads as 'to "X"' does;
    "shown" is a word no check reads and keeps the core event, and so do other words left
    beside it (a number written after "displayed as" keeps its digits unread). A handle side
    that placed the call still gets no caller: a caller row names persons or accounts, and
    code never decides which account a handle is. The same forms also count as a plain call
    clause where a phone is one side (`_phone_is_a_side`), which sets the time range's
    parties.
  - "a second" is a tested length only after a word that leads into a length ("lasted a
    second", "for one minute and a second", "one minute, and a second"; a comma after a unit
    leads only into "and a second"). Anywhere else, and always after an article or a
    possessive ("a second, telephone call", "their second (WhatsApp) call"), it is an ordinal
    and a word no check reads, so it keeps the core event. Filler 13 read "a second WhatsApp
    call that lasted two minutes" with "a second" as a length, so the claim could rest on its
    time row alone. A word and its separators in the call-noun guard never share a character,
    so a run of hyphens is read in one way only. The caller row adds no second event when the
    claim already holds one.
- Where: PR #279
- Verified: `tests/test_fill_calls.py` (ordinal forms read with the event kept, on the call log
  and on an app; an ordinal anywhere but after the article refused; "displayed as" and "shown
  as" read for an account side, refused for a person, for a handle that placed the call and
  for other descriptors; an ordinal beside a tested length keeps the event however many of the
  call's words stand between, or a hyphen, which fails without the fix; the ordinal guards
  stay fast on a run of hyphens; a caller read through an ordinal
  keeps its event even when the guard reads nothing, which fails without the fix; "a second"
  read as a length only after a length word, with a comma, a dash or brackets before "call",
  and after a unit and a comma only as "and a second", which fails without the fix). `tests/test_fill*.py`, `tests/*filler*.py`,
  `tests/test_call_parties.py`, `tests/test_fewer_calls.py`: 1,235 passed. Free replay of
  stored answers (no spend), Android 13 v4 (150 claims) and iOS 15 dev (106), rerun on the
  final code: one claim changes, iOS 15 C07
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
