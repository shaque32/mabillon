"""Rules 0.6.0 (proposed): rule 3d', a time the check computed is not left open by a model's
"complicates" label when the claim rests on code checks."""

from __future__ import annotations

import pytest

from core.audit import rules
from core.contracts import AssumptionKind as K
from core.contracts import CheckOutcome as O
from core.contracts import EvidenceStatus as S
from core.contracts import Stance, SupportedBasis, Verdict
from tests.contract.test_rules import asm, decide, ev
from tests.contract.test_rules_050 import COMMUNICATION, SENDER, TIME, TIMING, chk


def test_version_0_6_0():
    assert rules.RULE_VERSION == "0.6.0"


@pytest.mark.parametrize("status", [S.OPEN, S.AI_ACCEPTED])
def test_a_complicates_label_on_a_checked_time_no_longer_blocks(status):
    flag = ev(2, TIME, Stance.COMPLICATES, status)
    d = decide([SENDER, TIME], [flag], [chk(SENDER, name="sender"), chk(TIME)], claim=COMMUNICATION)
    assert d.verdict is Verdict.SUPPORTED
    assert d.supported_basis is SupportedBasis.CHECKED
    assert d.cited_evidence_ids == ()  # the label is listed, never cited as support
    assert any(r.startswith("Rule 3d':") and flag.record_id in r for r in d.reasons)


def test_a_complicates_label_on_identity_still_blocks():
    flag = ev(2, SENDER, Stance.COMPLICATES, S.OPEN)
    d = decide([SENDER, TIME], [flag], [chk(SENDER, name="sender"), chk(TIME)], claim=COMMUNICATION)
    assert d.verdict is Verdict.UNPROVEN
    assert any(r.startswith("Rule 3d:") for r in d.reasons)


def test_a_complicates_label_on_a_non_core_time_still_blocks():
    side = asm(6, K.TIME, core=False)
    flag = ev(2, side, Stance.COMPLICATES, S.OPEN)
    d = decide([TIME, side], [flag], [chk(TIME), chk(side)], claim=TIMING)
    assert d.verdict is Verdict.UNPROVEN


def test_a_time_whose_check_names_no_records_still_blocks():
    flag = ev(2, TIME, Stance.COMPLICATES, S.OPEN)
    d = decide(
        [SENDER, TIME],
        [flag],
        [chk(SENDER, name="sender"), chk(TIME), chk(TIME, name="time2", records=())],
        claim=COMMUNICATION,
    )
    assert d.verdict is Verdict.UNPROVEN


def test_an_inconclusive_time_check_still_blocks():
    flag = ev(2, TIME, Stance.COMPLICATES, S.OPEN)
    d = decide(
        [SENDER, TIME],
        [flag],
        [chk(SENDER, name="sender"), chk(TIME), chk(TIME, O.INCONCLUSIVE, name="time2")],
        claim=COMMUNICATION,
    )
    assert d.verdict is Verdict.UNPROVEN


def test_an_unconfirmed_contradicts_on_a_checked_time_still_blocks():
    against = ev(2, TIME, Stance.CONTRADICTS, S.OPEN)
    d = decide([TIME], [against], [chk(TIME)], claim=TIMING)
    assert d.verdict is Verdict.UNPROVEN


def test_claims_checks_cannot_carry_keep_the_old_rule():
    """No rule 3c' (an event assumption has no check): the label blocks as under 0.5.0."""
    event = asm(2)
    flag = ev(3, TIME, Stance.COMPLICATES, S.OPEN)
    d = decide([TIME, event], [ev(1, event, status=S.ACCEPTED), flag], [chk(TIME)], claim=TIMING)
    assert d.verdict is Verdict.UNPROVEN
