"""Synthetic carrier call detail records (CDR) in two invented layouts. The reader that maps
them into a case database through a rule pack's layout is in reader.py.

Everything here is fictional: invented carriers ("Carrier A", "Carrier B"), 555-01xx numbers,
designations instead of names. No real carrier's layout is copied. The records are for one
subscriber line (the TARGET LINE); direction is from that line.

The generator is seeded and deterministic. The same events render in both layouts, so a claim
has the same right answer whichever layout the case arrives in.
"""

from __future__ import annotations

import csv
import io
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from eval.rulepacks.pack import RulePack
from eval.rulepacks.reader import SUBJECT_2_LINE, SUBJECT_3_LINE, TARGET, Loaded, read

SEED = 20261115


@dataclass(frozen=True)
class Event:
    """What happened, in UTC. Direction is worked out from TARGET when rendered."""

    id: str
    ts_utc: datetime
    caller: str
    callee: str
    duration_s: int
    kind: str  # voice | sms | voicemail | forwarded


def _z(y: int, mo: int, d: int, h: int, mi: int, s: int = 0) -> datetime:
    return datetime(y, mo, d, h, mi, s, tzinfo=UTC)


# Hand-placed events the gold claims and traps rest on. Times in comments are US Eastern.
PLACED: tuple[Event, ...] = (
    Event("e1", _z(2026, 3, 4, 7, 14, 40), SUBJECT_2_LINE, TARGET, 46, "voice"),  # 2:14 a.m.
    Event("e2", _z(2026, 3, 4, 7, 31, 2), TARGET, SUBJECT_2_LINE, 0, "sms"),
    Event("e3", _z(2026, 3, 5, 1, 30, 0), TARGET, SUBJECT_2_LINE, 120, "voice"),  # Mar 4 8:30 p.m.
    Event("e4", _z(2026, 3, 5, 2, 10, 0), TARGET, SUBJECT_2_LINE, 25, "voicemail"),  # 9:10 p.m.
    Event("e5", _z(2026, 3, 6, 3, 0, 0), SUBJECT_3_LINE, TARGET, 60, "forwarded"),  # Mar 5 10 p.m.
    Event("e6", _z(2026, 3, 9, 23, 45, 0), TARGET, SUBJECT_3_LINE, 300, "voice"),  # 7:45 p.m. EDT
)


def background(seed: int = SEED) -> tuple[Event, ...]:
    """Seeded calls between TARGET and numbers no claim names, kept off the placed events'
    days so they never change a claim's answer."""
    rng = random.Random(seed)  # noqa: S311 - synthetic data, not crypto
    others = [f"555010{n:04d}" for n in range(600, 640)]
    out = []
    for i in range(80):
        day = rng.choice([1, 2, 3, 7, 8, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20])
        ts = _z(2026, 3, day, rng.randrange(0, 24), rng.randrange(0, 60), rng.randrange(0, 60))
        other = rng.choice(others)
        out_going = rng.random() < 0.5
        kind = rng.choices(["voice", "sms", "voicemail"], [6, 3, 1])[0]
        dur = 0 if kind == "sms" else rng.randrange(5, 900)
        a, b = (TARGET, other) if out_going else (other, TARGET)
        out.append(Event(f"bg{i:03d}", ts, a, b, dur, kind))
    return tuple(out)


def events(seed: int = SEED) -> list[Event]:
    return sorted((*PLACED, *background(seed)), key=lambda e: (e.ts_utc, e.id))


# ---------------------------------------------------------------- the two invented layouts

CARRIER_A = {
    "headers": ["Date", "Time (UTC)", "Originating", "Terminating", "Direction",
                "Duration (s)", "Type"],
    "direction": {"outgoing": "OUT", "incoming": "IN"},
    "type": {"voice": "VOICE", "sms": "SMS", "voicemail": "VM", "forwarded": "CFWD"},
    "zone": "UTC",
    "date": "%Y-%m-%d",
    "time": "%H:%M:%S",
}  # fmt: skip
CARRIER_B = {
    "headers": ["Call Date", "Call Time (CT)", "Calling Number", "Called Number", "MO/MT",
                "Seconds", "Call Type"],
    "direction": {"outgoing": "MO", "incoming": "MT"},
    "type": {"voice": "V", "sms": "S", "voicemail": "VM", "forwarded": "FW"},
    "zone": "America/Chicago",
    "date": "%m/%d/%Y",
    "time": "%H:%M:%S",
}  # fmt: skip
LAYOUTS = {"carrier-a": CARRIER_A, "carrier-b": CARRIER_B}


def render(layout_id: str, evs: list[Event] | None = None) -> str:
    """The CSV a carrier of this invented layout would return for TARGET."""
    spec = LAYOUTS[layout_id]
    zone = ZoneInfo(spec["zone"])
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(spec["headers"])
    for e in evs if evs is not None else events():
        local = e.ts_utc.astimezone(zone)
        direction = "outgoing" if e.caller == TARGET else "incoming"
        w.writerow([
            local.strftime(spec["date"]),
            local.strftime(spec["time"]),
            e.caller,
            e.callee,
            spec["direction"][direction],
            e.duration_s,
            spec["type"][e.kind],
        ])  # fmt: skip
    return buf.getvalue()


def load_case(pack: RulePack, layout_id: str) -> Loaded:
    """Render the synthetic file in layout_id and read it with the pack's layout of that id."""
    return read(render(layout_id), pack.layout(layout_id))
