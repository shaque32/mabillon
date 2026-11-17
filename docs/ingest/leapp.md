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
is skipped and counted (`same_as_an_sms_or_mms_message`) when an SMS or MMS within two seconds
has the same direction, text, number of attachments and other party, so no message is counted
twice; the rest (RCS, chiefly) is imported. Each SMS or MMS stands for at most one Google
Messages message. The other party is the sender of a received message, and for a sent one the
receiver: `Other Participant/Conversation Name` when it is a number or email, else the one
sender of the chat's received messages when the chat has exactly one. An SMS or MMS names its
other party in `Address`, `From Address` (received) or `To Address`, `Cc` and `Bcc` (sent), and
counts only when it names exactly one. Numbers compare by their digits, and one with a country
code of up to three digits in front of at least ten digits matches the same number without it
(`+19195550111` and `(919) 555-0111`); emails compare without case. When the direction and text
match but either side names no other party, or several, the Google Messages message is kept and
flagged (`may_be_same_as_an_sms_or_mms_message`), so a count over it may hold one message twice.
On the public Android 13 phone all 123 copies found by direction and text alone still match
under this rule, and the same pairs. The coverage record and the import's audit log entry list each skipped one under
`leapp.google_messages_skipped`: its locator, its part rows (LAVA rowids), the SMS or MMS it
matched (`same_as`, the nearest in time) and `seconds_apart`, so another reader can re-check
every pair. An MMS part whose file ALEAPP did not find is written as its path in `Body`; that path
is recorded as the attachment's name, never as text, and flagged (`media_file_not_in_extraction`).

### Other chat apps

LEAPP publishes, for each chat artifact, a conversation view (the manifest's
`data_views.conversation`) naming its conversation, text, direction, time, sender and media
columns. Mabillon reads a chat artifact through that view only when it is listed in
`CHAT_SPECS`, which holds the artifacts checked record by record against Mabillon's UFDR import of
the same public test phone (2026-11-16): every message with text matched a UFDR message on time
(within a second), text and direction, and every sender id read matched the UFDR's.

| Tool | Artifact | App | Sender id read from |
|---|---|---|---|
| ALEAPP | `instagramDirectMessages` | Instagram | Sender ID (sent and received) |
| ALEAPP | `kik_messages` | Kik Messenger | Partner JID (received only) |
| ALEAPP | `get_snapchat_arroyo_messages` | Snapchat | Sender ID (sent and received) |
| ALEAPP | `get_tikTok` | TikTok | none |
| ALEAPP | `get_whatsapp_one_to_one_messages` | WhatsApp | Sending Party JID (received only) |
| iLEAPP | `DiscordChatsA` | Discord | Sender ID (sent and received) |
| iLEAPP | `facebookMessengerChats` | Facebook Messenger | Sender ID (sent and received) |
| iLEAPP | `groupMeMessages` | GroupMe | none |
| iLEAPP | `instagram_threads` | Instagram | Sender ID (sent and received) |
| iLEAPP | `kikMessages` | Kik Messenger | none |
| iLEAPP | `get_signalIOSMessages` | Signal | Author (received only) |
| iLEAPP | `telegramMessages` | Telegram | none |
| iLEAPP | `tiktok_messages` | TikTok | Sender (sent and received) |
| iLEAPP | `viber_chats` | Viber | Sender (Phone) (received only) |
| iLEAPP | `whatsAppMessages` | WhatsApp | From ID (received only; a group's id is not a sender) |

A sender named only by display name gets no account (two people can share one display name),
and is flagged `sender_name_only`; a sent message whose table does not state the owner's id has
no sender. A direction other than the view's sent value or a plain received value is unknown
and flagged. Other chat artifacts, including ones that did not match (iLEAPP `discordChats`,
`facebook_messenger_client_chats`, `line`, `teamsMessages`, `twitterDirectMessages`,
`snapchatMessages`, `threema_chats`, `session_messages`; ALEAPP `get_line_messages`,
`get_Viber_messages`, `get_whatsapp_group_messages`), stay not imported.

### What an absence check may rest on

The coverage record lists `apps_read_in_full`: the phone's own messages (`Native Messages`) and
call log (`unknown`) when their tables were read, and a chat app only when no other artifact in
its LEAPP category holds records Mabillon did not read. The absence check (1.0.2) treats any other
app, a search on every channel at once, and calls on every app as not covered by a LEAPP source,
so "no contact" never passes on an app LEAPP read only in part. On both development phones every
chat app was partial (each has other tables, such as WhatsApp's group messages), so only texts
and the phone's own calls can show absence there.

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

## The phone's time zone and OS

`devices.timezone` is the IANA zone the phone's own tables recorded: iLEAPP's `powerlogTimeZone`
(Time Zone Name, with its time) and `timezone_info` (the `Last Bootstrap Timezone` property),
ALEAPP's `get_battery_usage_v4` (Timezone, with its time). It is set only when every zone those
tables recorded is the same one. A phone that recorded two or more zones, or none, gets no zone
and an attention item saying so, and a claim with a time window is not tested until the expert
sets the zone (case screen, or `mabillon set-device-zone`). Any name the standard library knows
counts, `UTC` included. A value it does not know is counted (`zones_not_read`), and the phone then
gets no zone either, with its own attention item, since that value may be a second zone. The coverage record keeps every zone seen,
with its record count, tables and first and last time (`leapp.device.zones_seen`), and the item
says the zone places every record, including any from times the phone did not record its zone.

`devices.os_version` is iLEAPP's `last_build` ProductName and ProductVersion ("iPhone OS
15.3.1") or ALEAPP's `usagestatsVersion` Android Version ("Android 13").

On the two public development phones both read `America/New_York`, the zone their UFDRs give
(the Android 13 UFDR gives none).

## Coverage and absence

`fidelity` is `full_extraction` when LEAPP read a file system extraction (`param_type` fs, tar,
zip or gz) with no profile and its manifest says the run completed (`processing_status`
`Complete`, which LEAPP's lavafuncs.py writes when a run ends; it writes `In Progress` when one
starts). Then the tables it read are whole for the databases it parsed, and the absence check
still needs records on the named app in the source. A run whose manifest gives any other status
is `unknown`, since a table may have been cut short. A profile run is a `curated_report`, and an
iTunes backup is `unknown`; none of these can show absence.

A table Mabillon reads counts as read only when it was read through. If the manifest lists it
but its table is missing from the database, or a chat app's conversation view names no text,
direction or time column, it is listed in `not_imported` with `read_failed` and its reason, the
coverage summary raises `leapp_artifact_not_read`, and its app is not in `apps_read_in_full`.
The phone's own messages, or its calls, count as read in full only when every one of their
tables that holds records was read. The absence check and the count check's "at most" and
"exactly" read that list: an app not on it cannot show that something is absent or that a count
is complete.

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
- Chat apps outside `CHAT_SPECS`, and the calls apps record, are not read.
- The device's model is not read.
- Forwarded and quoted messages are not marked; iLEAPP's SMS table does not state them.
