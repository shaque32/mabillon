"""The LEAPP side of score_hickman (validation v5): keys by LAVA row, and bar 8 table by table.

A v5 run reads its phones from LEAPP output (iLEAPP, ALEAPP) through core/ingest/leapp.py, one
or two phones in one case. This module reads each phone's LAVA output itself (sqlite3 and the
manifest, through eval/validation/dump_lava.py, never through the importer) and gives the
scorer two things the UFDR path gets from dump_ufdr.py:

1. Key mapping. A key record is `lava:<phone>:<table>:<rowid>`: a phone's source id as the run
   names it, a LAVA table, and that table's SQLite rowid, all of which the key writer reads from
   the LAVA output with no Mabillon code. The importer writes each record's locator as
   `<table>/<column>=<value>` from the rows it came from (core/ingest/leapp.py, its module
   docstring). So the key row, and for a table whose kinds entry names dedupe columns every row
   sharing those values (one message written as several rows), gives every locator it could
   stand behind, and the key maps to the one record of that phone whose locator is one of them.
   A key with no single match (none, or several records) is listed, never matched to a near
   miss. A Google Messages row the importer skipped as a copy of an SMS or MMS maps to that
   SMS or MMS only when this module confirms the pair from the LAVA rows (below).
2. Bar 8's import counts. For each table the kinds file reads, the reader's count (dump_lava)
   against Mabillon's records from that table: its distinct locators in messages, calls and
   contacts (one contact row per identifier counts once; a call notice read from a chat table
   as a call counts for that table). The importer's skipped Google Messages rows are added
   to Mabillon's side only where this module confirms each one's pair: the same direction, the
   same text with runs of white space read as one space (an ALEAPP MMS body that is a part's
   path is an attachment, not text), as many attachments on each side, the same other party,
   at most SAME_MESSAGE_SECONDS apart, one text at most on the Google Messages side, and no SMS
   or MMS standing for two skipped rows. The rule is restated here from the importer's stated
   behaviour, not imported, so a change to the importer cannot also change this check.
   A row whose dedupe value is empty is a record of its own in the importer (a Google Messages
   message groups its parts with the empty value as one value), and the reader leaves such rows
   out of its count, so this module adds them to the reader's side by that rule.
   Bar 8 passes when every table's counts agree, every skipped row's pair is confirmed, and
   no record comes from a table the kinds file does not read.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import zipfile
from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from core.contracts import GoldClaim
from eval.validation import dump_lava
from eval.validation.dump_lava import DATABASE, MANIFEST, fold, quote

KINDS_FILE = Path(__file__).with_name("lava_kinds.json")
KEY_RE = re.compile(r"lava:(?P<phone>[^:\s]+):(?P<table>[^:\s]+):(?P<rowid>[1-9]\d*)")
RECORD_TABLES = ("messages", "calls", "contacts")
GOOGLE_MESSAGES = "get_googlemessages"
# The importer skips a Google Messages message as a copy of an SMS or MMS at most this many
# seconds apart (core/ingest/leapp.py states two seconds).
SAME_MESSAGE_SECONDS = 2
# ALEAPP writes an MMS part whose file it did not find as the part's path in the body.
_PART_PATH_RE = re.compile(r"^/\S*/(?:app_parts|parts)/\S+$")
# A handle as both stores write it: a number (digits, spaces, + ( ) . -) or an email.
_HANDLE_RE = re.compile(r"^(?:\+?[\d\s().-]{5,}|[^@\s]+@[^@\s]+)$")
# LAVA names its manifest either way; the manifest names its database (lava_db_name).
MANIFEST_NAMES = (MANIFEST, "_lava_data.json")
MAX_MANIFEST_BYTES = 256 * 1024 * 1024
MAX_DB_BYTES = 8 * 1024 * 1024 * 1024
# The names SQLite reads as a row's id; a real column so named is never a locator's row id.
_ROWID_NAMES = ("_rowid_", "rowid", "oid")
_DIRECTION = {"incoming": "received", "outgoing": "sent"}
# The name each row read here carries its SQLite row id under (no LEAPP table has the column).
ROWID = "mabillon_score_rowid"


@dataclass
class LavaPhone:
    """One phone's LEAPP output as this module reads it."""

    source_id: str
    folder: Path  # holds MANIFEST and DATABASE, extracted from the phone's zip
    sha256: str
    reader: dict[str, Any]  # dump_lava.read on the folder
    kinds: dict[str, dict]  # the kinds file, by folded table name

    def connect(self) -> sqlite3.Connection:
        uri = f"{(self.folder / DATABASE).resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        # a value as the importer compares it: text, stripped, None as empty
        conn.create_function(NORM, 1, lambda v: _value(v) or "", deterministic=True)
        return conn


