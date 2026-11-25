## 2026-11-25: Filler 15: more ways to name a side as a saved contact or a phone number (#282)
- Changed: the follow-up PR #279 promised before the v5 run, for older gaps its Claude reviews
  found (filler 13 read them the same way). A claim that names the other side as a saved contact
  or a phone number states a part no check reads, so the unread-words guard
  (`core/audit/assumption_filler.py`, assumption filler 14 to 15) now keeps the core event for
  more ways to write it, and a timing or communication claim worded so can no longer rest on its
  time row alone:
  - a number side: 'the phone number "X"', 'the WhatsApp number "X"' (up to three words
    before the noun), 'the number: "X"', 'the number, "X",', 'the number for "X"', 'the number
    saved for "X"' (also listed or stored as, for or under, and "belonging to"), 'the number
    called "X"', "the number Marc Garage", "the number @handle", '"X" (a number)', '"X", a number,';
  - a saved contact: "called contact Marc Garage" (a bare "contact" before a capitalised name,
    right after a call's word, also in capitals: "PETROV CALLED CONTACT MARC GARAGE"), 'the contact with the name "X"' (also "by the name", "under the
    name"), '"X", who is (or who's) his contact', '"X" on WhatsApp, his contact', '"X" on
    WhatsApp, a contact of REYES', '"X" (a contact of REYES)', '"X" — his contact —' (also "--"
    and ";"), '"X", his saved WhatsApp Business contact'.
  Right after a quoted name any words may follow ('"X", a contact of his', '"X", his contact
  for years'), as filler 14 read them. After a capitalised word or in brackets, "a contact
  that lasted", "a contact for two minutes" and "the number of calls" stay plain, and after a
  lower-case word nothing is read as a side ("12 messages, a number the log confirms"). A
  phone written as a number stays the side a check reads ("the number (212) 555-0199"); "a
  number called PETROV" is the call's verb, and so is "to contact Marc Garage". Written inside
  a quoted message, these words stay the message's, as in filler 14. The words found are named
  in the drop reason; each kind is now listed, where filler 14 stopped at the first.
- Where: PR #282
- Verified: `tests/test_fill_calls.py`: `test_more_ways_to_name_a_contact_or_number_keep_the_event`
  (27 wordings, communication and timing; the 16 new forms fail without the fix, and the 11
  added in review, 4 of which filler 14 already caught, guard the reviews' findings; claims
  in capitals get no rows from the builder, so their wordings are tested at word level) and
  `test_a_phone_number_or_a_contact_as_a_communication_stays_plain` (14 wordings).
  `tests/test_fill*.py`, `tests/*filler*.py`, `tests/test_call_parties.py`,
  `tests/test_fewer_calls.py`: 1,438 passed with `tests/test_changelog.py`. Free replay of
  stored answers (no spend, no model calls), Android 13 v4 (150 claims) and iOS 15 dev (106):
  assumptions and verdicts identical to filler 14 on both (Android 13: 6 Supported, 8
  Contradicted, 136 Unproven; iOS 15: 2, 11, 93). `make eval`: see the PR description. Cloud
  container, Linux x86_64, 2026-11-25.
- Open: development phones only. Still older and not in this PR: where the model's answer holds
  its own core event, code adds no unread event of its own, so words no check reads are not
  named for the expert beside it (the claim still needs an expert to accept that event); a fix
  needs `Proposal` to tell code's missed-call event from a repaired model event. Close variants
  still read as plain: a lower-case name after "the contact" ("the contact marc garage"), an
  article-less '"X", contact of REYES', four or more words before the noun. This changes the
  code frozen at tag `validation-v5`, as #279 did: v5 needs a new tag and a redone freeze
  addendum.
- Affects: capabilities (which call claims code can test)
- Status doc: pending: section 2 table, step 5 (Assumptions): add "Filler 15 keeps a core event
  for more ways to name a call's other side as a saved contact or a phone number ('the phone
  number "X"', '"X" (a number)', '"X", who is his contact'), so such a claim stays Unproven
  until an expert accepts that part (follow-up to #279)." Header "Other versions": assumption
  filler 15.
