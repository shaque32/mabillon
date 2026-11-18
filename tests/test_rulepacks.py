"""Rule packs and the trap harness (eval/rulepacks/). Every value is invented."""

from __future__ import annotations

import csv
import dataclasses
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from core.contracts import CheckOutcome, CheckResult
from eval.rulepacks import carrier, check_layout, harness, reader
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
    stale = Signature(
        role="examiner", name="x", signed_at_utc="2026-11-15T00:00:00Z", pack_sha256="0" * 64
    )
    owner = stale.model_copy(update={"role": "owner"})
    with pytest.raises(ValidationError, match="another version"):
        RulePack.model_validate({**body, "status": "signed", "signatures": [
            stale.model_dump(mode="json"), owner.model_dump(mode="json")]})  # fmt: skip


def test_the_hash_ignores_signatures_and_status_but_not_content(pack: RulePack) -> None:
    h = pack.sha256()
    sigs = tuple(
        Signature(role=r, name="x", signed_at_utc="2026-11-15T00:00:00Z", pack_sha256=h)
        for r in ("examiner", "owner")
    )
    signed = RulePack.model_validate(
        {**pack.model_dump(mode="json"), "status": "signed",
         "signatures": [s.model_dump(mode="json") for s in sigs]}
    )  # fmt: skip
    assert signed.sha256() == h
    assert pack.without_guard("forwarded-leg").sha256() != h


def test_the_hash_covers_the_traps_each_guard_names(pack: RulePack) -> None:
    draft = RulePack.model_validate(_unnamed(pack))  # guards name no traps
    assert draft.sha256() != pack.sha256()  # writing the found traps in makes a new version
    h = pack.sha256()  # the version the harness runs with its traps named is the one signed
    sigs = [
        Signature(role=r, name="x", signed_at_utc="2026-11-18T00:00:00Z", pack_sha256=h)
        for r in ("examiner", "owner")
    ]
    body = pack.model_dump(mode="json")
    body.update(status="signed", signatures=[s.model_dump(mode="json") for s in sigs])
    assert RulePack.model_validate(body).sha256() == h
    first = {**body["guards"][0], "blocks": ["t-forwarded"]}
    changed = {**body, "guards": [first, *body["guards"][1:]]}
    with pytest.raises(ValidationError, match="another version"):
        RulePack.model_validate(changed)


def test_the_reader_refuses_another_layouts_file(pack: RulePack) -> None:
    with pytest.raises(ValueError, match="header row"):
        reader.read(carrier.render("carrier-b"), pack.layout("carrier-a"))


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


# ---- code review on #260


def test_a_pack_that_guards_too_much_is_dropped(pack: RulePack) -> None:
    # A guard on every call type blocks the traps but also turns true claims unproven.
    blanket = Guard(
        id="every-call",
        text="No call record of any kind may carry a check result.",
        record_types=("voice", "voicemail", "forwarded"),
        blocks=("t-voicemail", "t-forwarded", "t-count-voicemail"),
    )
    rep = harness.evaluate(pack.model_copy(update={"guards": (blanket,)}))
    assert not rep.passed and rep.false_supported == []
    assert {"carrier-a:g-in-call", "carrier-a:t-direction"} <= set(rep.wrong)


@pytest.mark.parametrize("time_col", ["Time (UTC -05:00)", "Time (UTC +1)", "Time UTC-5"])
def test_a_zone_word_with_any_offset_after_it_is_refused(pack: RulePack, time_col: str) -> None:
    body = pack.model_dump(mode="json")
    lay = body["layouts"][0]
    lay["headers"] = [(time_col if h == "Time (UTC)" else h) for h in lay["headers"]]
    lay["time_col"] = time_col
    with pytest.raises(ValidationError, match="zone_evidence"):
        RulePack.model_validate(body)


def test_central_standard_time_is_not_read_as_chicago_time(pack: RulePack) -> None:
    body = pack.model_dump(mode="json")
    lay = body["layouts"][1]
    col = "Call Time (Central Standard Time)"
    lay["headers"] = [(col if h == "Call Time (CT)" else h) for h in lay["headers"]]
    lay["time_col"], lay["zone_evidence"] = col, "Central"
    with pytest.raises(ValidationError, match="zone_evidence"):
        RulePack.model_validate(body)