# The SQL function a LavaPhone connection reads a value through, as the importer does.
NORM = "mabillon_score_norm"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_kinds(path: Path) -> tuple[dict[str, dict], str]:
    kinds = json.loads(path.read_text("utf-8"), object_pairs_hook=dump_lava.no_duplicate_keys)
    folded = {fold(t): spec for t, spec in kinds.items()}
    if len(folded) != len(kinds):
        raise SystemExit(f"score: {path} names one table twice")
    return kinds, _sha256(path)


def is_leapp_run(record: dict[str, Any]) -> bool:
    """True for a run whose phones were all read from LEAPP output; a run that mixes LEAPP and
    UFDR phones is refused, since neither path can score the other's keys."""
    importers = {p.get("importer") for p in record.get("phones") or []}
    if "leapp" in importers and importers != {"leapp"}:
        raise SystemExit("score: the run mixes LEAPP and UFDR phones; neither path scores both")
    return importers == {"leapp"}


def _member_size(z: zipfile.ZipFile, member: str, limit: int, zip_path: Path) -> None:
    size = z.getinfo(member).file_size
    if size > limit:
        raise SystemExit(f"score: {member} in {zip_path} unpacks to {size:,} bytes, over {limit:,}")


def _extract(zip_path: Path, folder: Path) -> None:
    """The phone zip's one manifest and the database it names beside it, copied into folder as
    MANIFEST and DATABASE: the files a LAVA reader takes, found as LAVA names them (either
    manifest name, the manifest's lava_db_name in the manifest's own folder)."""
    try:
        z = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as err:
        raise SystemExit(f"score: {zip_path} is not a zip file") from err
    with z:
        names = z.namelist()
        found = [
            n
            for n in names
            if PurePosixPath(n).name in MANIFEST_NAMES and not n.startswith("__MACOSX/")
        ]
        if len(found) != 1:
            raise SystemExit(f"score: {zip_path} holds {len(found)} LEAPP manifests, not one")
        man = found[0]
        _member_size(z, man, MAX_MANIFEST_BYTES, zip_path)
        raw = z.read(man)
        try:
            manifest = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            raise SystemExit(f"score: {man} in {zip_path} is not a LEAPP manifest") from err
        if not isinstance(manifest, dict):
            raise SystemExit(f"score: {man} in {zip_path} is not a LEAPP manifest")
        db_name = str(manifest.get("lava_db_name") or DATABASE)
        parent = str(PurePosixPath(man).parent)
        db_member = db_name if parent == "." else f"{parent}/{db_name}"
        if db_member not in names:
            raise SystemExit(f"score: {zip_path} holds {man} but not {db_name} beside it")
        _member_size(z, db_member, MAX_DB_BYTES, zip_path)
        (folder / MANIFEST).write_bytes(raw)
        with z.open(db_member) as src, (folder / DATABASE).open("wb") as dst:
            shutil.copyfileobj(src, dst, 1 << 20)


def open_phones(
    record: dict[str, Any], given: dict[str, Path], kinds_path: Path, work: Path
) -> dict[str, LavaPhone]:
    """Each phone the run read, from the zip it was given, checked against the run's hash."""
    in_run = {p["source_id"]: p for p in record.get("phones") or []}
    if set(given) != set(in_run):
        raise SystemExit(
            f"score: give --phone for exactly the run's phones {sorted(in_run)}, not"
            f" {sorted(given)}"
        )
    kinds, _ = load_kinds(kinds_path)
    out: dict[str, LavaPhone] = {}
    for sid, path in sorted(given.items()):
        if not path.is_file():
            raise SystemExit(f"score: --phone {sid}: {path} is not a file")
        folder = work / f"lava-{len(out)}"
        folder.mkdir(parents=True)
        # one copy is hashed and read, so the bytes read are the bytes the hash checked
        snap = folder / "phone.zip"
        shutil.copyfile(path, snap)
        digest = _sha256(snap)
        if digest != in_run[sid].get("sha256"):
            raise SystemExit(
                f"score: {path} is not the {sid} file the run read (SHA-256 {digest}, the run"
                f" read {in_run[sid].get('sha256')})"
            )
        _extract(snap, folder)
        snap.unlink()
        reader = dump_lava.read(folder, kinds)
        out[sid] = LavaPhone(sid, folder, digest, reader, {fold(t): s for t, s in kinds.items()})
    return out


