"""Count check: how many messages, or calls, one phone holds between two parties in a window."""

from __future__ import annotations

from core.audit.checks._common import (
    CALL_CHANNEL,
    CaseData,
    Party,
    Row,
    apps_not_read,
    calls_for_accounts,
    channel_ok,
    in_window,
    incomplete,
    incomplete_beside,
    involves_all,
    may_be_between,
    messages_for_accounts,
    parties,
    sentences,
    window_str,
    zone_notes,
)
from core.audit.checks.base import TemplateCheck
from core.contracts import AssumptionParams, CheckOutcome, CheckResult, Fidelity

_OPS = {"eq": "exactly", "ge": "at least", "le": "at most"}


# seconds within which a row with the same words as the row before it may be the same message;
# the rows chain, so three copies a second and a half apart are one group (`look_alike_groups`)
TWIN_S = 2


def look_alikes_matter(n: int, twins: int, want: int, op: str) -> bool:
    """True when the claim's answer differs somewhere between n - twins and n counted
    messages, so look-alike rows must hold the count open: "exactly 12" over 17 rows with 5
    look-alikes, but not "at least 5" over 10 rows with 2, nor "at most 20" over 17."""
    lo = n - twins
    if not twins:
        return False
    if op == "ge":
        return lo < want <= n
    if op == "le":
        return lo <= want < n
    return lo <= want <= n  # eq: below lo or above n the answer is the same at every number


def look_alike_groups(rows: list[Row]) -> list[list[Row]]:
    """The rows that repeat one another's words (folded case and spaces, never empty), each
    within TWIN_S seconds of the one before, in groups of two or more in time order: rows a
    count may hold as one message. The rows chain on purpose: a group only holds a count open,
    never passes or fails it, so a longer group errs toward the expert (CodeRabbit on #265).
    The app, sender and direction are left out on purpose: one message's copies in two stores
    can carry different labels ("Native Messages" in one, a number written "9198887386" or no
    sender at all in the other, as on the Android 13 development phone), so a group may be one
    message of any sender in it."""
    last: dict[str, list[Row]] = {}
    groups: list[list[Row]] = []
    for r in sorted((r for r in rows if r.ts_utc is not None), key=lambda r: r.ts_utc):
        words = " ".join((r.text or "").casefold().split())
        if not words:
            continue
        group = last.get(words)
        if group is not None and (r.ts_utc - group[-1].ts_utc).total_seconds() <= TWIN_S:
            group.append(r)  # rows are in time order, so the latest copy is the nearest
        else:
            group = [r]
            groups.append(group)
        last[words] = group
    return [g for g in groups if len(g) > 1]


def look_alike(rows: list[Row]) -> int:
    """How many of the rows repeat an earlier row's words within TWIN_S seconds
    (`look_alike_groups`): rows a count may hold twice. A look-alike only holds a count open,
    never passes or fails it: the count passes or fails only when every number from n -
    look-alikes to n gives that answer (CodeRabbit and the Claude review on #265)."""
    return sum(len(g) - 1 for g in look_alike_groups(rows))


def fewest_messages(
    chosen: list[Row], rows: list[Row], groups: list[list[Row]] | None = None
) -> int:
    """The fewest messages the `chosen` rows (those of `rows` a count keeps, such as one
    side's) may hold: one for each row in no look-alike group of `rows`, and one for each
    group whose every row is chosen. A group that holds a row not chosen may be that row's
    one message, so it may add none: "A to B 'ok'" and "B to A 'ok'" a second apart may be
    B's message alone (CodeRabbit on #265). The groups are read over every row first, before
    a side is chosen; `groups` passes them in when already read."""
    if groups is None:
        groups = look_alike_groups(rows)
    ids = {r.id for r in chosen}
    grouped = {r.id for g in groups for r in g}
    return sum(1 for r in chosen if r.id not in grouped) + sum(
        1 for g in groups if all(r.id in ids for r in g)
    )


def each_way_rests_on_look_alikes(rows: list[Row], a_ids: set[str], b_ids: set[str]) -> bool:
    """True when a message each way may rest on look-alike rows: a side whose rows may hold
    no message (`fewest_messages`), as each of its rows is in a group with the other side's
    row, which may be the one message (CodeRabbit on #265: "A to B 'ok'" and "B to A 'ok'" a
    second apart). Two copies of one side's message still hold a message from that side."""
    groups = look_alike_groups(rows)
    return any(
        fewest_messages([r for r in rows if r.sender in ids], rows, groups) == 0
        for ids in (a_ids, b_ids)
    )


