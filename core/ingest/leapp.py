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
  the call log (`get_calllog`), contacts (`contacts`);
- the chat tables in `CHAT_SPECS` and the app call tables in `CALL_SPECS`, each added only after
  it matched Mabillon's UFDR import of the same public test phone record by record.

A table missing any column its reader uses is not read at all, and is listed as not read.

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
  sender. A message that matches an SMS or MMS already imported (the same direction, text,
  number of attachments and other party, within two seconds, each SMS or MMS matched once) is
  skipped and counted; the others (RCS, chiefly) are imported. One that may be a copy but cannot
  be told for sure is imported, flagged and listed as a possible copy, so a count over it is
  inconclusive.
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
import math
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
    APPS_READ_KEY,
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
IMPORTER_VERSION = "0.2.0"
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
FIDELITY_REASON_INCOMPLETE = (
    "LEAPP's manifest does not say the run completed, so any table may have been cut short and "
    "it cannot support a claim that something is absent from the phone."
)
RUN_COMPLETE = "Complete"  # processing_status LEAPP's lavafuncs.py writes when a run ends
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
    data_views: dict[str, Any] = field(default_factory=dict)


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
    # calls stored with neither side, by app: no check finds them, so that app's calls are not
    # held in full
    calls_without_sides: Counter[str] = field(default_factory=Counter)
    # rows of the phone's own call table that keep it from being held in full: stored with
    # neither side (under whichever app the row names), or naming no package on ALEAPP
    native_calls_not_held: int = 0
    # ALEAPP call log rows written by a package other than the phone's own telephony
    calls_from_other_packages: int = 0
    # artifacts refused for their shape (ctx.failed): never read, never used as a copy source
    refused: set[int] = field(default_factory=set)
    # each table's columns as stored; two manifest entries can share a table with other maps
    _columns: dict[str, list[str]] = field(default_factory=dict, repr=False)
    # record kinds stored from a table read as another kind (a chat table's call notices)
    extra_kinds: set[RecordKind] = field(default_factory=set)

    def has_table(self, art: Artifact) -> bool:
        return bool(
            self.db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (art.table,)
            ).fetchone()
        )

    def headers(self, art: Artifact) -> set[str]:
        """The artifact's columns, as LEAPP wrote their headers (none when the table is missing)."""
        if art.table not in self._columns:
            quoted = art.table.replace(chr(34), chr(34) * 2)
            info = self.db.execute(f'PRAGMA table_info("{quoted}")')
            self._columns[art.table] = [r[1] for r in info]
        return {art.column_map.get(c, c) for c in self._columns[art.table]}

    def rows(self, art: Artifact) -> Iterator[tuple[int, dict[str, Any]]]:
        """(rowid, {header as LEAPP wrote it: value}) for each row of the artifact's table; none
        when the table is missing (the importer lists such an artifact as not read)."""
        if not self.has_table(art):
            return
        quoted = art.table.replace(chr(34), chr(34) * 2)
        real = {r[1].lower() for r in self.db.execute(f'PRAGMA table_info("{quoted}")')}
        alias = next((a for a in ("_rowid_", "rowid", "oid") if a not in real), None)
        if alias is None:
            # Every name for SQLite's row id is a real column here, so no row could be cited.
            raise ValueError(f"LEAPP table {art.table} has columns that hide its row ids")
        cur = self.db.execute(f'SELECT {alias}, * FROM "{quoted}"')  # noqa: S608  (a table the manifest names, quoted)
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
        # deserialize copies the bytes into SQLite, so the read is not kept past this call
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
                    data_views=e["data_views"] if isinstance(e.get("data_views"), dict) else {},
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
    failed: str | None = None  # why the table could not be read; set by its mapper

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
            # The phone's own line received it. When the row does not name that line, the
            # receivers are not all known, so none are stored and the checks hold the row open
            # as possibly to anyone, never as to the other members only (Claude review, #264).
            recips = ([_party(p) for p in participants if p != s] + [owner]) if owner else []
            if owner is None:
                c.flag("received_without_own_account", loc)
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
        # Every receiver the MMS names: To, Cc and Bcc (Greptile on #264).
        named = [p for k in ("To Address", "Cc", "Bcc") for p in _split(r.get(k))]
        to = [_party(p) for p in dict.fromkeys(named)]
        if direction is MessageDirection.INCOMING:
            # ALEAPP does not say which number is the phone's own line, so a received MMS that
            # names receivers may leave it out; like a received SMS, it stores none and the
            # checks hold it open as possibly to anyone (Claude review, #264).
            to = []
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


def _party_key(v: object) -> str | None:
    """A handle as compared across message stores: an email casefolded, a number as its digits;
    None for a display name or nothing."""
    s = _ident(v)
    if s is None or not _IDENT_RE.match(s):
        return None
    if "@" in s:
        return s.casefold()
    digits = re.sub(r"\D", "", s)
    if not digits:
        return None
    # An explicit international prefix ("+" or "00") is kept as "+", so two numbers that both
    # carry their country code are never matched by suffix (CodeRabbit on #264).
    if s.startswith("+"):
        return "+" + digits
    if digits.startswith("00") and len(digits) > 2:
        return "+" + digits[2:]
    return digits


def _same_party(a: str, b: str) -> bool:
    """True when two party keys name one handle: equal, or one number is the other with a
    country code of up to three digits in front of at least ten digits ("+19195550111" and
    "(919) 555-0111"). The longer one must carry its country code explicitly ("+" or "00"):
    without it, "17912345678" may be another national number, not "7912345678" with a country
    code (CodeRabbit on #264). Two numbers that both carry one match only when equal."""
    if a == b:
        return True
    if "@" in a or "@" in b or (a.startswith("+") and b.startswith("+")):
        return False
    short, long = sorted((a, b), key=lambda k: len(k.lstrip("+")))
    return long.startswith("+") and _suffix_of(short, long)


