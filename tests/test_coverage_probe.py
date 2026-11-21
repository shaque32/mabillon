"""The coverage probe (eval/validation/coverage_probe.py and hickman_run.py --coverage-probe):
the filler and checks on every claim, no evidence labeled, counts only, the case deleted. On
synthetic case01 with the eval's stand-in components."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from core import pipeline
from eval.pipeline_fakes import fake_components
from eval.synthetic.generate import generate
from eval.synthetic.ufdr import write_case01
from eval.validation import coverage_probe, hickman_run, score_hickman

CLAIMS = [
    {"claim_id": "C01", "page": 1, "para_no": 1, "claim_type": "communication",
     "text": "On April 28, 2023, the TARGET PHONE exchanged Signal messages with (919) 888-7386."},
    {"claim_id": "C02", "page": 1, "para_no": 2, "claim_type": "content",
     "text": 'SUBJECT-1 wrote "I\'m here!" to SUBJECT-2 on April 28, 2023.'},
    {"claim_id": "D01", "page": 2, "para_no": 3, "claim_type": "timing",
     "text": "On Tuesday, April 24, 2023, the TARGET PHONE's Discord account exchanged messages."},
]  # fmt: skip
IDS = [c["claim_id"] for c in CLAIMS]


@pytest.fixture(scope="module")
def ufdr(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("case01")
    generate(out)
    return write_case01(out)[0]


def _args(ufdr: Path, tmp_path: Path, out: str, *extra: str) -> list[str]:
    claims = tmp_path / "claims.jsonl"
    claims.write_text("".join(json.dumps(r) + "\n" for r in CLAIMS), encoding="utf-8")
    return ["--ufdr", str(ufdr), "--claims", str(claims), "--out", str(tmp_path / out),
            "--fake", *extra]  # fmt: skip


def test_the_probe_keeps_counts_only_and_deletes_the_case(ufdr, tmp_path, capsys):
    assert hickman_run.main(_args(ufdr, tmp_path, "probe", "--coverage-probe")) == 0
    out = tmp_path / "probe"
    # no case, copy, affidavit, report or results: only the counts, the run record and the log
    assert sorted(p.name for p in out.iterdir()) == [
        "probe.json",
        "progress.log",
        "run.json",
    ]
    counts = json.loads((out / "probe.json").read_text(encoding="utf-8"))
    assert counts["claims"] == 3 and sum(counts["tiers"].values()) == 3
    assert set(counts["tiers"]) == set(coverage_probe.TIERS)
    assert sorted(counts["by_kind"]) == ["communication", "content_meaning", "timing"]
    run = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert run["coverage_probe"] is True
    assert run["audit"]["probe"] == counts and "verdicts" not in run["audit"]
    assert run["audit"]["fake"] is True  # the stand-in labeler is eval's, so never scored
    # no claim id or verdict anywhere it writes or prints
    printed = capsys.readouterr().out
    for text in (
        printed,
        (out / "progress.log").read_text(encoding="utf-8"),
        (out / "run.json").read_text(encoding="utf-8"),
        (out / "probe.json").read_text(encoding="utf-8"),
    ):
        for claim_id in IDS:
            assert claim_id not in text, claim_id
        for verdict in ("unproven", "supported", "contradicted"):
            assert verdict not in text.lower(), verdict
    assert "coverage probe: 3 claims" in printed
    # with the case gone, the same command builds and probes afresh
    assert hickman_run.main(_args(ufdr, tmp_path, "probe", "--coverage-probe")) == 0
    assert json.loads((out / "probe.json").read_text(encoding="utf-8")) == counts


def test_the_probe_counts_the_tiers_a_full_run_gives(ufdr, tmp_path):
    """The tiers depend on the filler and checks only, so the probe's counts are the full
    run's, tier for tier, as the scorer reads them."""
    assert hickman_run.main(_args(ufdr, tmp_path, "probe", "--coverage-probe")) == 0
    assert hickman_run.main(_args(ufdr, tmp_path, "run")) == 0
    probe = json.loads((tmp_path / "probe" / "probe.json").read_text(encoding="utf-8"))
    conn = sqlite3.connect(tmp_path / "run" / "case.db")
    try:
        run = pipeline.last_run(conn)
        assert run is not None
        assert coverage_probe.counts(conn, run["manifest"], run["not_tested"]) == probe
        tiers = [score_hickman._check_tier(conn, run["manifest"], c) for c in IDS]
    finally:
        conn.close()
    assert sorted(tiers) == sorted(
        t for t, n in probe["tiers"].items() for _ in range(n) if t != coverage_probe.NOT_TESTED
    )