class CountCheck(TemplateCheck):
    """Parties are matched by account identifier, so a renamed handle is still one party.

    A report can leave records out, and phones lose them, so finding fewer than claimed is
    never a fail. Finding more than "exactly" or "at most" allows is a fail: those records are
    there. "At most" can only pass on a full extraction. When any matching message is one the
    extraction tool numbered as a copy of another row, the count neither passes nor fails.

    With 'call' among the channels it counts calls instead, on the other apps named if any
    (validation fill f). A call count never fails: a call log keeps calls that did not connect,
    and an extraction can hold one call twice (two databases, a few seconds apart). It passes
    only when the rows match the claim and no two counted calls with the same party fall
    within DUPLICATE_S of each other; otherwise it is inconclusive.

    With `sent_by` it counts only the messages that side sent (validation R2). A message to the
    other side with no recorded sender may be one of them, so "exactly" and "at most" then
    stay inconclusive unless the known ones already exceed the claim. With `each_way`
    ("exchanged messages", R3) it passes only when each side sent at least one counted message;
    one side's silence is never a fail, since coverage is unknown.
    """

    name = "count"
    # 1.2.1: a message or call that names no sender or no receiver, with a party on it or in a
    # chat with one, keeps "at most" and "exactly" from passing (Greptile on #264).
    # 1.3.0: look-alike rows hold a count open when merging them could change the answer.
    # 1.3.1: both guards together (#264 and #265 merged), and look-alikes read over both
    # sides before a side is chosen (CodeRabbit on #265).
    version = "1.3.1"

    def evaluate(self, assumption_id: str, p: AssumptionParams, data: CaseData) -> CheckResult:
        if p.window is None or p.expected_count is None or p.count_op is None:
            raise ValueError("the count check needs a window, expected_count and count_op")
        sources = data.sources_for(p.device_ids)
        a, b = parties(data, p)
        a_ids, b_ids = data.account_ids(a.keys), data.account_ids(b.keys)
        calls = CALL_CHANNEL in {c.strip().lower() for c in p.channels}
        if calls:
            return self._calls(assumption_id, p, data)
        on = ", ".join(p.channels) if p.channels else "every channel"
        searched = (
            f"Messages on {on} between {a.describe()} and {b.describe()} on "
            f"{', '.join(p.device_ids)} ({', '.join(sources) or 'no source'}); window "
            f"{window_str(p.window)}."
        )
        notes = a.notes + b.notes + zone_notes(data, p.window, sources)
        if len(sources) != 1 or not a_ids or not b_ids:
            why = (
                "the device is in no single evidence source"
                if len(sources) != 1
                else "a party has no accounts in the data"
            )
            return self.done(
                assumption_id,
                CheckOutcome.INCONCLUSIVE,
                searched,
                sentences(f"Cannot count: {why}", notes),
                [],
                sources,
            )
        (source_id,) = sources
        source = data.sources[source_id]
        pool = [
            r
            for r in messages_for_accounts(data, a_ids | b_ids)
            if r.source_id == source_id and channel_ok(r, p.channels)
        ]
        rows = [r for r in pool if involves_all(r, [a_ids, b_ids])]
        seen = {r.id for r in pool}
        beside = [
            r
            for r in incomplete_beside(data, a_ids | b_ids)
            if r.id not in seen and r.source_id == source_id and channel_ok(r, p.channels)
        ]
        # Rows that may be messages between the two sides but name no sender or no receiver
        # (a LEAPP chat names a sender only, and a phone's own message often neither side).
        unplaced = [
            r
            for r in pool + beside
            if incomplete(r)
            and may_be_between(r, a_ids, b_ids)
            and (r.ts_utc is None or in_window(r.ts_utc, p.window))
        ]
        counted = [r for r in rows if r.ts_utc is not None and in_window(r.ts_utc, p.window)]
        # Look-alikes are read over both sides, before a side is chosen, and, for one side's
        # messages, beside the timed rows that name no sender or no receiver: a row of the side
        # counted may be a copy of one of those (CodeRabbit on #265). Those rows are never
        # counted, and a count of both sides' messages needs no such reading, since its copy
        # already shows the message passed between them.
        between = counted + ([r for r in unplaced if r.ts_utc is not None] if p.sent_by else [])
        no_time = [r for r in rows if r.ts_utc is None]
        if (p.sent_by or p.each_way) and a_ids & b_ids:
            # A message from an account both sides hold is no side's alone (Codex on #172).
            return self.done(
                assumption_id,
                CheckOutcome.INCONCLUSIVE,
                searched,
                sentences(
                    "Cannot count by direction: the two sides share an account, so which side "
                    "sent a message is not known",
                    notes,
                ),
                [],
                sources,
            )
        lines: list[str] = []
        unknown_sender: list[Row] = []
        one_side_silent = False
        each_way_open = False
        if p.sent_by:
            side = _sending_side(p, a, b)
            if side is None:
                return self.done(
                    assumption_id,
                    CheckOutcome.INCONCLUSIVE,
                    searched,
                    sentences("Cannot count: sent_by is not exactly one side", notes),
                    [],
                    sources,
                )
            mine, theirs = (a_ids, b_ids) if side is a else (b_ids, a_ids)
            unknown_sender = [
                r
                for r in pool
                if r.sender is None
                and set(r.recipients) & theirs
                and (r.ts_utc is None or in_window(r.ts_utc, p.window))
            ]
            counted = [r for r in counted if r.sender in mine]
            # Only a row the sending side may have sent can be one of its messages.
            unplaced = [
                r
                for r in unplaced
                if (r.sender is None and (not r.recipients or set(r.recipients) & theirs))
                or r.sender in mine
            ]
            no_time = [r for r in no_time if r.sender in mine]
            searched += f" Only messages {side.describe()} sent."
            if unknown_sender:
                lines.append(
                    f"{len(unknown_sender)} messages to {(b if side is a else a).describe()} "
                    "have no recorded sender, so they may be among them"
                )
        if p.each_way:
            by_a = sum(1 for r in counted if r.sender in a_ids)
            by_b = sum(1 for r in counted if r.sender in b_ids)
            lines.append(f"{a.describe()} sent {by_a} of them and {b.describe()} sent {by_b}")
            one_side_silent = not (by_a and by_b)
            if one_side_silent:
                lines.append("Not finding a message each way does not mean one was never sent")
            elif each_way_rests_on_look_alikes(counted, a_ids, b_ids):
                each_way_open = True
                lines.append(
                    "A message each way rests on rows that repeat another's words and time, "
                    "which may be one message; an expert must decide which rows are the same "
                    "message"
                )
        n, want, op = len(counted), p.expected_count, p.count_op
        lines.insert(0, f"Counted {n}; the claim says {_OPS[op]} {want}")
        deleted = sum(1 for r in counted if r.deleted)
        if deleted:
            lines.append(f"{deleted} of them carry the source's deletion flag")
        if no_time:
            lines.append(f"{len(no_time)} matching messages have no usable time")
        named_already = {r.id for r in unknown_sender}
        extra = [r for r in unplaced if r.id not in named_already]
        if extra:
            lines.append(
                f"{len(extra)} messages name no sender or no receiver, so they may be among "
                f"them: {', '.join(r.id for r in extra)}"
            )
        full = source.fidelity is Fidelity.FULL_EXTRACTION
        if not full:
            lines.append(f"{source_id} is a curated report, so it may omit messages")
        # "At most" and "exactly" need every record on the apps counted (CodeRabbit on #264).
        unread = apps_not_read(data, source_id, {c.strip().lower() for c in p.channels})
        if unread and op != "ge":
            lines.append(unread)

        copies = sum(1 for r in counted + no_time if r.id in data.numbered_copies)
        if copies:
            lines.append(
                f"{copies} of the matching messages {'is' if copies == 1 else 'are'} listed "
                "by the import as a possible copy of another row (numbered as a copy by the "
                "extraction tool, or with the same direction, time and text as another) or as "
                "possibly several messages joined, so the count may hold one message twice or "
                "several as one; an expert must decide which rows are which messages"
            )
        # A row of the side counted may be a copy of the other side's message (CodeRabbit on
        # #265), so the fewest is read over both sides' rows; with no side chosen it is the
        # rows less their look-alikes (`look_alike`).
        groups = look_alike_groups(between)
        twins = n - fewest_messages(counted, between, groups)
        # the other side's rows that make one side's rows look-alikes, cited when they hold the
        # count open (CodeRabbit on #265)
        mine_ids = {r.id for r in counted}
        peers = [
            r for g in groups if any(x.id in mine_ids for x in g) for r in g if r.id not in mine_ids
        ]
        # 1.3.0 (v5 failure hunt, 2026-11-16): a UFDR can hold one message twice with no copy
        # number, a live row and a recovered one or the SMS store and Google Messages (Android
        # 13: 12 TikTok messages stored as 17 rows), so "exactly 12" would fail. The messages
        # number between n - twins and n; the count is held open only when that range spans
        # the claim (Claude review on #265: "at least 5" over 10 rows, 2 of them look-alikes,
        # still holds).
        lo = n - twins
        twins_open = look_alikes_matter(n, twins, want, op)
        if twins:
            lines.append(
                f"{twins} of the counted messages repeat another one's words and time "
                f"(within {TWIN_S} seconds), so the count may hold one message twice"
                + (
                    " or the other side's message"
                    if p.sent_by and twins > look_alike(counted)
                    else ""
                )
                + (
                    "; an expert must decide which rows are the same message"
                    if twins_open
                    else f", and {lo} to {n} messages all give the same count answer"
                )
            )

        if copies or twins_open:
            outcome = CheckOutcome.INCONCLUSIVE
        elif op in ("eq", "le") and lo > want:
            outcome = CheckOutcome.FAIL
        elif (
            no_time
            or one_side_silent
            or each_way_open
            or ((unknown_sender or unplaced or unread) and op != "ge")
        ):
            outcome = CheckOutcome.INCONCLUSIVE
        elif op == "eq":
            outcome = CheckOutcome.PASS if n == want else CheckOutcome.INCONCLUSIVE
        elif op == "ge":
            outcome = CheckOutcome.PASS if n >= want else CheckOutcome.INCONCLUSIVE
        else:
            outcome = CheckOutcome.PASS if full else CheckOutcome.INCONCLUSIVE
        if outcome is CheckOutcome.INCONCLUSIVE and n < want:
            lines.append("Finding fewer than claimed does not mean the others never existed")
        # The outcome rests on the rows that may be among them too (CodeRabbit on #264).
        # ...but not when too many were counted: that FAIL rests on the counted rows alone.
        held_open = outcome is CheckOutcome.INCONCLUSIVE and (unplaced or unknown_sender)
        held_open = held_open and op != "ge"
        ids = [r.id for r in counted + no_time + ((unknown_sender + unplaced) if held_open else [])]
        if twins_open:
            ids += [r.id for r in peers]
        return self.done(
            assumption_id,
            outcome,
            searched,
            sentences(lines, notes),
            list(dict.fromkeys(ids)),
            [source_id],
        )

    def _calls(self, assumption_id: str, p: AssumptionParams, data: CaseData) -> CheckResult:
        if p.window is None or p.expected_count is None or p.count_op is None:
            raise ValueError("the count check needs a window, expected_count and count_op")
        if p.sent_by or p.each_way:
            raise ValueError("a count of calls reads no direction (sent_by, each_way)")
        sources = data.sources_for(p.device_ids)
        a, b = parties(data, p)
        a_ids, b_ids = data.account_ids(a.keys), data.account_ids(b.keys)
        apps = {c.strip().lower() for c in p.channels} - {CALL_CHANNEL}
        on = ", ".join(sorted(apps)) if apps else "every app"
        searched = (
            f"Calls on {on} between {a.describe()} and {b.describe()} on "
            f"{', '.join(p.device_ids)} ({', '.join(sources) or 'no source'}); window "
            f"{window_str(p.window)}."
        )
        notes = a.notes + b.notes + zone_notes(data, p.window, sources)
        if len(sources) != 1 or not a_ids or not b_ids:
            why = (
                "the device is in no single evidence source"
                if len(sources) != 1
                else "a party has no accounts in the data"
            )
            return self.done(
                assumption_id,
                CheckOutcome.INCONCLUSIVE,
                searched,
                sentences(f"Cannot count: {why}", notes),
                [],
                sources,
            )
        (source_id,) = sources
        pool = [
            r
            for r in calls_for_accounts(data, a_ids | b_ids)
            if r.source_id == source_id and (not apps or r.app.strip().lower() in apps)
        ]
        rows = [r for r in pool if involves_all(r, [a_ids, b_ids])]
        # A call with a party on it that names no other side (LEAPP names the other side of a
        # phone's call but not the phone's own line) may be a call between them.
        unplaced = [
            r
            for r in pool
            if incomplete(r)
            and may_be_between(r, a_ids, b_ids)
            and (r.ts_utc is None or in_window(r.ts_utc, p.window))
        ]
        counted = [r for r in rows if r.ts_utc is not None and in_window(r.ts_utc, p.window)]
        no_time = [r for r in rows if r.ts_utc is None]
        n, want, op = len(counted), p.expected_count, p.count_op
        lines = [f"Counted {n} calls; the claim says {_OPS[op]} {want}"]
        twins = _possible_twins(counted)
        if twins:
            pairs = "; ".join(f"{x} and {y}" for x, y in twins)
            lines.append(
                f"{len(twins)} pairs of counted calls are within {DUPLICATE_S} seconds of each "
                f"other ({pairs}), so the count may hold one call twice; an expert must decide "
                "which rows are the same call"
            )
        if no_time:
            lines.append(f"{len(no_time)} matching calls have no usable time")
        if unplaced:
            lines.append(
                f"{len(unplaced)} calls with a party on them name no other side, so they may "
                f"be among them: {', '.join(r.id for r in unplaced)}"
            )
        # A row with no length, or a zero length, may be a call that never connected, so it
        # cannot count toward "spoke N times".
        unconnected = sum(1 for r in counted if not r.duration_s)
        if unconnected:
            lines.append(
                f"{unconnected} counted calls have no length or a zero length, so they may not "
                "have connected"
            )
        deleted = sum(1 for r in counted if r.deleted)
        if deleted:
            lines.append(f"{deleted} of them carry the source's deletion flag")
        full = data.sources[source_id].fidelity is Fidelity.FULL_EXTRACTION
        if not full:
            lines.append(f"{source_id} is a curated report, so it may omit calls")
        unread = apps_not_read(data, source_id, apps)
        if unread and op != "ge":
            lines.append(unread)
        if twins or no_time or unconnected or ((unplaced or unread) and op != "ge"):
            outcome = CheckOutcome.INCONCLUSIVE
        elif op == "eq":
            outcome = CheckOutcome.PASS if n == want else CheckOutcome.INCONCLUSIVE
        elif op == "ge":
            outcome = CheckOutcome.PASS if n >= want else CheckOutcome.INCONCLUSIVE
        else:
            outcome = CheckOutcome.PASS if full and n <= want else CheckOutcome.INCONCLUSIVE
        if outcome is CheckOutcome.INCONCLUSIVE:
            lines.append(
                "A call count never fails: the log keeps calls that did not connect, and one call"
                " can be stored twice"
            )
        held_open = outcome is CheckOutcome.INCONCLUSIVE and unplaced and op != "ge"
        ids = [r.id for r in counted + no_time + (unplaced if held_open else [])]
        return self.done(
            assumption_id,
            outcome,
            searched,
            sentences(lines, notes),
            list(dict.fromkeys(ids)),
            [source_id],
        )


