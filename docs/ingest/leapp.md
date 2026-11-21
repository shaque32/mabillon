# iLEAPP and ALEAPP import (unverified)

Importer: `core/ingest/leapp.py` (`LeappImporter`, importer `leapp` 0.3.0). It implements
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

A database up to 2,000,000,000 bytes is read into memory and never written out. SQLite loads a
database into memory as one allocation and refuses one above about 2 GiB, and a real phone's
LAVA database can be larger (a public iOS 17 phone's is 5.6 GB, mostly file system events the
import does not read). A larger one, or a smaller one this computer lacks the memory to load, is
streamed to a new owner-only temporary folder (the system's, or `TMPDIR`; `TEMP` on Windows),
opened read-only (`mode=ro&immutable=1`), and removed when the import ends, whether it succeeds
or not (best effort: a folder the system will not let it remove stays). On Linux the import then tries to remove its name at once (macOS should behave the
same; not yet tested there); if that removal fails, the named copy stays until the import ends.
Its freed disk blocks are not wiped. An import stopped mid-copy (killed, crashed, power lost)
leaves its folder; the next large import tries to remove this user's folders older than six
hours, best effort (a folder it cannot remove, or a newer one, stays). The copy is the plain database, also in an encrypted case, where the case's
own copy of the zip stays encrypted (`docs/encryption.md`, "Not covered"). Where the temporary
folder is in memory (tmpfs on some Linux systems), the copy takes memory too; set `TMPDIR` to a
folder on disk. The import refuses a database whose temporary disk lacks its size plus 512 MiB
free, and any database over 64 GiB. The coverage record says which way it was read
(`leapp.database_read_from`: `memory` or `temporary_file`).

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
has the same direction, text, number of attachments and other party, so such a repeat is not
counted twice; the rest (RCS, chiefly) is imported, including a possible copy that cannot be told
for sure (below), which is listed so that a count over it is inconclusive. Pairs are made nearest in time first, and each SMS
or MMS stands for at most one Google Messages message. The two stores name an attachment's file
differently (a Google Messages cache path, an MMS part file), so attachments are compared by
number only, and a message with attachments is paired only when it has one such SMS or MMS and
that SMS or MMS has no other such Google Messages message; otherwise all of them are kept and
listed as possible copies. A unique match is taken to be the same message: a different photo
sent to the same person with the same text within two seconds, held only in Google Messages,
would be skipped as that MMS. The other party is the sender of a received message, and for a sent one the
receiver: `Other Participant/Conversation Name` when it is a number or email; when it is a
display name, the one number the phone's contacts (ALEAPP `contacts`) give that name, if every
sender of the chat's received messages is that number too (ALEAPP does not say whether a chat
is a group, so a group named exactly as a contact, where only that contact has written, is
taken for that contact's chat). Failing both, the chat's one sender
(when it has exactly one) is used only to find a possible copy, never to skip one, since a group
may have had one sender so far. An SMS or MMS names its other party in `Address`, `From Address`
(received) or `To Address`, `Cc` and `Bcc` (sent), and counts only when it names exactly one.
Numbers compare by their digits, and one with a country code of up to three digits in front of
at least ten digits matches the same number without it (`+19195550111` and `(919) 555-0111`),
but only when that country code is marked (`+` or `00`): `17912345678` and `7912345678` may be
two national numbers, so they make only a possible copy (below). Two numbers that both carry a
country code match only when equal. A national
number written with its trunk 0 (`07911 123456`) never matches the same number with its country
code (`+44 7911 123456`), but when its other seven or more digits follow a country code of up to
three digits it makes a possible copy (below). Emails compare without case. When the direction
and text match but either side names no other party, or several, or the party was only inferred,
or the two numbers may be one number written two ways, the Google Messages message is kept, flagged
(`may_be_same_as_an_sms_or_mms_message`) and listed with the SMS or MMS as possible copies
(`numbered_copy_records`), so a count over them is inconclusive. The same holds for a Google
Messages message left over when its SMS or MMS was already paired with another one: the pair
is skipped as before, and the one left over is kept and listed with that SMS or MMS. On the public Android 13 phone
all 123 copies found by direction and text alone still match under this rule, with the same
pairs; the 12 sent ones are confirmed by the contact's number. The coverage record and the import's audit log entry list each skipped one under
`leapp.google_messages_skipped`: its locator, its part rows (LAVA rowids), the SMS or MMS it
matched (`same_as`, the nearest in time) and `seconds_apart`, so another reader can re-check
every pair. An MMS part whose file ALEAPP did not find is written as its path in `Body`; that path
is recorded as the attachment's name, never as text, and flagged (`media_file_not_in_extraction`). Google
Messages parts carry no message id and are grouped by the whole second, so a group with more than
one text may be several messages from one sender joined; it is flagged (`may_be_several_messages`)
and listed with the possible copies, so a count over it is inconclusive. Such a group is never
taken for a copy of an SMS or MMS: one with the same text is kept, and both are listed as possible
copies.

### Other chat apps

LEAPP publishes, for each chat artifact, a conversation view (the manifest's
`data_views.conversation`) naming its conversation, text, direction, time, sender and media
columns. Mabillon reads a chat artifact through that view only when it is listed in
`CHAT_SPECS`, which holds the artifacts checked record by record against Mabillon's UFDR import of
the same public test phone (2026-11-16, and 2026-11-17 for Telegram and iLEAPP Snapchat): every
message with text matched a UFDR message on time (within a second), text and direction, and every
sender id read matched the UFDR's.

| Tool | Artifact | App | Sender id read from |
|---|---|---|---|
| ALEAPP | `instagramDirectMessages` | Instagram | Sender ID (sent and received) |
| ALEAPP | `kik_messages` | Kik Messenger | Partner JID (received only) |
| ALEAPP | `get_snapchat_arroyo_messages` | Snapchat | Sender ID (sent and received) |
| ALEAPP | `get_telegramMessages` | Telegram | Sender ID (sent and received; read through Mabillon's own view, below) |
| ALEAPP | `get_tikTok` | TikTok | none |
| ALEAPP | `get_whatsapp_one_to_one_messages` | WhatsApp | Sending Party JID (received only) |
| iLEAPP | `DiscordChatsA` | Discord | Sender ID (sent and received) |
| iLEAPP | `facebookMessengerChats` | Facebook Messenger | Sender ID (sent and received) |
| iLEAPP | `groupMeMessages` | GroupMe | none |
| iLEAPP | `instagram_threads` | Instagram | Sender ID (sent and received) |
| iLEAPP | `kikMessages` | Kik Messenger | none |
| iLEAPP | `get_signalIOSMessages` | Signal | Author (received only) |
| iLEAPP | `snapchatMessages` | Snapchat | Sender Username (sent and received; recovered rows are possible copies, below) |
| iLEAPP | `telegramMessages` | Telegram | none |
| iLEAPP | `tiktok_messages` | TikTok | Sender (sent and received) |
| iLEAPP | `viber_chats` | Viber | Sender (Phone) (received only) |
| iLEAPP | `whatsAppMessages` | WhatsApp | From ID (received only; a group's id is not a sender) |

A sender named only by display name gets no account (two people can share one display name),
and is flagged `sender_name_only`; a sent message whose table does not state the owner's id has
no sender. A direction other than the view's sent value or a plain received value is unknown
and flagged. Other chat artifacts, including ones that did not match (iLEAPP `discordChats`,
`facebook_messenger_client_chats`, `line`, `teamsMessages`, `twitterDirectMessages`,
`threema_chats`, `session_messages`; ALEAPP `get_line_messages`,
`get_Viber_messages`, `get_whatsapp_group_messages`), stay not imported.

ALEAPP's `get_telegramMessages` has no conversation view, so Mabillon names its columns itself
(`Message`, `Direction`, `Timestamp`, `Dialog ID`, `Chat`, `Sender`, `Recorded Media Path`). It
also writes rows recovered from the database's free space or journal (`Record Origin` other than
`Live`); such a row can repeat a live one, so it is imported, flagged
(`recovered_record_may_repeat_another`) and listed as a possible copy (`numbered_copy_records`):
a count over it is inconclusive. iLEAPP's `snapchatMessages` writes such rows too and is read
the same way (3 of 21 on the iOS 15 phone). ALEAPP's Telegram table also writes each call as a
row whose text is a call notice (`[Phone call (call id ..., outcome hung up, duration seconds
N)]`); such a row is stored as a Telegram call, never as a message (`call_notice_read_as_call`),
from its sender, with that length. Only a live notice of a call that was answered and hung up,
in a stated direction, keeps its side; any other is stored with no sides and flagged, so
Telegram's calls are not read in full. A placed call whose row names no sender is flagged
`sent_without_own_account`. A recovered notice is listed as a possible copy, like a recovered
message, so a count over it is inconclusive. Only a row whose whole text has the form ALEAPP
writes for a notice (`[Phone call (call id N)]`, with `, outcome ...` and `, duration seconds N`
when the record holds them) is read as a call; other text that starts with `[Phone call` stays a
message. A row that opens like a notice (`[Phone call (call id N`) but is not in that whole form,
such as an outcome or field not seen, is kept as a message, flagged
`call_notice_shape_not_checked`, and keeps Telegram's calls from being read in full. The table
marks no row as a notice, so a message typed in exactly that form cannot be told from one. On the Android 13 phone 2 of its 29 rows are recovered;
its 4 call notices matched the UFDR's 4 Telegram calls on time, direction, caller and length; 23
of the other 25 matched the UFDR with their sender, and 2 have no text.

A table is read only when it has every column its reader uses: the conversation view's columns
and the sender id for a chat table, the columns below for a call table, and, for each phone
table, every column that sets a record's time, direction, parties, text or attachment names.
Only display columns may be missing, and are then read as empty: an iOS chat's name and contact
label, an attachment's path beside its name, and the ALEAPP call log column that marks a call removed from the list (a call's
status there is then unknown). A table missing any of them is not read at all, never in part: it is
listed in `not_imported` with `read_failed` (`its table has no column ...`), and its app is not
read in full. A LEAPP version that renames or drops a column is caught this way rather than read
with that column empty. A phone message table refused this way is not used to find Google
Messages copies either, so a Google Messages message is never skipped as a copy of an SMS or MMS
that was not imported.

### App calls

`CALL_SPECS` lists the chat apps' call tables read as calls, each checked against the UFDR's calls
for that app on the public test phones (2026-11-17, development data). On the Android 13 phone all
4 WhatsApp, 4 Viber and 4 Line calls matched on time, direction and length (within a second), and
on other party wherever LEAPP names one. On the iOS 15 phone all 4 WhatsApp calls matched the
same way; the 4 Line calls matched the UFDR's CallKit calls on time, direction and length, and
their ids matched the UFDR's record from Line's own database (which the UFDR times at the call's
end).

| Tool | Artifact | App | Other party | Length |
|---|---|---|---|---|
| ALEAPP | `get_whatsapp_call_logs` | WhatsApp | Caller JID | Call Duration |
| ALEAPP | `get_Viber` | Viber | Phone Number | end time less start |
| ALEAPP | `get_line_calls` | Line | From ID | End Time less Start Time |
| iLEAPP | `whatsAppCallHistory` | WhatsApp | Contact ID | Duration H:M:S |
| iLEAPP | `lineCalls` | Line | Contact MID (the owner from Account ID) | Duration (seconds) |

An incoming call goes from the other party to the owner, an outgoing one from the owner to the
other party; the owner's own id is stated only by iLEAPP Line. iLEAPP WhatsApp's `Missed` Yes
makes an incoming call missed. A call the checks were not shown on is imported with direction
unknown and no sides, and flagged: a group call (`group_call_parties_not_read`, since only one
party is named), and a direction other than incoming or outgoing, a `Missed` value other than
No (or Yes on an incoming call), an iLEAPP Line `Result` other than NORMAL or an ALEAPP Line call that names a `To ID`
(`call_not_incoming_outgoing_or_missed`). A call stored with neither side, for these reasons or
because the row names no other party, keeps its app from being read in full, as it does the
phone's own call log. ALEAPP's WhatsApp call log names a group call only by the subject of the
group chat it was placed from; a group call started outside a group chat has none, and ALEAPP
does not read its participants, so it reads as a call with the caller alone. WhatsApp is
therefore never read in full from ALEAPP output. An app can also place calls through Android's telecom service, which
writes them to the phone's call log, where they are stored under the call log, not the app. So
when an ALEAPP call log row names a `Phone Account Package` other than `com.android.phone`
(flagged `call_placed_by_another_app`), or names none (flagged `call_package_not_stated`), or
the call log was not read or is not in the run, or any call log entry in the manifest holds
records that were not read, no chat app counts as read in full. A row from another package is
stored with neither side, so no check reads it as a phone call, and the call log then does not
count as read in full either; a row that names no package keeps its sides, since a phone call
can be written that way too, but the call log then does not count as read in full. ALEAPP's
package is the part of the account's component before the slash; on the Samsung images in
ALEAPP's own sample data it names a Samsung messaging app, so on such a phone every call would
be stored with no sides until that value is checked against a UFDR. Calls stored from a chat table's call notices count among the
kinds the import read. Every call log row on the Android 13 phone is `com.android.phone`. On the Android 13 phone ALEAPP leaves `Caller JID` empty on outgoing
WhatsApp calls, so its two outgoing calls have no sides and WhatsApp is not read in full there.

Other app call tables did not match a UFDR's calls one to one, so they stay not imported: ALEAPP
`get_teams_calllog` (an incoming call names the caller only by display name),
`get_telegramVoipLogs` (call log files, with no direction or party), `get_fb_msys_calls` (3 rows
for 4 calls, no party id) and `instagramDirectCalls` (17 call events for 9 calls); iLEAPP
`facebookMessengerCalls` (4 rows for 26 calls), `instagram_calls` (25 rows for 17 calls),
`teamsCalls` (5 rows for 1 call) and `signalLogCallEvents` (164 log events for 8 calls).

### What an absence check may rest on

The coverage record lists `apps_read_in_full`: the phone's own messages (`Native Messages`) and
call log (`unknown`) when their tables were read and no row of the phone's own call table, under
whichever app it names (FaceTime included), was stored with neither side; and, on ALEAPP only, a
chat app when one of its chat tables was read, every call table listed for it was read, its
call table can hold every party of a call, no other artifact in its LEAPP category holds records
Mabillon did not read, none of its calls was stored with neither side, and every call log entry
was read and holds no row from another app or with no package (above). A call table alone, such
as ALEAPP Viber's or Line's, holds none of the app's messages, so it never makes the app read in
full. On iLEAPP no chat app counts as read in full: the iOS 15 phone's UFDR
holds WhatsApp, Viber and other app calls from the phone's own call records (CallKit) that
iLEAPP lists under no app, so no iLEAPP table holds every call of an app. The absence check (1.0.2) treats any other
app, a search on every channel at once, and calls on every app as not covered by a LEAPP source,
so "no contact" never passes on an app LEAPP read only in part. On both development phones every
chat app is partial (each has other tables, such as WhatsApp's group messages, or calls with no
sides), so only texts and the phone's own calls can show absence there.

Every other artifact in the manifest (ALEAPP's combined `SMS and MMS Messages` included, which
repeats the two tables above) is listed as not imported, with its record count, in one
attention item: a claim resting on another app is not tested from this source, and a record
missing from it is not shown to be absent.

Direction and parties:

- iLEAPP `From Me` 1 is outgoing, sent by the owner's line (`Destination Caller ID`, else
  `Account` without its `E:`/`P:` prefix) to the chat's participants; 0 is incoming, from
  `Sender`, to the owner's line and the other participants. An incoming row that names neither
  owner field is stored with no receivers (`received_without_own_account`): the phone's own line
  received it, so storing only the other members would hide it from a check between the sender
  and the owner.
