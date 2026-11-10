## 2026-11-10: The filler reads a text message's number on no app, and bare digits as a WhatsApp id
- Changed: two readings in `core/audit/assumption_filler.py`, both found on the Android 12
  practice run, where they left claims untested.
  - A number the model writes on no app ("unknown", or "SMS" or "text" when the case has no
    app by that name) in a claim about a text message ("text message", "texted", "SMS"; not
    "text" alone, and not when the claim also names a call) is read on the phone's own
    messaging app (`_text_message_account`). Only when the case has exactly one app of a
    phone's own messages that holds threads (Android or iOS "Native Messages", or "SMS"), the
    claim names no other app, and the template reads one quoted message (sender, record_time,
    meaning). The search's channels are then that app, so a quoted text found on another app
    is never read as sent by someone else.
  - In a text-message claim such a number is refused, never read in the call log ("unknown"),
    for a count or an absence, when the case holds two such apps or none, or when the claim
    names another app. Before this, "never texted (212) 555-0199" with the model's "unknown"
    was searched in the call log alone and could pass on texts it never searched.
  - Bare digits ("19195794674") on an app the claim names match an account whose WhatsApp id
    is exactly those digits ("19195794674@s.whatsapp.net"), and then every account on that app
    with the same number (ruling R6) (`_jid_number`, in `_accounts`). Whole digits only: the
    number without its country code, or a longer run, matches nothing. A group (`@g.us`) or
    linked id (`@lid`) is no number. Digits that are one account's whole id and another's
    WhatsApp number are refused.
  - No identity is linked and no account merged; a name never picks an app. FILLER_VERSION is
    not bumped here (the lead bumps once for the batch).
- Where: branch fix/accounts, not yet in a PR
- Verified: `tests/test_fill_accounts.py` (22 tests, synthetic case01): the reading, the call
  log never searched for a text, count and absence refused, another app named, two phone
  message apps, a call and a text, "the text" of a message, a model channel that is not the
  app, whole digits only, an unnamed app, group and linked ids, digits on two accounts.
  Replay of the stored practice answers (no model call), 2026-11-10: Android 12 A14 now gets
  sender, record_time and meaning (sender and time checks pass) and A16 a person_identity;
  no other claim on either phone changed. `make check` result in the branch report.
- Open: which apps count as a phone's own text messages is a judgment call, written for a
  ruling in the rulings note for this area (project files, validation fix round); the conservative reading is implemented. Bare digits
  against a "+"-written number (iOS 15 B12) and a contact entry on a number no account of the
  named app holds (B15) are left refused, also in the rulings note for this area (project files, validation fix round).
- Affects: capabilities (more claims about text messages and WhatsApp numbers can be tested;
  fewer absences are read on the call log alone). No privacy, network or verdict-rule change.
- Status doc: pending: in the "5. Assumptions" row, after "one number written several ways
  as one party", add "a text message's number written on no app on the case's one app of a
  phone's own messages (never in the call log, never for a count or an absence), and bare
  digits as the WhatsApp id holding exactly those digits".