def _tables(conn: sqlite3.Connection) -> dict[str, str]:
    """Each table the LAVA database holds, by folded name, as the database spells it."""
    return {
        fold(r[0]): r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        if not fold(r[0]).startswith("sqlite_")
    }


def _rowid_alias(conn: sqlite3.Connection, table: str) -> str:
    """A name for the row id that no real column takes (a LEAPP table may have a column called
    rowid)."""
    real = {fold(r[1]) for r in conn.execute(f"PRAGMA table_info({quote(table)})")}
    alias = next((a for a in _ROWID_NAMES if a not in real), None)
    if alias is None or ROWID in real:
        raise SystemExit(f"score: table {table!r} has no free name for its row id")
    return alias


def _rows(
    conn: sqlite3.Connection, table: str, rowid: int, dedupe: str | list[str] | None
) -> list[dict[str, Any]]:
    """The key row and, when the kinds file groups the table by dedupe columns, every row that
    shares their values, each read as the importer reads it (text, stripped). A row whose one
    dedupe column is empty is a record of its own; a table grouped by several columns (Google
    Messages) groups an empty value as one value. Each row carries its row id under ROWID."""
    alias = _rowid_alias(conn, table)
    # Names are quoted, and each is one the database itself lists (sqlite_master, table_info).
    sql = f"SELECT {alias} AS {ROWID}, * FROM {quote(table)}"  # noqa: S608
    row = conn.execute(f"{sql} WHERE {alias} = ?", (rowid,)).fetchone()
    if row is None:
        return []
    first = dict(row)
    cols = [dedupe] if isinstance(dedupe, str) else list(dedupe or [])
    by_fold = {fold(c): c for c in first if c != ROWID}
    keys = [by_fold[fold(c)] for c in cols if fold(c) in by_fold]
    if not cols or len(keys) != len(cols) or (len(keys) == 1 and _value(first[keys[0]]) is None):
        return [first]
    where = " AND ".join(f"{NORM}({quote(k)}) = ?" for k in keys)
    params = [_value(first[k]) or "" for k in keys]
    return [dict(r) for r in conn.execute(f"{sql} WHERE {where}", params)]


def _value(v: object) -> str | None:
    s = str(v).strip() if v is not None else ""
    return s or None


def _candidates(table: str, rows: list[dict[str, Any]]) -> set[str]:
    """Every locator a record made from these rows could have: `<table>/rowid=<n>` for each
    row, and `<table>/<column>=<value>` for each column with a value. A real column named as
    SQLite names the row id is left out: its value is not the row's id."""
    out: set[str] = set()
    for r in rows:
        out.add(f"{table}/rowid={r[ROWID]}")
        for col, v in r.items():
            if col == ROWID or fold(col) in _ROWID_NAMES:
                continue
            if (s := _value(v)) is not None:
                out.add(f"{table}/{col}={s}")
    return out


def _records(case: sqlite3.Connection, sid: str, locators: set[str]) -> dict[str, list[str]]:
    """Mabillon's record ids by locator, for this phone's records with one of the locators."""
    found: dict[str, list[str]] = {}
    want = sorted(locators)
    for t in RECORD_TABLES:
        for i in range(0, len(want), 500):
            part = want[i : i + 500]
            marks = ", ".join("?" * len(part))
            for rid, loc in case.execute(
                f"SELECT id, locator FROM {t} WHERE source_id = ? AND locator IN ({marks})",  # noqa: S608
                (sid, *part),
            ):
                found.setdefault(loc, []).append(rid)
    return found


def skipped_rows(case: sqlite3.Connection, sid: str) -> list[dict[str, Any]]:
    """The Google Messages rows the importer skipped as copies, as its coverage lists them."""
    row = case.execute(
        "SELECT payload_json FROM source_coverage WHERE source_id = ?", (sid,)
    ).fetchone()
    if row is None:
        raise SystemExit(f"score: the case holds no coverage record for phone {sid}")
    payload = json.loads(row[0])
    leapp = payload.get("leapp")
    if not isinstance(leapp, dict):
        raise SystemExit(f"score: phone {sid}'s coverage is not a LEAPP import's")
    return list(leapp.get("google_messages_skipped") or [])


