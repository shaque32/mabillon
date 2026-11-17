"""Gold claims for the synthetic carrier records: true claims and traps.

Each claim is written as the government might write it, with the assumptions a reviewer
would fill and the verdict a correct, cautious audit returns. Times are US Eastern, as the
mock affidavit states them. A trap is a claim the records do not support that a wrong pack
(a wrong time zone, a flipped direction map, a missing guard) would mark SUPPORTED.

These are reference traps for testing the harness itself. A pack's own trap set is written
by a separate session that never sees the draft pack (baker/plans/rule-drafting.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core.audit.assumptions import local_window
from core.contracts import ClaimType, Verdict
from eval.rulepacks.carrier import LINE_DEVICE, P1, P3, SUBJECT_2_LINE, SUBJECT_3_LINE

ET = "America/New_York"
A2, A3 = f"a:cdr:{SUBJECT_2_LINE}", f"a:cdr:{SUBJECT_3_LINE}"


def _w(start: datetime, end: datetime, raw: str):
    return local_window(start, end, ET, raw)


@dataclass(frozen=True)
class GoldClaim:
    id: str
    text: str
    claim_type: ClaimType
    assumptions: tuple[tuple[str, dict[str, Any]], ...]
    expected: Verdict
    trap: bool
    tests: str  # what the claim tests, in a few words


def _call(caller: str, callee: str, window, duration=None) -> tuple[tuple[str, dict], ...]:
    """'caller placed a call to callee in window': who placed it, and when. One side is
    SUBJECT-1 (the TARGET LINE's holder); the other is a person or an account id."""
    if P1 not in (caller, callee):
        raise ValueError("one side of a carrier claim is SUBJECT-1")
    other = callee if caller == P1 else caller
    base: dict[str, Any] = {"channels": ["call"], "window": window}
    if duration:
        base["duration_s"] = duration
    parties: dict[str, Any] = {"person_ids": [P1]}
    if other.startswith("person:"):
        parties["person_ids"] = [P1, other]
    else:
        parties["account_ids"] = [other]
    return (
        ("caller", {**base, **parties, "sent_by": [caller]}),
        ("record_time", {**base, **parties}),
    )


MAR4_2AM = _w(datetime(2026, 3, 4, 2, 0), datetime(2026, 3, 4, 2, 30), "about 2:14 a.m. on March 4")
MAR4_830PM = _w(
    datetime(2026, 3, 4, 20, 15), datetime(2026, 3, 4, 20, 45), "about 8:30 p.m. on March 4"
)
MAR4_910PM = _w(
    datetime(2026, 3, 4, 21, 0), datetime(2026, 3, 4, 21, 20), "about 9:10 p.m. on March 4"
)
MAR5_10PM = _w(
    datetime(2026, 3, 5, 21, 45), datetime(2026, 3, 5, 22, 15), "about 10 p.m. on March 5"
)
MAR9_745PM = _w(
    datetime(2026, 3, 9, 19, 30), datetime(2026, 3, 9, 20, 0), "about 7:45 p.m. on March 9"
)
# the e3 call (8:30 p.m. ET) read wrongly: its UTC time as if Eastern, its Central time as Eastern
MAR5_130AM = _w(
    datetime(2026, 3, 5, 1, 0), datetime(2026, 3, 5, 2, 0), "about 1:30 a.m. on March 5"
)
MAR4_730PM = _w(
    datetime(2026, 3, 4, 19, 15), datetime(2026, 3, 4, 19, 45), "about 7:30 p.m. on March 4"
)
MAR3_6 = _w(datetime(2026, 3, 3), datetime(2026, 3, 7), "March 3 to 6")  # fmt: skip

CLAIMS: tuple[GoldClaim, ...] = (
    GoldClaim(
        "g-in-call",
        "At about 2:14 a.m. on March 4, 555-010-0377 called SUBJECT-1.",
        ClaimType.COMMUNICATION,
        _call(A2, P1, MAR4_2AM),
        Verdict.SUPPORTED,
        False,
        "an incoming call read the right way",
    ),
    GoldClaim(
        "g-out-call",
        "At about 8:30 p.m. on March 4, SUBJECT-1 called 555-010-0377 and talked for "
        "about two minutes.",
        ClaimType.COMMUNICATION,
        _call(P1, A2, MAR4_830PM, (100, 140)),
        Verdict.SUPPORTED,
        False,
        "an outgoing call and its length",
    ),
    GoldClaim(
        "g-dst-call",
        "At about 7:45 p.m. on March 9, SUBJECT-1 called 555-010-0444.",
        ClaimType.COMMUNICATION,
        _call(P1, A3, MAR9_745PM),
        Verdict.SUPPORTED,
        False,
        "a call after daylight saving began",
    ),
    GoldClaim(
        "t-direction",
        "At about 2:14 a.m. on March 4, SUBJECT-1 called 555-010-0377.",
        ClaimType.COMMUNICATION,
        _call(P1, A2, MAR4_2AM),
        Verdict.CONTRADICTED,
        True,
        "direction: the record shows the call came in",
    ),
    GoldClaim(
        "t-voicemail",
        "At about 9:10 p.m. on March 4, SUBJECT-1 called 555-010-0377 and they "
        "spoke for about 25 seconds.",
        ClaimType.COMMUNICATION,
        _call(P1, A2, MAR4_910PM, (20, 30)),
        Verdict.UNPROVEN,
        True,
        "a voicemail leg is not a conversation",
    ),
    GoldClaim(
        "t-forwarded",
        "At about 10 p.m. on March 5, 555-010-0444 called SUBJECT-1.",
        ClaimType.COMMUNICATION,
        _call(A3, P1, MAR5_10PM),
        Verdict.UNPROVEN,
        True,
        "a forwarded leg may never have reached the handset",
    ),
    GoldClaim(
        "t-holder",
        "At about 7:45 p.m. on March 9, SUBJECT-1 called SUBJECT-3.",
        ClaimType.COMMUNICATION,
        _call(P1, P3, MAR9_745PM),
        Verdict.UNPROVEN,
        True,
        "the subscriber of a number is not proof of who used it",
    ),
    GoldClaim(
        "t-zone-utc",
        "At about 1:30 a.m. on March 5, SUBJECT-1 called 555-010-0377.",
        ClaimType.COMMUNICATION,
        _call(P1, A2, MAR5_130AM),
        Verdict.UNPROVEN,
        True,
        "a UTC time read as Eastern",
    ),
    GoldClaim(
        "t-zone-central",
        "At about 7:30 p.m. on March 4, SUBJECT-1 called 555-010-0377.",
        ClaimType.COMMUNICATION,
        _call(P1, A2, MAR4_730PM),
        Verdict.UNPROVEN,
        True,
        "a Central time read as Eastern",
    ),
    GoldClaim(
        "t-count-voicemail",
        "Between March 3 and March 6, SUBJECT-1 and 555-010-0377 spoke on "
        "the phone at least three times.",
        ClaimType.COUNT,
        (
            (
                "message_count",
                {
                    "person_ids": [P1],
                    "account_ids": [A2],
                    "device_ids": [LINE_DEVICE],
                    "channels": ["call"],
                    "window": MAR3_6,
                    "expected_count": 3,
                    "count_op": "ge",
                },
            ),
        ),
        Verdict.UNPROVEN,
        True,
        "a voicemail leg counted as a conversation",
    ),  # fmt: skip
)
