"""Read a carrier call-record CSV into a case database through a rule pack's layout.

Kept apart from the synthetic generator (carrier.py) so that a drafting session can be given
the reader and the sample files without the generator's source, which states each layout's
codes outright and marks which events the claims rest on (DRAFTING.md). The drafter still sees
every record: the samples in formats/samples/ are checked-in snapshots of carrier.render().
The harness never reads the samples. It passes carrier.render() to read() directly, so editing a
sample does not change a harness run; check_layout.py is the tool that reads the samples, and a
test keeps them identical to render().
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from core.db import apply_schema, connect
from eval.rulepacks.pack import CALL_TYPES, Layout

TARGET = "5550100201"  # the subscriber line the records are for
SUBJECT_2_LINE = "5550100377"
SUBJECT_3_LINE = "5550100444"

P1, P2, P3 = "person:subject-1", "person:subject-2", "person:subject-3"
LINE_DEVICE = f"line:{TARGET}"
SOURCE_ID = "cdr:target"


@dataclass
class Loaded:
    conn: sqlite3.Connection
    record_types: dict[str, str]  # call id -> canonical record type (guards read this)
    coverage: dict[str, object]


def read(text: str, layout: Layout) -> Loaded:
    """Load one CDR file into a fresh in-memory case database through the pack's layout.

    A file whose header row is not exactly the layout's is refused. A row whose direction or
    type the layout does not map is skipped and counted; so is every sms row. Times are read
    in the layout's zone and stored as UTC with the offset and the raw value kept.
    """
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or tuple(rows[0]) != layout.headers:
        raise ValueError(f"header row does not match layout {layout.id}")
    col = {h: i for i, h in enumerate(rows[0])}
    zone = ZoneInfo(layout.zone)
    conn = connect(":memory:")
    apply_schema(conn)
    conn.execute(
        "INSERT INTO sources VALUES (?, 'synthetic', 'full_extraction', 'not_applicable', ?, ?,"
        " NULL, NULL, NULL, '2026-11-15T00:00:00Z')",
        (SOURCE_ID, f"{layout.id}.csv", _sha(text)),
    )
    conn.execute(
        "INSERT INTO devices VALUES (?, ?, 'line', 'TARGET LINE', NULL, NULL, ?)",
        (LINE_DEVICE, SOURCE_ID, "America/New_York"),
    )
    accounts: dict[str, str] = {}

    def account(number: str) -> str:
        if number not in accounts:
            aid = f"a:cdr:{number}"
            conn.execute(
                "INSERT INTO accounts VALUES (?, ?, 'x', ?, 'phone', ?, NULL)",
                (aid, SOURCE_ID, LINE_DEVICE if number == TARGET else None, number),
            )
            accounts[number] = aid
        return accounts[number]

    account(TARGET)
    record_types: dict[str, str] = {}
    skipped = {
        "sms": 0,
        "unmapped_direction": 0,
        "unmapped_type": 0,
        "bad_time": 0,
        "malformed": 0,
    }
    unsure_times = 0  # rows kept with no UTC time: a local time DST makes double or missing
    for n, r in enumerate(rows[1:], start=2):
        if len(r) != len(layout.headers):
            skipped["malformed"] += 1
            continue
        raw_duration = r[col[layout.duration_col]].strip()
        # ASCII digits only, at most 9 (about 31 years): longer would overflow SQLite's integer
        if raw_duration and not re.fullmatch(r"[0-9]{1,9}", raw_duration):
            skipped["malformed"] += 1
            continue
        duration = int(raw_duration) if raw_duration else None  # blank: not stated, not 0
        kind = layout.type_values.get(r[col[layout.type_col]])
        if kind is None:
            skipped["unmapped_type"] += 1
            continue
        if kind not in CALL_TYPES:
            skipped["sms"] += 1
            continue
        direction = layout.direction_values.get(r[col[layout.direction_col]])
        if direction is None:
            skipped["unmapped_direction"] += 1
            continue
        raw = f"{r[col[layout.date_col]]} {r[col[layout.time_col]]}"
        try:
            naive = datetime.strptime(raw, layout.datetime_format)
        except ValueError:
            skipped["bad_time"] += 1
            continue
        local = naive.replace(tzinfo=zone)
        ts_utc: str | None = local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        off_min: int | None = int((local.utcoffset() or timedelta(0)).total_seconds() // 60)
        if not _one_instant(naive, zone):
            ts_utc, off_min = None, None  # the raw value is kept; no check reads a guess
            unsure_times += 1
        frm, to = account(r[col[layout.from_col]]), account(r[col[layout.to_col]])
        cid = f"call:cdr:{n}"
        conn.execute(
            "INSERT INTO calls (id, source_id, locator, device_id, app, from_account_id,"
            " to_account_id, direction, ts_utc, ts_offset_min, ts_raw, duration_s, deleted_flag)"
            " VALUES (?, ?, ?, ?, 'phone', ?, ?, ?, ?, ?, ?, ?, NULL)",
            (
                cid,
                SOURCE_ID,
                f"{layout.id}.csv:row {n}",  # source_ref back to the original row
                LINE_DEVICE,
                frm,
                to,
                direction,
                ts_utc,
                off_min,
                raw,
                duration,
            ),
        )
        record_types[cid] = kind
    coverage = {
        "layout": layout.id,
        "zone": layout.zone,
        "rows": len(rows) - 1,
        "calls": len(record_types),
        "skipped": skipped,
        "unsure_times": unsure_times,
        "notes": [
            "A local time that daylight saving makes happen twice, or not at all, is kept with"
            " its raw value and no UTC time.",
            "A carrier record shows the line's activity, not who held the phone.",
            "Synthetic: treated as complete for the line over the file's dates.",
        ],
    }
    conn.execute(
        "INSERT INTO source_coverage VALUES (?, 'eval.rulepacks.carrier', '0.1.0', ?)",
        (SOURCE_ID, json.dumps(coverage, sort_keys=True)),
    )
    _people(conn, accounts)
    return Loaded(conn, record_types, coverage)


def _one_instant(naive: datetime, zone: ZoneInfo) -> bool:
    """True if this wall-clock time names exactly one instant in the zone: not repeated when
    clocks fall back, not skipped when they spring forward."""
    a, b = naive.replace(tzinfo=zone, fold=0), naive.replace(tzinfo=zone, fold=1)
    if a.utcoffset() != b.utcoffset():
        return False
    return a.astimezone(UTC).astimezone(zone).replace(tzinfo=None) == naive


def _people(conn: sqlite3.Connection, accounts: dict[str, str]) -> None:
    """SUBJECT-1 holds the TARGET LINE (an expert-confirmed stipulation); SUBJECT-2 uses 0377
    (a confirmed link); SUBJECT-3 is only the listed subscriber of 0444 (a proposed link)."""
    conn.executemany(
        "INSERT INTO persons VALUES (?, ?, 'expert:synthetic')",
        [(P1, "SUBJECT-1"), (P2, "SUBJECT-2"), (P3, "SUBJECT-3")],
    )
    conn.execute(
        "INSERT INTO stipulations VALUES (?, 'device_owner', ?, ?, ?, 'confirmed',"
        " 'expert:synthetic', '2026-11-15T00:00:00Z')",
        (f"stip:device_owner:{LINE_DEVICE}", LINE_DEVICE, P1, "The TARGET LINE is SUBJECT-1's"),
    )
    links = [
        ("link:p2", accounts.get(SUBJECT_2_LINE), P2, "confirmed"),
        ("link:p3", accounts.get(SUBJECT_3_LINE), P3, "proposed"),
    ]
    for lid, aid, pid, status in links:
        if aid is None:
            continue
        confirmed = status == "confirmed"
        conn.execute(
            "INSERT INTO identity_links VALUES (?, ?, ?, ?, ?, 'subscriber record', ?, ?)",
            (
                lid,
                aid,
                pid,
                status,
                "confirmed" if confirmed else "inferred",  # as core/review/actions.py sets it
                "expert:synthetic" if confirmed else None,
                "2026-11-15T00:00:00Z" if confirmed else None,
            ),
        )


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
