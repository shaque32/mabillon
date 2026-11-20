"""Blind trap set for the carrier call detail record pack (DRAFTING.md, trap writer, round 1).

Written without seeing any pack, the reference claims or the harness. Every claim is about
SUBJECT-1's line (the TARGET LINE, 555-010-0201) and states its times in US Eastern, as an
affidavit would. The events behind each claim are the hand-placed ones in carrier.py:

    e1  Mar 4 2:14:40 a.m. EST   0377 -> TARGET   voice      46 s
    e2  Mar 4 2:31:02 a.m. EST   TARGET -> 0377   sms         0 s  (not a call)
    e3  Mar 4 8:30 p.m. EST      TARGET -> 0377   voice     120 s  (Carrier A prints Mar 5)
    e4  Mar 4 9:10 p.m. EST      TARGET -> 0377   voicemail  25 s  (a voicemail session)
    e5  Mar 5 10:00 p.m. EST     0444 -> TARGET   forwarded  60 s  (forwarded onward)
    e6  Mar 9 7:45 p.m. EDT      TARGET -> 0444   voice     300 s  (after DST began Mar 8)

SUBJECT-2 is tied to 0377 by a confirmed link; SUBJECT-3 is only the listed subscriber of
0444 (a proposed link), so a claim about SUBJECT-3 names a person the records do not tie to a
number. Background calls use numbers no claim names and fall on other days.

Each `expected` is the trap writer's judgment of what a correct, cautious audit returns under
core/audit/rules.py 0.5.0, not human gold: an examiner reviews each one before signing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from core.contracts import ClaimType, Verdict
from eval.rulepacks.claim_api import A3, GoldClaim, call, window
from eval.rulepacks.reader import LINE_DEVICE, P1, P2, P3


def _d(mo: int, d: int, h: int = 0, mi: int = 0) -> datetime:
    """Wall-clock time in 2026; the zone (US Eastern) is given by claim_api.window."""
    return datetime(2026, mo, d, h, mi)


def _calls_count(
    other: dict[str, Any], start: datetime, end: datetime, raw: str, n: int
) -> tuple[tuple[str, dict[str, Any]], ...]:
    """'at least n calls between SUBJECT-1 and the other side' on the TARGET LINE."""
    params: dict[str, Any] = {
        "channels": ["call"],
        "device_ids": [LINE_DEVICE],
        "window": window(start, end, raw),
        "expected_count": n,
        "count_op": "ge",
    }
    return (("message_count", {**params, **other}),)


S, U, C = Verdict.SUPPORTED, Verdict.UNPROVEN, Verdict.CONTRADICTED
COMM, TIMING, COUNT = ClaimType.COMMUNICATION, ClaimType.TIMING, ClaimType.COUNT

BLIND_CLAIMS: tuple[GoldClaim, ...] = (
    # ------------------------------------------------------------ traps: zone and DST
    GoldClaim(
        "b-zone-a-date",
        "On March 5, 2026, SUBJECT-1 placed a call of about two minutes to SUBJECT-2.",
        TIMING,
        call(P1, P2, window(_d(3, 5), _d(3, 6), "March 5, 2026"), (100, 140)),
        U,
        True,
        "Carrier A prints e3 as 2026-03-05 01:30 UTC; in Eastern it is March 4, 8:30 p.m. "
        "Reading the UTC date as the local date puts it on March 5.",
    ),
    GoldClaim(
        "b-zone-a-hour",
        "At about 7:15 a.m. on March 4, 2026, SUBJECT-2 called SUBJECT-1.",
        TIMING,
        call(P2, P1, window(_d(3, 4, 7, 10), _d(3, 4, 7, 20), "about 7:15 a.m. on March 4")),
        U,
        True,
        "Carrier A prints e1 at 07:14:40 UTC (2:14 a.m. Eastern). Reading the UTC clock as "
        "Eastern puts it at 7:14 a.m.",
    ),
    GoldClaim(
        "b-zone-b-as-eastern",
        "At about 1:14 a.m. on March 4, 2026, SUBJECT-2 called SUBJECT-1.",
        TIMING,
        call(P2, P1, window(_d(3, 4, 1, 10), _d(3, 4, 1, 20), "about 1:14 a.m. on March 4")),
        U,
        True,
        "Carrier B prints e1 at 01:14:40 Central (2:14 a.m. Eastern). Reading the CT column "
        "as Eastern puts it an hour early.",
    ),
    GoldClaim(
        "b-zone-a-as-central",
        "At about 2:30 a.m. on March 5, 2026, SUBJECT-1 called SUBJECT-2 for about two minutes.",
        TIMING,
        call(
            P1,
            P2,
            window(_d(3, 5, 2, 25), _d(3, 5, 2, 35), "about 2:30 a.m. on March 5"),
            (100, 140),
        ),
        U,
        True,
        "Carrier A prints e3 at 2026-03-05 01:30 UTC. Applying Carrier B's Central zone to "
        "Carrier A's file puts it at 2:30 a.m. Eastern on March 5; it was 8:30 p.m. March 4.",
    ),
    GoldClaim(
        "b-zone-b-as-utc",
        "At about 8:15 p.m. on March 3, 2026, SUBJECT-2 called SUBJECT-1.",
        TIMING,
        call(P2, P1, window(_d(3, 3, 20, 10), _d(3, 3, 20, 20), "about 8:15 p.m. on March 3")),
        U,
        True,
        "Carrier B prints e1 as 03/04/2026 01:14:40 CT. Applying Carrier A's UTC zone to "
        "Carrier B's file puts it at 8:14 p.m. Eastern on March 3; it was 2:14 a.m. March 4.",
    ),
    GoldClaim(
        "b-dst-standard-time",
        "At about 6:45 p.m. on March 9, 2026, SUBJECT-1 placed a call of about five minutes "
        "to 555-010-0444.",
        TIMING,
        call(
            P1,
            A3,
            window(_d(3, 9, 18, 40), _d(3, 9, 18, 50), "about 6:45 p.m. on March 9"),
            (270, 330),
        ),
        U,
        True,
        "e6 is 23:45 UTC on March 9, after daylight saving time began on March 8: 7:45 p.m. "
        "EDT. Subtracting five hours (EST) or reading Carrier B's 18:45 CT as Eastern gives "
        "6:45 p.m.",
    ),
    GoldClaim(
        "b-dst-fixed-central",
        "At about 8:45 p.m. on March 9, 2026, SUBJECT-1 placed a call of about five minutes "
        "to 555-010-0444.",
        TIMING,
        call(
            P1,
            A3,
            window(_d(3, 9, 20, 40), _d(3, 9, 20, 50), "about 8:45 p.m. on March 9"),
            (270, 330),
        ),
        U,
        True,
        "Carrier B prints e6 at 18:45 CDT. Reading Central as standard time all year "
        "(UTC-6) puts it at 00:45 UTC, 8:45 p.m. Eastern; it was 7:45 p.m.",
    ),
    # ------------------------------------------------------------ traps: codes and record types
    GoldClaim(
        "b-direction-flip",
        "At about 2:14 a.m. on March 4, 2026, SUBJECT-1 called SUBJECT-2.",
        COMM,
        call(P1, P2, window(_d(3, 4, 2, 10), _d(3, 4, 2, 20), "about 2:14 a.m. on March 4")),
        C,
        True,
        "e1 is the only call in the window and is IN/MT: SUBJECT-2's number placed it, so the "
        "caller check fails. A pack that reads the direction (and the party columns) from the "
        "other end shows SUBJECT-1 as the caller.",
    ),
    GoldClaim(
        "b-sms-as-call",
        "At about 2:30 a.m. on March 4, 2026, SUBJECT-1 called SUBJECT-2 back.",
        COMM,
        call(P1, P2, window(_d(3, 4, 2, 25), _d(3, 4, 2, 35), "about 2:30 a.m. on March 4")),
        U,
        True,
        "The only record in the window is e2, an SMS row (Type SMS / Call Type S), which is a "
        "text message event, not a call. A pack that maps the SMS code to a call finds one.",
    ),
    GoldClaim(
        "b-voicemail-as-conversation",
        "At about 9:10 p.m. on March 4, 2026, SUBJECT-1 called SUBJECT-2 and the two spoke for "
        "about 25 seconds.",
        COMM,
        call(
            P1,
            P2,
            window(_d(3, 4, 21, 5), _d(3, 4, 21, 15), "about 9:10 p.m. on March 4"),
            (20, 30),
        ),
        U,
        True,
        "The only 25-second record is e4, a VM row: a call routed to the voicemail platform, "
        "whose duration is the voicemail session. It does not show the two spoke. A pack that "
        "reads VM as an ordinary call, or does not guard it, passes both checks.",
    ),
    GoldClaim(
        "b-forwarded-as-answered",
        "At 10:00 p.m. on March 5, 2026, SUBJECT-1 took a one-minute call from 555-010-0444.",
        COMM,
        call(
            A3,
            P1,
            window(_d(3, 5, 21, 55), _d(3, 5, 22, 5), "10:00 p.m. on March 5"),
            (50, 70),
        ),
        U,
        True,
        "The only record is e5, a CFWD/FW row: the network forwarded the call onward under "
        "the line's forwarding setting, so it does not show SUBJECT-1's line took a "
        "one-minute call. A pack that reads forwarded rows as voice passes both checks.",
    ),
    # ------------------------------------------------------------ traps: counts with wrong rows
    GoldClaim(
        "b-count-includes-voicemail",
        "On March 4, 2026, SUBJECT-1 and SUBJECT-2 spoke by phone at least three times.",
        COUNT,
        _calls_count({"person_ids": [P1, P2]}, _d(3, 4), _d(3, 5), "March 4, 2026", 3),
        U,
        True,
        "March 4 Eastern holds e1 and e3 (voice) and e4 (voicemail); e2 is an SMS. Only two "
        "rows show a conversation; a count that takes the voicemail row as a call reaches 3.",
    ),
    GoldClaim(
        "b-count-includes-forwarded",
        "Between March 5 and March 9, 2026, SUBJECT-1 spoke by phone with 555-010-0444 at "
        "least twice.",
        COUNT,
        _calls_count(
            {"person_ids": [P1], "account_ids": [A3]},
            _d(3, 5),
            _d(3, 10),
            "between March 5 and March 9, 2026",
            2,
        ),
        U,
        True,
        "The window holds e5 (forwarded onward, never reached SUBJECT-1's handset) and e6 "
        "(voice). Only one row shows a conversation; a count that takes the forwarded leg as "
        "a call reaches 2.",
    ),
    # ------------------------------------------------------------ trap: person not tied
    GoldClaim(
        "b-person-not-linked",
        "At about 7:45 p.m. on March 9, 2026, SUBJECT-1 called SUBJECT-3 and spoke for about "
        "five minutes.",
        COMM,
        call(
            P1,
            P3,
            window(_d(3, 9, 19, 40), _d(3, 9, 19, 50), "about 7:45 p.m. on March 9"),
            (270, 330),
        ),
        U,
        True,
        "e6 is a voice call to 0444, but SUBJECT-3 is only the listed subscriber of 0444 (a "
        "proposed link no expert confirmed). The records tie 0444, not SUBJECT-3, to the call.",
    ),
    # ------------------------------------------------------------ true claims
    GoldClaim(
        "b-true-incoming-night",
        "At about 2:14 a.m. on March 4, 2026, SUBJECT-2 called SUBJECT-1.",
        COMM,
        call(P2, P1, window(_d(3, 4, 2, 10), _d(3, 4, 2, 20), "about 2:14 a.m. on March 4")),
        S,
        False,
        "e1, an incoming voice call from SUBJECT-2's confirmed number, read in each file's own "
        "zone (07:14 UTC, 01:14 CT). Lost by a direction or zone misread or a guard on voice.",
    ),
    GoldClaim(
        "b-true-outgoing-date-cross",
        "At about 8:30 p.m. on March 4, 2026, SUBJECT-1 called SUBJECT-2; the call lasted about "
        "two minutes.",
        COMM,
        call(
            P1,
            P2,
            window(_d(3, 4, 20, 25), _d(3, 4, 20, 35), "about 8:30 p.m. on March 4"),
            (100, 140),
        ),
        S,
        False,
        "e3, an outgoing 120-second voice call that Carrier A prints on March 5 (UTC) and "
        "Carrier B on March 4 (CT). Lost by reading Carrier A's date as local.",
    ),
    GoldClaim(
        "b-true-after-dst",
        "At about 7:45 p.m. on March 9, 2026, SUBJECT-1 placed a call of about five minutes to "
        "555-010-0444.",
        TIMING,
        call(
            P1,
            A3,
            window(_d(3, 9, 19, 40), _d(3, 9, 19, 50), "about 7:45 p.m. on March 9"),
            (270, 330),
        ),
        S,
        False,
        "e6, an outgoing 300-second voice call after daylight saving began (23:45 UTC, 18:45 "
        "CDT, 19:45 EDT). Lost by a reading that ignores daylight saving time.",
    ),
    GoldClaim(
        "b-true-voice-count",
        "Between 2 a.m. and 9 p.m. on March 4, 2026, SUBJECT-1 and SUBJECT-2 had at least two "
        "phone calls.",
        COUNT,
        _calls_count(
            {"person_ids": [P1, P2]},
            _d(3, 4, 2),
            _d(3, 4, 21),
            "between 2 a.m. and 9 p.m. on March 4, 2026",
            2,
        ),
        S,
        False,
        "e1 and e3, two voice calls with lengths, both directions; the SMS e2 is not counted "
        "and the voicemail e4 (9:10 p.m.) falls outside. A pack that drops or guards voice "
        "rows, or misreads a zone, loses it.",
    ),
)
