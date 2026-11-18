"""Weekday check: which date does a weekday named in a message point to?

"lets meet monday" sent on Friday March 6 points to Monday March 9, counted forward from the
send date in the phone's own zone. The check passes when every copy of the message points to
the claimed day. Language is loose ("monday" can mean the one after), so anything else is
inconclusive, never a fail: a different reading is the model's and the expert's question.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.audit.checks._common import (
    TEXT_MATCH,
    CaseData,
    channel_ok,
    incomplete,
    involves_all,
    local_str,
    messages_with_text,
    parties,
    sentences,
)
from core.audit.checks.base import TemplateCheck
from core.contracts import AssumptionParams, CheckOutcome, CheckResult

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_NAME = re.compile(r"\b(" + "|".join(WEEKDAYS) + r")\b", re.IGNORECASE)
_QUALIFIED = re.compile(
    r"\b(next|this|last|coming|following|every)\s+(" + "|".join(WEEKDAYS) + r")\b", re.IGNORECASE
)


class WeekdayCheck(TemplateCheck):
    name = "weekday"
    # 1.0.2: curly quotes and runs of spaces fold (TEXT_MATCH). 1.0.3: a message with the words
    # that names no sender or no receiver keeps it from passing (Greptile on #264).
    version = "1.0.3"

    def evaluate(self, assumption_id: str, p: AssumptionParams, data: CaseData) -> CheckResult:
        if p.window is None or not p.quoted_text:
            raise ValueError("the weekday check needs quoted_text and a window")
        sources = data.sources_for(p.device_ids)
        found = parties(data, p)
        party_ids = [data.account_ids(x.keys) for x in found]
        text = p.quoted_text
        searched = (
            f"Messages containing {text!r} ({TEXT_MATCH}) in {', '.join(sources)}; the weekday it "
            f'names, counted forward from the send date on the phone, against "{p.window.raw}".'
        )
        notes = [n for x in found for n in x.notes]

        def inconclusive(why: str, ids: tuple[str, ...] = ()) -> CheckResult:
            return self.done(
                assumption_id, CheckOutcome.INCONCLUSIVE, searched, sentences(why, notes), ids,
                sources,
            )  # fmt: skip

        try:
            zone = ZoneInfo(p.window.tz)
        except (ZoneInfoNotFoundError, ValueError):
            return inconclusive(f"The window's zone {p.window.tz!r} is unknown")
        first = p.window.start_utc.astimezone(zone).date()
        last = p.window.end_utc.astimezone(zone).date()
        if first != last:
            return inconclusive("The claimed window is not a single day")
        names = {m.lower() for m in _NAME.findall(text)}
        if len(names) != 1:
            return inconclusive("The quoted words must name exactly one weekday")
        if _QUALIFIED.search(text):
            return inconclusive(
                "The weekday is qualified (next, this, last...), so the date is open"
            )
        (weekday,) = names
        target = WEEKDAYS.index(weekday)

        rows = [
            r
            for r in messages_with_text(data, text)
            if r.source_id in sources and channel_ok(r, p.channels)
        ]
        everyone = set().union(*party_ids) if party_ids else set()
        unplaced = [
            r.id
            for r in rows
            if party_ids
            and incomplete(r)
            # With one party named, a message from anyone may be to that party (CodeRabbit on
            # #264); with two, a known sender must be one of them.
            and (len(party_ids) == 1 or r.sender is None or r.sender in everyone)
        ]
        if unplaced:
            # A LEAPP chat names a sender only: such a message may be the one meant, on
            # another day.
            return inconclusive(
                f"{len(unplaced)} messages with the words name no sender or no receiver, so one"
                f" may be the message meant: {', '.join(unplaced)}",
                tuple(unplaced),
            )
        rows = [r for r in rows if not party_ids or involves_all(r, party_ids)]
        if not rows:
            return inconclusive("None found. Not found does not mean the message was never sent")

        lines, resolved = [], set()
        for r in rows:
            tz = data.tz_for(r.source_id)
            if r.ts_utc is None or tz is None:
                return inconclusive(f"{r.id} has no usable time or phone zone", (r.id,))
            sent = r.ts_utc.astimezone(tz).date()
            if sent.weekday() == target:
                return inconclusive(
                    f"{r.id} was sent on a {weekday.capitalize()} itself, so the day is open",
                    (r.id,),
                )
            day = _forward(sent, target)
            resolved.add(day)
            lines.append(
                f"{r.id} sent {local_str(data, r)}, a {sent:%A}: '{weekday}' is {day:%A %Y-%m-%d}"
            )
        ids = [r.id for r in rows]
        if resolved == {first}:
            lines.append(f"That is the claimed day, {first:%A %Y-%m-%d}")
            return self.done(
                assumption_id, CheckOutcome.PASS, searched, sentences(lines, notes), ids, sources
            )
        lines.append(
            f"The claimed day is {first:%A %Y-%m-%d}; another reading is a question of meaning"
        )
        return self.done(
            assumption_id, CheckOutcome.INCONCLUSIVE, searched, sentences(lines, notes), ids,
            sources,
        )  # fmt: skip


def _forward(sent: date, target: int) -> date:
    return sent + timedelta(days=(target - sent.weekday()) % 7)
