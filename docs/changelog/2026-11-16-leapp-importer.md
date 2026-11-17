## 2026-11-16: iLEAPP and ALEAPP output importer, source kind `leapp` (contracts and schema 0.9.0) (#264)
- Changed: New importer `leapp` 0.1.0 (`core/ingest/leapp.py`, doc `docs/ingest/leapp.md`) reads
  the LAVA pair (`_lava_data.lava` and `_lava_artifacts.db`) from a zip of one iLEAPP or ALEAPP
  run's output. It reads iLEAPP `sms`, `callHistory` and `addressBook`, and ALEAPP `get_sms_mms`,
  `get_sms_mms_mms`, `get_googleMessages`, `get_calllog` and `contacts`. Every phone message takes
  the app `Native Messages`, as a UFDR does. Google Messages rows that repeat an SMS or MMS
  (same direction, text, number of attachments and other party within two seconds; each SMS or
  MMS matched at most once) are skipped and counted, so a repeat is not counted twice (one that
  cannot be told for sure is kept and listed as a possible copy, so a count over it is
  inconclusive). Every other artifact is listed, with its record count, in one attention item saying a
  claim on it is not tested and a record missing from it is not shown to be absent. A draft,
  queued or failed message, and a call type other than incoming, outgoing, missed or rejected,
  is imported with direction unknown and flagged. `core/ingest/pick.py` routes a `.zip` holding
  a LEAPP manifest here; every other `.zip` stays a UFDR. Contracts and schema 0.9.0 add source
  kind `leapp` (signed by Arsh 2026-11-16, `PROPOSED_CHANGES.md`). Why: the next held-out public
  test (an iOS 17 and Android 14 pair) is published as raw extractions with no Cellebrite or
  AXIOM export, and LEAPP is the free, open-source way to read them. The absence check 1.0.2
  (`core/audit/checks/absence.py`, Greptile on #264) now treats a message or call that records
  no receiver as unplaced, the way it already treated one with no sender: LEAPP names the other
  side of a phone's incoming SMS and call but often not the phone's own line, and such a record
  was silently left out, so "no contact" could pass with an incoming text from the other person
  inside the window. It now makes the check inconclusive. The zip's manifest and database are
  refused when they unpack past 256 MB and 8 GB. The device row takes the phone's time zone
  (only when every zone its tables recorded is the same one; otherwise none, with an attention
  item) and OS version from LEAPP's device tables. Fifteen chat-app tables (WhatsApp, Signal,
  Telegram, Instagram, Snapchat, Viber, Discord, Facebook Messenger, Kik, TikTok, GroupMe) are
  read through LEAPP's own conversation view, each only after matching Mabillon's UFDR import of
  the same public phone record by record; senders come only from id columns that matched, never
  from display names. The import lists the apps it read in full (`apps_read_in_full`), and the
  absence check treats every other app, and a search on every channel, as not covered by that
  source, so "no contact" never passes on an app LEAPP read only in part. Greptile's second
  review on #264 found three more ways an import with a missing side could pass a check, all
  fixed. (1) A LEAPP chat row names a sender only, and the phone's own message in a chat often
  names neither side, so a count over such rows counted zero and "at most one" passed. Count
  1.2.1, time 1.1.1 and weekday 1.0.3 now treat a message or call that names no sender or no
  receiver, with a party on it or in a chat with one, as possibly between the parties. It keeps
  a count's "at most" and "exactly" from passing, a time check from failing and a weekday check
  from passing. The absence check reads the same chat rows as unplaced. (2) An MMS's Cc and Bcc
  are receivers too, so a person copied on one is no longer lost. (3) "UTC" is a zone, and a
  phone that recorded a zone value the reader cannot read gets no zone, with an attention item,
  so a second zone is never silently dropped. CodeRabbit's review on #264 found ten more, all
  fixed. (1) The Google Messages copy match now compares the other party too (numbers by their
  digits, with or without a country code; emails without case), so "OK" from Bob is never taken
  for a copy of "OK" from Alice, and each SMS or MMS stands for at most one Google Messages
  message, paired nearest in time first. Attachments cannot be compared one to one across the
  two stores (their file names differ), so a message with attachments is paired only when the
  pairing is unambiguous; otherwise every row involved is kept and listed as a possible copy. A
  sent message's other party comes from the chat's number, or from the phone's contacts for a
  chat named by display name; the chat's one sender alone only marks a possible copy. Two
  numbers that both carry a country code match only when equal. When the other party cannot be compared (a sent message whose chat has no single
  sender, or a group MMS), the message is kept, flagged `may_be_same_as_an_sms_or_mms_message`,
  and both rows are listed as possible copies, so a count over them is inconclusive. The count
  check's wording for such rows now says "listed by the import as a possible copy". (2) The
  absence check no longer counts a third party's message with no receiver as possible contact.
  (3) With one party named, the weekday and time checks treat a message from anyone that names
  no receiver as possibly to that party. (4) Count and time list the rows that held them open in
  their record ids. (5) A table counts as read only when it was read through: a missing table, or
  a chat view naming no text, direction or time column, is listed with `read_failed`, raises
  `leapp_artifact_not_read`, and leaves its app out of `apps_read_in_full`; the phone's own
  messages or calls count as read in full only when all their tables that may hold records (a
  missing count counts as may) were read, compared by manifest entry.
  (6) A run whose manifest does not say `Complete` (LEAPP writes `In Progress` when a run starts)
  is fidelity `unknown`, not `full_extraction`. (7) The count check's "at most" and "exactly"
  need every app counted to be read in full in that source (`apps_read_in_full`); otherwise they
  are inconclusive. (8) The report's limitations name the LEAPP reader for a LEAPP import, not
  the UFDR reader.
