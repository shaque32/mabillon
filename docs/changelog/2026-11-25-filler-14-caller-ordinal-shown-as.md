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
    "shown" and "caller" are words no check reads and keep the core event, and so do "the
    contact" (a saved contact, also "the contact X", "his contact X", 'the contact entry
    "X"', 'Contact "X"', "the contact named X" or "saved as X" with no "displayed as", which
    filler 13 read as plain; also beside a contact_entry row, which may name another saved
    contact) and "the number displayed as" (a phone number), on every path: the unread
    guard reads them, and the caller row also adds the event itself and with no event allowed
    gets no caller row. So do other words left beside it (a number written after "displayed as" keeps its digits unread). A handle side
    that placed the call still gets no caller: a caller row names persons or accounts, and
    code never decides which account a handle is. The same forms also count as a plain call
    clause where a phone is one side (`_phone_is_a_side`), which sets the time range's
    parties.
  - A length whose words could be an ordinal ("a second", "and a second", "thirty-second")
    is read as a tested length only where it is part of the length a row tests, as
    `duration_range` reads it ("lasted a second" beside a row testing one second, "one minute
    and a second", "one minute, and a second" or "1 minute and a second" beside one testing 61
    seconds), and its clause
    ends right after it (a full stop, a comma, a dash, a bracket, or a word such as "and" or
    "on"; for "and a second", only a sentence's end and never after a comma, so "one
    minute, and a second." is read as a possible second call, and ", and a second on Item 1", ", and a
    second, from (212) 555-0199" or "in the evening" is a second call by ellipsis, which filler
    13 read as a length). Anywhere else it is an ordinal and a word no check reads, so it keeps the core
    event: "a second, telephone call", "for a second time", "over a second line", "two
    minutes, and a second call", "about two minutes, and a second to (212) 555-0199" (a second
    call written by ellipsis, which filler 13 also read as a length). Filler 13 read "a second
    WhatsApp call that lasted two minutes" with "a second" as a length, so the claim could rest
    on its time row alone. A length with no ordinal reading ("a one second call", "thirty
    seconds", "a 90 second WhatsApp call") reads as before, or now as a length where filler 13
    read "second" after digits as an ordinal. A missed call written with an ordinal keeps its
    missed event and gets the unread event beside it, so the testability sheet check still
    counts the missed event; so does a call whose claim already holds a model's own event.
    "another call" states an earlier call as an ordinal does and keeps the event the same
    way.
    The words no check reads are listed once each in a drop reason.
  - A stated length, spoken or in digits, is read as tested only where it is the length a
    row tests, as `duration_range` reads it, whole or in parts ("two minutes and 30 seconds",
    "a minute and a half"). Any other stated length is a part no check reads and keeps the
    core event. Before this, every spoken length with no ordinal reading was cut as tested
    whatever its value, and a digit length was read as a plain numeral whenever any row
    tested a length, so "a 30 second call that lasted about two minutes" (or "a thirty
    second call ...") beside a row testing about two minutes could rest on its time row
    alone (filler 13 too, for the spoken form). A word and its separators in the call-noun guard never share a
    character, so a run of hyphens is read in one way only. The caller row adds its unread event
    beside any other event the claim holds.
  - Three older gaps in the unread-words guard, each of which let a timing claim rest on its
    checks alone, now keep the core event: a phrase that is never plain once an app's name is
    blanked ("his last WhatsApp call") is no longer dropped unreported; "back" before a quoted
    party's name ('a call back to "Marc Garage"', also through "the party displayed as") or
    after a call verb ('called back "Marc Garage"') stays a word no check reads, while a reply
    whose message is quoted after the party ('replied to "X" on LINE, "..."') stays plain; and
    a tested length covers one stated length only ("lasted 100 seconds and a call of 100
    seconds"), also when written compactly ("a 30s call"); a saved contact is read with
    punctuation before the name ('his contact, "X"', 'the contact: "X"') or after it ('"X"
    (a contact)', '"X", his contact,'), and so is 'the contact for "X"' and a side named as a
    number by a quoted name ('the number "X"'). "the contact" followed by no name ("a contact that lasted", "the contact
    between") stays plain, and an abbreviated length ("1 min. 40 sec.") is read whole.
- Where: PR #279
- Verified: `tests/test_fill_calls.py` (ordinal forms read with the event kept, on the call log
  and on an app; an ordinal anywhere but after the article refused; "displayed as" and "shown
  as" read for an account side, refused for a person, for a handle that placed the call and
  for other descriptors, "the contact" or "the number displayed as" keeping the event; an ordinal beside a tested length keeps the event however many of the
  call's words stand between, or a hyphen, which fails without the fix; the ordinal guards
  stay fast on a run of hyphens; a caller read through an ordinal
  keeps its event even when the guard reads nothing, which fails without the fix; "a second"
  read as a length only as part of the tested length and where its clause ends, with a
  comma, a dash or brackets before "call", "for a second time", "over a second line",
  "minutes, and a second call" and "minutes, and a second to (212) 555-0199", which fail
  without the fix). `tests/test_fill*.py`, `tests/*filler*.py`,
  `tests/test_call_parties.py`, `tests/test_fewer_calls.py`: 1,349 passed. A length no row
  tests ("a 30 second", "a thirty second", "a 30-second call that lasted about two minutes")
  keeps the event, which fails without the fix; each stated length read only where a row
  tests it, spoken and in digits, whole and in parts. Free replay of
  stored answers (no spend), Android 13 v4 (150 claims) and iOS 15 dev (106), rerun on the
  final code: one claim changes, iOS 15 C07
  (gold contradicted), which gains a caller row that stays inconclusive (calls both ways in
  the window), so it is held open by a check, not only by the event. Bars 1 to 3 unchanged on
  both: 0 false Supported, 0 false Contradicted. v5 bar 4 as replayed 0 of 50 and 0 of 37;
  worst case 1 of 50 (D023) and 1 of 37 (D27), was 1 and 2. `make eval`: see the PR
  description. Cloud container, Linux x86_64, 2026-11-25.
- Open: development phones only. Older than this PR: where the model's answer holds its own
  core event, the unread-words guard adds no event of code's own, so words no check reads
  (such as an untested "30 second") are not named for the expert beside it; the claim still
  needs an expert's acceptance of that event. A fix needs a way to tell code's missed-call
  event from a model event whose range code repaired, which `Proposal` does not carry yet.
  Also older and left for a follow-up PR before the v5 run (Claude review on #279): close
  variants of a number side ('the phone number "X"', 'the number: "X"', '"X" (a number)') and
  of a saved contact ('contact Marc Garage' with no article, 'the contact with the name
  "X"', '"X", who is his contact', '"X" on WhatsApp, his contact', '"X" (a contact of
  REYES)', '"X" — his contact —', '"X", his WhatsApp contact') still read as plain. D27 ("received ... from the party displayed as") stays: the
  caller is a handle side. D023 stays: its key reads "about 2:08" as the failed 2:08 attempt,
  while the signed 8-minute "about" finds the connected 2:14 call. The time range must still
  name both parties for any caller row (iOS 15 D14 reads the form, gets none). This changes
  the code frozen at tag `validation-v5`: v5 needs a new tag and a redone freeze addendum.
- Affects: capabilities (which call claims code can test)
- Status doc: pending: section 2 table, step 5 (Assumptions): add "Filler 14 reads who placed
  a call written with an ordinal ('a second Signal call', the ordinal keeping a core event) or
  with the other side named by what the log shows ('the party displayed as "X"', an account
  side only), and reads a stated length as tested only where it is the length a row tests,
  so any other stated length ('a 30 second call that lasted about two minutes') keeps a core
  event and the claim stays Unproven (#279)." Header "Other versions": assumption filler 14.
