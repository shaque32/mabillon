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
    # no case, copy, report or results: only the counts, the run record, the log and the
    # affidavit the claims file made
    assert sorted(p.name for p in out.iterdir()) == [
        "affidavit.pdf",
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


def test_counts_follow_the_scorers_tiers_and_the_phones_a_deciding_check_searched(ufdr, tmp_path):
    assert hickman_run.main(_args(ufdr, tmp_path, "run")) == 0
    db = tmp_path / "run" / "case.db"
    conn = sqlite3.connect(db)
    try:
        run = pipeline.last_run(conn)
        assert run is not None
        manifest = run["manifest"]
        checks = {c: manifest[c]["checks"] for c in IDS}
        assert all(checks.values()), "the stand-in checks run on every claim"
        with conn:
            # C01: a pass on one phone and a fail on two; C02: inconclusive only; D01's
            # assumptions made not core, so no check counts and it is expert only
            first, *rest = checks["C01"]
            conn.execute(
                "UPDATE check_results SET outcome = 'pass', source_ids_json = ? WHERE id = ?",
                (json.dumps(["ios15"]), first),
            )
            for cid in rest or [first]:
                conn.execute(
                    "UPDATE check_results SET outcome = 'fail', source_ids_json = ? WHERE id = ?",
                    (json.dumps(["ios15", "item2"]), cid),
                )
            conn.execute("UPDATE assumptions SET is_core = 0 WHERE claim_id = 'D01'")
        got = coverage_probe.counts(conn, manifest, {})
        tiers = {c: score_hickman._check_tier(conn, manifest, c) for c in IDS}
        untested = coverage_probe.counts(conn, manifest, {"C02": "no core assumption"})
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
    # a claim counts once for each phone its deciding checks searched
    assert got["code_checked_by_phone"] == {"ios15": 1, "item2": 1}
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