- ALEAPP `Type` (SMS) or `Direction` (MMS) `Received` is incoming and `Sent` outgoing. Draft,
  Outbox, Queued, Failed and any other value are imported with direction unknown and flagged
  (`not_sent_or_received`), so none counts as sent. A received SMS or MMS is stored with no
  receivers: ALEAPP does not say which number is the phone's own line, so the numbers an MMS
  names may leave it out, and the checks hold such a row open as possibly to anyone.
- iLEAPP incoming calls with `Answered` No are missed. ALEAPP call types 1, 2 and 3 are
  incoming, outgoing and missed, and 5 (rejected on the phone) is missed too, since the other side
  placed it and it was not answered; any other (voicemail, blocked, answered elsewhere), and an
  iLEAPP call with no direction, is imported with direction unknown, no sides, and flagged.
  No check can find such a call, so the call log then does not count as read in full; the same
  holds for any call that names neither side, such as a withheld caller on a line the row does
  not name. ALEAPP's
  `Phone Account Address` is the owner's line on the call. The public Android 13 phone has 38
  voicemail and other such calls, so its call log is not read in full.

iOS writes U+FFFC (the object replacement character) in a message's text where an attachment
sits; it is removed from the text, and the attachment is recorded on its own.

Times: LEAPP converts the phone's value to a UTC epoch in whole seconds (the phone's
milliseconds are dropped), so each time is stored as UTC with offset 0, and the epoch as stored,
marked `(LEAPP UTC epoch)`, is the raw value. A timing claim closer than a second needs the
phone's own value, from the source path LEAPP names.

