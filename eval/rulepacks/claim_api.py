"""What a claim over the synthetic carrier records looks like, and helpers to write one.

Shared by every claim set: the reference claims (carrier_claims.py) and the blind trap set a
separate session writes (claims_blind.py, DRAFTING.md). A set is a tuple of GoldClaim.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core.audit.assumptions import local_window
from core.contracts import ClaimType, TimeWindow, Verdict
from eval.rulepacks.reader import P1, SUBJECT_2_LINE, SUBJECT_3_LINE

ET = "America/New_York"
A2, A3 = f"a:cdr:{SUBJECT_2_LINE}", f"a:cdr:{SUBJECT_3_LINE}"


def window(start: datetime, end: datetime, raw: str) -> TimeWindow:
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


def call(
    caller: str, callee: str, window: TimeWindow, duration: tuple[int, int] | None = None
) -> tuple[tuple[str, dict[str, Any]], ...]:
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
