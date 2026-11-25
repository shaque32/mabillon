"""A record in reading words, for the review screen only: who, when, what and where it sits in
the file, short enough to read as one row.

The report prints each record with its exported values (core/report/html.py record_line: the
UTC time and the time as the source printed it). The screen says the same record in words and
keeps those values one click away, in a fold beside the row. Nothing here changes what is
stored, what the report prints or what a model is sent: the time is the same phone-local time
the screen already showed (core/enrich/local_time.py format_local), written for reading, with
the full value and its UTC offset in the hover title.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from core.contracts import ProvenanceTier
from core.enrich.local_time import device_zone, format_local, parse_utc
from core.enrich.records import get_record
from core.ingest import forwarded
from core.report.fmt import e, q
from core.report.selection import sender_words
from core.restore.view import Line, message_lines
from core.zones import device_zones

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
# format_local's two timed forms: "2026-02-20 19:02:11 EST (UTC-05:00)" and
# "2026-02-20 19:02:11 UTC (device zone unknown)".
_LOCAL = re.compile(
    r"^(?P<y>\d{4})-(?P<mo>\d\d)-(?P<d>\d\d) (?P<h>\d\d):(?P<mi>\d\d):(?P<s>\d\d) "
    r"(?P<zone>\S+) \((?P<note>[^()]+)\)$"
)
_SHEET_ROW = re.compile(r"^(?P<sheet>.+)!(?P<row>\d+)$")
EXCEL = "cellebrite_excel"
EXCEL_ROW_NOTE = "An Excel row is the spreadsheet's own row number, not the report's # column."
LOCAL_TIME_NOTE = "derived from UTC and the phone's time zone"
# a message with no sender account, as core/restore/view.py and core/audit/context.py name it
UNKNOWN_SENDERS = frozenset({"unknown", "unknown sender"})


@dataclass(frozen=True)
class Reading:
    """A phone-local time in reading words."""

    date: str  # "Mar 10, 2026"
    clock: str  # "11:16:44 AM EDT"
    caveat: str  # "device zone unknown" when the time shown is UTC, else ""


def reading(local: str) -> Reading | None:
    """format_local's string in reading words. None for any other text (a time the source did
    not give), which the caller then prints as it is."""
    m = _LOCAL.match(local or "")
    if m is None or not 1 <= int(m["mo"]) <= 12:
        return None
    hour = int(m["h"])
    clock = f"{hour % 12 or 12}:{m['mi']}:{m['s']} {'AM' if hour < 12 else 'PM'} {m['zone']}"
    caveat = "" if m["note"].startswith("UTC") else m["note"]
    return Reading(f"{MONTHS[int(m['mo']) - 1]} {int(m['d'])}, {m['y']}", clock, caveat)


def when(local: str, date: bool = True) -> str:
    """A time as HTML: "Mar 10, 2026, 11:16:44 AM EDT", the full value with its UTC offset in
    the hover title. date=False leaves the date to the row's date cell."""
    r = reading(local)
    if r is None:
        return e(local)
    words = f"{r.date}, {r.clock}" if date else r.clock
    return f"<span class='lt' title='{e(local)}'>{e(words)}</span>" + (
        f" ({e(r.caveat)})" if r.caveat else ""
    )


def zone_names(conn: sqlite3.Connection) -> str:
    """The time zones the case's phones are read in, by their full names: "America/New_York",
    or "America/New_York or Asia/Kolkata, by phone"; "" when no phone's zone is known. A time
    in view ends in the zone's short name ("EDT", "CST"), which more than one zone can share;
    the full name beside the note on times settles which, and with it the UTC offset."""
    names = sorted(
        {z.key for z in (device_zone(conn, d) for d in device_zones(conn)) if z is not None}
    )
    return " or ".join(names) + (", by phone" if len(names) > 1 else "")


def _local_words(zones: str) -> str:
    return f"Times are the phone's local time{f' ({zones})' if zones else ''}, {LOCAL_TIME_NOTE}"


def time_note(locals_: Iterable[str], zones: str = "") -> str:
    """How to read the times of a set of rows, said once above them: the phone's local time,
    UTC where the phone's zone is unknown, or both; "" when no row has a time in either form.
    zones: zone_names(conn), named once so a short zone name in a row is not ambiguous."""
    readings = [r for r in (reading(x) for x in locals_ if x) if r is not None]
    if not readings:
        return ""
    zoned = sum(1 for r in readings if not r.caveat)
    if zoned == len(readings):
        return f"{_local_words(zones)}."
    if zoned == 0:
        return "Times are UTC: the phone's time zone is unknown."
    return f"{_local_words(zones)}, except those marked device zone unknown, which are UTC."