## The phone's time zone and OS

`devices.timezone` is the IANA zone the phone's own tables recorded: iLEAPP's `powerlogTimeZone`
(Time Zone Name, with its time) and `timezone_info` (the `Last Bootstrap Timezone` property),
ALEAPP's `get_battery_usage_v4` (Android 13 and earlier) and `get_battery_usage_v9` (Android 14,
ALEAPP's `battery_usage_v9.py`), each its Timezone with its time. It is set only when every zone those
tables recorded is the same one. A phone that recorded two or more zones, or none, gets no zone
and an attention item saying so, and a claim with a time window is not tested until the expert
sets the zone (case screen, or `mabillon set-device-zone`). Any name the standard library knows
counts, `UTC` included. A value it does not know is counted (`zones_not_read`), and the phone then
gets no zone either, with its own attention item, since that value may be a second zone. These
tables cover only the span they kept (iOS powerlog keeps days to weeks), so a phone that was in
another zone before that span still gets the one zone, and a weekday or local-time claim about
an earlier record may be read in the wrong zone; the expert can set the zone. The coverage record keeps every zone seen,
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
tables that may hold records was read. A table may hold records unless the manifest states 0, or
states no count and the table is in the database with no rows. Tables are compared by manifest
entry, so two entries with one key are each counted. The absence check and the count check's "at most" and
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
- Chat tables outside `CHAT_SPECS`, and call tables outside `CALL_SPECS`, are not read.
- No table list says which of an app's LEAPP tables hold no messages or calls, so an app with any
  other table holding records is never read in full.
- The device's model is not read.
- Forwarded and quoted messages are not marked; iLEAPP's SMS table does not state them.