def _one_row_file(layout_id: str, row: list[str]) -> str:
    head = carrier.render(layout_id).splitlines()[0]
    return head + "\n" + ",".join(row) + "\n"


def test_a_local_time_daylight_saving_repeats_or_skips_keeps_no_utc_time(pack: RulePack) -> None:
    for day, clock in [("11/01/2026", "01:30:00"), ("03/08/2026", "02:30:00")]:
        text = _one_row_file(
            "carrier-b", [day, clock, reader.TARGET, "5550100377", "MO", "60", "V"]
        )
        loaded = reader.read(text, pack.layout("carrier-b"))
        row = loaded.conn.execute("SELECT ts_utc, ts_offset_min, ts_raw FROM calls").fetchone()
        assert row == (None, None, f"{day} {clock}")
        assert loaded.coverage["unsure_times"] == 1


def test_malformed_rows_are_counted_and_a_blank_length_is_not_zero(pack: RulePack) -> None:
    lay = pack.layout("carrier-a")
    good = ["2026-03-04", "07:14:40", "5550100377", reader.TARGET, "IN"]
    text = _one_row_file("carrier-a", [*good, "", "VOICE"])
    text += ",".join(good[:3]) + "\n"  # short row
    text += ",".join([*good, "1:23", "VOICE"]) + "\n"  # not whole seconds
    text += ",".join([*good, "\u00b2", "VOICE"]) + "\n"  # a digit int() refuses (CodeRabbit)
    text += ",".join([*good, "9223372036854775808", "VOICE"]) + "\n"  # overflows SQLite
    text += ",".join([*good, "9" * 5000, "VOICE"]) + "\n"  # past int()'s digit limit
    loaded = reader.read(text, lay)
    assert loaded.conn.execute("SELECT duration_s FROM calls").fetchall() == [(None,)]
    assert loaded.coverage["skipped"]["malformed"] == 5


def test_a_pack_must_list_every_template_its_claims_use(pack: RulePack) -> None:
    rep = harness.evaluate(pack.model_copy(update={"templates": ("record_time",)}))
    assert not rep.passed
    assert "g-in-call:caller" in rep.template_errors
    assert "t-count-voicemail:message_count" in rep.template_errors


def test_a_trap_the_full_pack_lets_through_is_not_credited_to_a_guard(pack: RulePack) -> None:
    # A type map that reads forwarded legs as voice lets t-forwarded through with every guard
    # on, so removing forwarded-leg changes nothing and the guard is unearned.
    body = pack.model_dump(mode="json")
    for lay in body["layouts"]:
        lay["type_values"] = {k: ("voice" if v == "forwarded" else v)
                              for k, v in lay["type_values"].items()}  # fmt: skip
    rep = harness.evaluate(RulePack.model_validate(body))
    assert "carrier-a:t-forwarded" in rep.false_supported
    assert "t-forwarded" not in rep.rule_kill["forwarded-leg"]
    assert "forwarded-leg" in rep.unearned_guards


def test_a_carrier_claim_names_subject_1_and_its_stated_caller() -> None:
    from eval.rulepacks.carrier_claims import A2, A3, MAR4_2AM, call

    caller, _ = call(A2, reader.P1, MAR4_2AM)
    assert caller[1]["sent_by"] == [A2] and caller[1]["account_ids"] == [A2]
    with pytest.raises(ValueError, match="SUBJECT-1"):
        call(A3, A2, MAR4_2AM)