def test_counts_follow_the_scorers_tiers_and_the_phones_a_deciding_check_rests_on(ufdr, tmp_path):
    assert hickman_run.main(_args(ufdr, tmp_path, "run")) == 0
    db = tmp_path / "run" / "case.db"
    conn = sqlite3.connect(db)
    try:
        run = pipeline.last_run(conn)
        assert run is not None
        manifest = run["manifest"]
        checks = {c: manifest[c]["checks"] for c in IDS}
        assert all(checks.values()), "the stand-in checks run on every claim"
        (msg,) = conn.execute(
            "SELECT id FROM messages WHERE source_id = 'ios15' ORDER BY id LIMIT 1"
        ).fetchone()
        searched = json.dumps(["ios15", "item2"])
        with conn:
            # C01: a check that searched two sources and rests on one record of ios15 passes,
            # and the rest fail citing no record; C02: inconclusive only; D01's assumptions made
            # not core, so no check counts and it is expert only
            first, *rest = checks["C01"]
            conn.execute(
                "UPDATE check_results SET outcome = 'pass', source_ids_json = ?,"
                " record_ids_json = ? WHERE id = ?",
                (searched, json.dumps([msg]), first),
            )
            for cid in rest:
                conn.execute(
                    "UPDATE check_results SET outcome = 'fail', source_ids_json = ?,"
                    " record_ids_json = '[]' WHERE id = ?",
                    (searched, cid),
                )
            conn.execute("UPDATE assumptions SET is_core = 0 WHERE claim_id = 'D01'")
        got = coverage_probe.counts(conn, manifest, {})
        tiers = {c: score_hickman._check_tier(conn, manifest, c) for c in IDS}
        untested = coverage_probe.counts(conn, manifest, {"C02": "no core assumption"})
        with conn:  # the deciding check cites no record now, and searched two sources
            conn.execute("UPDATE check_results SET record_ids_json = '[]' WHERE id = ?", (first,))
        unnamed = coverage_probe.counts(conn, manifest, {})
    finally:
        conn.close()
    assert tiers == {"C01": "code_checked", "C02": "check_unsettled", "D01": "expert_only"}
    assert got["tiers"] == {
        "code_checked": 1,
        "check_unsettled": 1,
        "expert_only": 1,
        "not_tested": 0,
    }
    assert got["by_kind"]["communication"]["code_checked"] == 1
    assert got["by_kind"]["timing"]["expert_only"] == 1
    # a claim counts for the phone its deciding records are on, not every source searched
    assert got["code_checked_by_phone"] == {"ios15": 1}
    assert got["code_checked_unattributed"] == 0
    # one no phone can be named for is counted apart, and every phone is listed, 0 included
    assert unnamed["code_checked_by_phone"] == {"ios15": 0}
    assert unnamed["code_checked_unattributed"] == 1
    # a claim the pipeline left untested is counted so, whatever check rows it has
    assert untested["tiers"]["not_tested"] == 1
    assert untested["by_kind"]["content_meaning"]["not_tested"] == 1


def test_a_probe_never_resumes_as_a_run_nor_a_run_as_a_probe(ufdr, tmp_path, monkeypatch):
    # a probe stopped before it finished leaves its case; a run on it is refused, since the
    # case holds no stance labels to reuse
    real = hickman_run._probe_done

    def stop(*a, **k):  # noqa: ANN002, ANN003, ANN202
        raise SystemExit("stopped")

    monkeypatch.setattr(hickman_run, "_probe_done", stop)
    with pytest.raises(SystemExit, match="stopped"):
        hickman_run.main(_args(ufdr, tmp_path, "probe", "--coverage-probe"))
    assert (tmp_path / "probe" / "built.ok").exists()
    with pytest.raises(SystemExit, match="built for a coverage probe, not a run"):
        hickman_run.main(_args(ufdr, tmp_path, "probe"))
    monkeypatch.setattr(hickman_run, "_probe_done", real)
    assert hickman_run.main(_args(ufdr, tmp_path, "probe", "--coverage-probe")) == 0

    assert hickman_run.main(_args(ufdr, tmp_path, "run")) == 0
    with pytest.raises(SystemExit, match="built for a run, not a coverage probe"):
        hickman_run.main(_args(ufdr, tmp_path, "run", "--coverage-probe"))
    assert (tmp_path / "run" / "case.db").exists()  # a refused probe deletes nothing