def _same_as_rows(
    conn: sqlite3.Connection, tables: dict[str, str], same_as: str
) -> tuple[str, list[dict[str, Any]]] | None:
    """(table, rows) of the SMS or MMS a skipped row names (`get_sms_mms/msg_id=5`): an SMS's
    one row, or every part row of an MMS (ALEAPP writes one row per part)."""
    m = re.fullmatch(r"(get_sms_mms|get_sms_mms_mms)/(msg_id|rowid)=(\S+)", same_as or "")
    if not m or fold(m.group(1)) not in tables:
        return None
    table = tables[fold(m.group(1))]
    alias = _rowid_alias(conn, table)
    where = f"{alias} = ?" if m.group(2) == "rowid" else f"{NORM}({quote('msg_id')}) = ?"
    sql = f"SELECT {alias} AS {ROWID}, * FROM {quote(table)} WHERE {where} ORDER BY {alias}"  # noqa: S608
    rows = [dict(r) for r in conn.execute(sql, (m.group(3),))]
    return fold(table), rows


def _epoch(v: object) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int | float):
        return float(v)
    s = _value(v)
    try:
        return float(s) if s is not None else None
    except ValueError:
        return None


def _flat(text: str) -> str:
    """Text with every run of white space read as one space, as the importer compares it."""
    return " ".join(text.split())


def _handle(v: object) -> str | None:
    """A number as its digits, an email casefolded; None for a display name or nothing."""
    s = _value(v)
    if s is None:
        return None
    s = re.sub(r"^(?:[A-Za-z]:|tel:|mailto:)", "", s).strip()
    if not _HANDLE_RE.match(s):
        return None
    if "@" in s:
        return s.casefold()
    return re.sub(r"\D", "", s) or None


def _same_handle(a: str, b: str) -> bool:
    """Equal, or one number is the other after a country code of up to three digits, the
    shorter one at least ten digits ("+19195550111" and "(919) 555-0111")."""
    if a == b:
        return True
    if "@" in a or "@" in b:
        return False
    short, long = sorted((a, b), key=len)
    return len(short) >= 10 and long.endswith(short) and len(long) - len(short) <= 3


def _one_handle(values: list[object]) -> str | None:
    """The one handle these values name, or None when they name none or several."""
    got: list[str] = []
    for v in values:
        for part in re.split(r"[,\r\n]+", _value(v) or ""):
            if (h := _handle(part)) is not None and not any(_same_handle(h, x) for x in got):
                got.append(h)
            elif h is None and _value(part):
                return None  # a party that is not a handle: it cannot be compared
    return got[0] if len(got) == 1 else None


def contact_handles(conn: sqlite3.Connection, tables: dict[str, str]) -> dict[str, list[str]]:
    """ALEAPP contacts: display name -> the handles of its phone numbers."""
    out: dict[str, list[str]] = {}
    table = tables.get("contacts")
    if table is None:
        return out
    cols = {fold(r[1]) for r in conn.execute(f"PRAGMA table_info({quote(table)})")}
    if not {"display_name", "phone_number"} <= cols:
        return out
    sql = f"SELECT display_name, phone_number FROM {quote(table)}"  # noqa: S608
    for name, number in conn.execute(sql):
        if (n := _value(name)) and (h := _handle(number)):
            out.setdefault(n, []).append(h)
    return out


def _gm_party(parts: list[dict[str, Any]], contacts: dict[str, list[str]]) -> str | None:
    """A Google Messages message's other party: the sender of a received one; for a sent one,
    the conversation's name when it is a handle, else the one number the phone's contacts give
    that name. None when it cannot be told."""
    first = parts[0]
    if fold(_value(first.get("direction")) or "") == "incoming":
        return _handle(first.get("message_sender"))
    label = first.get("other_participantconversation_name")
    if (h := _handle(label)) is not None:
        return h
    nums = contacts.get(_value(label) or "", [])
    if nums and all(_same_handle(nums[0], n) for n in nums[1:]):
        return nums[0]
    return None


