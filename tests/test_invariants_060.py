"""core/audit/invariants.py on a checked SUPPORTED under rules 0.6.0: only rule 3d's labels may
stay open. SYNTHETIC."""

from __future__ import annotations

import pytest

from core import contracts as c
from core.audit.invariants import InvariantViolation, _check_open_labels_on_checked
from core.contracts import AssumptionKind as K
from core.contracts import EvidenceStatus as S
from core.contracts import Stance
from tests.contract.test_rules import asm, claim_of, ev
from tests.contract.test_rules_050 import chk

SENDER = asm(3, K.IDENTITY, template="sender")
TIME = asm(1, K.TIME)
COMMUNICATION = claim_of(c.ClaimType.COMMUNICATION)
CHECKS = [chk(SENDER, name="sender"), chk(TIME)]


def test_an_open_label_on_a_checked_time_passes():
    _check_open_labels_on_checked(
        COMMUNICATION, [SENDER, TIME], [ev(2, TIME, Stance.COMPLICATES, S.OPEN)], CHECKS
    )


@pytest.mark.parametrize(
    ("item", "assumptions", "checks"),
    [
        (ev(2, TIME, Stance.COMPLICATES, S.AI_ACCEPTED), [SENDER, TIME], CHECKS),
        (ev(2, TIME, Stance.COMPLICATES, S.ACCEPTED), [SENDER, TIME], CHECKS),
        (ev(2, SENDER, Stance.COMPLICATES, S.OPEN), [SENDER, TIME], CHECKS),
        (ev(2, TIME, Stance.COMPLICATES, S.OPEN), [TIME], [chk(TIME)]),
        (
            ev(2, TIME, Stance.COMPLICATES, S.OPEN),
            [SENDER, TIME],
            [CHECKS[0], chk(TIME, records=())],
        ),
        (ev(2, TIME, Stance.CONTRADICTS, S.OPEN), [SENDER, TIME], CHECKS),
    ],
    ids=[
        "ai-accepted",
        "expert-accepted",
        "on-identity",
        "no-identity",
        "no-records",
        "contradicts",
    ],
)
def test_anything_else_left_open_fails_the_run(item, assumptions, checks):
    with pytest.raises(InvariantViolation):
        _check_open_labels_on_checked(COMMUNICATION, assumptions, [item], checks)


def test_a_dismissed_label_is_not_open():
    dismissed = ev(2, SENDER, Stance.COMPLICATES, S.DISMISSED)
    _check_open_labels_on_checked(COMMUNICATION, [SENDER, TIME], [dismissed], CHECKS)
