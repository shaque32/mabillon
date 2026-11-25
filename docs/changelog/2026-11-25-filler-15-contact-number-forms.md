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
    called "X"', "the number Marc Garage", "the number @handle", '"X" (a number)', '"X", a number,',
    'the numbers "X" and "Y"', "called number Marc Garage";
  - a saved contact: "called contact Marc Garage" (a bare "contact" before a capitalised name,
    right after a call's or a message's word, as in "texted contact" or "a message to contact",
    also in capitals: "PETROV CALLED CONTACT MARC GARAGE"), 'the contact with the name "X"'
    (also "by the name", "under the name"), '"X", who is (or who's) his contact', '"X" on
    WhatsApp, his contact' (the name in double or single quotes), '"X" on WhatsApp at 9:14
    p.m., his contact', '"X" on WhatsApp, a
    contact of REYES', '"X" (a contact of REYES)', '"X" (a contact with whom he spoke)', '"X" —
    his contact —' (also "--" and ";"), '"X", his saved WhatsApp Business contact'.
  Right after a quoted name any words may follow ('"X", a contact of his', '"X", his contact
  for years', '"X" (a contact with whom he spoke)'), as filler 14 read them. Later in a sentence
  with a party's quoted name, or in brackets elsewhere, "a contact that lasted", "a contact for
  two minutes" and "the contact between" stay plain, and a "number" must end its phrase, so a
  count's "number" stays plain ("(a number the log shows)"). With no quoted name before them,
  these words are the communication or the count, as in filler 14: "REYES, a contact on
  WhatsApp" (the checks read REYES), "4 times on WhatsApp, a number the log shows", "which was
  the number of calls", "12 messages, a number the log confirms". A quoted message is not a
  name ('wrote "ok" to REYES, his contact'), a count's "number" right after a quoted name stays
  plain ('"X", a number of times'), and a later side must stand in the quote's sentence (a dot
  after "p.m.", "U.S." or "Mr." does not end it). A saved
  contact stays unread as the caller too ("his contact called PETROV", as in filler 14), and
  "called the number called Marc Garage" names the number. A
  phone written as a number stays the side a check reads ("the number (212) 555-0199"); "a
  number called PETROV" is the call's verb, and so is "to contact Marc Garage". Written inside
  a quoted message, these words stay the message's, as in filler 14. The words found are named
  in the drop reason; each kind is now listed, where filler 14 stopped at the first.
- Where: PR #282
- Verified: `tests/test_fill_calls.py`: `test_more_ways_to_name_a_contact_or_number_keep_the_event`
  (35 wordings, communication and timing; 27 fail on filler 14, and the other 8, which filler
  14 already caught, guard against regressions the reviews found; claims
  in capitals or with a second time get no rows from the builder, so those wordings are
  tested at word level, in `test_contact_as_a_communication_is_plain`) and
  `test_a_phone_number_or_a_contact_as_a_communication_stays_plain` (31 wordings), and
  `test_a_side_named_two_ways_is_named_once`.
  `tests/test_fill*.py`, `tests/*filler*.py`, `tests/test_call_parties.py`,
  `tests/test_fewer_calls.py`: 1,472 passed with `tests/test_changelog.py`. Free replay of
  stored answers (no spend, no model calls), Android 13 v4 (150 claims) and iOS 15 dev (106):
  assumptions and verdicts identical to filler 14 on both (Android 13: 6 Supported, 8
  Contradicted, 136 Unproven; iOS 15: 2, 11, 93). `make eval`: CI on the PR's final head, numbers in the PR description. Cloud
  container, Linux x86_64, 2026-11-25.
- Open: development phones only. Still older and not in this PR: where the model's answer holds
  its own core event, code adds no unread event of its own, so words no check reads are not
  named for the expert beside it (the claim still needs an expert to accept that event); a fix
  needs `Proposal` to tell code's missed-call event from a repaired model event. Close variants
  still read as plain: a lower-case name after "the contact" ("the contact marc garage"), an
  article-less '"X", contact of REYES', four or more words before the noun, an unquoted name
  before the noun ("Marc Garage, his contact", which "REYES, a contact" makes ambiguous), and
  words after the noun later in a sentence ('"X" on WhatsApp, his contact for years', '"X" on
  WhatsApp, the number that he saved'); each such claim still needs its other unread words
  to hold the event. This changes the
  code frozen at tag `validation-v5`, as #279 did: v5 needs a new tag and a redone freeze
  addendum.
- Affects: capabilities (which call claims code can test)
- Status doc: pending: section 2 table, step 5 (Assumptions): add "Filler 15 keeps a core event
  for more ways to name a call's other side as a saved contact or a phone number ('the phone
  number "X"', '"X" (a number)', '"X", who is his contact'), so such a claim stays Unproven
  until an expert accepts that part (follow-up to #279)." Header "Other versions": assumption
  filler 15.