def test_signatures_need_a_name_and_a_time_and_a_changed_copy_is_unsigned(
    pack: RulePack,
) -> None:
    h = pack.sha256()
    with pytest.raises(ValidationError):
        Signature(role="examiner", name="", signed_at_utc="2026-11-15T00:00:00Z", pack_sha256=h)
    with pytest.raises(ValidationError):
        Signature(role="examiner", name="x", signed_at_utc="2026-11-15", pack_sha256=h)
    sigs = [
        Signature(role=r, name="x", signed_at_utc="2026-11-15T00:00:00Z", pack_sha256=h)
        for r in ("examiner", "owner")
    ]
    signed = RulePack.model_validate(
        {**pack.model_dump(mode="json"), "status": "signed",
         "signatures": [s.model_dump(mode="json") for s in sigs]}
    )  # fmt: skip
    copy = signed.without_guard("voicemail-leg")
    assert copy.status == "draft" and copy.signatures == ()


# ---------------------------------------------------------------- drafting (DRAFTING.md)


def test_the_sample_files_a_drafter_sees_are_the_files_the_harness_reads() -> None:
    for lid in carrier.LAYOUTS:
        raw = (check_layout.SAMPLES / f"{lid}.csv").read_bytes()
        assert raw == carrier.render(lid).encode("utf-8")  # byte for byte: no CRLF, no BOM


def test_the_drafters_check_tool_reads_each_sample_and_names_a_missing_one(
    pack: RulePack, tmp_path: Path
) -> None:
    res = check_layout.check(pack)
    assert set(res) == {"carrier-a", "carrier-b"}
    for v in res.values():
        assert v["coverage"]["skipped"]["unmapped_type"] == 0  # type: ignore[index]
        assert v["coverage"]["skipped"]["malformed"] == 0  # type: ignore[index]
    assert check_layout.check(pack, tmp_path)["carrier-a"] == {
        "error": "no sample file carrier-a.csv"
    }


def test_the_drafters_tools_do_not_load_claims_the_generator_or_the_harness() -> None:
    code = (
        "import sys, eval.rulepacks.check_layout\n"
        "bad = [m for m in ('eval.rulepacks.carrier', 'eval.rulepacks.carrier_claims',"
        " 'eval.rulepacks.claim_api', 'eval.rulepacks.claims_blind', 'eval.rulepacks.harness')"
        " if m in sys.modules]\n"
        "print(bad)\n"
    )
    out = subprocess.run(  # noqa: S603 - fixed code, this interpreter
        [sys.executable, "-c", code], capture_output=True, text=True, check=True,
        cwd=Path(__file__).parent.parent,
    )  # fmt: skip
    assert out.stdout.strip() == "[]"


def _unnamed(pack: RulePack, status: str = "draft") -> dict:
    body = pack.model_dump(mode="json")
    body["status"] = status
    body["guards"] = [{**g, "blocks": []} for g in body["guards"]]
    return body


def test_a_drafts_guards_may_name_no_traps_and_the_harness_finds_what_they_block(
    pack: RulePack,
) -> None:
    draft = RulePack.model_validate(_unnamed(pack))
    rep = harness.evaluate(draft)
    assert rep.passed, rep
    assert rep.rule_kill == {
        "voicemail-leg": ["t-count-voicemail", "t-voicemail"],
        "forwarded-leg": ["t-forwarded"],
    }


def test_a_reference_or_signed_packs_guards_must_name_their_traps(pack: RulePack) -> None:
    with pytest.raises(ValidationError, match="names the traps it blocks"):
        RulePack.model_validate(_unnamed(pack, "reference"))


def test_claim_sets_run_together_need_unique_ids_and_a_subset_can_leave_a_guard_unearned(
    pack: RulePack,
) -> None:
    with pytest.raises(ValueError, match="unique"):
        harness.evaluate(pack, CLAIMS + CLAIMS[:1])
    true_only = tuple(c for c in CLAIMS if not c.trap)
    rep = harness.evaluate(pack, true_only)
    assert rep.wrong == [] and set(rep.unearned_guards) == {"voicemail-leg", "forwarded-leg"}
    assert not rep.passed


def test_a_guard_card_says_what_gets_through_without_it(
    pack: RulePack, report: harness.Report
) -> None:
    cards = harness.cards(pack, report)
    assert cards[0].startswith("Guard voicemail-leg (voicemail): A call that went to voicemail")
    assert cards[0].endswith("Without it: t-count-voicemail, t-voicemail")


