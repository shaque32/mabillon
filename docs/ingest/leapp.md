# iLEAPP and ALEAPP import (unverified)

Importer: `core/ingest/leapp.py` (`LeappImporter`, importer `leapp` 0.1.0). It implements
`EvidenceImporter` and writes the same canonical rows as the other importers, through the same
writer (`_Writer` in `core/ingest/cellebrite_common.py`), so retrieval, checks, rules, the review
screen and the report work unchanged. `core/ingest/pick.py` chooses it for a `.zip` that holds a
LEAPP manifest; every other `.zip` stays a Cellebrite UFDR package.

Its sources are stored with kind `leapp` (contracts and schema 0.9.0, signed by Arsh
2026-11-16). A case made before 0.9.0 keeps its old CHECK, so a LEAPP import into it fails with
the CHECK error; a new case takes LEAPP output.

**Format support is unverified.** The importer was built from LEAPP's published source
(github.com/abrignoni/iLEAPP and ALEAPP, MIT licence) and tested on synthetic LAVA pairs
(`eval/synthetic/leapp.py`). Every import records `"format_support": "unverified"`, shows the
unverified-reader notice first among the items to review, and prints the "Untested export
format" notice with LEAPP's version as written.

## What the examiner hands over

A zip of one iLEAPP or ALEAPP run's output folder, or of just its LAVA pair:

| File | What it is |
|---|---|
| `_lava_data.lava` (or the older `_lava_data.json`) | JSON manifest: `parser_info` (tool and version), `param_type` (the input type), `profile_used`, and `artifacts` by category, each with `name`, `tablename`, `column_map`, `record_count`, `source_path` |
| `_lava_artifacts.db` (the manifest's `lava_db_name`) | SQLite, one table per artifact; a datetime column is an INTEGER UTC epoch |

The zip must hold exactly one manifest, with its database beside it. HTML, TSV and media files in
the zip are not read.

## What is read

| Tool | Artifact (function) | Read as | Grouped by | Locator |
|---|---|---|---|---|
| iLEAPP | `sms` (SMS & iMessage) | messages, app `Native Messages` | `Message Row ID` (one row per attachment) | `sms/message_row_id=<id>` |
| iLEAPP | `callHistory` | calls; `com.apple.Telephony` is the phone's own call log (app `unknown`), FaceTime is `FaceTime`, other providers as stored | | `callhistory/rowid=<n>` |
| iLEAPP | `addressBook` | contacts, one row per number or address | | `addressbook/rowid=<n>` |
| ALEAPP | `get_sms_mms` (SMS Messages) | messages, app `Native Messages` | | `get_sms_mms/msg_id=<id>` |
| ALEAPP | `get_sms_mms_mms` (MMS Messages) | messages, app `Native Messages`; text parts joined in order | `MSG ID` (one row per part) | `get_sms_mms_mms/msg_id=<id>` |
| ALEAPP | `get_googleMessages` (Google Messages, bugle_db) | messages, app `Native Messages`, only those not already read from SMS or MMS | `Conversation ID`, time, `Direction`, `Message Sender` (one row per part) | `get_googlemessages/rowid=<first part>` |
| ALEAPP | `get_calllog` | calls, app `unknown`, direction from `Raw Call Type (as stored)` | | `get_calllog/rowid=<n>` |
| ALEAPP | `contacts` | contacts | | `contacts/rowid=<n>` |

Every message takes the app `Native Messages`, the name a UFDR gives a phone's own iMessage,
SMS, MMS and RCS together, so a claim about texts or iMessages is searched across all of them
(the app is in `assumption_filler.WIDER_APPS`), and an absence check never passes because a
message was stored under another of the phone's own services.

Google Messages holds most of the phone's SMS and MMS a second time. A Google Messages message
with the same direction and text as an SMS or MMS within two seconds is skipped and counted
(`same_as_an_sms_or_mms_message`), so no message is counted twice; the rest (RCS, chiefly) is
imported. The coverage record and the import's audit log entry list each skipped one under
`leapp.google_messages_skipped`: its locator, its part rows (LAVA rowids), the SMS or MMS it
matched (`same_as`, the nearest in time) and `seconds_apart`, so another reader can re-check
every pair. An MMS part whose file ALEAPP did not find is written as its path in `Body`; that path
is recorded as the attachment's name, never as text, and flagged (`media_file_not_in_extraction`).

Every other artifact in the manifest (ALEAPP's combined `SMS and MMS Messages` included, which
repeats the two tables above) is listed as not imported, with its record count, in one
attention item: a claim resting on another app is not tested from this source, and a record
missing from it is not shown to be absent.

Direction and parties:

- iLEAPP `From Me` 1 is outgoing, sent by the owner's line (`Destination Caller ID`, else
  `Account` without its `E:`/`P:` prefix) to the chat's participants; 0 is incoming, from
  `Sender`, to the owner's line and the other participants.
