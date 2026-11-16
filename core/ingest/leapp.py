"""iLEAPP and ALEAPP output importer (the LAVA manifest and database). UNVERIFIED format support.

iLEAPP (iPhone) and ALEAPP (Android) are free, open-source (MIT) parsers that read a raw phone
extraction. Each run writes, beside its HTML and TSV reports, a LAVA pair: `_lava_data.lava`, a
JSON manifest naming every artifact it parsed (category, name, table, column names as written,
record count, the source path it read), and `_lava_artifacts.db`, a SQLite database with one
table per artifact. The examiner zips the run's output folder (or just that pair) and hands
Mabillon the zip.

Mabillon reads, from that pair only:

- iLEAPP: SMS and iMessage messages (`sms`), call history (`callHistory`), contacts
  (`addressBook`);
- ALEAPP: SMS messages (`get_sms_mms`), MMS messages (`get_sms_mms_mms`), Google Messages
  (`get_googleMessages`, for RCS and other messages the phone's SMS and MMS store does not hold),
  the call log (`get_calllog`), contacts (`contacts`).

Every message from these tables takes the app every importer gives a phone's own messages,
"Native Messages" (what a UFDR calls iMessage, SMS, MMS and RCS together), so a claim that names
texts or iMessages is searched across all of them and never passes an absence check because the
message was stored under another of the phone's message services.

Every other artifact in the manifest is listed in the coverage record as not imported, with its
name and record count, so an app Mabillon did not read is never taken as absent. Built from
LEAPP's published source (github.com/abrignoni/iLEAPP and ALEAPP) and run on public test phones
only, never on case data, so every import says it was read with an unverified reader.

What the tables say, and how it is read:

- Times are LEAPP's own conversion of the phone's value to a UTC epoch, so each time is stored
  as UTC with offset 0 and the epoch exactly as LEAPP stored it as the raw value. The phone's
  own value (Cocoa or Unix milliseconds) is in the source path LEAPP names, not in LAVA.
- iLEAPP writes one SMS row per attachment, so rows are grouped by the message's row id into
  one message with its attachments. ALEAPP writes one MMS row per part, grouped by the MMS id;
  the text parts, in order, are the body. A media part whose file LEAPP did not find is written
  as its path in the Body column; that path is read as the attachment, never as text.
- Google Messages (bugle_db) holds most of the same SMS and MMS a second time. ALEAPP writes one
  row per part with no message id, so parts are grouped by conversation, time, direction and
  sender. A message that matches an SMS or MMS already imported (the same direction and text,
  within two seconds) is skipped and counted, so a message is never counted twice; the others
  (RCS, chiefly) are imported.
- Direction is read from what the table states (iLEAPP's `From Me`, ALEAPP's `Type` and
  `Direction`); a draft, queued, outbox or failed message is imported with direction unknown and
  flagged, never as sent. An iLEAPP incoming call not answered is a missed call, and so is an
  ALEAPP rejected call (type 5, declined on the phone); any other ALEAPP call type (voicemail,
  blocked, answered elsewhere) is imported with direction unknown.
- The phone's own line or account is read from iLEAPP's `Destination Caller ID` (and `Account`
  on sent rows) and from ALEAPP's `Phone Account Address`, and marked as the owner's.

A message, call or contact's locator is `<table>/<column>=<value>`: the LAVA table and the
row id that ties it to the phone's database (iLEAPP's message row id, ALEAPP's message id), or
`<table>/rowid=<n>` for a table with no such id. The input is hashed, read from a seekable
read-only handle and hashed again before anything is stored.
"""

from __future__ import annotations

import io
import json
import re
import sqlite3
import zipfile
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core import db as db_errors
from core.contracts import (
    CallDirection,
    ExtractionType,
    Fidelity,
    MessageDirection,
    Source,
    SourceKind,
    Timestamp,
)
from core.encryption import open_input
from core.ingest import tested
from core.ingest.cellebrite_common import (
    Coverage,
    Party,
    RecordKind,
    TableCoverage,
    _db_bool,
    _listed,
    _ts_cols,
    _Writer,
    coverage_payload,
    parse_duration,
)
from core.ingest.source_file import require_sha256, sha256_input
from core.review import audit_log

IMPORTER_NAME = "leapp"
IMPORTER_VERSION = "0.1.0"
# The app every importer gives a phone's own messages (a UFDR's name for iMessage, SMS, MMS and
# RCS together; assumption_filler APP_ALIASES and WIDER_APPS).
NATIVE_MESSAGES_APP = "Native Messages"
# UNVERIFIED: built from LEAPP's published source and run on public test phones only.
FORMAT_SUPPORT = "unverified"
MANIFEST_NAMES = ("_lava_data.lava", "_lava_data.json")  # LAVA accepts both names
DEFAULT_DB_NAME = "_lava_artifacts.db"
# The most the manifest and the database may unpack to. The database is read into memory (never
# written out unencrypted), so a zip member that claims more is refused before it is expanded.
# The public iOS 15 test phone's database is 1.4 GB, most of it file system events.
MAX_MANIFEST_BYTES = 256 * 1024 * 1024
MAX_DB_BYTES = 8 * 1024 * 1024 * 1024
LEAPP_NAMES = {"ileapp": "iLEAPP", "aleapp": "ALEAPP"}
# LEAPP input types that are a phone's file system (fs, tar, zip, gz); an iTunes backup is not.
FILE_SYSTEM_INPUTS = {"fs", "tar", "zip", "gz", "tgz", "file"}