def _suffix_of(short: str, long: str) -> bool:
    """True when `long`'s digits are `short`'s (at least ten) after one to three more."""
    s, l_ = short.lstrip("+"), long.lstrip("+")
    return len(s) >= 10 and l_.endswith(s) and 1 <= len(l_) - len(s) <= 3


def _maybe_same_party(a: str, b: str) -> bool:
    """True when two numbers that `_same_party` keeps apart may still be one handle: one is the
    other after one to three digits that may be a country code but are not marked as one
    ("17912345678" and "7912345678"), or a national number written with its trunk 0
    ("07911 123456") whose rest of at least seven digits is the other number after a country
    code of up to three digits ("+44 7911 123456"). Never enough for a copy, only for a
    possible copy (CodeRabbit on #264)."""
    if "@" in a or "@" in b or (a.startswith("+") and b.startswith("+")) or _same_party(a, b):
        return False
    if _suffix_of(*sorted((a, b), key=lambda k: len(k.lstrip("+")))):
        return True
    for nat, intl in ((a, b), (b, a)):
        rest, full = nat[1:], intl.lstrip("+")
        if (
            nat.startswith("0")
            and not nat.startswith("00")
            and len(rest) >= 7
            and full.endswith(rest)
            and 1 <= len(full) - len(rest) <= 3
        ):
            return True
    return False


@dataclass(frozen=True)
class _Native:
    """An SMS or MMS as the Google Messages reader compares it."""

    locator: str
    party: str | None  # the one other party it names; None when it names none or several
    media: int  # attachments


def _one_party(idents: list[str]) -> str | None:
    keys = {k for k in (_party_key(i) for i in idents) if k}
    return next(iter(keys)) if len(keys) == 1 and len(idents) == 1 else None


def _native_keys(c: _Ctx) -> dict[tuple[int, str, str], list[_Native]]:
    """(epoch second, direction, text) of every SMS and MMS in the output, as read above, to the
    messages that have it, in table order."""
    keys: dict[tuple[int, str, str], list[_Native]] = defaultdict(list)
    probe = _Ctx(c.w, TableCoverage(name="", kind=None), c.art, c.lava)
    for art in c.lava.artifacts:
        spec = SPECS.get((c.lava.leapp_name, art.key))
        if spec is None or not c.lava.has_table(art):
            continue
        if id(art) in c.lava.refused or not set(spec.required) <= c.lava.headers(art):
            # a table refused is not imported, so it never stands for a copy (CodeRabbit and
            # Claude review on #268); the column test covers a table read after this one
            continue
        if art.key == "get_sms_mms":
            for rowid, r in c.lava.rows(art):
                ts = _time(r.get("Date")).utc
                d = _android_direction(probe, r.get("Type"), f"rowid={rowid}", count=False)
                if ts is not None:
                    keys[(int(ts.timestamp()), d.value, _norm(str(r.get("Body") or "")))].append(
                        _Native(
                            _loc(art.table, "msg_id", r.get("MSG ID"), rowid),
                            _one_party(_split(r.get("Address"))),
                            0,
                        )
                    )
        elif art.key == "get_sms_mms_mms":
            groups: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
            for rowid, r in c.lava.rows(art):
                groups[_text(r.get("MSG ID")) or f"rowid:{rowid}"].append((rowid, r))
            for rows in groups.values():
                rowid, r = rows[0]
                ts = _time(r.get("Date")).utc
                d = _android_direction(probe, r.get("Direction"), "", count=False)
                if ts is None:
                    continue
                text, media = _mms_parts(probe, rows, "")
                if d is MessageDirection.INCOMING:
                    frm = _ident(r.get("From Address"))
                    named = [frm] if frm and frm.lower() != "insert-address-token" else []
                elif d is MessageDirection.OUTGOING:
                    cols = ("To Address", "Cc", "Bcc")
                    named = list(dict.fromkeys(p for k in cols for p in _split(r.get(k))))
                else:
                    named = []
                keys[(int(ts.timestamp()), d.value, _norm(text))].append(
                    _Native(
                        _loc(art.table, "msg_id", r.get("MSG ID"), rowid),
                        _one_party(named),
                        len(media),
                    )
                )
    return keys


@dataclass(frozen=True)
class _GmMessage:
    """A Google Messages message as compared with the SMS and MMS tables."""

    ts: Timestamp
    direction: MessageDirection
    body: str
    party: str | None  # its other party (_party_key); None when it cannot be told
    media: int  # attachments
    inferred: bool = False  # party taken from the chat's one sender, not stated or a contact
    several: bool = False  # more than one text in one second: may be several messages joined