def _native_party(table: str, rows: list[dict[str, Any]], direction: str) -> str | None:
    first = rows[0]
    if table == "get_sms_mms":
        return _one_handle([first.get("address")])
    if direction == "received":
        frm = _value(first.get("from_address"))
        return None if frm is None or fold(frm) == "insert-address-token" else _handle(frm)
    return _one_handle([first.get(k) for k in ("to_address", "cc", "bcc")])


def _pair_problem(
    parts: list[dict[str, Any]],
    native: tuple[str, list[dict[str, Any]]] | None,
    contacts: dict[str, list[str]] | None = None,
) -> str | None:
    """Why a skipped Google Messages message is not shown to be its SMS or MMS, or None."""
    if not parts:
        return "its rows are not in the table"
    if native is None or not native[1] or (native[0] == "get_sms_mms" and len(native[1]) != 1):
        return "the SMS or MMS it names is not in the LAVA tables"
    table, rows = native
    g_dir = {fold(_value(p.get("direction")) or "") for p in parts}
    col = "type" if table == "get_sms_mms" else "direction"  # as the importer reads each
    n_dir = {fold(_value(r.get(col)) or "") for r in rows}
    if len(g_dir) != 1 or len(n_dir) != 1 or _DIRECTION.get(next(iter(g_dir))) != next(iter(n_dir)):
        return "its direction is not the SMS or MMS's"
    texts = [s for p in parts if (s := _value(p.get("message")))]
    if len(texts) > 1:
        return "it joins several texts, which may be several messages"
    g_text = _flat(texts[0] if texts else "")
    g_media = sum(
        1
        for p in parts
        if _value(p.get("attachment_location"))
        or not (_value(p.get("message_type")) or "text/plain").startswith("text/")
    )
    n_texts: list[str] = []
    n_media = 0
    for r in rows:
        body = _value(r.get("body"))
        if table == "get_sms_mms_mms":
            n_media += 1 if _value(r.get("media")) else 0
            if body and _PART_PATH_RE.match(body):
                n_media += 1
                continue
        if body:
            n_texts.append(body)
    if g_text != _flat("\n".join(n_texts)):
        return "its text is not the SMS or MMS's"
    if g_media != n_media:
        return f"it has {g_media} attachment(s), the SMS or MMS {n_media}"
    g_party = _gm_party(parts, contacts or {})
    n_party = _native_party(table, rows, next(iter(n_dir)))
    if g_party is None or n_party is None:
        return "its other party cannot be compared with the SMS or MMS's"
    if not _same_handle(g_party, n_party):
        return "its other party is not the SMS or MMS's"
    # whole seconds, as the importer compares them; every part of an MMS within the limit
    g_t = {_epoch(p.get("message_timestamp")) for p in parts}
    n_t = [_epoch(r.get("date")) for r in rows]
    if None in g_t or None in n_t or len(g_t) != 1:
        return "a time is missing or the rows disagree on it"
    g = int(next(iter(g_t)))  # type: ignore[arg-type]
    if any(abs(g - int(n)) > SAME_MESSAGE_SECONDS for n in n_t):  # type: ignore[arg-type]
        return f"it is more than {SAME_MESSAGE_SECONDS} seconds from the SMS or MMS"
    return None


def confirm_skipped(case: sqlite3.Connection, phone: LavaPhone) -> dict[str, Any]:
    """Each skipped Google Messages row's pair, checked from the LAVA rows: the confirmed ones
    (row id -> the SMS or MMS locator it stands for) and every one not confirmed, with why."""
    skipped = skipped_rows(case, phone.source_id)
    confirmed: dict[int, str] = {}
    problems: list[dict[str, Any]] = []
    with closing(phone.connect()) as conn:
        tables = _tables(conn)
        gm = tables.get(GOOGLE_MESSAGES)
        contacts = contact_handles(conn, tables)
        claimed = Counter(s.get("same_as") for s in skipped)
        for s in skipped:
            listed = s.get("rows")
            ids_ok = isinstance(listed, list) and all(type(r) is int for r in listed)
            rows: list[int] = list(listed) if ids_ok else []  # type: ignore[arg-type]
            parts: list[dict[str, Any]] = []
            if gm is not None:
                alias = _rowid_alias(conn, gm)
                sql = f"SELECT {alias} AS {ROWID}, * FROM {quote(gm)} WHERE {alias} = ?"  # noqa: S608
                parts = [dict(r) for i in rows for r in conn.execute(sql, (i,))]
            if not ids_ok:
                why: str | None = "its rows are not all row ids"
            elif len(parts) != len(rows) or not rows:
                why = "its rows are not in the table"
            elif claimed[s.get("same_as")] > 1:
                why = "the SMS or MMS it names stands for another skipped row too"
            else:
                why = _pair_problem(parts, _same_as_rows(conn, tables, s.get("same_as")), contacts)
            if why is None:
                for i in rows:
                    confirmed[i] = s["same_as"]
            else:
                problems.append({"locator": s.get("locator"), "same_as": s.get("same_as"),
                                 "why": why})  # fmt: skip
    return {"skipped": len(skipped), "confirmed": confirmed, "not_confirmed": problems}


