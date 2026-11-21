"""The coverage probe (validation v5, PREREGISTERED_v5 section 7a, gate C4).

Before a paid run, the probe measures how many of the frozen claims the deterministic checks
can settle on the held-out phones. A claim's coverage tier depends only on the assumptions the
filler writes and the checks code runs on them, never on stance labels, so the probe runs the
same filler and checks as a real pass and labels no evidence: ProbeLabeler stands in for the
stance labeler and makes no model call. The run then costs only the filler's calls.

The probe keeps counts only: the tiers by claim kind and by phone, never a claim id, verdict
or check result. hickman_run.py --coverage-probe writes them to DIR/probe.json and deletes the
case once counted.

ProbeLabeler lives here, in eval/, so pipeline.Components.fake() marks any run that uses it as
fake however the driver is started, and no scorer or report takes it.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Collection, Mapping
from datetime import UTC, datetime

from core.contracts import Assumption, ModelRun, Stance, StanceLabel

PROBE_RUN_ID = "mr:coverage-probe-stance"

# The tiers as score_hickman._check_tier sets them, plus the claims the filler left untested.
CODE_CHECKED = "code_checked"
CHECK_UNSETTLED = "check_unsettled"
EXPERT_ONLY = "expert_only"
NOT_TESTED = "not_tested"
TIERS = (CODE_CHECKED, CHECK_UNSETTLED, EXPERT_ONLY, NOT_TESTED)


class ProbeLabeler:
    """The probe's stand-in for the stance labeler: no model call, every candidate irrelevant."""

    def __init__(self) -> None:
        self.model_runs = (
            ModelRun(
                id=PROBE_RUN_ID,
                purpose="stance",
                model_name="coverage-probe-no-labels",
                model_sha256="0" * 64,
                prompt_version="none",
                params={"stand_in": True, "coverage_probe": True},
                seed=0,
                started_at_utc=datetime(2026, 11, 21, tzinfo=UTC),
            ),
        )

    def label(self, assumption: Assumption, candidate) -> StanceLabel:  # noqa: ANN001
        return StanceLabel(
            assumption_id=assumption.id,
            record_id=candidate.record_id,
            stance=Stance.IRRELEVANT,
            quote=candidate.text[:30],
            rationale="Coverage probe: no label is made.",
            model_run_id=PROBE_RUN_ID,
        )


def tier(conn: sqlite3.Connection, check_ids: Collection[str]) -> tuple[str, set[str]]:
    """A tested claim's tier from the checks its manifest cites, as score_hickman._check_tier
    sets it, and the sources its pass or fail checks on core assumptions searched."""
    outcomes: set[str] = set()
    phones: set[str] = set()
    for cid in sorted(check_ids):
        row = conn.execute(
            "SELECT c.outcome, c.source_ids_json FROM check_results c"
            " JOIN assumptions a ON a.id = c.assumption_id WHERE c.id = ? AND a.is_core = 1",
            (cid,),
        ).fetchone()
        if row is None:
            continue
        outcomes.add(row[0])
        if row[0] in ("pass", "fail"):
            phones.update(str(x) for x in json.loads(row[1] or "[]"))
    if outcomes & {"pass", "fail"}:
        return CODE_CHECKED, phones
    return (CHECK_UNSETTLED if outcomes else EXPERT_ONLY), set()


def counts(
    conn: sqlite3.Connection,
    manifest: Mapping[str, Mapping[str, list[str]]],
    not_tested: Collection[str],
) -> dict:
    """The tiers of every claim the run audited, counted in total, by claim kind and, for the
    code-checked ones, by each phone a deciding check searched (a claim checked on both phones
    counts for each). Counts only: no claim id, verdict or check result."""
    total = dict.fromkeys(TIERS, 0)
    by_kind: dict[str, dict[str, int]] = {}
    by_phone: dict[str, int] = {}
    for claim_id in sorted(manifest):
        row = conn.execute("SELECT claim_type FROM claims WHERE id = ?", (claim_id,)).fetchone()
        kind = str(row[0]) if row else "unknown"
        if claim_id in not_tested:
            t, phones = NOT_TESTED, set()
        else:
            t, phones = tier(conn, manifest[claim_id].get("checks", []))
        total[t] += 1
        by_kind.setdefault(kind, dict.fromkeys(TIERS, 0))[t] += 1
        for ph in phones:
            by_phone[ph] = by_phone.get(ph, 0) + 1
    return {
        "claims": sum(total.values()),
        "tiers": total,
        "by_kind": dict(sorted(by_kind.items())),
        "code_checked_by_phone": dict(sorted(by_phone.items())),
    }