def _match_copies(
    msgs: list[_GmMessage], native: dict[tuple[int, str, str], list[_Native]]
) -> list[tuple[tuple[str, int] | None, str | None]]:
    """For each Google Messages message, (match, possible).

    A candidate is an SMS or MMS within SAME_MESSAGE_SECONDS with the same direction, text and
    number of attachments. It is a copy when both name their other party and the two are the
    same (`_same_party`). Copies are paired nearest in time first (then in table order), each
    SMS or MMS and each Google Messages message at most once (CodeRabbit on #264). The two
    stores name an attachment's file differently (a Google Messages cache path, an MMS part
    file), so attachments cannot be compared one to one: a message with attachments is paired
    only when it has one copy and that SMS or MMS is a copy of no other Google Messages message.
    A message whose party was inferred, or that joins several texts sent in one second, is never
    paired.

    match is (locator, seconds apart) of its pair. possible, when it has no pair, is the
    locator of the nearest candidate it may be a copy of: one whose other party cannot be
    compared or may be the same number written another way (`_maybe_same_party`), or a copy
    left unpaired because attachments could not tell which is which or its SMS or MMS was
    paired with another Google Messages message. Any candidate counts, paired or not, so a
    count over both is inconclusive (CodeRabbit on #264)."""
    cands: list[list[tuple[int, int, _Native]]] = []
    for m in msgs:
        out: list[tuple[int, int, _Native]] = []
        if m.ts.utc is not None:
            sec = int(m.ts.utc.timestamp())
            for dt in range(-SAME_MESSAGE_SECONDS, SAME_MESSAGE_SECONDS + 1):
                for n in native.get((sec + dt, m.direction.value, _norm(m.body)), []):
                    if n.media == m.media:
                        out.append((abs(dt), dt, n))
        cands.append(sorted(out, key=lambda x: (x[0], x[1])))

    def copy(m: _GmMessage, n: _Native) -> bool:
        return m.party is not None and n.party is not None and _same_party(m.party, n.party)

    # A party taken only from the chat's one sender may be a group's one sender so far, and a
    # group of texts sent in one second may be several messages joined, so neither ever
    # confirms a copy (CodeRabbit on #264): such a match is a possible copy.
    copies = [
        [x for x in cs if copy(m, x[2])] if not (m.inferred or m.several) else []
        for m, cs in zip(msgs, cands, strict=True)
    ]
    claimants = Counter(x[2].locator for cs in copies for x in cs)
    result: list[tuple[tuple[str, int] | None, str | None]] = [(None, None)] * len(msgs)
    used: set[str] = set()
    paired: set[int] = set()
    for _a, i, j in sorted((x[0], i, j) for i, cs in enumerate(copies) for j, x in enumerate(cs)):
        _, dt, n = copies[i][j]
        if i in paired or n.locator in used:
            continue
        if msgs[i].media and (len(copies[i]) > 1 or claimants[n.locator] > 1):
            continue
        paired.add(i)
        used.add(n.locator)
        result[i] = ((n.locator, dt), None)
    for i, (m, cs) in enumerate(zip(msgs, cands, strict=True)):
        if i in paired:
            continue
        possible = next(
            (
                n.locator
                for _a, _dt, n in cs
                if copy(m, n)
                or m.party is None
                or n.party is None
                or _maybe_same_party(m.party, n.party)
            ),
            None,
        )
        result[i] = (None, possible)
    return result


def _contact_numbers(lava: Lava) -> dict[str, list[str]]:
    """ALEAPP contacts: display name -> the party keys of its phone numbers."""
    out: dict[str, list[str]] = defaultdict(list)
    for art in lava.artifacts:
        if art.key == "contacts":
            for _rowid, r in lava.rows(art):
                name, k = _text(r.get("Display Name")), _party_key(r.get("Phone Number"))
                if name and k:
                    out[name].append(k)
    return out


def _sent_party(
    r: dict[str, Any], heard: set[str], named: dict[str, list[str]]
) -> tuple[str | None, bool]:
    """(other party, inferred) of a sent Google Messages message. `Other Participant/
    Conversation Name` when it is a number or email; else, when it is a display name, the one
    number the phone's contacts give that name, if every sender heard in the chat is that number
    too; else the chat's one sender, inferred (it may be a group's one sender so far)."""
    label = r.get("Other Participant/Conversation Name")
    if k := _party_key(label):
        return k, False
    nums = named.get(_text(label) or "", [])
    if nums and all(_same_party(nums[0], x) for x in nums[1:]):
        if all(_same_party(nums[0], h) for h in heard):
            return nums[0], False
        return None, False
    if len(heard) == 1:
        return next(iter(heard)), True
    return None, False


