## 2026-11-16: Claims with words no check reads need an expert; a named app limits the search to that app; counts flag look-alike rows
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
    "a video call") is a word no check reads, not an app's name (CodeRabbit on #265). A spoken
    length no row tests ("over one hour", "for half an hour", "a quarter hour") is read even
    when each of its words is plain alone, and a message "on Telegram and Viber" gets the event, since a row
    searched on both apps finds it on either. Each join between two apps named next to each
    other is read: only "or" or "/" alone keeps them alternatives, so "on Telegram and on either
    Viber or WhatsApp", "Telegram, Viber or WhatsApp" and "on Telegram and SMS" (a phone's
    own messages app written by name, never "texted") get the event too, while "Telegram or
    Wickr" on a case holding Wickr Pro stays alternatives (CodeRabbit on #265). "Sent an SMS"
    or "an iMessage" searched on Native Messages, which holds both, gets the event too: no check
    reads which of the two a row was (CodeRabbit on #265). A slash keeps two apps alternatives
    only when it stands alone between them ("Telegram/Viber"), not inside a date in the gap,
    and each mention is read as the longest app name written there ("Facebook Messenger" is
    one app). A reply ("replied", "wrote back") is plain only when it is the quoted message;
    ", and REYES replied" after the quote states a second message no row tests and gets the
    event, as does a reply in a sentence of its own. A number in digits is blanked as a phone
    number only when it is one ("one of 10000 that day" is a count). "Answered" is plain only
    beside a row that tests a call's length, and a length a
    row does not test is read beside one it tests ("one minute and a quarter hour")
    (CodeRabbit on #265). "On SMS and MMS" is two kinds joined, so it gets the event, while
    "SMS or MMS" stays alternatives (CodeRabbit on #265).
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
    picks the claim's apps, and a phone's name ("the WHATSAPP PHONE") as no app, and an app
    written only inside a longer app's name as no app ("Facebook Messenger" binds no
    Facebook; a hyphen joins its words too, so "Line-Business" binds no Line, as does a line break, and the join
    scan and the unread-word scan read it the same way, so "Telegram or Line-Business" gets no event), while "by phone"
    is still one kind of contact on a case with a phone named "Phone" (CodeRabbit on #265). "Texted" on a
    case with two apps of a phone's own messages (SMS and iMessage) searches both for a message,
    as a code-made sender does, and reads no count or absence, also one the model put on SMS
    alone (Claude review and CodeRabbit on #265). A phone's own messages app written by name
    beside another app ("on Telegram or SMS") is searched too, on the case's apps that word
    names, each kind apart ("MMS" is no "SMS"), and no count or absence reads the mix; a
    claim naming a kind the case holds no app for ("on SMS or MMS" with no MMS app) is refused
    rather than read on the kinds it holds, unless an app holds several kinds; the
    sheet check counts those apps as the claim's own (CodeRabbit on #265). A claim that names
    one kind alone ("sent an iMessage") is searched on that kind's apps, never on the SMS app,
    and a row on a phone's own messages app of another kind is refused, whether code or the
    model chose it. A handle ("to @sms") names no phone's own messages app (CodeRabbit on
    #265). A message row the model put on fewer apps than the claim names ("Telegram or SMS"
    read on Telegram alone) is searched on all of them: a Telegram copy outside the range could
    otherwise fail the time check of a true claim sent by SMS. Every app the claim names
    widens it, in any case ("Telegram or viber"), but an app whose name is also a plain word
    ("an account", "a regular line"; "Accounts" and "Recents" join that list) only when
    written with a capital, and a call keeps its own reading. A row on several apps whose
    party the model gave as accounts is refused, since an account holds one app's messages,
    and so is one whose party is a handle when the claim names those apps as alternatives
    ("to @northstar on Telegram or SMS"), since a handle resolves to one account; "texted
    @northstar", spread by code over the phone's own apps, still reads the app its account is
    on (CodeRabbit on #265). Before, "wrote on
    Viber" passed on a WhatsApp message, and "no contact on Signal" was CONTRADICTED by WhatsApp
    messages. An app whose name is also a plain word ("his second line") gets no count or absence
    unless the claim writes it with a capital at a mention of its own (never inside a longer
    app's name), however the export spells the app, whether code or the model chose it
    (Greptile and CodeRabbit on #265). Nor does code bind a row, the model's on no app or
    code's own sender and the time row that copies it, to such an app written without a
    capital (`_scope_apps`, read by `_bind_named_app`, `_message_apps` and `claim_apps`):
    "wrote to REYES on his second line" searches every app, "texted REYES on his second line"
    the phone's own messages, never Line, where a true text would go unfound, and "on
    Telegram or his second line" Telegram alone (CodeRabbit on #265). Code's own sender for
    "sent an SMS" searches the SMS app only, never an iMessage store beside it, also on a case
    with Line ("an SMS on his second line"). An app the model puts a row on must be named outside
    the quoted words ('on Telegram: "... on Signal"' gives no Signal row) and outside handles,
    addresses and a phone's name ("to @sms on Telegram" gives no SMS row, "on the WHATSAPP
    PHONE ... on Telegram" searches Telegram alone: code's own sender never picks WhatsApp, and
    a WhatsApp channel the model gave is left out of its row; "on the SMS PHONE" names no kind
    of a phone's messages, so code's own sender searches every app; "on the SMS SIGNAL PHONE" on
    a case with no Signal no longer stops code's own sender; a phone named only by an app or a
    kind, such as "the SMS" or "the SIGNAL" (held by the case or not), keeps no message row,
    count or absence, from code or the model, since its name and the app read the same, and the
    claim stays unproven (a call's time stays `_call_app`'s); the phone's name inside a quote
    is the message's words, and a handle ("to @SMS") or an address is an account, not the
    phone, so it neither stops a row nor holds code's sender to that phone), and "Facebook"
    alone beside a held "Facebook Messenger" is an app the case lacks, so the claim stays
    unproven (CodeRabbit on #265).
  - Times to the second (`check_window`). A claim that states a time with seconds ("9:31:04",
    "21:14:05Z", "T21:14:05") gets no minute range, nor a whole day from a tie to an event
    ("the day after the RAID, at 2026-03-21T21:14:05Z"), so it is no longer tested by one wider than
    it states; `coverage_gap` also refuses such a claim whatever path its range took. A length
    written so ("lasted 0:12:45") is not a time of day, but one with a.m./p.m. or a zone after
    it, in any form a zone is written after a time ("for 09:31:04 UTC", "09:31:04 (UTC)",
    "09:31:04 Eastern Time", "09:31:04-04:00"), is. A communication, timing or count claim that quotes more than one message
    gets the expert-only event whenever code keeps a row for it and the claim's template allows
    an event; where it allows none, the claim is refused, and with no row there is nothing to
    add the event to. Either way the claim stays unproven: a check finds a quote's words inside a longer message, so one record ("ok, thanks")
    may pass the rows for both 'wrote "ok" and then "thanks"', and code cannot show at fill time
    that two quotes are two records. A claim with one quoted message is unchanged. A quote that matches
    a person's or an account's name is left out as a party only where the claim writes it as
    one: in brackets, after "to", "as", "user", "account" and the like, or as the subject at the
    start of a sentence or clause, with a verb of saying after it ('On November 6, 2022,
    "ThisIs DfirTwo" asked'); 'wrote to REYES: "Petrov"', 'and then, "Petrov".' and 'and
    then, "Petrov" on Telegram.' are messages. Quoted words are never read as unread words (CodeRabbit on #265). For the readers
    that blank quoted words with `_unquoted` (the seconds guards, stated ranges, the time-of-day,
    month and year scans of coverage gaps, unread words and the app readers), a time, an app or
    any other word inside a quote that a line break wraps is the quote's, not the claim's:
    `_unquoted` now masks a wrapped quote as one (CodeRabbit on #265). A date, a year, a time or a weekday
    inside quoted words is never one the claim states (CodeRabbit on #265): `check_window` no
    longer takes a quoted date as a stated day ('On March 12, 2026, PETROV wrote "see you March
    11, 2026"' let a range start on March 11), and refuses a model's range words that cross a
    quote's edge ('March 11, 2026".') so code reads the claim's own date; a date with no year
    never takes a year written only in a quote ('On March 12, ... "back in 2025"' read March 12,
    2025), in `stated_windows`, `stated_part_day`, the open range of no contact and
    `check_window` (`_stated_years`); and a quoted weekday ("See you Monday, March 11") is never
    judged against the claim's year. Some scans still read the raw claim, quotes included, and
    each only refuses: the date scans of coverage gaps and of a tie to an event
    (`date_mentions`), so a quoted date with no time range kept leaves the claim unproven, and
    the numeric-date checks in `stated_windows` and `stated_part_day`, so a quoted numeric date
    ("03/13/2026") builds no range.
  - Look-alike rows in a count (`core/audit/checks/count.py`, `look_alike`, count 1.3.0, then
    1.3.1 on merging #264's count 1.2.1 guard, which it keeps). Rows
    that repeat an earlier row's words within 2 seconds, on any app and from any sender, make
    the count inconclusive, with a note for the expert. On the Android 13 development phone a
    chat of 12 messages is stored as 17 rows, and each text is held twice (the SMS store and
    Google Messages), one copy often with the number written another way or no sender, so a
    true "exactly 12" failed. App, sender and direction are left out of the match on purpose
    (CodeRabbit on #265): a look-alike only holds a count open, and only when merging the
    look-alikes could change the answer ("at least 5" over 10 rows with 2 look-alikes still
    passes; `look_alikes_matter`, Claude review on #265). A message each way ("exchanged") that
    rests on a look-alike pair alone is held open too (`each_way_rests_on_look_alikes`,
    CodeRabbit on #265), but two copies of one side's own message still hold a message from
    that side. Look-alikes are read over both sides before a count picks one side's messages
    (`fewest_messages`, 1.3.1), so "A sent at least 1" over A's "ok" and B's "ok" a second
    apart is held open: both rows may be B's message. A count of one side's messages also reads
    look-alikes beside rows that name no receiver, so "A sent exactly 1" over A's "ok" and "hi"
    no longer fails when B's "ok" a second later names no receiver; the other side's rows that
    hold such a count open are cited beside the counted rows. A message each way reads those
    rows too, so "exchanged at least 2" over A's "ok", B's "ok" a second later to no one
    named, and B's "sure" is held open, and B's row is cited, though not beside a fail on the
    counted rows. A look-alike whose every row names one side as sender stays that side's
    message, so A's copy with no receiver never takes A's message away. Only the rows beside
    the side that may hold no message are cited, and the note for the expert is left off a
    fail on the counted rows. A count of both sides' messages also reads look-alikes beside
    the rows that name no sender or no receiver: one such "ok" between two counted "ok" rows 4
    seconds apart may join them into one message, so "at least 3" over them is held open
    (CodeRabbit on #265).
  - Testability sheet check (`core/audit/testability.py`, `eval/run_pipeline.py`, step 0.3.0).
    An app code binds from the claim's own words (`LocalAssumptionFiller.claim_apps`) is not
    counted as naming more than the signed sheet, as a party the claim names is not. Without
    this, "texted" bound to SMS read as a mismatch on case01 C12. Other apps a try names still
    count, and so does a plain-word app the claim writes without a capital ("his recents"),
    which code binds no row to. The step's version goes to 0.3.0, so verify-bundle notes a 0.2.0 try as not re-run
    instead of failing it on filler 12's new rows (CodeRabbit on #265).
- Where: PR #265 (after #263 and #264, both merged; main merged in, with #267 and #268)
- Verified: new tests in `tests/test_assumption_filler.py` (plain claims get no event, twelve
  unread tails, a named app bound, an app or email the case lacks, seconds and lengths, six
  absence wordings, a plain-word app, short names and handles, texted on two apps, spans) and
  `tests/test_count_look_alike.py`; each test for a review finding fails on the code before
  its fix. The filler, fill, replay, override, check and LEAPP suites pass locally after merging
  main, the full local test run passes (4,702 passed, 9 skipped, before the last round of
  fixes; the filler, check, count, fill, LEAPP, replay, override, testability and timeline
  suites pass after it), and
  `make eval-model-free` on case01 is unchanged (accuracy 1.00, false supported 0). Class batteries of new wordings with wrong
  answers on the Android 13 phone (messages, calls, counts and timing): no false SUPPORTED;
  only the three true base claims are SUPPORTED. A replay of stored v4 model answers on
  Android 13, iOS 15 and Android 12 (no model call; results in project files only) leaves
  every check outcome unchanged and adds the expert-only event to 20 claims (4 of them false
  claims in the v4 answer key; iOS 15 B32, "had four calls" with no count row, after the
  Claude review; Android 13 D069, "received a video call", true in the key, after CodeRabbit:
  the call log keeps no kind of call, so it now waits for an expert; iOS 15 C07, "placed a
  second Signal call", after the fixes on the merge with main: "a second" is read as a length
  no row tests, and the ordinal is one no check reads); one message-only absence that was
  inconclusive is now refused.
  On case01, C11 (gold contradicted, its time check fails) also gains the event. `make check` runs on GitHub CI.
- Open: the plain-word list is blunt in both directions. A true claim with an unlisted word
  loses the code-checked path and waits for an expert; a word on the list that carries meaning
  in some sentence still passes. These are tests of code's guards, not of the model: a model
  can still propose something unexpected that code accepts. Look-alike rows within 2 seconds
  that are really two messages make a count inconclusive, and the rows chain, so a long run of
  copies is one group. Not fixed here (CodeRabbit on #265, outside this change): the Axiom
  importer labels iMessage rows with app "SMS" while the Cellebrite importer keeps "iMessage",
  so on an Axiom case an SMS-only claim can rest on an iMessage row; settling one label at
  import is a follow-up. The v5 phones use the LEAPP importer.
- Affects: verdicts (fewer code-checked SUPPORTED; claims naming an app the case lacks, or
  naming one kind of contact in an absence, go untested; counts over look-alike rows go
  inconclusive); customer-facing claims: none. No privacy or network change.
- Status doc: pending: header "Other versions": filler 12, count 1.3.1 (this entry's 1.3.0 plus #264's 1.2.1 guard; it replaces #264's count 1.2.1), testability step 0.3.0. Section 2, step 5
  (Assumptions): add "a communication, timing or count claim with words no check reads gets a
  code-made event that only an expert can carry; a message row gets the app the claim names;
  a time stated to the second gets no minute range". Section on the count check: add "since
  1.3.0, rows repeating another row's words within 2 seconds, on any app and from any sender,
  make the count inconclusive when merging them could change the answer; since 1.3.1 they are
  read over both sides before a count of one side's messages".