def times_note(conn: sqlite3.Connection) -> str:
    """The same note for lines whose times are not gathered in one table (evidence cards, the
    labeled-irrelevant list): true whether each phone's zone is known or not."""
    return f"{_local_words(zone_names(conn))}, or UTC where the zone is unknown."


def local_day(conn: sqlite3.Connection, ts_utc: str | None, device_id: str | None) -> str:
    """A stored UTC time's date on the phone's calendar, "Feb 21, 2026", as the rows' date
    cells give it; the UTC date with " (UTC)" when the phone's zone is unknown; "" when the
    time cannot be read."""
    try:
        dt = parse_utc(ts_utc)
    except ValueError:
        return ""
    if dt is None:
        return ""
    r = reading(format_local(dt, device_zone(conn, device_id), None))
    if r is None:
        return ""
    return r.date + (" (UTC)" if r.caveat else "")


class Sources:
    """The case's files by source id, read once a page: (file name, kind)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._seen: dict[str, tuple[str, str]] = {}

    def get(self, source_id: str) -> tuple[str, str]:
        if source_id not in self._seen:
            row = self._conn.execute(
                "SELECT file_name, kind FROM sources WHERE id = ?", (source_id,)
            ).fetchone()
            self._seen[source_id] = (row[0], row[1]) if row else (source_id, "")
        return self._seen[source_id]

    def row(self, source_id: str, locator: str) -> str:
        """Where in its file, as HTML: "Chats sheet, Excel row 947" for an Excel report, else
        the locator as the importer wrote it."""
        m = _SHEET_ROW.match(locator)
        if self.get(source_id)[1] == EXCEL and m:
            return f"{q(m['sheet'])} sheet, Excel row {e(m['row'])}"
        return f"at <span class='mono'>{e(locator)}</span>"

    def sheet(self, source_id: str, locator: str) -> str | None:
        """The sheet an Excel report's row is on; None for any other record."""
        m = _SHEET_ROW.match(locator)
        return m["sheet"] if self.get(source_id)[1] == EXCEL and m else None

    def place(self, source_id: str, locator: str) -> str:
        """The file and the place in it: "item1.xlsx, Chats sheet, Excel row 947"."""
        return f"{q(self.get(source_id)[0])}, {self.row(source_id, locator)}"

    def excel(self, source_ids: Iterable[str]) -> bool:
        return any(self.get(s)[1] == EXCEL for s in source_ids)


def follows(sender: str, direction: str) -> bool:
    """The direction is what the sender already says: the phone's own account sent it, or
    another known account's message came in. A message with no sender account says nothing
    about its direction, so its direction is always written."""
    own = sender.endswith(" (this phone)")
    if not own and sender in UNKNOWN_SENDERS:
        return False
    return direction == ("outgoing" if own else "incoming")


def who(ln: Line, app: str | None = None, name: str | None = None) -> str:
    """A message's sender as HTML (core/report/selection.py sender_words), with the direction in
    words only when it does not follow from whose account sent it, so no direction is lost.
    name: the account's display name in the source, as the report's record line gives it:
    "5551234 (@alex92)", "7001001 (Dan P, this phone)". A name printed on the message's own
    row (shown_as) leads instead, as sender_words puts it."""
    if ln.shown_as or not name:
        words = sender_words(ln.sender, ln.shown_as, app)
    else:
        own = ln.sender.endswith(" (this phone)")
        ident = sender_words(ln.sender.removesuffix(" (this phone)"), None, app)
        words = f"{ident} ({q(name)}{', this phone' if own else ''})"
    return words if follows(ln.sender, ln.direction) else f"{words} · {e(ln.direction)}"


def warning(conn: sqlite3.Connection, record_id: str, found: dict[str, str] | None) -> str:
    """The forwarded-or-quoted-copy note for a record, as record_line prints it; "" for none."""
    note = (found or {}).get(record_id)
    if not note:
        return ""
    parts = forwarded.record_note(conn, record_id, note)
    return "".join(q(t) if cited else e(t) for t, cited in parts)


@dataclass(frozen=True)
class Row:
    """One record as a table row."""

    record_id: str
    source_id: str
    locator: str
    local: str  # format_local's string; "" for a record with no time (a contact)
    who: str  # HTML; "" when the record's text names its parties (a call)
    what: str  # HTML: the message, or the record's text
    tier: ProvenanceTier | None  # None for a record no longer in the case: nothing to observe
    target: bool = False
    way: str = ""  # a message's direction where who says it (it does not follow from the sender)
    app: str = ""  # a message's app
    thread: str = ""  # a message's thread id
    title: str = ""  # a message's thread title


