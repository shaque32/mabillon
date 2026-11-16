## 2026-11-16: iLEAPP and ALEAPP output importer, source kind `leapp` (contracts and schema 0.9.0) (#264)
- Changed: New importer `leapp` 0.1.0 (`core/ingest/leapp.py`, doc `docs/ingest/leapp.md`) reads
  the LAVA pair (`_lava_data.lava` and `_lava_artifacts.db`) from a zip of one iLEAPP or ALEAPP
  run's output. It reads iLEAPP `sms`, `callHistory` and `addressBook`, and ALEAPP `get_sms_mms`,
  `get_sms_mms_mms`, `get_googleMessages`, `get_calllog` and `contacts`. Every phone message takes
  the app `Native Messages`, as a UFDR does. Google Messages rows that repeat an SMS or MMS
  (same direction and text within two seconds) are skipped and counted, so no message is counted
  twice. Every other artifact is listed, with its record count, in one attention item saying a
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
  source, so "no contact" never passes on an app LEAPP read only in part.
- Where: PR #264 (branch claude/project-thread-mtq9u7)
- Verified: `tests/test_leapp.py` (10 tests, synthetic LAVA pairs from `eval/synthetic/leapp.py`)
  and the contract, ingest and coverage tests pass locally (281 passed); full `make check` runs
  in CI. A development check on the public Android 13 test phone (ALEAPP 2026.4.6-dev, cloud
  container, 2026-11-16) against Mabillon's UFDR import of the same phone: 113 of 114 text
  messages match on time to the second, direction and text (the other differs by a line break);
  all 108 calls match on time and other party; all 13 phone contacts are in the UFDR. All 123
  Google Messages messages on that phone repeat an SMS or MMS and were skipped. On the public
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
  check on LEAPP output is a judgment for review. The Google Messages match is by direction, text
  and time within two seconds, with no message id, so two identical texts sent within two seconds
  would be read as one. Rejected calls (ALEAPP type 5) are read as missed, where Mabillon's UFDR
  import of the same phone shows them as incoming.
- Affects: capabilities (a new input format, unverified); verdict path (absence check
  1.0.2 can only turn a PASS into INCONCLUSIVE); customer-facing claims (none until a scored run;
  framing stays "tested on public forensic images")
- Status doc: pending: in "Contracts and schema", change 0.8.0 to 0.9.0 and add "0.9.0 adds
  source kind `leapp` (signed by Arsh 2026-11-16, #264)". In "Importers (main)", add "iLEAPP and
  ALEAPP output `leapp` 0.1.0 (`core/ingest/leapp.py`, #264; `FORMAT_SUPPORT = "unverified"`;
  messages, calls and contacts only, every other artifact listed as not imported)". In section 8
  item 1 (Import), add "iLEAPP and ALEAPP LAVA output (unverified; checked against a UFDR on the
  public Android 13 and iOS 15 test phones, #264)". In the check versions line, "same_account and absence 1.0.1" becomes
  "same_account 1.0.1, absence 1.0.2 (#264: a record with no receiver, or a source that read only some apps, blocks PASS)". In "Real-data formats
  unverified", add LEAPP output to the formats with no real case export imported.