def test_the_cli_refuses_an_unknown_claim_set() -> None:
    with pytest.raises(SystemExit):
        harness.main([str(REFERENCE), "--claims", "reference,nope"])


DRAFT = REFERENCE.parent / "carrier-cdr-draft.json"


def test_the_ai_drafted_pack_passes_the_reference_and_blind_sets_with_no_named_traps() -> None:
    draft = load(DRAFT)
    assert draft.status == "draft" and draft.drafted_by.startswith("ai:")
    assert all(not g.blocks for g in draft.guards)  # the drafter never saw a trap
    both = harness.claim_set("reference") + harness.claim_set("blind")
    rep = harness.evaluate(draft, both)
    assert rep.passed, rep
    assert rep.false_supported == [] and rep.wrong == [] and rep.unearned_guards == []


def test_the_blind_set_is_independent_of_the_reference_claims() -> None:
    blind = harness.claim_set("blind")
    src = (REFERENCE.parent.parent / "claims_blind.py").read_text()
    assert "carrier_claims" not in src
    assert all(c.id.startswith("b-") for c in blind)
    assert sum(c.trap for c in blind) >= 12 and sum(not c.trap for c in blind) >= 4
    assert harness.evaluate(load(REFERENCE), blind).wrong == []


def test_a_trap_named_from_a_claim_set_left_out_of_the_run_fails_the_gate() -> None:
    ref = load(REFERENCE)
    rep = harness.evaluate(ref, harness.claim_set("blind"))
    named = sorted(f"{g.id}:{t}" for g in ref.guards for t in g.blocks)
    assert not rep.passed and sorted(rep.unknown_traps) == named
    both = harness.evaluate(ref, harness.claim_set("reference") + harness.claim_set("blind"))
    assert both.unknown_traps == [] and both.passed, both


def test_a_guard_naming_a_blind_trap_it_does_not_block_is_dropped_on_a_reference_run(
    pack: RulePack,
) -> None:
    body = pack.model_dump(mode="json")
    body["guards"][0]["blocks"] = [*body["guards"][0]["blocks"], "b-direction-flip"]
    rep = harness.evaluate(RulePack.model_validate(body))  # the default reference-only run
    assert not rep.passed and rep.unknown_traps == [f"{body['guards'][0]['id']}:b-direction-flip"]


def test_the_check_tool_warns_of_rows_with_no_utc_time(pack: RulePack, tmp_path: Path) -> None:
    for lid in carrier.LAYOUTS:
        (tmp_path / f"{lid}.csv").write_text(carrier.render(lid))
    text = carrier.render("carrier-b")  # Central time: 2:30 on 2026-03-08 never happened
    gap = "03/08/2026,02:30:00,5550100201,5550100615,MO,60,V\n"
    (tmp_path / "carrier-b.csv").write_text(text + gap)
    res = check_layout.check(pack, tmp_path)
    assert res["carrier-b"]["warnings"] == [
        "1 rows kept with no UTC time (daylight saving double or gap)"
    ]
    assert res["carrier-a"]["warnings"] == []