FIDELITY_REASON = (
    "LEAPP parsed a file system extraction with every module it has, so the tables it read are "
    "whole for the databases it parsed. It cannot show that something is absent from an app it "
    "did not parse, and those apps are listed as not imported."
)
FIDELITY_REASON_PROFILE = (
    "LEAPP ran only the modules a profile selected, or read an input that is not a file system "
    "extraction, so it cannot support a claim that something is absent from the phone."
)

# Service providers iLEAPP's call history names, and the app Mabillon gives them. The phone's
# own calls take the app every importer gives a call with no source app (assumption_filler
# NATIVE_CALL_APP); other providers keep their name as stored.
IOS_CALL_APPS = {"com.apple.telephony": "unknown", "com.apple.facetime": "FaceTime"}
_ACCOUNT_PREFIX_RE = re.compile(r"^(?:[EePp]:|tel:|mailto:)")
_SMS_IN = {"received"}
_SMS_OUT = {"sent"}
_ANDROID_CALL_DIR = {
    "1": CallDirection.INCOMING,
    "2": CallDirection.OUTGOING,
    "3": CallDirection.MISSED,
    "5": CallDirection.MISSED,  # rejected: declined on the phone, so placed by the other side
}
# ALEAPP writes a media part's path in the MMS Body column when it did not find the file.
_MMS_PART_PATH_RE = re.compile(r"^/\S*/(?:app_parts|parts)/\S+$")
OBJECT_REPLACEMENT = "\ufffc"
# Seconds within which a Google Messages message is the same as an SMS or MMS one.
SAME_MESSAGE_SECONDS = 2


# ---------------------------------------------------------------- reading the pair


@dataclass
class Artifact:
    """One manifest entry: what LEAPP says it wrote."""

    category: str
    name: str
    key: str  # LEAPP's function name for it (artifact_key)
    table: str
    module: str
    column_map: dict[str, str]  # column in the database -> the header as LEAPP wrote it
    record_count: int | None
    source_path: str | None


