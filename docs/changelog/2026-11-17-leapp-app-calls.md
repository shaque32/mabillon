## 2026-11-17: LEAPP importer reads app calls, Telegram and iLEAPP Snapchat, and fails closed on new table shapes (#268)
- Changed: Importer `leapp` 0.2.0 (`core/ingest/leapp.py`, doc `docs/ingest/leapp.md`).
  (1) App calls: ALEAPP `get_whatsapp_call_logs`, `get_Viber` and `get_line_calls`, and iLEAPP
  `whatsAppCallHistory` and `lineCalls`, are read as calls (`CALL_SPECS`). A group call, a
  direction other than incoming or outgoing, and a row whose other columns differ from what was
  checked (iLEAPP Line `Result` other than NORMAL, ALEAPP Line with a `To ID`) are imported with
  direction unknown and no sides, and flagged. (2) Two more chat tables: ALEAPP
  `get_telegramMessages` (no LEAPP conversation view, so Mabillon names its columns) and iLEAPP
  `snapchatMessages`. A Telegram row recovered from the database's free space or journal is
  flagged and listed as a possible copy, so a count over it is inconclusive. (3) Fail closed: a
  table missing any column its reader uses (phone messages, calls, chat and call tables) is not
  read at all and is listed as not read, so a LEAPP version that renames a column is never read
  with that column empty. (4) Apps read in full: a call stored with neither side keeps its own
  app (not only the phone's call log) from being read in full, and on iLEAPP no chat app counts
  as read in full, because the iOS 15 phone's UFDR holds WhatsApp, Viber and other app calls
  from the phone's own call records (CallKit) that iLEAPP lists under no app. Why: the plan for
  the next held-out public test (`/mnt/project-files/baker/plans/leapp-chat-apps.md`); each
  table was added only after it matched Mabillon's UFDR import of the same development phone.
- Where: PR #268
- Verified: `tests/test_leapp.py` 62 tests (8 new: app calls on each platform, Telegram recovered
  rows, iLEAPP Snapchat, a missing column on a phone, chat and call table). On the public
  development phones (cloud container, 2026-11-17, ALEAPP ed1b63d, iLEAPP fb05694; development
  data, not a scored run): Android 13 WhatsApp, Viber and Line calls 4 of 4 each match the UFDR
  on time, direction and length, and on other party where LEAPP names one; iOS 15 WhatsApp calls
  4 of 4, and Line calls 4 of 4 on time, direction and length; Telegram 23 of 29 rows match with
  their sender (2 recovered rows flagged, 4 call notices, 2 rows with no text); iOS Snapchat 19
  of 21 match with their sender (2 have no text). Google Messages pairs unchanged (the same 123).
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