def test_a_run_after_a_probe_in_the_same_dir_leaves_no_probe_counts(ufdr, tmp_path):
    assert hickman_run.main(_args(ufdr, tmp_path, "probe", "--coverage-probe")) == 0
    assert hickman_run.main(_args(ufdr, tmp_path, "probe")) == 0
    assert not (tmp_path / "probe" / "probe.json").exists()
    assert (tmp_path / "probe" / "results.zip").exists()


def test_a_cloud_probe_needs_a_spend_cap(ufdr, tmp_path):
    args = [a for a in _args(ufdr, tmp_path, "probe", "--coverage-probe") if a != "--fake"]
    with pytest.raises(SystemExit, match="--coverage-probe with --cloud needs --max-usd"):
        hickman_run.main([*args, "--cloud", "claude-opus-5-5"])
    assert not (tmp_path / "probe").exists()  # refused before anything is written


def test_the_probe_labeler_makes_no_label_and_marks_the_run_fake():
    comps = fake_components()
    comps.labeler = coverage_probe.ProbeLabeler()
    assert comps.names()["labeler"] == "eval.validation.coverage_probe.ProbeLabeler"
    assert comps.fake()
    (run,) = comps.labeler.model_runs
    assert run.purpose == "stance" and run.params["coverage_probe"] is True


def test_a_fresh_probe_starts_its_cap_at_zero_and_keeps_the_earlier_spend(
    ufdr, tmp_path, monkeypatch
):
    assert hickman_run.main(_args(ufdr, tmp_path, "probe", "--coverage-probe")) == 0
    run_path = tmp_path / "probe" / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["cloud"] = {"sessions": [{"spent_usd": 3.0}], "spent_usd": 3.0}  # as a paid probe leaves it
    run_path.write_text(json.dumps(run), encoding="utf-8")
    seen: list[float] = []
    real = hickman_run.Budgeted

    def budgeted(model, max_usd, spent_usd=0.0):  # noqa: ANN001, ANN202
        seen.append(spent_usd)
        return real(model, max_usd, spent_usd)

    from core.llm import cloud

    monkeypatch.setattr(hickman_run, "Budgeted", budgeted)
    monkeypatch.setenv(cloud.KEY_ENV, "sk-test")
    monkeypatch.setattr(cloud.ClaudeModel, "_get_client", lambda self: _NoAnswer())

    def no_stance(*a, **k):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("a probe builds no stance labeler")

    from core.audit import stance

    monkeypatch.setattr(stance, "create", no_stance)
    args = [a for a in _args(ufdr, tmp_path, "probe", "--coverage-probe") if a != "--fake"]
    assert hickman_run.main([*args, "--cloud", "claude-opus-5-5", "--max-usd", "5"]) == 3
    assert seen == [0.0]  # the deleted case's $3 does not count against this case's cap
    again = json.loads(run_path.read_text(encoding="utf-8"))
    (earlier,) = again["earlier_cases"]
    assert earlier["cloud"]["spent_usd"] == 3.0 and "probe" in earlier["audit"]
    assert again["cloud"]["spent_usd"] == 0
    # a resume of this case keeps its own spend as the baseline
    again["cloud"]["spent_usd"] = 1.0
    run_path.write_text(json.dumps(again), encoding="utf-8")
    assert hickman_run.main([*args, "--cloud", "claude-opus-5-5", "--max-usd", "5"]) == 3
    assert seen == [0.0, 1.0]
    assert len(json.loads(run_path.read_text(encoding="utf-8"))["earlier_cases"]) == 1


class _NoAnswer:
    """An Anthropic client whose every call fails as an account out of credit does."""

    class messages:  # noqa: N801 - the SDK's attribute name
        @staticmethod
        def create(**kw):  # noqa: ANN003, ANN205
            raise RuntimeError("Error code: 400 - credit balance is too low")