@dataclass
class Lava:
    manifest: dict[str, Any]
    db: sqlite3.Connection
    manifest_member: str
    db_member: str
    leapp_name: str
    leapp_version: str | None
    artifacts: list[Artifact]
    # Google Messages messages skipped as the same as an SMS or MMS, each with the one it matched
    dropped: list[dict[str, Any]] = field(default_factory=list)

    def rows(self, art: Artifact) -> Iterator[tuple[int, dict[str, Any]]]:
        """(rowid, {header as LEAPP wrote it: value}) for each row of the artifact's table."""
        tables = {
            r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if art.table not in tables:
            return
        cur = self.db.execute(f'SELECT rowid, * FROM "{art.table.replace(chr(34), chr(34) * 2)}"')  # noqa: S608  (a table the manifest names, quoted)
        cols = [d[0] for d in cur.description][1:]
        names = [art.column_map.get(c, c) for c in cols]
        for row in cur:
            yield int(row[0]), dict(zip(names, row[1:], strict=True))


def _member(names: list[str], wanted: tuple[str, ...]) -> list[str]:
    return [n for n in names if PurePosixPath(n).name in wanted and not n.startswith("__MACOSX/")]


def _check_size(z: zipfile.ZipFile, member: str, limit: int, file_name: str) -> None:
    """Refuse a member that unpacks to more than `limit` bytes. zipfile reads no more than the
    size the member's header states, so the header's size bounds what is expanded."""
    size = z.getinfo(member).file_size
    if size > limit:
        raise ValueError(
            f"{member} in {file_name} unpacks to {size:,} bytes, more than the {limit:,} Mabillon "
            "reads from a LEAPP output"
        )


def read_lava(data: io.BufferedIOBase | io.BytesIO, file_name: str) -> Lava:
    """Read the LAVA pair from a zip of a LEAPP output folder. Refuses a zip that holds no
    manifest, more than one, or no database beside it."""
    try:
        z = zipfile.ZipFile(data)
    except zipfile.BadZipFile as err:
        raise ValueError(f"{file_name} is not a zip file") from err
    names = z.namelist()
    found = _member(names, MANIFEST_NAMES)
    if not found:
        raise ValueError(
            f"{file_name} holds no LEAPP manifest ({MANIFEST_NAMES[0]}); zip the whole iLEAPP or "
            "ALEAPP output folder"
        )
    if len(found) > 1:
        raise ValueError(
            f"{file_name} holds {len(found)} LEAPP manifests; zip one LEAPP run's output folder"
        )
    man_member = found[0]
    _check_size(z, man_member, MAX_MANIFEST_BYTES, file_name)
    try:
        manifest = json.loads(z.read(man_member).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise ValueError(f"{man_member} in {file_name} is not a LEAPP manifest") from err
    if not isinstance(manifest, dict) or not isinstance(manifest.get("artifacts"), dict):
        raise ValueError(f"{man_member} in {file_name} is not a LEAPP manifest (no artifacts)")
    db_name = str(manifest.get("lava_db_name") or DEFAULT_DB_NAME)
    parent = str(PurePosixPath(man_member).parent)
    db_member = db_name if parent == "." else f"{parent}/{db_name}"
    if db_member not in names:
        raise ValueError(f"{file_name} holds {man_member} but not {db_name} beside it")
    _check_size(z, db_member, MAX_DB_BYTES, file_name)
    db = sqlite3.connect(":memory:")
    try:
        db.deserialize(z.read(db_member))
        db.execute("PRAGMA query_only = ON")
        db.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except db_errors.DatabaseError as err:
        db.close()
        raise ValueError(f"{db_member} in {file_name} is not a SQLite database") from err
    info = manifest.get("parser_info") if isinstance(manifest.get("parser_info"), dict) else {}
    raw_name = str(info.get("leapp_name") or "")
    leapp = LEAPP_NAMES.get(raw_name.strip().lower())
    if leapp is None:
        db.close()
        raise ValueError(
            f"{file_name}'s manifest names {raw_name or 'no tool'}; Mabillon reads iLEAPP and "
            "ALEAPP output only"
        )
    version = info.get("leapp_version")
    arts: list[Artifact] = []
    for category, entries in manifest["artifacts"].items():
        for e in entries if isinstance(entries, list) else []:
            if not isinstance(e, dict) or not e.get("tablename"):
                continue
            rc = e.get("record_count")
            arts.append(
                Artifact(
                    category=str(category),
                    name=str(e.get("name") or e["tablename"]),
                    key=str(e.get("artifact_key") or e["tablename"]),
                    table=str(e["tablename"]),
                    module=str(e.get("module") or ""),
                    column_map={str(k): str(v) for k, v in (e.get("column_map") or {}).items()},
                    record_count=int(rc) if isinstance(rc, int) else None,
                    source_path=str(e["source_path"]) if e.get("source_path") else None,
                )
            )
    return Lava(
        manifest=manifest,
        db=db,
        manifest_member=man_member,
        db_member=db_member,
        leapp_name=leapp,
        leapp_version=str(version) if version else None,
        artifacts=arts,
    )


def looks_like_leapp_zip(path: Path) -> bool:
    """True when a .zip holds a LEAPP manifest (a UFDR never does)."""
    try:
        with open_input(path) as f, zipfile.ZipFile(f) as z:
            return bool(_member(z.namelist(), MANIFEST_NAMES))
    except (zipfile.BadZipFile, OSError, ValueError):
        return False


# ---------------------------------------------------------------- values


def _text(v: object) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _ident(v: object) -> str | None:
    """A handle as stored, without an iMessage account prefix ('E:', 'P:') or a URI scheme."""
    s = _text(v)
    return _ACCOUNT_PREFIX_RE.sub("", s).strip() or None if s else None


def _time(v: object) -> Timestamp:
    """LEAPP's UTC epoch (seconds) as stored; anything else is kept raw with no time."""
    raw = _text(v)
    if raw is None:
        return Timestamp(utc=None, offset_min=None, raw=None)
    try:
        sec = float(raw)
    except ValueError:
        return Timestamp(utc=None, offset_min=None, raw=raw)
    try:
        utc = datetime.fromtimestamp(sec, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return Timestamp(utc=None, offset_min=None, raw=raw)
    return Timestamp(utc=utc, offset_min=0, raw=f"{raw} (LEAPP UTC epoch)")


def _split(v: object) -> list[str]:
    s = _text(v)
    if s is None:
        return []
    return [p for p in (_ident(x) for x in re.split(r"[,\r\n]+", s)) if p]


def _loc(table: str, column: str, value: object, rowid: int) -> str:
    v = _text(value)
    return f"{table}/{column}={v}" if v is not None else f"{table}/rowid={rowid}"


# ---------------------------------------------------------------- mappers


@dataclass
class _Ctx:
    w: _Writer
    tc: TableCoverage
    art: Artifact
    lava: Lava
    flags: Counter[str] = field(default_factory=Counter)

    def flag(self, reason: str, locator: str) -> None:
        self.tc.flag_counts[reason] += 1
        _listed(self.tc.flagged_locators, reason, locator)


def _party(ident: str | None, owner: bool = False) -> Party:
    return Party(ident, None, owner, None)


def _add_message(
    c: _Ctx,
    app: str,
    locator: str,
    chat_key: str,
    title: str | None,
    sender: Party | None,
    recips: list[Party],
    direction: MessageDirection,
    ts: Timestamp,
    body: str,
    attachments: list[str],
) -> None:
    w = c.w
    scope = chat_key
    sender_id = w.account(app, sender, locator, scope) if sender and sender.identifier else None
    recip_ids = [w.account(app, p, locator, scope) for p in recips if p.identifier]
    tid = w.thread(app, chat_key, locator, title)
    mid = f"msg:{w.src}:{locator}"
    w.messages.append(
        (mid, w.src, locator, tid, sender_id, direction.value, *_ts_cols(ts), body, None, None)
    )
    w.recipients.extend((mid, a) for a in dict.fromkeys(recip_ids) if a != sender_id)
    for n, fname in enumerate(dict.fromkeys(a for a in attachments if a), start=1):
        w.attachments.append((f"att:{w.src}:{locator}:{n}", w.src, locator, mid, fname))
    if not body.strip() and not attachments:
        c.flag("no_body_or_attachment", locator)
    if ts.utc is None:
        c.flag("no_time", locator)
    c.tc.rows_imported += 1


def _ios_sms(c: _Ctx) -> None:
    """iLEAPP `sms`: one row per attachment, grouped by Message Row ID."""
    groups: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for rowid, r in c.lava.rows(c.art):
        c.tc.rows_read += 1
        key = _text(r.get("Message Row ID")) or f"rowid:{rowid}"
        groups[key].append((rowid, r))
    for rows in groups.values():
        rowid, r = rows[0]
        loc = _loc(c.art.table, "message_row_id", r.get("Message Row ID"), rowid)
        owner_ids = [
            i
            for i in (_ident(r.get("Destination Caller ID")), _ident(r.get("Account")))
            if i is not None
        ]
        owner = _party(owner_ids[0], owner=True) if owner_ids else None
        from_me = _text(r.get("From Me"))
        participants = _split(r.get("Chat Participants"))
        if from_me == "1":
            direction = MessageDirection.OUTGOING
            sender = owner
            recips = [_party(p) for p in participants]
            if sender is None:
                c.flag("sent_without_own_account", loc)
        elif from_me == "0":
            direction = MessageDirection.INCOMING
            s = _ident(r.get("Sender"))
            sender = _party(s) if s else None
            recips = [_party(p) for p in participants if p != s]
            if owner is not None:
                recips.append(owner)
            if s is None:
                c.flag("received_without_sender", loc)
        else:
            direction, sender, recips = MessageDirection.UNKNOWN, None, []
            c.flag("direction_not_stated", loc)
        chat = _text(r.get("Chat ID"))
        chat_key = f"chat:{chat}" if chat else f"row:{loc}"
        title = _text(r.get("Chat Name")) or _text(r.get("Chat Contact ID"))
        # iOS writes U+FFFC (the object replacement character) where an attachment sits; the
        # attachment is recorded below, so the character is not part of the text
        body = str(r.get("Message") or "").replace(OBJECT_REPLACEMENT, "")
        atts = [
            _text(x.get("Attachment Name")) or _text(x.get("Attachment Path")) or ""
            for _, x in rows
        ]
        _add_message(
            c, NATIVE_MESSAGES_APP, loc, chat_key, title, sender, recips, direction,
            _time(r.get("Message Timestamp")), body, [a for a in atts if a],
        )  # fmt: skip
        if len(rows) > 1:
            c.tc.flag_counts["rows_grouped_into_one_message"] += len(rows) - 1


def _android_direction(c: _Ctx, value: object, loc: str, count: bool = True) -> MessageDirection:
    v = (_text(value) or "").lower()
    if v in _SMS_IN:
        return MessageDirection.INCOMING
    if v in _SMS_OUT:
        return MessageDirection.OUTGOING
    if count:
        c.flag("not_sent_or_received" if v else "direction_not_stated", loc)
        if v:
            c.w.cov.unmapped_direction_values[str(value)] += 1
    return MessageDirection.UNKNOWN


def _android_sms(c: _Ctx) -> None:
    """ALEAPP `get_sms_mms`: one row per SMS."""
    for rowid, r in c.lava.rows(c.art):
        c.tc.rows_read += 1
        loc = _loc(c.art.table, "msg_id", r.get("MSG ID"), rowid)
        direction = _android_direction(c, r.get("Type"), loc)
        other = _ident(r.get("Address"))
        sender = _party(other) if direction is MessageDirection.INCOMING and other else None
        recips = [_party(other)] if direction is not MessageDirection.INCOMING and other else []
        thread = _text(r.get("Thread ID"))
        chat_key = f"thread:{thread}" if thread else f"sms:{other}" if other else f"row:{loc}"
        _add_message(
            c, NATIVE_MESSAGES_APP, loc, chat_key, other, sender, recips, direction,
            _time(r.get("Date")), str(r.get("Body") or ""), [],
        )  # fmt: skip


def _android_mms(c: _Ctx) -> None:
    """ALEAPP `get_sms_mms_mms`: one row per MMS part, grouped by MSG ID."""
    groups: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for rowid, r in c.lava.rows(c.art):
        c.tc.rows_read += 1
        groups[_text(r.get("MSG ID")) or f"rowid:{rowid}"].append((rowid, r))
    for rows in groups.values():
        rowid, r = rows[0]
        loc = _loc(c.art.table, "msg_id", r.get("MSG ID"), rowid)
        direction = _android_direction(c, r.get("Direction"), loc)
        frm = _ident(r.get("From Address"))
        to = [_party(p) for p in _split(r.get("To Address"))]
        sender = _party(frm) if frm and frm.lower() != "insert-address-token" else None
        thread = _text(r.get("Thread ID"))
        chat_key = f"thread:{thread}" if thread else f"row:{loc}"
        body, media = _mms_parts(c, rows, loc)
        _add_message(
            c, NATIVE_MESSAGES_APP, loc, chat_key, frm, sender, to, direction,
            _time(r.get("Date")), body, media,
        )  # fmt: skip
        if len(rows) > 1:
            c.tc.flag_counts["rows_grouped_into_one_message"] += len(rows) - 1


def _mms_parts(c: _Ctx, rows: list[tuple[int, dict[str, Any]]], loc: str) -> tuple[str, list[str]]:
    """(text parts joined in order, media) for one MMS's part rows."""
    texts: list[str] = []
    media: list[str] = []
    for _, x in rows:
        b, m = _text(x.get("Body")), _text(x.get("Media"))
        if m:
            media.append(m)
        if b and _MMS_PART_PATH_RE.match(b):
            media.append(PurePosixPath(b).name)
            c.flag("media_file_not_in_extraction", loc)
        elif b:
            texts.append(b)
    return "\n".join(texts), media


def _norm(body: str) -> str:
    return " ".join(body.split())


def _native_keys(c: _Ctx) -> dict[tuple[int, str, str], list[str]]:
    """(epoch second, direction, text) of every SMS and MMS in the output, as read above, to the
    locators of the messages that have it."""
    keys: dict[tuple[int, str, str], list[str]] = defaultdict(list)
    probe = _Ctx(c.w, TableCoverage(name="", kind=None), c.art, c.lava)
    for art in c.lava.artifacts:
        if art.key == "get_sms_mms":
            for rowid, r in c.lava.rows(art):
                ts = _time(r.get("Date")).utc
                d = _android_direction(probe, r.get("Type"), f"rowid={rowid}", count=False)
                if ts is not None:
                    keys[(int(ts.timestamp()), d.value, _norm(str(r.get("Body") or "")))].append(
                        _loc(art.table, "msg_id", r.get("MSG ID"), rowid)
                    )
        elif art.key == "get_sms_mms_mms":
            groups: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
            for rowid, r in c.lava.rows(art):
                groups[_text(r.get("MSG ID")) or f"rowid:{rowid}"].append((rowid, r))
            for rows in groups.values():
                rowid, r = rows[0]
                ts = _time(r.get("Date")).utc
                d = _android_direction(probe, r.get("Direction"), "", count=False)
                if ts is not None:
                    text = _norm(_mms_parts(probe, rows, "")[0])
                    keys[(int(ts.timestamp()), d.value, text)].append(
                        _loc(art.table, "msg_id", r.get("MSG ID"), rowid)
                    )
    return keys


def _same_message(
    native: dict[tuple[int, str, str], list[str]],
    ts: Timestamp,
    direction: MessageDirection,
    body: str,
) -> tuple[str, int] | None:
    """(locator, seconds apart) of the nearest SMS or MMS with this direction and text within
    SAME_MESSAGE_SECONDS, the earliest locator on a tie; None when there is none."""
    if ts.utc is None:
        return None
    sec = int(ts.utc.timestamp())
    for dt in sorted(range(-SAME_MESSAGE_SECONDS, SAME_MESSAGE_SECONDS + 1), key=abs):
        locs = native.get((sec + dt, direction.value, _norm(body)))
        if locs:
            return locs[0], dt
    return None


def _android_google_messages(c: _Ctx) -> None:
    """ALEAPP `get_googleMessages` (bugle_db): one row per part, no message id. Parts are grouped
    by conversation, time, direction and sender; a message the SMS and MMS tables already hold is
    skipped and counted."""
    groups: dict[tuple[str, ...], list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for rowid, r in c.lava.rows(c.art):
        c.tc.rows_read += 1
        key = tuple(
            _text(r.get(k)) or ""
            for k in ("Conversation ID", "Message Timestamp", "Direction", "Message Sender")
        )
        groups[key].append((rowid, r))
    native = _native_keys(c)
    for rows in groups.values():
        rowid, r = rows[0]
        loc = f"{c.art.table}/rowid={rowid}"
        ts = _time(r.get("Message Timestamp"))
        d = (_text(r.get("Direction")) or "").lower()
        direction = {"incoming": MessageDirection.INCOMING, "outgoing": MessageDirection.OUTGOING}
        mdir = direction.get(d, MessageDirection.UNKNOWN)
        texts = [t for t in (_text(x.get("Message")) for _, x in rows) if t]
        body = "\n".join(texts)
        media = [
            PurePosixPath(a).name if "/" in a else a
            for a in (_text(x.get("Attachment Location")) for _, x in rows)
            if a
        ]
        media += [
            mt
            for _, x in rows
            if not _text(x.get("Attachment Location"))
            and (mt := _text(x.get("Message Type")) or "")
            and not mt.startswith("text/")
        ]
        match = _same_message(native, ts, mdir, body)
        if match is not None:
            c.tc.rows_skipped["same_as_an_sms_or_mms_message"] += 1
            _listed(c.tc.skipped_locators, "same_as_an_sms_or_mms_message", loc)
            c.lava.dropped.append(
                {"locator": loc, "rows": [i for i, _ in rows], "same_as": match[0],
                 "seconds_apart": match[1]}
            )  # fmt: skip
            continue
        sender_ident = _ident(r.get("Message Sender"))
        convo = _text(r.get("Other Participant/Conversation Name"))
        if mdir is MessageDirection.OUTGOING:
            sender = _party(sender_ident, owner=True) if sender_ident else None
            recips = [_party(_ident(convo))] if convo and _IDENT_RE.match(convo) else []
        elif mdir is MessageDirection.INCOMING:
            sender = _party(sender_ident) if sender_ident else None
            recips = []
            if sender is None:
                c.flag("received_without_sender", loc)
        else:
            sender, recips = None, []
            c.flag("direction_not_stated", loc)
        cid = _text(r.get("Conversation ID"))
        chat_key = f"bugle:{cid}" if cid else f"row:{loc}"
        _add_message(
            c, NATIVE_MESSAGES_APP, loc, chat_key, convo, sender, recips, mdir, ts, body, media
        )
        if len(rows) > 1:
            c.tc.flag_counts["rows_grouped_into_one_message"] += len(rows) - 1


# A conversation name that is a phone number or an address, so it names the other party.
_IDENT_RE = re.compile(r"^(?:\+?[\d\s().-]{5,}|[^@\s]+@[^@\s]+)$")


def _add_call(
    c: _Ctx,
    app: str,
    loc: str,
    frm: Party | None,
    to: Party | None,
    direction: CallDirection,
    ts: Timestamp,
    duration: int | None,
    deleted: bool | None,
) -> None:
    w = c.w
    scope = f"row:{loc}"
    from_id = w.account(app, frm, loc, scope) if frm and frm.identifier else None
    to_id = w.account(app, to, loc, scope) if to and to.identifier else None
    w.calls.append(
        (f"call:{w.src}:{loc}", w.src, loc, w.dev, app, from_id, to_id, direction.value,
         *_ts_cols(ts), duration, _db_bool(deleted))
    )  # fmt: skip
    if ts.utc is None:
        c.flag("no_time", loc)
    c.tc.rows_imported += 1


def _ios_calls(c: _Ctx) -> None:
    """iLEAPP `callHistory`: one row per call."""
    for rowid, r in c.lava.rows(c.art):
        c.tc.rows_read += 1
        loc = _loc(c.art.table, "rowid", rowid, rowid)
        provider = _text(r.get("Service Provider")) or ""
        app = IOS_CALL_APPS.get(provider.lower(), provider or "unknown")
        other = _party(_ident(r.get("Phone Number")))
        d = (_text(r.get("Call Direction")) or "").lower()
        answered = (_text(r.get("Answered")) or "").lower()
        if d == "outgoing":
            direction, frm, to = CallDirection.OUTGOING, None, other
        elif d == "incoming":
            missed = answered == "no"
            direction = CallDirection.MISSED if missed else CallDirection.INCOMING
            frm, to = other, None
        else:
            direction, frm, to = CallDirection.UNKNOWN, None, None
            c.flag("direction_not_stated", loc)
            if other.identifier:
                c.w.account(app, other, loc, f"row:{loc}")
        _add_call(
            c, app, loc, frm, to, direction, _time(r.get("Starting Timestamp")),
            parse_duration(_text(r.get("Call Duration"))), None,
        )  # fmt: skip


def _android_calls(c: _Ctx) -> None:
    """ALEAPP `get_calllog`: one row per call."""
    for rowid, r in c.lava.rows(c.art):
        c.tc.rows_read += 1
        loc = _loc(c.art.table, "rowid", rowid, rowid)
        other = _party(_ident(r.get("Partner")))
        own = _ident(r.get("Phone Account Address"))
        owner = _party(own, owner=True) if own else None
        raw_type = _text(r.get("Raw Call Type (as stored)"))
        direction = _ANDROID_CALL_DIR.get(raw_type or "", CallDirection.UNKNOWN)
        if direction is CallDirection.OUTGOING:
            frm, to = owner, other
        elif direction is CallDirection.UNKNOWN:
            frm, to = None, None
            c.flag("call_type_not_incoming_outgoing_or_missed", loc)
            c.w.cov.unmapped_direction_values[str(raw_type)] += 1
            for p in (other, owner):
                if p and p.identifier:
                    c.w.account("unknown", p, loc, f"row:{loc}")
        else:
            frm, to = other, owner
        dur = _text(r.get("Duration in Secs"))
        deleted = _text(r.get("Deleted"))
        _add_call(
            c, "unknown", loc, frm, to, direction, _time(r.get("Call Date")),
            int(dur) if dur and dur.isdigit() else None,
            None if deleted is None else deleted not in ("0", "False", "false"),
        )  # fmt: skip


def _entries(v: object) -> list[str]:
    """'Mobile: +1 555 0100' lines (iLEAPP joins them with carriage returns) -> the values."""
    s = _text(v)
    if s is None:
        return []
    out = []
    for line in (ln.strip() for ln in s.splitlines()):
        if not line:
            continue
        label, sep, value = line.partition(": ")
        out.append(value.strip() if sep and value.strip() else line)
    return out


def _add_contact(c: _Ctx, loc: str, name: str | None, idents: list[str]) -> None:
    w = c.w
    idents = list(dict.fromkeys(i for i in idents if i))
    if not idents:
        idents = [""]
        w.cov.counters["contacts_without_identifier"] += 1
    for n, ident in enumerate(idents, start=1):
        w.contacts.append((f"contact:{w.src}:{loc}#{n}", w.src, loc, w.dev, name, ident))
    c.tc.rows_imported += 1


def _ios_contacts(c: _Ctx) -> None:
    """iLEAPP `addressBook`: one row per contact; numbers and addresses one per line."""
    for rowid, r in c.lava.rows(c.art):
        c.tc.rows_read += 1
        loc = _loc(c.art.table, "rowid", rowid, rowid)
        name = _text(r.get("Display Name")) or " ".join(
            p for p in (_text(r.get(k)) for k in ("First Name", "Middle Name", "Last Name")) if p
        ) or _text(r.get("Company"))  # fmt: skip
        idents = _entries(r.get("Phone Numbers")) + _entries(r.get("Email addresses"))
        _add_contact(c, loc, name or None, idents)


def _android_contacts(c: _Ctx) -> None:
    """ALEAPP `contacts`: one row per number or address, with the contact's display name."""
    for rowid, r in c.lava.rows(c.art):
        c.tc.rows_read += 1
        loc = _loc(c.art.table, "rowid", rowid, rowid)
        ident = _text(r.get("Phone Number")) or _text(r.get("Email Address"))
        _add_contact(c, loc, _text(r.get("Display Name")), [ident] if ident else [])


@dataclass(frozen=True)
class Spec:
    kind: RecordKind
    read: Callable[[_Ctx], None]


# (tool, LEAPP's function name for the artifact) -> how Mabillon reads it
SPECS: dict[tuple[str, str], Spec] = {
    ("iLEAPP", "sms"): Spec(RecordKind.CHATS, _ios_sms),
    ("iLEAPP", "callHistory"): Spec(RecordKind.CALLS, _ios_calls),
    ("iLEAPP", "addressBook"): Spec(RecordKind.CONTACTS, _ios_contacts),
    ("ALEAPP", "get_sms_mms"): Spec(RecordKind.SMS, _android_sms),
    ("ALEAPP", "get_sms_mms_mms"): Spec(RecordKind.SMS, _android_mms),
    ("ALEAPP", "get_googleMessages"): Spec(RecordKind.SMS, _android_google_messages),
    ("ALEAPP", "get_calllog"): Spec(RecordKind.CALLS, _android_calls),
    ("ALEAPP", "contacts"): Spec(RecordKind.CONTACTS, _android_contacts),
}
# Read elsewhere: listed as not imported with this reason instead of the general one.
SAME_RECORDS = {
    ("ALEAPP", "get_sms_mms_combined"): "the same messages as SMS Messages and MMS Messages",
}
ORDER = [RecordKind.CONTACTS, RecordKind.CHATS, RecordKind.SMS, RecordKind.CALLS]


# ---------------------------------------------------------------- the device


# Where LEAPP writes the phone's time zone: (tool, artifact) -> (time header, zone header), or
# (property header, value header, property) for a property table.
ZONE_SOURCES: dict[tuple[str, str], tuple[str, str] | tuple[str, str, str]] = {
    ("iLEAPP", "powerlogTimeZone"): ("Timestamp", "Time Zone Name"),
    ("iLEAPP", "timezone_info"): ("Property", "Property Value", "Last Bootstrap Timezone"),
    ("ALEAPP", "get_battery_usage_v4"): ("Timestamp", "Timezone"),
}
# Where LEAPP writes the phone's OS version: (tool, artifact) -> (property header, value header,
# properties joined in order).
OS_SOURCES: dict[tuple[str, str], tuple[str, str, tuple[str, ...]]] = {
    ("iLEAPP", "last_build"): ("Property", "Property Value", ("ProductName", "ProductVersion")),
    ("ALEAPP", "usagestatsVersion"): ("Property", "Property Value", ("Android Version",)),
}


def _zone(name: str | None) -> str | None:
    """An IANA zone name the standard library knows, else None."""
    if not name or "/" not in name:
        return None
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    return name


def device_facts(lava: Lava) -> dict[str, Any]:
    """The phone's time zone and OS as LEAPP's device tables state them. The zone is set only
    when every zone the phone recorded is the same one; a phone that recorded two or more gets
    none, since no one zone places all its records, and the expert enters it."""
    zones: dict[str, dict[str, Any]] = {}
    invalid: Counter[str] = Counter()
    os_parts: dict[str, str] = {}
    os_from: str | None = None
    for art in lava.artifacts:
        src = ZONE_SOURCES.get((lava.leapp_name, art.key))
        if src is not None:
            for _rowid, r in lava.rows(art):
                if len(src) == 3:
                    if _text(r.get(src[0])) != src[2]:
                        continue
                    raw, when = _text(r.get(src[1])), None
                else:
                    raw, when = _text(r.get(src[1])), _time(r.get(src[0])).utc
                if raw is None:
                    continue
                name = _zone(raw)
                if name is None:
                    invalid[raw] += 1
                    continue
                z = zones.setdefault(
                    name, {"zone": name, "rows": 0, "first": None, "last": None, "tables": []}
                )
                z["rows"] += 1
                if art.table not in z["tables"]:
                    z["tables"].append(art.table)
                if when is not None:
                    w = _iso(when)
                    z["first"] = min(filter(None, (z["first"], w)))
                    z["last"] = max(filter(None, (z["last"], w)))
        osrc = OS_SOURCES.get((lava.leapp_name, art.key))
        if osrc is not None:
            for _rowid, r in lava.rows(art):
                prop, value = _text(r.get(osrc[0])), _text(r.get(osrc[1]))
                if prop in osrc[2] and value and prop not in os_parts:
                    os_parts[prop] = value
                    os_from = art.table
    found = sorted(zones)
    os_props = next((o[2] for k, o in OS_SOURCES.items() if k[0] == lava.leapp_name), ())
    os_version = " ".join(os_parts[k] for k in os_props if k in os_parts) or None
    if lava.leapp_name == "ALEAPP" and os_version:
        os_version = f"Android {os_version}"
    return {
        "timezone": found[0] if len(found) == 1 else None,
        "zones_seen": [zones[n] for n in found],
        "zones_not_read": dict(invalid),
        "os_version": os_version,
        "os_version_table": os_from,
    }


# ---------------------------------------------------------------- importer


def _fidelity(m: dict[str, Any]) -> tuple[Fidelity, ExtractionType, str]:
    kind = str(m.get("param_type") or "").strip().lower()
    if kind == "itunes":
        return Fidelity.UNKNOWN, ExtractionType.LOGICAL, FIDELITY_REASON_PROFILE
    if kind in FILE_SYSTEM_INPUTS and not m.get("profile_used"):
        return Fidelity.FULL_EXTRACTION, ExtractionType.FILE_SYSTEM, FIDELITY_REASON
    ext = ExtractionType.FILE_SYSTEM if kind in FILE_SYSTEM_INPUTS else ExtractionType.UNKNOWN
    return Fidelity.CURATED_REPORT, ext, FIDELITY_REASON_PROFILE


def _source_id(path: Path, sha: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_\-]{1,64}", path.stem):
        return path.stem
    return f"src_{sha[:12]}"


def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z") if dt else None


class LeappImporter:
    """Implements core.contracts.EvidenceImporter for a zip of an iLEAPP or ALEAPP output
    folder. Format support is UNVERIFIED (module docstring); each import records that."""

    name = IMPORTER_NAME

    def __init__(
        self,
        source_id: str | None = None,
        now: datetime | None = None,
        date_order: str | None = None,
        expected_sha256: str | None = None,
    ) -> None:
        """`date_order` is accepted for the importers' common signature and unused: LEAPP
        stores times as epochs, which have no day/month order."""
        self.source_id = source_id
        self.now = now
        self.expected_sha256 = expected_sha256

    def import_source(self, path: Path, conn: sqlite3.Connection) -> Source:
        sha = sha256_input(path)
        require_sha256(path.name, self.expected_sha256, sha)
        with open_input(path) as f:
            lava = read_lava(f, path.name)
        try:
            source = self._write(path, sha, conn, lava)
        finally:
            lava.db.close()
        return source

    def _write(self, path: Path, sha: str, conn: sqlite3.Connection, lava: Lava) -> Source:
        src = self.source_id or _source_id(path, sha)
        if conn.execute("SELECT 1 FROM sources WHERE id = ?", (src,)).fetchone():
            raise ValueError(f"source {src} is already in this case database")
        fidelity, ext, reason = _fidelity(lava.manifest)
        source = Source(
            id=src,
            kind=SourceKind.LEAPP,
            fidelity=fidelity,
            extraction_type=ext,
            file_name=path.name,
            sha256=sha,
            tool_name=lava.leapp_name,
            tool_version=lava.leapp_version,
            extracted_at_utc=None,
            imported_at_utc=self.now or datetime.now(UTC),
        )
        dev = f"dev:{src}"
        cov = Coverage()
        w = _Writer(conn, src, dev, cov)
        read: list[tuple[Spec, Artifact]] = []
        for art in lava.artifacts:
            spec = SPECS.get((lava.leapp_name, art.key))
            if spec is None:
                why = SAME_RECORDS.get((lava.leapp_name, art.key), "Mabillon does not read it")
                cov.not_imported.append(
                    {"name": art.name, "category": art.category, "table": art.table,
                     "records": art.record_count, "reason": why}
                )  # fmt: skip
                continue
            read.append((spec, art))
        with conn:
            conn.execute(
                "INSERT INTO sources (id, kind, fidelity, extraction_type, file_name, sha256,"
                " tool_name, tool_version, extracted_at_utc, imported_at_utc)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (source.id, source.kind.value, source.fidelity.value,
                 source.extraction_type.value, source.file_name, source.sha256,
                 source.tool_name, source.tool_version, _iso(source.extracted_at_utc),
                 _iso(source.imported_at_utc)),
            )  # fmt: skip
            device = device_facts(lava)
            conn.execute(
                "INSERT INTO devices (id, source_id, locator, label, model, os_version, timezone)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (dev, src, lava.manifest_member, f"Device in {path.name}", None,
                 device["os_version"], device["timezone"]),
            )  # fmt: skip
            for kind in ORDER:
                for spec, art in read:
                    if spec.kind is not kind:
                        continue
                    tc = TableCoverage(name=art.name, kind=kind.value)
                    tc.header_locator = art.table
                    cov.tables.append(tc)
                    spec.read(_Ctx(w, tc, art, lava))
                    if art.record_count is not None and art.record_count != tc.rows_read:
                        tc.header_notes.append(
                            f"The manifest states {art.record_count} records; the table holds "
                            f"{tc.rows_read} rows."
                        )
            w.flush()
            payload = coverage_payload(
                source, IMPORTER_NAME, None, None, cov, sorted({s.kind for s, _ in read})
            )
            payload.update(
                importer_version=IMPORTER_VERSION,
                fidelity_reason=reason,
                format_support=FORMAT_SUPPORT,
                leapp={
                    "leapp_name": lava.leapp_name,
                    "leapp_version": lava.leapp_version,
                    "lava_schema_version": lava.manifest.get("lava_schema_version"),
                    "input_type": lava.manifest.get("param_type"),
                    "profile_used": bool(lava.manifest.get("profile_used")),
                    "processing_status": lava.manifest.get("processing_status"),
                    "manifest_member": lava.manifest_member,
                    "database_member": lava.db_member,
                    "artifacts_read": [
                        {
                            "key": a.key,
                            "name": a.name,
                            "table": a.table,
                            "records": a.record_count,
                            "source_path": a.source_path,
                        }
                        for _, a in read
                    ],  # fmt: skip
                    "artifacts_in_manifest": len(lava.artifacts),
                    # every skipped Google Messages message: its locator, its part rows (LAVA
                    # rowids), the SMS or MMS it matched and how many seconds apart
                    "google_messages_skipped": lava.dropped,
                    # the device's zone and OS, and every zone its tables recorded
                    "device": device,
                },
            )
            check = tested.at_import(
                IMPORTER_NAME, source.id, source.file_name, source.tool_version, lava.leapp_name
            )
            payload["format_check"] = check.payload()
            conn.execute(
                "INSERT INTO source_coverage (source_id, importer, importer_version, payload_json)"
                " VALUES (?, ?, ?, ?)",
                (source.id, IMPORTER_NAME, IMPORTER_VERSION, json.dumps(payload, sort_keys=True)),
            )
            audit_log.append(conn, source.imported_at_utc, "system", "import", payload)
            audit_log.append(conn, source.imported_at_utc, "system", tested.ACTION, check.payload())
            if sha256_input(path) != sha:
                raise ValueError(
                    f"{path.name} changed while Mabillon read it; nothing was imported. Nothing "
                    "should change a copied input, so check the case folder"
                )
        return source