def _of_messages(conn: sqlite3.Connection, ids: list[str]) -> dict[str, tuple[str, str, str, str]]:
    """message id: (thread id, app, thread title, the sender account's display name)."""
    out: dict[str, tuple[str, str, str, str]] = {}
    for at in range(0, len(ids), 500):
        part = ids[at : at + 500]
        marks = ",".join("?" * len(part))
        for r in conn.execute(
            "SELECT m.id, t.id, t.app, t.title, a.display_name FROM messages m"  # noqa: S608
            " JOIN threads t ON t.id = m.thread_id"
            f" LEFT JOIN accounts a ON a.id = m.sender_account_id WHERE m.id IN ({marks})",
            part,
        ):
            out[r[0]] = (r[1], r[2] or "", r[3] or "(untitled)", r[4] or "")
    return out


def message_rows(
    conn: sqlite3.Connection, lines: Iterable[Line], app: str | None = None
) -> list[Row]:
    """Rows for messages already read as conversation lines. app: the conversation's app, left
    off each sender because the conversation's header gives it."""
    lines = list(lines)
    known = _of_messages(conn, [ln.record_id for ln in lines])
    out = []
    for ln in lines:
        thread, own_app, title, name = known.get(ln.record_id, ("", "", "", ""))
        label = forwarded.copy_label(ln.locator)
        body = q(ln.body) + (f"<br><strong class='warn'>{e(label)}</strong>" if label else "")
        out.append(
            Row(
                record_id=ln.record_id,
                source_id=ln.source_id,
                locator=ln.locator,
                local=ln.local,
                who=who(ln, app, name),
                what=body,
                tier=ln.tier,
                target=ln.is_target,
                way="" if follows(ln.sender, ln.direction) else ln.direction,
                app=app or own_app,
                thread=thread,
                title=title,
            )
        )
    return out


def _call_local(conn: sqlite3.Connection, record_id: str) -> str:
    r = conn.execute(
        "SELECT ts_utc, ts_raw, device_id FROM calls WHERE id = ?", (record_id,)
    ).fetchone()
    if r is None:
        return ""
    try:
        utc = parse_utc(r[0])
    except ValueError:  # not a time: say so with the source's own value, as a NULL time does
        utc = None
    return format_local(utc, device_zone(conn, r[2]), r[1])


def record_rows(conn: sqlite3.Connection, record_ids: Iterable[str]) -> list[Row]:
    """Rows for records of any kind, in the order given. A record that is no longer in the
    case keeps its row and says so. Every record is as its source holds it: tier observed.
    When every message among them is from one app, the senders leave the app's name off (the
    caller's heading or the row's thread gives it)."""
    ids = list(record_ids)
    known = _of_messages(conn, [r for r in ids if r.startswith("msg:")])
    apps = {v[1] for v in known.values()}
    app = next(iter(apps)) if len(apps) == 1 else None
    rows = message_rows(conn, message_lines(conn, [r for r in ids if r in known], None), app)
    by_id = {r.record_id: r for r in rows}
    out = []
    for rid in ids:
        if rid in by_id:
            out.append(by_id[rid])
            continue
        rec = get_record(conn, rid)
        if rec is None:
            out.append(Row(rid, "", "", "", "", "record not found", None))
            continue
        out.append(
            Row(
                record_id=rid,
                source_id=rec.ref.source_id,
                locator=rec.ref.locator,
                local=_call_local(conn, rid) if rid.startswith("call:") else "",
                who="",
                what=q(rec.text),
                tier=ProvenanceTier.OBSERVED,
            )
        )
    return out


@dataclass(frozen=True)
class Shared:
    """What every row of a table has in common, said once above it instead of in each row."""

    file: str | None  # the one file every row is in
    sheet: str | None  # the one Excel sheet of that file every row is on
    tier: ProvenanceTier | None  # the one tier every row carries
    app: str | None = None  # the app the rows' senders leave off, for the caller to name
    thread: str | None = None  # the one thread's title, when every message is from it

    @property
    def words(self) -> str:
        """HTML: "item1.xlsx, Chats sheet", "item1.xlsx", or "" when the rows differ."""
        if self.file is None:
            return ""
        return q(self.file) + (f", {q(self.sheet)} sheet" if self.sheet else "")


def shared(rows: list[Row], sources: Sources) -> Shared:
    ids = {r.source_id for r in rows if r.source_id}
    file = sources.get(next(iter(ids)))[0] if len(ids) == 1 else None
    sheets = {sources.sheet(r.source_id, r.locator) for r in rows if r.source_id}
    sheet = next(iter(sheets)) if file is not None and len(sheets) == 1 else None
    tiers = {r.tier for r in rows if r.tier is not None}
    # a message no longer in the case has no app to give, and takes none from the others
    apps = {r.app for r in rows if r.record_id.startswith("msg:") and r.source_id}
    app = next(iter(apps)) if len(apps) == 1 else None
    threads = {r.thread: r.title for r in rows if r.thread}
    thread = next(iter(threads.values())) if len(threads) == 1 else None
    tier = next(iter(tiers)) if len(tiers) == 1 else None
    return Shared(file, sheet, tier, app or None, thread)