- Where: PR #264 (branch claude/project-thread-mtq9u7)
- Verified: `tests/test_leapp.py` (46 tests, synthetic LAVA pairs from `eval/synthetic/leapp.py`)
  and the contract, ingest and coverage tests pass locally (281 passed); full `make check` runs
  in CI. A development check on the public Android 13 test phone (ALEAPP 2026.4.6-dev, cloud
  container, 2026-11-16) against Mabillon's UFDR import of the same phone: 113 of 114 text
  messages match on time to the second, direction and text (the other differs by a line break);
  all 108 calls match on time and other party; all 13 phone contacts are in the UFDR. All 123
  Google Messages messages on that phone repeat an SMS or MMS and were skipped; after the
  party-aware match (2026-11-17, same container) the same 123 are skipped, with the same pairs,
  and none is flagged as a possible copy. On the public
  iOS 15 phone (iLEAPP 2026.4.7-dev, same day and machine): all 37 text messages and all 22 calls
  match the UFDR import, and all 13 contact numbers are in it. Each skipped Google Messages
  message is listed with the SMS or MMS it matched (`leapp.google_messages_skipped` in the
  coverage record and the import's audit log entry), so another reader can re-check each pair.
  These phones are development data, not a scored run.
- Open: Format support is unverified: no case data has been read with it, and every import says
  so. Chat apps outside the checked list, app calls, the device model, and forwarded or quoted
  marks are not read. LEAPP stores whole seconds, so a timing claim
  closer than a second needs the phone's own value. A file system run with no profile is
  `full_extraction` for the tables LEAPP parsed; whether that is the right fidelity for an absence
  check on LEAPP output is a judgment for review. The Google Messages match is by direction, text,
  attachments, other party and time within two seconds, with no message id, so two identical
  texts to the same person within two seconds, one of them only in Google Messages, would be read
  as one. A photo only in Google Messages, sent by the same person with the same text within two
  seconds of an MMS photo whose own Google Messages copy is missing, would be read as that MMS.
  A number written with a national trunk prefix ("07911...") never matches the same number
  with a country code; such a copy is kept and listed as a possible copy, so a count over it is
  inconclusive rather than double. Rejected calls (ALEAPP type 5) are read as missed, where Mabillon's UFDR
  import of the same phone shows them as incoming.
- Affects: capabilities (a new input format, unverified); verdict path (absence 1.0.2, count
  1.2.1, time 1.1.1 and weekday 1.0.3 can only turn a PASS or a FAIL into INCONCLUSIVE against
  main; case01 model-free verdicts unchanged); customer-facing claims (none until a scored run;
  framing stays "tested on public forensic images")
- Status doc: pending: in "Contracts and schema", change 0.8.0 to 0.9.0 and add "0.9.0 adds
  source kind `leapp` (signed by Arsh 2026-11-16, #264)". In "Importers (main)", add "iLEAPP and
  ALEAPP output `leapp` 0.1.0 (`core/ingest/leapp.py`, #264; `FORMAT_SUPPORT = "unverified"`;
  messages, calls and contacts only, every other artifact listed as not imported)". In section 8
  item 1 (Import), add "iLEAPP and ALEAPP LAVA output (unverified; checked against a UFDR on the
  public Android 13 and iOS 15 test phones, #264)". In the check versions line, "same_account and absence 1.0.1" becomes
  "same_account 1.0.1, absence 1.0.2 (#264: a record with no receiver, or a source that read only some apps, blocks PASS)", and count, time and weekday become 1.2.1, 1.1.1 and 1.0.3 ("#264: a message or call that names no sender or no receiver holds them open; count's at most and exactly need every counted app read in full"). In "Real-data formats
  unverified", add LEAPP output to the formats with no real case export imported.