DUPLICATE_S = 60  # two rows of one call from two databases fall seconds apart


def _sending_side(p: AssumptionParams, a: Party, b: Party) -> Party | None:
    """The one party `sent_by` names, in `parties` order (each person, then the accounts
    together): one person, or exactly the accounts; else None."""
    order = [*p.person_ids, *(["accounts"] if p.account_ids or p.handles else [])]
    if len(p.sent_by) == 1 and p.sent_by[0] in p.person_ids:
        at = order.index(p.sent_by[0])
    elif set(p.sent_by) == set(p.account_ids) and not set(p.sent_by) & set(p.person_ids):
        at = order.index("accounts")
    else:
        return None
    return (a, b)[at] if at < 2 else None


def _possible_twins(rows: list[Row]) -> list[tuple[str, str]]:
    """Pairs of counted calls (all between the same two parties) DUPLICATE_S seconds apart or
    less."""
    timed = sorted((r.ts_utc, r.id) for r in rows if r.ts_utc is not None)
    out = []
    for i, (tx, x) in enumerate(timed):
        j = i + 1  # by index, so a sparse log is one pass, not a copy per call (Codex on #169)
        while j < len(timed) and (timed[j][0] - tx).total_seconds() <= DUPLICATE_S:
            out.append((x, timed[j][1]))
            j += 1
    return out