def test_a_run_rebuilt_after_a_run_keeps_counting_its_spend(ufdr, tmp_path, monkeypatch):
    """Only a probe's case (or a probe after a run) starts a fresh cap: a run rebuilt in the
    same DIR after a crash keeps its earlier spend against --max-usd (Claude review on #272)."""
    assert hickman_run.main(_args(ufdr, tmp_path, "run")) == 0
    out = tmp_path / "run"
    run = json.loads((out / "run.json").read_text(encoding="utf-8"))
    run["cloud"] = {"sessions": [{"spent_usd": 40.0}], "spent_usd": 40.0}
    (out / "run.json").write_text(json.dumps(run), encoding="utf-8")
    (out / "built.ok").unlink()  # as an operator clearing a crashed attempt would
    (out / "case.db").unlink()
    seen: list[float] = []
    real = hickman_run.Budgeted

    def budgeted(model, max_usd, spent_usd=0.0):  # noqa: ANN001, ANN202
        seen.append(spent_usd)
        return real(model, max_usd, spent_usd)

    from core.llm import cloud

    monkeypatch.setattr(hickman_run, "Budgeted", budgeted)
    monkeypatch.setenv(cloud.KEY_ENV, "sk-test")
    monkeypatch.setattr(cloud.ClaudeModel, "_get_client", lambda self: _NoAnswer())
    args = [a for a in _args(ufdr, tmp_path, "run") if a != "--fake"]
    assert hickman_run.main([*args, "--cloud", "claude-opus-5-5", "--max-usd", "55"]) == 3
    assert seen == [40.0]
    assert "earlier_cases" not in json.loads((out / "run.json").read_text(encoding="utf-8"))


def test_the_earlier_case_moves_on_disk_before_the_new_case_is_built(ufdr, tmp_path, monkeypatch):
    """A probe stopped after its new case is built but before run.json is written again must
    not resume with the earlier case's spend as its baseline (CodeRabbit on #272)."""
    assert hickman_run.main(_args(ufdr, tmp_path, "probe", "--coverage-probe")) == 0
    run_path = tmp_path / "probe" / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["cloud"] = {"sessions": [{"spent_usd": 3.0}], "spent_usd": 3.0}
    run_path.write_text(json.dumps(run), encoding="utf-8")
    on_disk: list[dict] = []
    real_build = hickman_run.build

    def build_then_stop(*a, **k):  # noqa: ANN002, ANN003, ANN202
        on_disk.append(json.loads(run_path.read_text(encoding="utf-8")))
        real_build(*a, **k)
        raise KeyboardInterrupt  # stopped before built.ok and run.json are written

    monkeypatch.setattr(hickman_run, "build", build_then_stop)
    with pytest.raises(KeyboardInterrupt):
        hickman_run.main(_args(ufdr, tmp_path, "probe", "--coverage-probe"))
    (seen,) = on_disk
    assert "cloud" not in seen and "build_id" not in seen
    assert seen["earlier_cases"][0]["cloud"]["spent_usd"] == 3.0
    monkeypatch.setattr(hickman_run, "build", real_build)
    assert hickman_run.main(_args(ufdr, tmp_path, "probe", "--coverage-probe")) == 0
    again = json.loads(run_path.read_text(encoding="utf-8"))
    assert len(again["earlier_cases"]) == 1 and "probe" in again["audit"]


def test_a_resume_starts_from_the_spend_unrounded(ufdr, tmp_path, monkeypatch):
    """run.json keeps the spend at full precision, so a resume near its cap never starts from a
    spend rounded down to the cent (CodeRabbit on #272)."""
    seen: list[float] = []
    real = hickman_run.Budgeted

    def budgeted(model, max_usd, spent_usd=0.0):  # noqa: ANN001, ANN202
        seen.append(spent_usd)
        m = real(model, max_usd, spent_usd)
        m.spent_usd += 0.004  # as a request that cost under a cent would
        return m

    from core.llm import cloud

    monkeypatch.setattr(hickman_run, "Budgeted", budgeted)
    monkeypatch.setenv(cloud.KEY_ENV, "sk-test")
    monkeypatch.setattr(cloud.ClaudeModel, "_get_client", lambda self: _NoAnswer())
    args = [a for a in _args(ufdr, tmp_path, "probe", "--coverage-probe") if a != "--fake"]
    cap = [*args, "--cloud", "claude-opus-5-5", "--max-usd", "5"]
    assert hickman_run.main(cap) == 3
    run = json.loads((tmp_path / "probe" / "run.json").read_text(encoding="utf-8"))
    assert run["cloud"]["spent_usd"] == pytest.approx(0.004)
    assert hickman_run.main(cap) == 3
    assert seen == [0.0, pytest.approx(0.004)]
