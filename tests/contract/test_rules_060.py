"""Rules 0.6.0 (Arsh, 2026-11-21): rule 3d', a time the check computed is not left open by a model's
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


def test_a_complicates_label_on_a_checked_time_no_longer_blocks():
    flag = ev(2, TIME, Stance.COMPLICATES, S.OPEN)
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


@pytest.mark.parametrize("status", [S.AI_ACCEPTED, S.COUNSEL_ACCEPTED, S.ACCEPTED])
def test_a_complicates_label_a_reviewer_accepted_still_blocks(status):
    """CodeRabbit, #275: an accepted "complicates" is a reviewer's doubt, not a model's."""
    accepted = ev(2, TIME, Stance.COMPLICATES, status)
    d = decide(
        [SENDER, TIME], [accepted], [chk(SENDER, name="sender"), chk(TIME)], claim=COMMUNICATION
    )
    assert d.verdict is Verdict.UNPROVEN
    assert any(r.startswith("Rule 3d:") and accepted.record_id in r for r in d.reasons)
    mixed = [ev(3, TIME, Stance.COMPLICATES, S.OPEN), accepted]
    d = decide([SENDER, TIME], mixed, [chk(SENDER, name="sender"), chk(TIME)], claim=COMMUNICATION)
    assert d.verdict is Verdict.UNPROVEN


def test_the_time_label_is_listed_when_another_blocker_remains():
    """CodeRabbit, #275: the exempt label stays in the reasons beside an identity blocker."""
    on_time = ev(2, TIME, Stance.COMPLICATES, S.OPEN)
    on_sender = ev(3, SENDER, Stance.COMPLICATES, S.OPEN)
    d = decide(
        [SENDER, TIME],
        [on_time, on_sender],
        [chk(SENDER, name="sender"), chk(TIME)],
        claim=COMMUNICATION,
    )
    assert d.verdict is Verdict.UNPROVEN
    assert any(r.startswith("Rule 3d':") and on_time.record_id in r for r in d.reasons)
    assert any(r.startswith("Rule 3d:") and on_sender.record_id in r for r in d.reasons)


def test_an_expert_accepted_support_keeps_the_label_blocking():
    """Claude review, #275: with an expert's support the claim would take the confirmed basis,
    which the invariants refuse while a complicating item is open, so 3d' does not apply."""
    flag = ev(2, TIME, Stance.COMPLICATES, S.OPEN)
    support = ev(1, SENDER, status=S.ACCEPTED)
    d = decide(
        [SENDER, TIME],
        [support, flag],
        [chk(SENDER, name="sender"), chk(TIME)],
        claim=COMMUNICATION,
    )
    assert d.verdict is Verdict.UNPROVEN
    assert any(r.startswith("Rule 3d:") and flag.record_id in r for r in d.reasons)


def test_a_claim_without_a_core_identity_assumption_keeps_the_label_blocking():
    """Claude review, #275: a timing claim can rest on its time alone, and the time check does
    not show who wrote the record, so a doubt about the account must still block."""
    flag = ev(2, TIME, Stance.COMPLICATES, S.OPEN)
    d = decide([TIME], [flag], [chk(TIME)], claim=TIMING)
    assert d.verdict is Verdict.UNPROVEN
    assert any(r.startswith("Rule 3d:") and flag.record_id in r for r in d.reasons)


def test_the_label_is_listed_after_the_code_checks_line():
    flag = ev(2, TIME, Stance.COMPLICATES, S.OPEN)
    d = decide([SENDER, TIME], [flag], [chk(SENDER, name="sender"), chk(TIME)], claim=COMMUNICATION)
    order = [r.split(":")[0] for r in d.reasons]
    assert order.index("Rule 3c'") < order.index("Rule 3d'")