- ALEAPP `Type` (SMS) or `Direction` (MMS) `Received` is incoming and `Sent` outgoing. Draft,
  Outbox, Queued, Failed and any other value are imported with direction unknown and flagged
  (`not_sent_or_received`), so none counts as sent.
- iLEAPP incoming calls with `Answered` No are missed. ALEAPP call types 1, 2 and 3 are
  incoming, outgoing and missed, and 5 (rejected on the phone) is missed too, since the other side
  placed it and it was not answered; any other (voicemail, blocked, answered elsewhere) is
  imported with direction unknown and flagged. ALEAPP's `Phone Account Address` is the owner's
  line on the call.

iOS writes U+FFFC (the object replacement character) in a message's text where an attachment
sits; it is removed from the text, and the attachment is recorded on its own.

Times: LEAPP converts the phone's value to a UTC epoch in whole seconds (the phone's
milliseconds are dropped), so each time is stored as UTC with offset 0, and the epoch as stored,
marked `(LEAPP UTC epoch)`, is the raw value. A timing claim closer than a second needs the
phone's own value, from the source path LEAPP names.

## Coverage and absence

`fidelity` is `full_extraction` when LEAPP read a file system extraction (`param_type` fs, tar,
zip or gz) with no profile; then the tables it read are whole for the databases it parsed, and
the absence check still needs records on the named app in the source. A profile run is a
`curated_report`, and an iTunes backup is `unknown`; neither can show absence.

## Checked against a UFDR of the same phone

ALEAPP (commit in the PR) on the public Android 13 test phone, against Mabillon's import of that
phone's UFDR, on 2026-11-16 in a cloud container (development data, not a scored run):

- Messages: every text message matches on time to the second, direction and text (113 of 114
  with text; the other has a line break the UFDR writes differently). The UFDR lists each message
  twice (once from the phone's SMS store, once from Google Messages); LEAPP's import keeps one.
  The UFDR writes some emoji as `????`; LEAPP keeps them.
- Calls: all 108 match on time and other party. The UFDR shows ALEAPP types 3 and 5 as incoming
  with no duration; LEAPP's import shows them as missed with duration 0. Type 4 is unknown in
  both.
- Contacts: all 13 phone contacts are in the UFDR, which also lists app contacts.

iLEAPP (commit in the PR) on the public iOS 15 test phone, the same way and day:

- Messages: all 37 text messages match on text, direction and time (to the second, or one second
  apart where the UFDR's milliseconds cross a second LEAPP drops). The UFDR lists each twice.
- Calls: all 22 call history rows match on time and other party. The UFDR also holds about 26
  more call records read from other databases and apps; LEAPP's call history does not have
  them, and they are listed among the artifacts not imported only where LEAPP parsed them.
- Contacts: all 13 numbers and addresses are in the UFDR.

## Not yet done

- No case data has been read with it. The public test phones are the only real LEAPP output it
  has read (`/mnt/project-files/baker/plans/public-image-benchmark.md`).
- Third-party chat apps (WhatsApp, Signal, Telegram and others) are not read yet.
- The device's model, OS and time zone are not read from LEAPP's device-info artifacts.
- Forwarded and quoted messages are not marked; iLEAPP's SMS table does not state them.