def table(
    rows: list[Row],
    sources: Sources,
    href: Callable[[Row], str | None] | None = None,
) -> str:
    """Records as one table: date, the phone's local time, sender, the message or record, and
    the row in the file. A date prints once per run of rows that share it. A column every row
    would leave empty is left out. What the rows share is left to the caller to say once above
    the table (shared(rows): the file and sheet, the tier, and the app its senders leave off):
    a row then gives only its Excel row number, and a tier column appears only when the rows
    differ in tier; a message says its thread only when the messages are from more than one.
    The time column says the phone's local time when any row's zone is known
    (a row whose zone is not says so). href: a link for a row's place in the file, such as its
    conversation."""
    same = shared(rows, sources)
    timed = any(r.local for r in rows)
    read = [rd for rd in (reading(r.local) for r in rows) if rd is not None]
    named = any(r.who for r in rows)
    split = len({r.thread for r in rows if r.thread}) > 1
    what = "Message" if rows and all(r.record_id.startswith("msg:") for r in rows) else "Record"
    if any(not rd.caveat for rd in read):
        clock = "Phone's local time"
    else:
        clock = "Time (UTC)" if read else "Time"
    head = (
        (f"<th>Date</th><th>{clock}</th>" if timed else "")
        + ("<th>From</th>" if named else "")
        + f"<th>{what}</th>"
        + ("" if same.tier else "<th>Tier</th>")
        + f"<th>{'Excel row' if same.sheet else 'Row in the file'}</th>"
    )
    out = [f"<table class='recs'><thead><tr>{head}</tr></thead>"]
    last_date = None
    for r in rows:
        cells = []
        if timed:
            rd = reading(r.local)
            if rd is None:
                # an empty date cell means "the same day as the row above": say there is none
                cells.append(f"<td class='d'>no date</td><td class='t'>{e(r.local)}</td>")
                last_date = None
            else:
                date = "" if rd.date == last_date else e(rd.date)
                cells.append(f"<td class='d'>{date}</td><td class='t'>{when(r.local, False)}</td>")
                last_date = rd.date
        if named:
            cells.append(f"<td class='from'>{r.who}</td>")
        # messages from more than one thread: each says its own (its counterparty), under the
        # message, where the row has room
        where = (
            f"<br><span class='muted'>in thread {q(r.title)}</span>" if split and r.thread else ""
        )
        cells.append(f"<td class='what'>{r.what}{where}</td>")
        if not same.tier:
            cells.append(f"<td class='tier'>{e(r.tier.value) if r.tier else ''}</td>")
        if not r.source_id:
            place = ""
        else:
            m = _SHEET_ROW.match(r.locator)
            if same.sheet and m:
                place = e(m["row"])
            else:
                place = (sources.row if same.file else sources.place)(r.source_id, r.locator)
            url = href(r) if href else None
            place = f"<a href='{e(url)}'>{place}</a>" if url else place
        cells.append(f"<td class='src'>{place}</td>")
        cls = " class='target'" if r.target else ""
        out.append(f"<tr{cls}>{''.join(cells)}</tr>")
    out.append("</table>")
    return "".join(out)


def line(
    conn: sqlite3.Connection,
    record_id: str,
    sources: Sources,
    place: tuple[str, str] | None = None,
    shown: bool = False,
    quoted: str | None = None,
) -> str:
    """One record as a short line of HTML: who, when and where it sits in the file.
    place: the (source id, locator) to print, when the caller holds its own reference to the
    record (an evidence item's); the default is the record's own. shown: the messages drawn
    above already give the time, so the line leaves it out; the sender stays, because only
    this line gives the account's display name from the source.
    quoted: the words the caller prints beside the line; a record whose whole text they are (a
    contact, a call) is not printed twice."""
    r = record_rows(conn, [record_id])[0]
    src, loc = place or (r.source_id, r.locator)
    if not src:
        return r.what
    where = sources.place(src, loc)
    if not r.source_id:  # the record is gone; the caller's own reference still places it
        return f"{r.what} · {where}"
    if r.thread:
        # " · " parts the line, so a direction that has to be said goes in brackets here
        sender = r.who.removesuffix(f" · {e(r.way)}") + (f" ({e(r.way)})" if r.way else "")
        head = f"{sender} in {q(r.app)} thread {q(r.title)}"
        return f"{head} · {where}" if shown else f"{head} · {when(r.local)} · {where}"
    rec = get_record(conn, record_id)
    what = "" if rec is not None and quoted is not None and rec.text == quoted else r.what
    return " · ".join(x for x in (what, when(r.local) if r.local else "", where) if x)