def test_json_output_carries_the_cards_when_asked(capsys: pytest.CaptureFixture[str]) -> None:
    assert harness.main([str(REFERENCE), "--json", "--cards"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["cards"][0].startswith("Guard voicemail-leg")


def test_the_check_tool_fails_a_layout_that_reads_no_calls_and_warns_on_skipped_rows(
    pack: RulePack,
) -> None:
    lay, other = pack.layout("carrier-a"), pack.layout("carrier-b")
    none = lay.model_copy(update={"type_values": {"Voice": "voice"}})
    res = check_layout.check(pack.model_copy(update={"layouts": (none, other)}))
    assert res["carrier-a"]["error"] == "no row read as a call"
    no_vm = lay.model_copy(
        update={"type_values": {k: v for k, v in lay.type_values.items() if k != "VM"}}
    )
    res = check_layout.check(pack.model_copy(update={"layouts": (no_vm, other)}))
    assert res["carrier-a"]["warnings"] and res["carrier-a"]["warnings"][0].endswith(
        "rows skipped as unmapped_type"
    )
    assert res["carrier-b"]["warnings"] == []


def test_the_check_tool_hashes_the_samples_bytes(pack: RulePack, tmp_path: Path) -> None:
    for lid in carrier.LAYOUTS:
        raw = carrier.render(lid).replace("\n", "\r\n").encode()
        (tmp_path / f"{lid}.csv").write_bytes(raw)
        assert check_layout.check(pack, tmp_path)[lid]["sha256"] == hashlib.sha256(raw).hexdigest()


def test_a_guard_naming_a_true_claim_names_no_trap(pack: RulePack) -> None:
    body = pack.model_dump(mode="json")
    body["guards"][0]["blocks"] = ["t-voicemail", "g-in-call"]
    rep = harness.evaluate(RulePack.model_validate(body))
    assert rep.unknown_traps == ["voicemail-leg:g-in-call"]


def test_the_cli_says_when_no_claim_set_is_given(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        harness.main([str(REFERENCE), "--claims", ","])
    assert "no claim set given" in capsys.readouterr().err


def test_a_card_says_when_rule_kill_never_ran(pack: RulePack) -> None:
    short = pack.model_copy(update={"layouts": (pack.layout("carrier-a"),)})
    rep = harness.evaluate(short)
    assert rep.layout_errors == ["missing:carrier-b"]
    assert harness.cards(short, rep)[0].endswith("not tested (the gate stopped before rule-kill)")


def test_the_check_tool_reports_an_unreadable_sample_and_goes_on(
    pack: RulePack, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for lid in carrier.LAYOUTS:
        (tmp_path / f"{lid}.csv").write_text(carrier.render(lid))
    real = Path.read_bytes

    def read_bytes(self: Path) -> bytes:
        if self.name == "carrier-a.csv":
            raise PermissionError("denied")
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    res = check_layout.check(pack, tmp_path)
    assert res["carrier-a"] == {"error": "denied"}
    assert "coverage" in res["carrier-b"]


def test_the_check_tool_reports_a_csv_parser_error_and_goes_on(
    pack: RulePack, tmp_path: Path
) -> None:
    for lid in carrier.LAYOUTS:
        (tmp_path / f"{lid}.csv").write_text(carrier.render(lid))
    header, rest = carrier.render("carrier-a").split("\n", 1)
    (tmp_path / "carrier-a.csv").write_text(f"{header}\n{'x' * 2000}\n{rest}")
    old = csv.field_size_limit(1000)
    try:
        res = check_layout.check(pack, tmp_path)
    finally:
        csv.field_size_limit(old)
    assert res["carrier-a"] == {"error": "field larger than field limit (1000)"}
    assert "coverage" in res["carrier-b"]


def test_a_layout_with_a_repeated_header_label_is_refused(pack: RulePack) -> None:
    body = pack.model_dump(mode="json")
    lay = body["layouts"][0]
    lay["headers"] = [*lay["headers"], lay["duration_col"]]
    with pytest.raises(ValidationError, match="header label repeats"):
        RulePack.model_validate(body)


def test_only_traps_earn_a_guard_credit(pack: RulePack) -> None:
    trap = next(c for c in CLAIMS if c.id == "t-voicemail")
    untagged = dataclasses.replace(trap, id="x-untagged", trap=False)
    rep = harness.evaluate(pack, (*CLAIMS, untagged))
    assert "t-voicemail" in rep.rule_kill["voicemail-leg"]
    assert "x-untagged" not in rep.rule_kill["voicemail-leg"]


def test_a_wrong_row_says_why_and_a_right_row_does_not() -> None:
    # the round 2 drafter gets a reference-only report and needs the reasons (DRAFTING.md)
    pack = load(REFERENCE)
    bare = pack.model_copy(update={"guards": ()})
    rep = harness.evaluate(bare)
    rows = [r for rows in rep.layouts.values() for r in rows]
    wrong = [r for r in rows if r["got"] != r["expected"]]
    assert wrong, "with no guards some trap should come out wrong"
    assert all(r["why"] for r in wrong)
    assert all("why" not in r for r in rows if r["got"] == r["expected"])
