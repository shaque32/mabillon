## 2026-11-16: Claims with words no check reads, or a named app, can no longer pass on checks alone; counts flag look-alike rows
- Changed: four fixes from the v5 failure hunt (plan in project files, no model calls), each a
  class found by feeding plausible wrong model answers and new claim wordings through the
  filler and checks on the public development phones.
  - Words no check reads (`core/audit/assumption_filler.py`, `unread_words`,
    `_add_unread_event`, FILLER_VERSION 12). A communication, timing or count claim whose words
    hold anything outside a list of plain words (who, when, which app, how long, how many)
    gets one more core event assumption, made by code, that only an expert can carry. Before,
    "never replied", "sent a photo", "forwarded", "the last message", "read", "edited", "twice",
    "while driving", "on a second phone" or "three minutes after the call" passed on the
    sender and time checks alone and was SUPPORTED with no human. Now such a claim stays
    UNPROVEN until an expert accepts the event. A time range's own words are skipped only when they hold
    nothing more than dates and times ("On March 12, 2026, while driving" kept as a range is
    still read, Greptile on #265), and "PETROV read: ..." is a person's act, not a message's
    words (CodeRabbit on #265). After the Claude review on #265: the words of a call ("called",
    "after a Telegram call", "during a call"), of a count ("two", "exactly", "times") and of a
    length ("lasted", "about two minutes") are plain only beside a kept row that tests a call,
    a count or a call's length, and "saved as" only beside a contact entry; "reading",
    "showed" and "displayed" are a person's acts except in "a message reading \"...\"", "the
    records show" and "displayed as"; an account named like a plain word ("Photo") hides that
    word only where the claim writes it as a name. A count or a length written in digits ("one of
    2 messages", "over 2 hours") is read as its spoken form is, and "video" ("sent a video",
    "a video call") is a word no check reads, not an app's name (CodeRabbit on #265).
  - The app the claim names (`_bind_named_app`). A message row the model leaves on no app gets the
    app the claim names from code ("on Viber", "texted" is the phone's own messages app). A claim
    naming an app the case does not hold, or an email, gets no such row and stays unproven, also
    beside an app it holds ("on Telegram and Signal", CodeRabbit on #265). A count or
    absence the model put on fewer apps than the claim names ("no contact on Telegram or Viber"
    read on Telegram alone) is refused (CodeRabbit on #265). An absence that names
    one kind of contact ("did not text", "never messaged on Telegram", "by telephone") is refused
    whatever its app, since the absence check reads messages and calls alike. The missing-app
    guard runs on every app row, also those the model scoped; it knows messaging, social and
    mail apps beyond the calling apps ("no contact on TikTok"), reads a short name of a held
    app as that app ("Wickr" for "Wickr Pro") and a handle ("@viber") as no app, also when it
    picks the claim's apps, and a phone's name ("the WHATSAPP PHONE") as no app, while "by phone"
    is still one kind of contact on a case with a phone named "Phone" (CodeRabbit on #265). "Texted" on a
    case with two apps of a phone's own messages (SMS and iMessage) searches both for a message,
    as a code-made sender does, and reads no count or absence, also one the model put on SMS
    alone (Claude review and CodeRabbit on #265). Before, "wrote on
    Viber" passed on a WhatsApp message, and "no contact on Signal" was CONTRADICTED by WhatsApp
    messages. An app whose name is also a plain word ("his second line") gets no count or absence
    unless the claim writes it with a capital, whether code or the model chose it (Greptile on
    #265).
  - Times to the second (`check_window`). A claim that states a time with seconds ("9:31:04",
    "21:14:05Z", "T21:14:05") gets no minute range, so it is no longer tested by one wider than
    it states. A length written so ("lasted 0:12:45") is not a time of day.
  - Look-alike rows in a count (`core/audit/checks/count.py`, `look_alike`, count 1.3.0, then 1.3.1 on merging #264's
    count 1.2.1 guard, which it keeps). Rows
    that repeat an earlier row's words within 2 seconds, on any app and from any sender, make
    the count inconclusive, with a note for the expert. On the Android 13 development phone a
    chat of 12 messages is stored as 17 rows, and each text is held twice (the SMS store and
    Google Messages), one copy often with the number written another way or no sender, so a
    true "exactly 12" failed. App, sender and direction are left out of the match on purpose
    (CodeRabbit on #265): a look-alike only holds a count open, and only when merging the
    look-alikes could change the answer ("at least 5" over 10 rows with 2 look-alikes still
    passes; `look_alikes_matter`, Claude review on #265). A message each way ("exchanged") that
    rests on a look-alike pair alone is held open too (`each_way_rests_on_look_alikes`,
    CodeRabbit on #265).
  - Testability sheet check (`core/audit/testability.py`, `eval/run_pipeline.py`, step 0.3.0).
    An app code binds from the claim's own words (`LocalAssumptionFiller.claim_apps`) is not
    counted as naming more than the signed sheet, as a party the claim names is not. Without
    this, "texted" bound to SMS read as a mismatch on case01 C12. Other apps a try names still
    count. The step's version goes to 0.3.0, so verify-bundle notes a 0.2.0 try as not re-run
    instead of failing it on filler 12's new rows (CodeRabbit on #265).
- Where: PR #265 (on top of #263)
- Verified: new tests in `tests/test_assumption_filler.py` (plain claims get no event, twelve
  unread tails, a named app bound, an app or email the case lacks, seconds and lengths, six
  absence wordings, a plain-word app, short names and handles, texted on two apps, spans) and
  `tests/test_count_look_alike.py`; each test for a review finding fails on the code before
  its fix. The filler, fill, replay, override and check suites pass locally (1,784), and
  `make eval-model-free` on case01 is unchanged (accuracy 1.00, false supported 0). Class batteries of new wordings with wrong
  answers on the Android 13 phone (messages, calls, counts and timing): no false SUPPORTED;
  only the three true base claims are SUPPORTED. A replay of stored v4 model answers on
  Android 13, iOS 15 and Android 12 (no model call; results in project files only) leaves
  every check outcome unchanged and adds the expert-only event to 19 claims (4 of them false
  claims in the v4 answer key; iOS 15 B32, "had four calls" with no count row, after the
  Claude review; Android 13 D069, "received a video call", true in the key, after CodeRabbit:
  the call log keeps no kind of call, so it now waits for an expert); one message-only absence that was inconclusive is now refused.
  On case01, C11 (gold contradicted, its time check fails) also gains the event. `make check` runs on GitHub CI.
- Open: the plain-word list is blunt in both directions. A true claim with an unlisted word
  loses the code-checked path and waits for an expert; a word on the list that carries meaning
  in some sentence still passes. These are tests of code's guards, not of the model: a model
  can still propose something unexpected that code accepts. Look-alike rows within 2 seconds
  that are really two messages make a count inconclusive.
- Affects: verdicts (fewer code-checked SUPPORTED; claims naming an app the case lacks, or
  naming one kind of contact in an absence, go untested; counts over look-alike rows go
  inconclusive); customer-facing claims: none. No privacy or network change.
- Status doc: pending: header "Other versions": filler 12, count 1.3.1 (this entry's 1.3.0 plus #264's 1.2.1 guard; it replaces #264's count 1.2.1), testability step 0.3.0. Section 2, step 5
  (Assumptions): add "a communication, timing or count claim with words no check reads gets a
  code-made event that only an expert can carry; a message row gets the app the claim names;
  a time stated to the second gets no minute range". Section on the count check: add "since
  1.3.0, rows repeating another row's words within 2 seconds, on any app and from any sender,
  make the count inconclusive when merging them could change the answer".