def map_lava_keys(
    case: sqlite3.Connection,
    gold: list[GoldClaim],
    phones: dict[str, LavaPhone],
    skipped: dict[str, dict[str, Any]],
) -> tuple[list[GoldClaim], dict[str, Any]]:
    """Like score_hickman.map_keys, for `lava:` keys: the keys as Mabillon record ids, each key
    left unmapped with why, and each mapped key record's ids per claim."""
    mapped: list[GoldClaim] = []
    unmapped: list[dict[str, str]] = []
    groups: dict[str, dict[str, list[str]]] = {}
    n_keys = 0
    conns = {sid: p.connect() for sid, p in phones.items()}
    try:
        tables = {sid: _tables(c) for sid, c in conns.items()}
        for g in gold:
            ids: list[str] = []
            groups[g.claim_id] = {}
            for key in g.key_evidence:
                n_keys += 1
                got, why = _map_one(case, key, phones, conns, tables, skipped)
                if got:
                    ids.extend(i for i in got if i not in ids)
                    groups[g.claim_id][key] = got
                else:
                    unmapped.append({"claim_id": g.claim_id, "key": key, "why": why})
            mapped.append(g.model_copy(update={"key_evidence": tuple(ids)}))
    finally:
        for c in conns.values():
            c.close()
    return mapped, {"keys": n_keys, "unmapped": unmapped, "groups": groups}


def _map_one(
    case: sqlite3.Connection,
    key: str,
    phones: dict[str, LavaPhone],
    conns: dict[str, sqlite3.Connection],
    tables: dict[str, dict[str, str]],
    skipped: dict[str, dict[str, Any]],
) -> tuple[list[str], str]:
    m = KEY_RE.fullmatch(key)
    if not m:
        return [], "not a LAVA key (lava:<phone>:<table>:<rowid>)"
    sid, rowid = m.group("phone"), int(m.group("rowid"))
    if sid not in phones:
        return [], f"phone {sid!r} is not one the run read"
    table = tables[sid].get(fold(m.group("table")))
    if table is None:
        return [], f"phone {sid} has no table {m.group('table')!r}"
    spec = phones[sid].kinds.get(fold(table))
    if spec is None or spec.get("kind") == dump_lava.SKIP:
        return [], (
            f"{table} is a table the importer does not read; cite the row in a table it reads"
            " (get_sms_mms_combined repeats get_sms_mms and get_sms_mms_mms)"
        )
    rows = _rows(conns[sid], table, rowid, spec.get("dedupe"))
    if not rows:
        return [], f"{table} has no row {rowid}"
    found = _records(case, sid, _candidates(table, rows))
    if not found and fold(table) == GOOGLE_MESSAGES:
        confirmed = skipped[sid]["confirmed"]
        pairs = {confirmed[r[ROWID]] for r in rows if r[ROWID] in confirmed}
        if not pairs:
            listed = {
                loc for p in skipped[sid]["not_confirmed"] if (loc := p.get("locator"))
            } & _candidates(table, rows)
            if listed:
                return [], "skipped by the importer as a copy whose pair was not confirmed"
        found = _records(case, sid, pairs)
    if len(found) == 1:
        return sorted(next(iter(found.values()))), ""
    return [], "no record matches" if not found else f"{len(found)} records match"


def _locator_table(locator: str) -> str:
    return fold(locator.split("/", 1)[0])


