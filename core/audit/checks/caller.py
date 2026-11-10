"""Caller check: who placed one call, read from the direction the phone's call log records."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from core.audit.checks._common import (
    CALL_CHANNEL,
    CaseData,
    Row,
    _ts,
    in_window,
    local_str,
    parties,
    sentences,
    window_str,
    zone_notes,
)
from core.audit.checks.base import TemplateCheck
from core.audit.checks.count import DUPLICATE_S, _sending_side
from core.contracts import AssumptionParams, CheckOutcome, CheckResult

_PLACED_BY_PHONE = frozenset({"outgoing"})
_PLACED_BY_OTHER = frozenset({"incoming", "missed"})


class CallerCheck(TemplateCheck):
    """A call log records each call's direction from the phone that holds it: 'outgoing' means
    the phone's side placed it, 'incoming' or 'missed' that the other side did. The phone's
    side is the party an expert-confirmed device_owner stipulation makes that phone's owner;
    the other side is the other party, matched by account identifier.

    The calls tested are those between the two sides inside the window (and of the stated
    length, if any), on the apps named beside 'call'. Pass only when every one of them agrees
    with the claimed caller. Fail only when every one was placed by the other side, each
    logged plainly as 'incoming' or 'outgoing': calls are picked by their parties and time, not
    their content, so a call the log does not hold is not seen, and the detail says so. A
    direction 'unknown', a row whose parties sit on the wrong side for its direction, a call
    with no usable time, a phone with no one confirmed owner among the parties, or calls both
    ways in the window leave it inconclusive. A 'missed' row agrees with a claim that the other
    side called and is never a fail on its own. The check speaks about the phone and its
    accounts; whether a person placed the call by hand is a separate question.
    """

    name = "caller"
    version = "1.0.0"

    def evaluate(self, assumption_id: str, p: AssumptionParams, data: CaseData) -> CheckResult:
        if p.window is None:
            raise ValueError("the caller check needs a window")
        sources = data.sources_for(p.device_ids)
        found = parties(data, p)
        apps = {c.strip().lower() for c in p.channels} - {CALL_CHANNEL}
        on = ", ".join(sorted(apps)) if apps else "every app"
        lasting = f" lasting {p.duration_s[0]} to {p.duration_s[1]} s" if p.duration_s else ""
        side = _sending_side(p, found[0], found[1]) if len(found) == 2 else None
        searched = (
            f"Calls on {on}{lasting} between "
            f"{' and '.join(x.describe() for x in found)} in {', '.join(sources) or 'no source'}"
            f"; window {window_str(p.window)}; expected caller "
            f"{side.label if side else 'not one side'}."
        )
        notes = [n for x in found for n in x.notes] + zone_notes(data, p.window, sources)

        def inconclusive(why: str) -> CheckResult:
            return self.done(
                assumption_id,
                CheckOutcome.INCONCLUSIVE,
                searched,
                sentences(why, notes),
                [],
                sources,
            )

        if side is None:
            return inconclusive("Cannot read a caller: the assumption does not name one side")
        a, b = found
        pids = [*p.person_ids, *([None] if p.account_ids or p.handles else [])]
        ids = [data.account_ids(a.keys), data.account_ids(b.keys)]
        if not ids[0] or not ids[1]:
            return inconclusive("Cannot read a caller: a side has no accounts in the data")
        if ids[0] & ids[1]:
            return inconclusive(
                "Cannot read a caller: the two sides share an account, so which side placed a "
                "call is not known"
            )

        rows = _calls(data, ids[0] | ids[1])
        wanted_devices = set(p.device_ids)
        agree: list[str] = []
        against: list[str] = []
        unread: list[str] = []
        lines: list[str] = []
        times: list[tuple[datetime, str]] = []
        for r in rows:
            if r["source_id"] not in sources:
                continue
            if wanted_devices and r["device_id"] not in wanted_devices:
                continue
            if apps and r["app"].strip().lower() not in apps:
                continue
            no_length = p.duration_s is not None and r["duration_s"] is None
            if p.duration_s is not None and not no_length:
                lo, hi = p.duration_s
                if not lo <= r["duration_s"] <= hi:
                    continue
            phone_at = _phone_side(data, r["device_id"], pids)
            # the other side's accounts must sit on the row for it to be a call between them
            if phone_at is not None:
                other_ids = ids[1 - phone_at]
                if not ({r["from"], r["to"]} & other_ids):
                    continue
            elif not ({r["from"], r["to"]} & ids[0] and {r["from"], r["to"]} & ids[1]):
                continue  # with neither side the phone's, only a row both sides are on
            ts = r["ts"]
            when = local_str(data, r["row"])
            if ts is not None and not in_window(ts, p.window):
                continue
            if ts is None:
                unread.append(r["id"])
                lines.append(f"{r['id']} has no usable time ({when}), so it may be this call")
                continue
            times.append((ts, r["id"]))
            if no_length:
                # a call of unknown length may be the claimed one, so it never lets a fail stand
                unread.append(r["id"])
                lines.append(f"{r['id']} at {when} has no recorded length, so it may be this call")
                continue
            if phone_at is None:
                unread.append(r["id"])
                lines.append(
                    f"{r['id']} at {when} is on {r['device_id'] or 'no device'}, which no "
                    "confirmed device_owner stipulation gives to exactly one of the sides"
                )
                continue
            placed = _placed_by(data, r, phone_at, ids[1 - phone_at])
            direction = r["direction"]
            if placed is None:
                unread.append(r["id"])
                lines.append(
                    f"{r['id']} at {when} is logged {direction!r}"
                    + (
                        ", so the log does not say who placed it"
                        if direction not in _PLACED_BY_PHONE | _PLACED_BY_OTHER
                        else ", but its accounts sit on the wrong side for that, so who placed"
                        " it is not read"
                    )
                )
                continue
            caller = found[placed]
            lines.append(f"{r['id']} at {when} is logged {direction!r}: {caller.label} placed it")
            if caller is side:
                agree.append(r["id"])
            elif direction == "missed":
                # 'missed' is an incoming call in the call logs this reads, but a fail rests
                # only on the plain words 'incoming' and 'outgoing'
                unread.append(r["id"])
            else:
                against.append(r["id"])
        record_ids = [*agree, *against, *unread]
        if not record_ids:
            return inconclusive(
                "No call between them in the window. Not found does not mean it did not happen"
            )
        twins = _twins(times)
        if twins:
            lines.append(
                f"Rows {'; '.join(f'{x} and {y}' for x, y in twins)} are within {DUPLICATE_S} "
                "seconds of each other, so they may be one call stored twice"
            )
        if agree and not against and not unread:
            outcome, verdict = CheckOutcome.PASS, f"Every such call was placed by {side.label}"
        elif against and not agree and not unread:
            outcome = CheckOutcome.FAIL
            verdict = (
                f"No such call was placed by {side.label}: every call between them in the "
                "window was placed by the other side. A call the log does not hold is not seen"
            )
        else:
            outcome = CheckOutcome.INCONCLUSIVE
            verdict = (
                "The calls in the window do not all say the same caller, or some do not say who"
                " placed them"
            )
        return self.done(
            assumption_id, outcome, searched, sentences(lines, verdict, notes), record_ids, sources
        )


def _calls(data: CaseData, account_ids: set[str]) -> list[dict[str, Any]]:
    """Calls with an account in the set on either side, with their device and direction."""
    ids = json.dumps(sorted(account_ids))
    out = []
    for cid, sid, dev, app, frm, to, direction, ts, raw, dur in data.conn.execute(
        "SELECT id, source_id, device_id, app, from_account_id, to_account_id, direction,"
        " ts_utc, ts_raw, duration_s FROM calls"
        " WHERE from_account_id IN (SELECT value FROM json_each(?))"
        " OR to_account_id IN (SELECT value FROM json_each(?)) ORDER BY id",
        (ids, ids),
    ):
        t = _ts(ts)
        row = Row(cid, "call", sid, app, frm, (to,) if to else (), t, raw, None, dur)
        out.append({"id": cid, "source_id": sid, "device_id": dev, "app": app, "from": frm,
                    "to": to, "direction": direction, "ts": t, "duration_s": dur,
                    "row": row})  # fmt: skip
    return out


def _phone_side(data: CaseData, device_id: str | None, pids: list[str | None]) -> int | None:
    """Which side (0 or 1) is the phone's owner by the one confirmed device_owner stipulation
    on the device; None when the device has no one confirmed owner, or it is not exactly one
    of the two sides."""
    if device_id is None:
        return None
    owners = {
        pid
        for _, did, pid, status in data.stipulations
        if did == device_id and status == "confirmed"
    }
    if len(owners) != 1:
        return None
    at = [i for i, pid in enumerate(pids) if pid is not None and pid in owners]
    return at[0] if len(at) == 1 else None


def _placed_by(data: CaseData, r: dict[str, Any], phone_at: int, other_ids: set[str]) -> int | None:
    """The side that placed the call by the row's direction, when its accounts agree with it:
    on an outgoing call the other side is the one called and the phone's own account (if any)
    the caller, on an incoming or missed call the reverse. None otherwise."""
    own = {a.id for a in data.accounts.values() if a.device_id == r["device_id"]}
    frm, to = r["from"], r["to"]
    if r["direction"] in _PLACED_BY_PHONE:
        if to in other_ids and (frm is None or frm in own):
            return phone_at
    elif r["direction"] in _PLACED_BY_OTHER:
        if frm in other_ids and (to is None or to in own):
            return 1 - phone_at
    return None


def _twins(timed: list[tuple[datetime, str]]) -> list[tuple[str, str]]:
    """Pairs of tested rows DUPLICATE_S seconds apart or less: perhaps one call stored twice."""
    ordered = sorted(timed)
    out = []
    for i, (tx, x) in enumerate(ordered):
        for ty, y in ordered[i + 1 :]:
            if (ty - tx).total_seconds() > DUPLICATE_S:
                break
            out.append((x, y))
    return out
