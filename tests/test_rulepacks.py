"""Rule packs and the trap harness (eval/rulepacks/). Every value is invented."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from core.contracts import CheckOutcome, CheckResult
from eval.rulepacks import carrier, harness
from eval.rulepacks.carrier_claims import CLAIMS
from eval.rulepacks.pack import Guard, RulePack, Signature, load

REFERENCE = Path(__file__).parent.parent / "eval/rulepacks/packs/carrier-cdr-reference.json"


@pytest.fixture(scope="module")
def pack() -> RulePack:
    return load(REFERENCE)


@pytest.fixture(scope="module")
def report(pack: RulePack) -> harness.Report:
    return harness.evaluate(pack)


def test_the_reference_pack_passes_with_zero_false_supported(report: harness.Report) -> None:
    assert report.passed, report
    assert report.false_supported == [] and report.wrong == []
    assert set(report.layouts) == {"carrier-a", "carrier-b"}
    for rows in report.layouts.values():
        assert len(rows) == len(CLAIMS) and all(r["expected"] == r["got"] for r in rows)


def test_each_guard_blocks_the_traps_it_names(report: harness.Report) -> None:
    assert report.rule_kill == {
        "voicemail-leg": ["t-count-voicemail", "t-voicemail"],
        "forwarded-leg": ["t-forwarded"],
    }
    assert report.unearned_guards == [] and report.unblocked_named_traps == []


def test_a_zone_mistake_shows_as_a_false_supported_trap(report: harness.Report) -> None:
    s = report.trap_strength
    assert s["carrier-a: zone read as America/New_York"]["false_supported"] == ["t-zone-utc"]
    assert s["carrier-b: zone read as America/New_York"]["false_supported"] == ["t-zone-central"]
    assert report.gaps == []  # every layout mistake changes some verdict


def test_a_pack_missing_a_guard_is_dropped(pack: RulePack) -> None:
    rep = harness.evaluate(pack.without_guard("voicemail-leg"))
    assert not rep.passed
    assert {"carrier-a:t-voicemail", "carrier-b:t-count-voicemail"} <= set(rep.false_supported)


def test_a_guard_that_blocks_nothing_is_dropped(pack: RulePack) -> None:
    idle = Guard(
        id="sms-row",
        text="An sms row is not a call, so no call check may rest on it.",
        record_types=("sms",),
        blocks=("t-voicemail",),
    )
    rep = harness.evaluate(pack.model_copy(update={"guards": (*pack.guards, idle)}))
    assert not rep.passed
    assert rep.unearned_guards == ["sms-row"] and "sms-row:t-voicemail" in rep.unblocked_named_traps


def test_a_zone_the_header_does_not_state_is_refused(pack: RulePack) -> None:
    body = pack.model_dump(mode="json")
    body["layouts"][1]["zone"] = "America/New_York"  # header says (CT)
    with pytest.raises(ValidationError, match="does not mean"):
        RulePack.model_validate(body)
    body["layouts"][1]["zone"] = "America/Chicago"
    body["layouts"][1]["zone_evidence"] = "(XT)"
    with pytest.raises(ValidationError, match="zone_evidence"):
        RulePack.model_validate(body)


def test_unknown_templates_and_unsigned_signed_packs_are_refused(pack: RulePack) -> None:
    body = pack.model_dump(mode="json")
    with pytest.raises(ValidationError, match="unknown template"):
        RulePack.model_validate({**body, "templates": ["caller", "made_up"]})
    with pytest.raises(ValidationError, match="examiner's and the owner's"):
        RulePack.model_validate({**body, "status": "signed"})
    stale = Signature(role="examiner", name="x", signed_at_utc="2026-11-15", pack_sha256="0" * 64)
    owner = stale.model_copy(update={"role": "owner"})
    with pytest.raises(ValidationError, match="another version"):
        RulePack.model_validate({**body, "status": "signed", "signatures": [
            stale.model_dump(), owner.model_dump()]})  # fmt: skip


def test_the_hash_ignores_signatures_and_status_but_not_content(pack: RulePack) -> None:
    h = pack.sha256()
    sigs = tuple(
        Signature(role=r, name="x", signed_at_utc="2026-11-15", pack_sha256=h)
        for r in ("examiner", "owner")
    )
    signed = RulePack.model_validate(
        {**pack.model_dump(mode="json"), "status": "signed",
         "signatures": [s.model_dump() for s in sigs]}
    )  # fmt: skip
    assert signed.sha256() == h
    assert pack.without_guard("forwarded-leg").sha256() != h


def test_the_reader_refuses_another_layouts_file(pack: RulePack) -> None:
    with pytest.raises(ValueError, match="header row"):
        carrier.read(carrier.render("carrier-b"), pack.layout("carrier-a"))


def test_the_generator_is_deterministic_and_keeps_raw_times(pack: RulePack) -> None:
    assert carrier.render("carrier-a") == carrier.render("carrier-a")
    loaded = carrier.load_case(pack, "carrier-b")
    row = loaded.conn.execute(
        "SELECT ts_utc, ts_offset_min, ts_raw, locator FROM calls WHERE ts_utc = ?",
        ("2026-03-09T23:45:00Z",),
    ).fetchone()
    assert row == ("2026-03-09T23:45:00Z", -300, "03/09/2026 18:45:00", row[3])
    assert row[3].startswith("carrier-b.csv:row ")
    assert loaded.coverage["skipped"]["sms"] > 0  # carrier sms rows are counted, not read


def test_a_guard_only_ever_turns_a_result_inconclusive() -> None:
    g = (Guard(id="vm", text="voicemail is not a talk", record_types=("voicemail",),
               blocks=("t",)),)  # fmt: skip
    types = {"r1": "voicemail", "r2": "voice"}
    for outcome in CheckOutcome:
        for rids in [("r1",), ("r2",), ("r1", "r2"), ()]:
            r = CheckResult(
                id="c", assumption_id="a", check_name="caller", check_version="1",
                outcome=outcome, searched="s", record_ids=rids, detail="d",
            )  # fmt: skip
            out = harness.guarded(r, g, types).outcome
            assert out in {outcome, CheckOutcome.INCONCLUSIVE}
            if "r1" in rids:
                assert out is CheckOutcome.INCONCLUSIVE


def test_a_guard_naming_an_unknown_trap_is_dropped(pack: RulePack) -> None:
    # Greptile on #260: a misspelled trap name must not let the guard skip its test.
    g = pack.guards[0].model_copy(update={"blocks": ("t-voicemial",)})
    rep = harness.evaluate(pack.model_copy(update={"guards": (g, *pack.guards[1:])}))
    assert not rep.passed and rep.unknown_traps == ["voicemail-leg:t-voicemial"]


def test_a_layout_mistake_lists_only_claims_it_changes(pack: RulePack) -> None:
    # Greptile on #260: compare with the pack's own result, not the gold. Without the
    # voicemail guard, t-count-voicemail is already supported, and the count check reads no
    # direction, so a flipped direction map does not change it.
    rep = harness.evaluate(pack.without_guard("voicemail-leg"))
    flipped = rep.trap_strength["carrier-a: direction map flipped"]
    assert "t-count-voicemail" not in flipped["changed"]
    assert "t-count-voicemail" in flipped["false_supported"]


def test_a_zone_word_followed_by_an_offset_is_refused(pack: RulePack) -> None:
    # CodeRabbit on #260: "Time (UTC-05:00)" states an offset, so it is not evidence of UTC.
    body = pack.model_dump(mode="json")
    lay = body["layouts"][0]
    lay["headers"] = [("Time (UTC-05:00)" if h == "Time (UTC)" else h) for h in lay["headers"]]
    lay["time_col"] = "Time (UTC-05:00)"
    with pytest.raises(ValidationError, match="zone_evidence"):
        RulePack.model_validate(body)


def test_a_pack_must_read_every_synthetic_layout_and_no_other(pack: RulePack) -> None:
    # CodeRabbit on #260: a pack with one layout must not pass untested on the other.
    one = pack.model_copy(update={"layouts": pack.layouts[:1]})
    rep = harness.evaluate(one)
    assert not rep.passed and rep.layout_errors == ["missing:carrier-b"]
    extra = pack.layouts[1].model_copy(update={"id": "carrier-c"})
    rep = harness.evaluate(pack.model_copy(update={"layouts": (*pack.layouts, extra)}))
    assert not rep.passed and rep.layout_errors == ["unknown:carrier-c"]
