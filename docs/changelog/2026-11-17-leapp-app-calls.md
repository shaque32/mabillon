## 2026-11-17: LEAPP importer reads app calls, Telegram and iLEAPP Snapchat, and fails closed on new table shapes (#268)
- Changed: Importer `leapp` 0.2.0 (`core/ingest/leapp.py`, doc `docs/ingest/leapp.md`).
  (1) App calls: ALEAPP `get_whatsapp_call_logs`, `get_Viber` and `get_line_calls`, and iLEAPP
  `whatsAppCallHistory` and `lineCalls`, are read as calls (`CALL_SPECS`). A group call, a
  direction other than incoming or outgoing, and a row whose other columns differ from what was
  checked (iLEAPP Line `Result` other than NORMAL, ALEAPP Line with a `To ID`) are imported with
  direction unknown and no sides, and flagged. (2) Two more chat tables: ALEAPP
  `get_telegramMessages` (no LEAPP conversation view, so Mabillon names its columns) and iLEAPP
  `snapchatMessages`. A row of either recovered from the database's free space or journal is
  flagged and listed as a possible copy, so a count over it is inconclusive. A Telegram row that
  is a call notice is stored as a Telegram call, not a message. (3) Fail closed: a
  table missing any column its reader uses (phone messages, calls, chat and call tables) is not
  read at all and is listed as not read, so a LEAPP version that renames a column is never read
  with that column empty. (4) Apps read in full: a call stored with neither side keeps its own
  app (not only the phone's call log) from being read in full, and any such row in the phone's
  own call table keeps the call log partial whichever app it names; on ALEAPP a call log row
  written by another app's package (a VoIP call, stored with neither side) or naming no package,
  or a call log that was not read in full, keeps every chat app from being read in full; a chat
  app counts as read in full only when one of its chat tables and every call table listed for it
  were read (a call table alone, such as Viber's, never does); ALEAPP
  WhatsApp is never read in full (a group call started outside a group chat cannot be told from
  a two-party call); and on
  iLEAPP no chat app counts
  as read in full, because the iOS 15 phone's UFDR holds WhatsApp, Viber and other app calls
  from the phone's own call records (CallKit) that iLEAPP lists under no app. Why: the plan for
  the next held-out public test (`/mnt/project-files/baker/plans/leapp-chat-apps.md`); each
  table was added only after it matched Mabillon's UFDR import of the same development phone.
- Where: PR #268
- Verified: `tests/test_leapp.py` 77 tests (23 new: app calls on each platform, Telegram recovered
  rows and call notices, iLEAPP Snapchat with a recovered row, a call log row from another app, a
  length that is not a finite number, ALEAPP WhatsApp never read in full, an outgoing call with an
  unchecked Missed value, a refused SMS table never standing for a Google Messages copy, a run
  with no call log, an unread call log entry beside a read one, a missing column on a phone, chat
  and call table, text that only starts like a call notice, a recovered call notice, a placed
  notice with no sender, an iOS FaceTime row with no sides, a call log row with no package, a
  chat app whose listed call table was not read). On the public development
  phones (cloud container, 2026-11-17, ALEAPP ed1b63d, iLEAPP fb05694; development data, not a
  scored run): Android 13 WhatsApp, Viber and Line calls 4 of 4 each match the UFDR
  on time, direction and length, and on other party where LEAPP names one; iOS 15 WhatsApp calls
  4 of 4, and Line calls 4 of 4 on time, direction and length; Telegram's 4 call notices match
  the UFDR's 4 Telegram calls on time, direction, caller and length, and 23 of its other 25 rows
  match with their sender (2 recovered rows flagged, 2 rows with no text); iOS Snapchat 19 of 21
  match with their sender (2 have no text; 3 recovered rows flagged). Every Android 13 call log
  row is `com.android.phone`. Google Messages pairs unchanged (the same 123).
  No table failed its column check on either phone. Eval numbers in the PR.
- Open: The plan's per-app list of tables that hold no messages or calls was not made, so an app
  with any other LEAPP table holding records is still never read in full; on iLEAPP the CallKit
  calls would make such a list unsafe on its own. Other app call tables (Teams, Telegram VoIP
  logs, Facebook Messenger, Instagram, Signal) did not match the UFDR one to one and stay not
  imported. ALEAPP leaves `Caller JID` empty on outgoing WhatsApp calls, so those calls have no
  sides. Format support stays unverified.
- Affects: capabilities (more apps' calls and messages read from LEAPP output; fewer apps can
  show absence on iOS)
- Status doc: pending: in "Importers (main)", the LEAPP line becomes "iLEAPP and ALEAPP output
  `leapp` 0.2.0 (`core/ingest/leapp.py`, #264, #268; `FORMAT_SUPPORT = "unverified"`; phone
  messages, calls and contacts, the chat and app call tables that matched a UFDR of the same
  public phone, every other artifact listed as not imported; a table missing a column it reads is
  not read)". If the #264 edit is not applied yet, apply it with this wording.