def empty_key_adjustment(
    conn: sqlite3.Connection, table: str, dedupe: str | list[str] | None
) -> int:
    """What to add to the reader's count so it counts rows with an empty dedupe value (NULL,
    empty or white space) as the importer makes records of them. The reader leaves NULL rows
    out and counts each distinct raw value, so "" and " " are one or two values to it. The
    importer makes one record per such row for a table grouped by one column (it names it by
    its row id), and for a table grouped by several (Google Messages) one per distinct group,
    each value read stripped and NULL as empty. Only rows with an empty value are counted
    again here; every other row is left as the reader counted it."""
    cols = [dedupe] if isinstance(dedupe, str) else list(dedupe or [])
    if not cols:
        return 0
    real = {fold(r[1]): r[1] for r in conn.execute(f"PRAGMA table_info({quote(table)})")}
    keys = [real[fold(c)] for c in cols if fold(c) in real]
    if len(keys) != len(cols):
        return 0  # the reader refuses a table without its dedupe columns
    names = ", ".join(quote(k) for k in keys)
    sql = f"SELECT {names} FROM {quote(table)}"  # noqa: S608
    importer_rows = 0
    importer_groups: set[tuple[str, ...]] = set()
    reader_groups: set[tuple[object, ...]] = set()
    for row in conn.execute(sql):
        norm = tuple(_value(v) or "" for v in row)
        if "" not in norm:
            continue  # no empty value: the reader and the importer group it alike
        importer_rows += 1
        importer_groups.add(norm)
        if all(v is not None for v in row):
            reader_groups.add(tuple(row))  # the reader counted it as one distinct value
    importer = importer_rows if len(keys) == 1 else len(importer_groups)
    return importer - len(reader_groups)


def import_counts(
    case: sqlite3.Connection, phones: dict[str, LavaPhone], skipped: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Bar 8 on LEAPP: each phone's records per table against the reader's count."""
    out: dict[str, Any] = {"phones": {}}
    every = True
    for sid, phone in sorted(phones.items()):
        ours: Counter[str] = Counter()
        for t in RECORD_TABLES:
            for (loc,) in case.execute(
                f"SELECT DISTINCT locator FROM {t} WHERE source_id = ?",  # noqa: S608
                (sid,),
            ):
                ours[_locator_table(loc)] += 1
        conf = skipped[sid]
        n_conf = len(conf["confirmed"])
        rows: dict[str, dict[str, Any]] = {}
        with closing(phone.connect()) as lava:
            in_db = _tables(lava)
            for table, t in sorted(phone.reader["tables"].items()):
                if t["kind"] == dump_lava.SKIP:
                    continue
                mine = ours.pop(fold(table), 0)
                # the reader counts a Google Messages message by its distinct dedupe values, the
                # importer lists each skipped message's rows: a skipped message counts once
                added = _confirmed_messages(conf) if fold(table) == GOOGLE_MESSAGES else 0
                nulls = 0
                if fold(table) in in_db:
                    spec = phone.kinds.get(fold(table), {})
                    nulls = empty_key_adjustment(lava, in_db[fold(table)], spec.get("dedupe"))
                rows[table] = {
                    "kind": t["kind"],
                    "mabillon": mine,
                    "skipped_confirmed": added,
                    "reader": t["count"],
                    "null_dedupe_rows": t.get("null_dedupe_rows", 0),
                    "empty_key_adjustment": nulls,
                    "pass": mine + added == t["count"] + nulls,
                }
        extra = dict(sorted(ours.items()))  # records from a table the reader does not count
        ok = all(r["pass"] for r in rows.values()) and not extra and not conf["not_confirmed"]
        every = every and ok
        out["phones"][sid] = {
            "tables": rows,
            "records_from_tables_not_counted": extra,
            "skipped": conf["skipped"],
            "skipped_rows_confirmed": n_conf,
            "skipped_not_confirmed": conf["not_confirmed"],
            "reader_tables_not_counted": phone.reader["tables_not_counted"],
            "reader": {
                k: phone.reader[k]
                for k in (
                    "dump_lava_version",
                    "manifest_sha256",
                    "database_sha256",
                    "leapp_name",
                    "leapp_version",
                    "counts",
                )
            },  # fmt: skip
            "pass": ok,
        }
    out["pass"] = every
    return out


def _confirmed_messages(conf: dict[str, Any]) -> int:
    """Skipped messages confirmed, counted once each (a message may be several rows)."""
    return len(set(conf["confirmed"].values()))
