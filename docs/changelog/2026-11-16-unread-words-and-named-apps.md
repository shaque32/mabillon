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
    still read, Greptile on #265).
  - The app the claim names (`_bind_named_app`). A message row the model leaves on no app gets
    the app the claim names from code ("on Viber", "texted" is the phone's own messages app).
    A claim naming an app the case does not hold, or an email, gets no such row and stays
    unproven. An absence that names one kind of contact ("did not text", "never messaged on
    Telegram", "by telephone") is refused whatever its app, since the absence check reads
    messages and calls alike. Before, "wrote on Viber" passed on a WhatsApp message, and "no contact on Signal" was
    CONTRADICTED by WhatsApp messages. An app whose name is also a plain word ("his second
    line") gets no count or absence unless the claim writes it with a capital, whether code or
    the model chose it (Greptile on #265).
  - Times to the second (`check_window`). A claim that states a time with seconds ("9:31:04")
    gets no minute range, so it is no longer tested by one wider than it states.
  - Look-alike rows in a count (`core/audit/checks/count.py`, `look_alike`, count 1.3.0). Rows
    that repeat an earlier row's app, sender, direction and words within 2 seconds make the
    count inconclusive, with a note for the expert. On the Android 13 development phone a chat
    of 12 messages is stored as 17 rows, and each text is held twice (the SMS store and Google
    Messages), so a true "exactly 12" failed.
  - Testability sheet check (`core/audit/testability.py`, `eval/run_pipeline.py`). An app code
    binds from the claim's own words (`LocalAssumptionFiller.claim_apps`) is not counted as
    naming more than the signed sheet, as a party the claim names is not. Without this, "texted"
    bound to SMS read as a mismatch on case01 C12. Other apps a try names still count.
- Where: branch claude/project-thread-kpsvpk (PR to come), on top of #263
- Verified: new tests in `tests/test_assumption_filler.py` (plain claims get no event, seven
  unread tails, a named app bound, an app or email the case lacks, seconds, four absence
  wordings, a plain-word app) and `tests/test_count_look_alike.py`. The filler, fill, replay,
  override and check suites pass locally (1,020). Class batteries of new wordings with wrong
  answers on the Android 13 phone (messages, calls, counts and timing): no false SUPPORTED;
  only the three true base claims are SUPPORTED. A replay of stored v4 model answers on
  Android 13, iOS 15 and Android 12 (no model call; results in project files only) leaves
  every check outcome unchanged and adds the expert-only event to 17 claims (4 of them false
  claims in the v4 answer key); one message-only absence that was inconclusive is now refused.
  On case01, C11 (gold contradicted, its time check fails) also gains the event. `make check` runs on GitHub CI.
- Open: the plain-word list is blunt in both directions. A true claim with an unlisted word
  loses the code-checked path and waits for an expert; a word on the list that carries meaning
  in some sentence still passes. These are tests of code's guards, not of the model: a model
  can still propose something unexpected that code accepts. Look-alike rows within 2 seconds
  that are really two messages make a count inconclusive.
- Affects: verdicts (fewer code-checked SUPPORTED; claims naming an app the case lacks, or
  naming one kind of contact in an absence, go untested; counts over look-alike rows go
  inconclusive); customer-facing claims: none. No privacy or network change.
- Status doc: pending: header "Other versions": filler 12, count 1.3.0. Section 2, step 5
  (Assumptions): add "a communication, timing or count claim with words no check reads gets a
  code-made event that only an expert can carry; a message row gets the app the claim names;
  a time stated to the second gets no minute range". Section on the count check: add "since
  1.3.0, rows repeating another row's app, sender, words and time within 2 seconds make the
  count inconclusive".