def _android_google_messages(c: _Ctx) -> None:
    """ALEAPP `get_googleMessages` (bugle_db): one row per part, no message id. Parts are grouped
    by conversation, time, direction and sender; a message the SMS and MMS tables already hold is
    skipped and counted. One that may be such a message, but whose other party cannot be compared,
    is kept and flagged."""
    groups: dict[tuple[str, ...], list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for rowid, r in c.lava.rows(c.art):
        c.tc.rows_read += 1
        key = tuple(
            _text(r.get(k)) or ""
            for k in ("Conversation ID", "Message Timestamp", "Direction", "Message Sender")
        )
        groups[key].append((rowid, r))
    native = _native_keys(c)
    # A sent message names the phone as its sender and the chat by display name, so its other
    # party is the one sender of the chat's received messages, when the chat has exactly one.
    heard: dict[str, set[str]] = defaultdict(set)
    for (cid, _t, d, who), _rows in groups.items():
        if d.lower() == "incoming" and (k := _party_key(who)):
            heard[cid].add(k)
    named = _contact_numbers(c.lava)
    msgs: list[_GmMessage] = []
    medias: list[list[str]] = []
    for rows in groups.values():
        r = rows[0][1]
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
        inferred = False
        if mdir is MessageDirection.INCOMING:
            party = _party_key(r.get("Message Sender"))
        elif mdir is MessageDirection.OUTGOING:
            cid = _text(r.get("Conversation ID")) or ""
            party, inferred = _sent_party(r, heard[cid], named)
        else:
            party = None
        msgs.append(_GmMessage(ts, mdir, body, party, len(media), inferred, len(texts) > 1))
        medias.append(media)
    matches = _match_copies(msgs, native)
    for rows, m, media, (match, possible) in zip(
        groups.values(), msgs, medias, matches, strict=True
    ):
        rowid, r = rows[0]
        loc = f"{c.art.table}/rowid={rowid}"
        ts, mdir, body = m.ts, m.direction, m.body
        if m.several:
            # Parts are grouped by the whole second, with no message id, so two texts from one
            # sender in one second may be two messages joined: a count over it never passes
            # (Claude review on #264).
            c.flag("may_be_several_messages", loc)
            c.w.cov.numbered_copy_records.append(f"msg:{c.w.src}:{loc}")
        if possible is not None:
            c.flag("may_be_same_as_an_sms_or_mms_message", loc)
            # Both may be one message, so a count over them never passes (count check).
            c.w.cov.numbered_copy_records += [f"msg:{c.w.src}:{loc}", f"msg:{c.w.src}:{possible}"]
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


# ---------------------------------------------------------------- other chat apps


def _has_columns(c: _Ctx, wanted: list[str]) -> bool:
    """True when the table has every column its mapper reads. Otherwise nothing is read and the
    table is listed as not read: a LEAPP version that writes another shape is never read in part
    (a missing column would read as empty on every row)."""
    missing = sorted(set(wanted) - c.lava.headers(c.art))
    if missing:
        named = ", ".join(missing)
        c.tc.header_notes.append(f"The table has no column {named}, so nothing was read.")
        c.failed = f"its table has no column {named}, a shape Mabillon has not checked"
        return False
    return True


@dataclass(frozen=True)
class ChatSpec:
    """A chat app's LEAPP artifact, read through the conversation view LEAPP itself publishes
    for it (the manifest's data_views.conversation: which columns hold the conversation, text,
    direction, time, sender and media). Only artifacts checked record by record against a UFDR
    of the same public test phone are listed (docs/ingest/leapp.md)."""

    app: str  # the app name every importer gives it (as a UFDR names it)
    sender_id: str | None = None  # header holding the sender's account id, checked on the UFDR
    sender_id_outgoing: bool = False  # True when that header also names the owner on sent rows
    # The columns to read, by header, for a table LEAPP publishes no conversation view for
    # (the same keys as the view's). None reads LEAPP's own view.
    view: dict[str, Any] | None = None
    # (header, value) a live row shows; any other row was recovered from free space and may
    # repeat a live one, so it is flagged and listed as a possible copy
    live: tuple[str, str] | None = None
    # True when the table writes the app's calls as rows whose text is a call notice (ALEAPP
    # Telegram's "[Phone call (call id ...)]"): such a row is read as a call, not a message
    call_notices: bool = False


CHAT_SPECS: dict[tuple[str, str], ChatSpec] = {
    ("ALEAPP", "instagramDirectMessages"): ChatSpec("Instagram", "Sender ID", True),
    ("ALEAPP", "kik_messages"): ChatSpec("Kik Messenger", "Partner JID"),
    ("ALEAPP", "get_snapchat_arroyo_messages"): ChatSpec("Snapchat", "Sender ID", True),
    ("ALEAPP", "get_tikTok"): ChatSpec("TikTok"),
    ("ALEAPP", "get_whatsapp_one_to_one_messages"): ChatSpec("WhatsApp", "Sending Party JID"),
    ("iLEAPP", "DiscordChatsA"): ChatSpec("Discord", "Sender ID", True),
    ("iLEAPP", "facebookMessengerChats"): ChatSpec("Facebook Messenger", "Sender ID", True),
    ("iLEAPP", "groupMeMessages"): ChatSpec("GroupMe"),
    ("iLEAPP", "instagram_threads"): ChatSpec("Instagram", "Sender ID", True),
    ("iLEAPP", "kikMessages"): ChatSpec("Kik Messenger"),
    ("iLEAPP", "get_signalIOSMessages"): ChatSpec("Signal", "Author"),
    ("iLEAPP", "telegramMessages"): ChatSpec("Telegram"),
    ("iLEAPP", "tiktok_messages"): ChatSpec("TikTok", "Sender", True),
    ("iLEAPP", "viber_chats"): ChatSpec("Viber", "Sender (Phone)"),
    ("iLEAPP", "whatsAppMessages"): ChatSpec("WhatsApp", "From ID"),
    # Added after #264, each checked against the UFDR import of the same public phone.
    ("ALEAPP", "get_telegramMessages"): ChatSpec(
        "Telegram",
        "Sender ID",
        sender_id_outgoing=True,
        view={
            "textColumn": "Message",
            "directionColumn": "Direction",
            "directionSentValue": "Outgoing",
            "timeColumn": "Timestamp",
            "conversationDiscriminatorColumn": "Dialog ID",
            "conversationLabelColumn": "Chat",
            "senderColumn": "Sender",
            "mediaColumn": "Recorded Media Path",
        },
        live=("Record Origin", "Live"),
        call_notices=True,
    ),
    ("iLEAPP", "snapchatMessages"): ChatSpec(
        "Snapchat", "Sender Username", True, live=("Record Origin", "Live")
    ),
}
# Direction values that mean received, beside the view's own sent value.
_CHAT_IN = {"incoming", "received", "inbound", "in"}


def _chat_direction(value: object, sent: object) -> MessageDirection:
    v = _text(value)
    if v is None:
        return MessageDirection.UNKNOWN
    if v == str(sent).strip():
        return MessageDirection.OUTGOING
    if str(sent).strip() in ("1", "True", "true") and v in ("0", "False", "false"):
        return MessageDirection.INCOMING
    return MessageDirection.INCOMING if v.lower() in _CHAT_IN else MessageDirection.UNKNOWN


def _chat_ident(v: object) -> str | None:
    """A sender id as stored; a group's id (WhatsApp '@g.us') or a placeholder is not a
    person's account."""
    s = _ident(v)
    if s is None or s.endswith("@g.us") or s.lower() in ("signed-in account", "local user"):
        return None
    return s


def _chat_messages(c: _Ctx) -> None:
    """A chat app's messages through LEAPP's conversation view: one message per row."""
    spec = CHAT_SPECS[(c.lava.leapp_name, c.art.key)]
    view = spec.view or c.art.data_views.get("conversation") or {}
    col = {} if spec.view else c.art.column_map

    def header(key: str) -> str | None:
        name = view.get(key)
        return col.get(str(name), str(name)) if name else None

    h_text, h_dir, h_time = header("textColumn"), header("directionColumn"), header("timeColumn")
    h_sender, h_convo = header("senderColumn"), header("conversationDiscriminatorColumn")
    h_label, h_media = header("conversationLabelColumn"), header("mediaColumn")
    if not (h_text and h_dir and h_time):
        c.tc.header_notes.append("LEAPP's conversation view for this table names no text, "
                                 "direction or time column, so nothing was read.")  # fmt: skip
        c.failed = "LEAPP's conversation view for it names no text, direction or time column"
        return
    wanted = [h_text, h_dir, h_time, h_sender, h_convo, h_label, h_media, spec.sender_id]
    wanted += [spec.live[0]] if spec.live else []
    if not _has_columns(c, [h for h in wanted if h]):
        return
    for rowid, r in c.lava.rows(c.art):
        c.tc.rows_read += 1
        loc = f"{c.art.table}/rowid={rowid}"
        direction = _chat_direction(r.get(h_dir), view.get("directionSentValue"))
        if direction is MessageDirection.UNKNOWN:
            c.flag("direction_not_stated", loc)
        # the view's sender column, when it is not the id column itself, is a display name
        name = _text(r.get(h_sender)) if h_sender and h_sender != spec.sender_id else None
        sid = _chat_ident(r.get(spec.sender_id)) if spec.sender_id else None
        if direction is MessageDirection.OUTGOING:
            sid = sid if spec.sender_id_outgoing else None
            sender = _party(sid, owner=True) if sid else None
        elif direction is MessageDirection.INCOMING:
            # a display name alone is not taken as an account: two people can share one
            sender = _party(sid) if sid else None
            if sender is None:
                c.flag("sender_name_only" if name else "received_without_sender", loc)
        else:
            sender = None
        recovered = bool(spec.live) and _text(r.get(spec.live[0])) != spec.live[1]
        text = str(r.get(h_text) or "")
        if spec.call_notices and (notice := _CALL_NOTICE_FORM.match(text)):
            _call_notice(c, spec.app, loc, notice, direction, sender, recovered, r.get(h_time))
            continue
        if spec.call_notices and _CALL_NOTICE_LEAD.match(text):
            c.flag("call_notice_shape_not_checked", loc)
            c.lava.calls_without_sides[spec.app] += 1
        convo = _text(r.get(h_convo)) if h_convo else None
        chat_key = f"chat:{convo}" if convo else f"row:{loc}"
        title = (_text(r.get(h_label)) if h_label else None) or convo
        media = _text(r.get(h_media)) if h_media else None
        _add_message(
            c, spec.app, loc, chat_key, title, sender, [], direction,
            _time(r.get(h_time)), text,
            [PurePosixPath(media).name if "/" in media else media] if media else [],
        )  # fmt: skip
        if recovered:
            # A row recovered from the database's free space or journal can repeat a live
            # one (Telegram on the public Android 13 phone): a count over it never passes.
            c.flag("recovered_record_may_repeat_another", loc)
            c.w.cov.numbered_copy_records.append(f"msg:{c.w.src}:{loc}")


# A row is a call notice only when its whole text has the form ALEAPP writes for one (its
# telegramAndroid.py at ed1b63d: the call id, then an outcome and a length when the record holds
# them), so a message someone typed that only starts like one stays a message (Claude review and
# CodeRabbit on #268). The chat table names no service rows, so a typed text in exactly this form
# cannot be told from a notice.
_CALL_NOTICE_FORM = re.compile(
    r"^\[Phone call \(call id -?\d+"
    r"(?:, outcome (?P<outcome>missed|disconnected|hung up|busy|unknown))?"
    r"(?:, duration seconds (?P<seconds>-?\d+))?\)\]$"
)
# Text that opens like a notice: one not in the whole form above is kept as a message, flagged,
# and keeps the app's calls from being held in full (Claude review on #268).
_CALL_NOTICE_LEAD = re.compile(r"^\[Phone call \(call id -?\d+\b")
# Only a notice of a call that was answered and hung up, with its length, was checked: on the
# public Android 13 phone each one matched a UFDR Telegram call on time, direction, caller and
# length.
_CHECKED_OUTCOME = "hung up"


def _call_notice(
    c: _Ctx,
    app: str,
    loc: str,
    notice: re.Match[str],
    direction: MessageDirection,
    sender: Party | None,
    recovered: bool,
    raw_time: object,
) -> None:
    """A chat row that records a call: stored as a call of the app, never as a message. Only a
    live notice of a call that was answered and hung up, in a stated direction, keeps its sides:
    the sender places the call. Any other notice is stored with no sides and flagged, so the
    app's calls are not held in full."""
    seconds = notice["seconds"]
    checked = (
        notice["outcome"] == _CHECKED_OUTCOME
        and seconds is not None
        and not seconds.startswith("-")
    )
    kind = {MessageDirection.OUTGOING: CallDirection.OUTGOING,
            MessageDirection.INCOMING: CallDirection.INCOMING}.get(direction)  # fmt: skip
    frm: Party | None = sender
    if recovered:
        c.flag("recovered_record_may_repeat_another", loc)
        c.w.cov.numbered_copy_records.append(f"call:{c.w.src}:{loc}")
    if not checked or kind is None or recovered or sender is None:
        if not checked:
            # a notice with no direction is flagged direction_not_stated with the chat's rows
            c.flag("call_not_incoming_outgoing_or_missed", loc)
        elif sender is None and kind is CallDirection.OUTGOING:
            # an incoming one is flagged received_without_sender with the chat's rows
            c.flag("sent_without_own_account", loc)
        if sender is not None and sender.identifier:
            c.w.account(app, sender, loc, f"row:{loc}")
        kind, frm = CallDirection.UNKNOWN, None
    c.flag("call_notice_read_as_call", loc)
    length = int(seconds) if checked and seconds is not None else None
    _add_call(c, app, loc, frm, None, kind, _time(raw_time), length, None)
    c.lava.extra_kinds.add(RecordKind.CALLS)


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
    if from_id is None and to_id is None:
        # No check can find a call that names neither side (no direction, or no number on
        # either end), so the call log is then not held in full (CodeRabbit on #264).
        c.lava.calls_without_sides[app] += 1
        if c.art.key in _NATIVE_CALL_KEYS:
            # whichever app the row names (CallKit providers on iOS): the phone's own call
            # table is then not held in full (Claude review on #268)
            c.lava.native_calls_not_held += 1
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


_ANDROID_TELEPHONY = "com.android.phone"


def _call_sides(
    c: _Ctx,
    app: str,
    loc: str,
    direction: CallDirection,
    other: Party | None,
    owner: Party | None,
) -> tuple[Party | None, Party | None]:
    """(from, to) of a call. A call of unknown direction stores neither side, since either may
    have placed it, but both accounts are still recorded."""
    if direction is CallDirection.OUTGOING:
        return owner, other
    if direction is CallDirection.UNKNOWN:
        for p in (other, owner):
            if p and p.identifier:
                c.w.account(app, p, loc, f"row:{loc}")
        return None, None
    return other, owner


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
        if direction is CallDirection.UNKNOWN:
            c.flag("call_type_not_incoming_outgoing_or_missed", loc)
            c.w.cov.unmapped_direction_values[str(raw_type)] += 1
        package = _text(r.get("Phone Account Package"))
        other_app = False
        if package != _ANDROID_TELEPHONY:
            # An app that places calls through Android's telecom service (a VoIP app) can write
            # them here, so no app's own call table holds every call it made; a row that names
            # no package may be one too.
            c.lava.calls_from_other_packages += 1
            if package:
                # Another app's call is not a phone call: it is kept with neither side, so no
                # check reads it as one, and the call log is not held in full (Claude review).
                other_app = True
                c.flag("call_placed_by_another_app", loc)
            else:
                # kept as a phone call, but the call log is not held in full (Claude review)
                c.lava.native_calls_not_held += 1
                c.flag("call_package_not_stated", loc)
        frm, to = _call_sides(
            c, "unknown", loc, CallDirection.UNKNOWN if other_app else direction, other, owner
        )
        dur = _text(r.get("Duration in Secs"))
        deleted = _text(r.get("Deleted"))
        _add_call(
            c, "unknown", loc, frm, to, direction, _time(r.get("Call Date")),
            int(dur) if dur and dur.isdigit() else None,
            None if deleted is None else deleted not in ("0", "False", "false"),
        )  # fmt: skip


@dataclass(frozen=True)
class CallSpec:
    """A chat app's call log as LEAPP writes it: one row per call. Only tables checked call by
    call against a UFDR of the same public test phone are listed (docs/ingest/leapp.md)."""

    app: str  # the app name every importer gives it (as a UFDR names it)
    time: str  # header of the call's start (LEAPP UTC epoch)
    direction: str  # header saying Incoming or Outgoing
    other: str  # header holding the other party's account id
    duration: str | None = None  # header holding the length (seconds or H:M:S)
    end: str | None = None  # header holding the end time, when no length is given
    owner: str | None = None  # header holding the phone's own account id
    group: str | None = None  # header naming a group call: its parties are not known
    missed: str | None = None  # header that is "Yes" on a missed call
    # (header, value) every call must show to be read; another value is a shape not checked
    expect: tuple[tuple[str, str], ...] = ()
    empty: tuple[str, ...] = ()  # headers empty on every checked call; a value is not read
    # False when a call with more than one other party cannot be told from a two-party call, so
    # the table never holds every party of the app's calls and the app is never read in full
    all_parties: bool = True

    def columns(self) -> list[str]:
        named = [self.time, self.direction, self.other, self.duration, self.end, self.owner,
                 self.group, self.missed, *(h for h, _ in self.expect), *self.empty]  # fmt: skip
        return [h for h in named if h]


CALL_SPECS: dict[tuple[str, str], CallSpec] = {
    ("ALEAPP", "get_whatsapp_call_logs"): CallSpec(
        "WhatsApp",
        "Call Start Timestamp",
        "Call Direction",
        "Caller JID",
        duration="Call Duration",
        group="Group Name",
        # Group Name is the subject of the group chat a call was placed from; a group call
        # started outside a group chat has none, and ALEAPP does not read its participants
        # (Claude review on #268), so it reads as a call with the caller alone.
        all_parties=False,
    ),  # fmt: skip
    ("ALEAPP", "get_Viber"): CallSpec(
        "Viber",
        "Call Start Time",
        "Call Direction",
        "Phone Number",
        end="Call End Time (computed: start + duration)",
    ),  # fmt: skip
    # ALEAPP writes the other party in From ID on both incoming and outgoing calls; To ID was
    # empty on every checked call.
    ("ALEAPP", "get_line_calls"): CallSpec(
        "Line",
        "Start Time",
        "Direction",
        "From ID",
        end="End Time",
        empty=("To ID",),
    ),  # fmt: skip
    ("iLEAPP", "whatsAppCallHistory"): CallSpec(
        "WhatsApp",
        "Starting Timestamp",
        "Direction",
        "Contact ID",
        duration="Duration H:M:S",
        group="Group JID",
        missed="Missed",
    ),  # fmt: skip
    ("iLEAPP", "lineCalls"): CallSpec(
        "Line",
        "Call Started",
        "Direction",
        "Contact MID",
        duration="Duration (seconds)",
        owner="Account ID",
        expect=(("Result (as stored)", "NORMAL"),),
    ),  # fmt: skip
}


def _seconds(v: object) -> int | None:
    """A length in whole seconds: '104', '00:01:44' or '83.0'."""
    t = _text(v)
    if t is None:
        return None
    n = parse_duration(t)
    if n is not None:
        return n
    try:
        f = float(t)
    except ValueError:
        return None
    return int(f) if math.isfinite(f) and f >= 0 else None


def _app_calls(c: _Ctx) -> None:
    """A chat app's call log (CALL_SPECS): one call per row. A call whose direction, group or
    other columns are not what was checked is imported with direction unknown and no sides, and
    flagged, so the app's calls are not held in full."""
    spec = CALL_SPECS[(c.lava.leapp_name, c.art.key)]
    if not _has_columns(c, spec.columns()):
        return
    for rowid, r in c.lava.rows(c.art):
        c.tc.rows_read += 1
        loc = _loc(c.art.table, "rowid", rowid, rowid)
        d = (_text(r.get(spec.direction)) or "").lower()
        direction = {"incoming": CallDirection.INCOMING, "outgoing": CallDirection.OUTGOING}.get(
            d, CallDirection.UNKNOWN
        )
        if spec.missed:
            # only "No", and "Yes" on an incoming call, were checked (CodeRabbit on #268)
            missed = (_text(r.get(spec.missed)) or "").lower()
            if missed == "yes" and direction is CallDirection.INCOMING:
                direction = CallDirection.MISSED
            elif missed != "no":
                direction = CallDirection.UNKNOWN
        unchecked = [h for h, v in spec.expect if _text(r.get(h)) != v]
        unchecked += [h for h in spec.empty if _text(r.get(h))]
        if spec.group and _text(r.get(spec.group)):
            c.flag("group_call_parties_not_read", loc)
            direction = CallDirection.UNKNOWN
        elif direction is CallDirection.UNKNOWN or unchecked:
            c.flag("call_not_incoming_outgoing_or_missed", loc)
            direction = CallDirection.UNKNOWN
        other = _party(_ident(r.get(spec.other)))
        own = _ident(r.get(spec.owner)) if spec.owner else None
        owner = _party(own, owner=True) if own else None
        frm, to = _call_sides(c, spec.app, loc, direction, other, owner)
        start = _time(r.get(spec.time))
        length = _seconds(r.get(spec.duration)) if spec.duration else None
        if spec.end and start.utc is not None:
            end = _time(r.get(spec.end))
            if end.utc is not None and end.utc >= start.utc:
                length = int((end.utc - start.utc).total_seconds())
        _add_call(c, spec.app, loc, frm, to, direction, start, length, None)


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
    # Columns the mapper reads for time, direction, parties or text. A table without one of them
    # is not read: an empty column would read as no sender, no text or no direction on every row.
    required: tuple[str, ...] = ()


# (tool, LEAPP's function name for the artifact) -> how Mabillon reads it
SPECS: dict[tuple[str, str], Spec] = {
    ("iLEAPP", "sms"): Spec(
        RecordKind.CHATS,
        _ios_sms,
        (
            "Message Row ID",
            "Message Timestamp",
            "From Me",
            "Sender",
            "Message",
            "Chat ID",
            "Chat Participants",
            "Destination Caller ID",
            "Account",
            "Attachment Name",
        ),
    ),
    ("iLEAPP", "callHistory"): Spec(
        RecordKind.CALLS,
        _ios_calls,
        (
            "Starting Timestamp",
            "Call Direction",
            "Answered",
            "Phone Number",
            "Service Provider",
            "Call Duration",
        ),
    ),
    ("iLEAPP", "addressBook"): Spec(RecordKind.CONTACTS, _ios_contacts),
    ("ALEAPP", "get_sms_mms"): Spec(
        RecordKind.SMS, _android_sms, ("Date", "Type", "Address", "Body", "MSG ID", "Thread ID")
    ),
    ("ALEAPP", "get_sms_mms_mms"): Spec(
        RecordKind.SMS,
        _android_mms,
        (
            "Date",
            "Direction",
            "From Address",
            "To Address",
            "Cc",
            "Bcc",
            "Body",
            "Media",
            "MSG ID",
            "Thread ID",
        ),
    ),
    ("ALEAPP", "get_googleMessages"): Spec(
        RecordKind.SMS,
        _android_google_messages,
        (
            "Message Timestamp",
            "Direction",
            "Message Sender",
            "Message",
            "Conversation ID",
            "Other Participant/Conversation Name",
            "Attachment Location",
            "Message Type",
        ),
    ),
    ("ALEAPP", "get_calllog"): Spec(
        RecordKind.CALLS,
        _android_calls,
        (
            "Call Date",
            "Raw Call Type (as stored)",
            "Partner",
            "Phone Account Address",
            "Phone Account Package",
            "Duration in Secs",
        ),
    ),
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
    """A zone name the standard library knows ("America/New_York", "UTC"), else None."""
    if not name or not name.strip() or name != name.strip():
        return None
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    return name


def device_facts(lava: Lava) -> dict[str, Any]:
    """The phone's time zone and OS as LEAPP's device tables state them. The zone is set only
    when every zone the phone recorded is the same one; a phone that recorded two or more gets
    none, since no one zone places all its records, and the expert enters it. So does a phone
    that recorded a zone value this reader cannot read beside the one it can (Greptile on
    #264): that value may be another zone."""
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
        "timezone": found[0] if len(found) == 1 and not invalid else None,
        "zones_seen": [zones[n] for n in found],
        "zones_not_read": dict(invalid),
        "os_version": os_version,
        "os_version_table": os_from,
    }


# ---------------------------------------------------------------- importer


def _may_hold_records(lava: Lava, art: Artifact) -> bool:
    """False only when the artifact is known to be empty: the manifest states 0 records, or it
    states no count and its table is in the database with no rows (CodeRabbit on #264)."""
    if art.record_count is not None:
        return art.record_count > 0
    if not lava.has_table(art):
        return True
    quoted = art.table.replace(chr(34), chr(34) * 2)
    return lava.db.execute(f'SELECT 1 FROM "{quoted}" LIMIT 1').fetchone() is not None  # noqa: S608  (a table the manifest names, quoted)


def _not_read(art: Artifact, why: str) -> dict[str, Any]:
    return {"name": art.name, "category": art.category, "table": art.table,
            "records": art.record_count, "reason": why, "read_failed": True}  # fmt: skip


_NATIVE_MESSAGE_KEYS = {"sms", "get_sms_mms", "get_sms_mms_mms", "get_googleMessages"}
_NATIVE_CALL_KEYS = {"callHistory", "get_calllog"}


def apps_read_in_full(lava: Lava, read: list[tuple[Spec, Artifact]]) -> list[str]:
    """The apps whose records this import holds in full, from the artifacts read through: the
    phone's own messages, and its calls, when every such table that holds records was read (and,
    for calls, every call's direction could be read), and
    a chat app when no artifact LEAPP wrote for it (by its category's first word) holds records
    Mabillon did not read. Every other app, and a search on every channel, is not covered by
    this source (the absence and count checks read this list)."""
    # By manifest entry, not by key: two entries can share a key, and one read through must not
    # hide another that was not (CodeRabbit on #264).
    done = {id(a) for _, a in read}
    keys = {a.key for _, a in read}
    unread = [a for a in lava.artifacts if id(a) not in done and _may_hold_records(lava, a)]
    unread_keys = {a.key for a in unread}
    apps: set[str] = set()
    if keys & _NATIVE_MESSAGE_KEYS and not unread_keys & _NATIVE_MESSAGE_KEYS:
        apps.add(NATIVE_MESSAGES_APP)
    # A call whose type names no direction is stored with neither side, so no check can find
    # it: the call log is then not held in full (Claude review on #264).
    if (
        keys & _NATIVE_CALL_KEYS
        and not unread_keys & _NATIVE_CALL_KEYS
        and not lava.native_calls_not_held
    ):
        apps.add("unknown")  # the phone's own call log (assumption_filler NATIVE_CALL_APP)
    if lava.leapp_name == "iLEAPP":
        # On the public iOS 15 phone the UFDR holds WhatsApp, Viber and other app calls from the
        # phone's own call records (CallKit) that iLEAPP lists under no app, so no table read
        # here holds every call of a chat app: none counts as read in full.
        return sorted(apps)
    if lava.calls_from_other_packages or "get_calllog" not in keys or "get_calllog" in unread_keys:
        # A VoIP app can write its calls to Android's call log too, where they are stored under
        # the call log, not the app (Claude review on #268): when the call log holds a row from
        # another package, or was not read (absent included), or one of its entries holds
        # records that were not read (CodeRabbit on #268), no chat app counts as read in full.
        return sorted(apps)
    # A chat app is read in full only when one of its chat tables was read and every call
    # table listed for it on this platform was read too: a call table alone holds none of its
    # messages, and a chat table alone none of its calls (Claude review on #268). An app
    # whose listed call table cannot hold every party of a call is never read in full,
    # whether or not that table was in this extraction.
    name = lava.leapp_name
    read_keys = {(name, a.key) for _, a in read}
    unread_words = {a.category.split()[0].lower() for a in unread if a.category.split()}
    chat_read = {v.app for k, v in CHAT_SPECS.items() if k[0] == name and k in read_keys}
    calls_unread = {v.app for k, v in CALL_SPECS.items() if k[0] == name and k not in read_keys}
    partial = {v.app for k, v in CALL_SPECS.items() if k[0] == name and not v.all_parties}
    for app in chat_read - calls_unread - partial:
        if app.split()[0].lower() not in unread_words and not lava.calls_without_sides.get(app):
            apps.add(app)
    return sorted(apps)


def _fidelity(m: dict[str, Any]) -> tuple[Fidelity, ExtractionType, str]:
    kind = str(m.get("param_type") or "").strip().lower()
    if m.get("processing_status") != RUN_COMPLETE:
        # LEAPP writes "In Progress" when a run starts and "Complete" when it ends, so any other
        # value is a run that stopped part way, whose tables may be cut short (CodeRabbit on #264).
        ext = ExtractionType.FILE_SYSTEM if kind in FILE_SYSTEM_INPUTS else ExtractionType.UNKNOWN
        return Fidelity.UNKNOWN, ext, FIDELITY_REASON_INCOMPLETE
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
            if spec is None and (lava.leapp_name, art.key) in CHAT_SPECS:
                spec = Spec(RecordKind.CHATS, _chat_messages)
            if spec is None and (lava.leapp_name, art.key) in CALL_SPECS:
                spec = Spec(RecordKind.CALLS, _app_calls)
            if spec is None:
                why = SAME_RECORDS.get((lava.leapp_name, art.key), "Mabillon does not read it")
                cov.not_imported.append(
                    {"name": art.name, "category": art.category, "table": art.table,
                     "records": art.record_count, "reason": why,
                     "may_hold_records": _may_hold_records(lava, art)}
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
            # Only a table read through counts as read (CodeRabbit on #264): a missing table, or
            # a chat view that names no text, direction or time, is listed as not read and its
            # app is not read in full.
            done: list[tuple[Spec, Artifact]] = []
            for kind in ORDER:
                for spec, art in read:
                    if spec.kind is not kind:
                        continue
                    if not lava.has_table(art):
                        cov.not_imported.append(_not_read(art, "its table is not in the database"))
                        continue
                    tc = TableCoverage(name=art.name, kind=kind.value)
                    tc.header_locator = art.table
                    cov.tables.append(tc)
                    ctx = _Ctx(w, tc, art, lava)
                    if _has_columns(ctx, list(spec.required)):
                        spec.read(ctx)
                    if ctx.failed:
                        # listed only as not read, never as a table read with 0 rows
                        cov.tables.pop()
                        lava.refused.add(id(art))
                        cov.not_imported.append(_not_read(art, ctx.failed))
                        continue
                    done.append((spec, art))
                    if art.record_count is not None and art.record_count != tc.rows_read:
                        tc.header_notes.append(
                            f"The manifest states {art.record_count} records; the table holds "
                            f"{tc.rows_read} rows."
                        )
            w.flush()
            payload = coverage_payload(
                source,
                IMPORTER_NAME,
                None,
                None,
                cov,
                sorted({s.kind for s, _ in done} | lava.extra_kinds),
            )
            payload.update(
                importer_version=IMPORTER_VERSION,
                fidelity_reason=reason,
                format_support=FORMAT_SUPPORT,
                **{APPS_READ_KEY: apps_read_in_full(lava, done)},
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
                        for _, a in done
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
