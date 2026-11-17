"""Trap harness: run a rule pack over the synthetic carrier cases and try to break it.

Verdicts come only from core.audit.rules.decide_verdict. The pack's guards act one step
earlier, on check results: a check that would pass or fail on a guarded record type comes
out inconclusive instead. That can only move a claim away from SUPPORTED or CONTRADICTED,
never toward them.

The gate (a pack is dropped if any part fails):
1. zero false supported: no claim the gold set says is not SUPPORTED comes out SUPPORTED,
   in any layout;
2. every guard earns its place: removing it lets at least one of the traps it names through
   as a false supported (rule-kill);
3. sensitivity: every SUPPORTED claim stops being SUPPORTED when the records it rests on are
   mutated (direction flipped, time moved six hours).

Trap strength is reported beside the gate: each plausible layout mistake (a wrong zone, a
flipped direction map) must change some claim's verdict, so the mistake shows. One that lets a
trap through as a false supported is caught by the traps; one that only turns true claims
unproven is caught by the gold claims; one that changes nothing is a gap in the claim set.

    python -m eval.rulepacks.harness eval/rulepacks/packs/carrier-cdr-reference.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from core.audit.assumptions import instantiate
from core.audit.checks import run_checks
from core.audit.rules import RULE_VERSION, decide_verdict
from core.contracts import CheckOutcome, CheckResult, Claim, ClaimStatus, Verdict
from core.pipeline import load_stipulations
from eval.rulepacks import carrier
from eval.rulepacks.carrier_claims import CLAIMS, GoldClaim
from eval.rulepacks.pack import Guard, RulePack, load

RUN_ID = "rulepack-harness"


@dataclass
class Outcome:
    claim_id: str
    expected: Verdict
    got: Verdict
    trap: bool
    reasons: tuple[str, ...]
    cited_records: tuple[str, ...]

    @property
    def false_supported(self) -> bool:
        return self.got is Verdict.SUPPORTED and self.expected is not Verdict.SUPPORTED


def guarded(r: CheckResult, guards: tuple[Guard, ...], types: dict[str, str]) -> CheckResult:
    """The check result with the pack's guards applied: a pass or fail resting on a guarded
    record type turns inconclusive, and the detail names the guard."""
    if r.outcome is CheckOutcome.INCONCLUSIVE:
        return r
    for g in guards:
        hit = sorted(rid for rid in r.record_ids if types.get(rid) in g.record_types)
        if hit:
            return r.model_copy(
                update={
                    "outcome": CheckOutcome.INCONCLUSIVE,
                    "detail": f"{r.detail} Guard {g.id}: {g.text} (records {', '.join(hit)}).",
                }
            )
    return r


def decide(
    claim: GoldClaim, conn: sqlite3.Connection, guards: tuple[Guard, ...], types: dict[str, str]
) -> Outcome:
    c = Claim(
        id=claim.id,
        paragraph_id="p:synthetic",
        text=claim.text,
        claim_type=claim.claim_type,
        status=ClaimStatus.ACCEPTED,
    )
    assumptions = [instantiate(c.id, t, p) for t, p in claim.assumptions]
    checks = [guarded(r, guards, types) for a in assumptions for r in run_checks(a, conn)]
    d = decide_verdict(c, assumptions, [], checks, load_stipulations(conn), RUN_ID)
    cited = tuple(
        sorted({rid for r in checks if r.id in d.cited_check_ids for rid in r.record_ids})
    )
    return Outcome(claim.id, claim.expected, d.verdict, claim.trap, d.reasons, cited)


def run_case(
    pack: RulePack, layout_id: str, *, guards: tuple[Guard, ...] | None = None
) -> list[Outcome]:
    loaded = carrier.load_case(pack, layout_id)
    g = pack.guards if guards is None else guards
    return [decide(c, loaded.conn, g, loaded.record_types) for c in CLAIMS]


def _mutate(conn: sqlite3.Connection, record_ids: set[str]) -> None:
    """Flip each record's direction and move it six hours later."""
    for rid in record_ids:
        row = conn.execute("SELECT direction, ts_utc FROM calls WHERE id = ?", (rid,)).fetchone()
        if row is None:
            continue
        flipped = _flip(row[0])
        ts = datetime.strptime(row[1], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=6)
        conn.execute(
            "UPDATE calls SET direction = ?, ts_utc = ? WHERE id = ?",
            (flipped, ts.strftime("%Y-%m-%dT%H:%M:%SZ"), rid),
        )


@dataclass
class Report:
    pack: str
    pack_sha256: str
    rule_version: str
    layouts: dict[str, list[dict]] = field(default_factory=dict)
    false_supported: list[str] = field(default_factory=list)
    wrong: list[str] = field(default_factory=list)  # any verdict other than expected
    rule_kill: dict[str, list[str]] = field(default_factory=dict)  # guard -> traps it blocks
    unearned_guards: list[str] = field(default_factory=list)
    unblocked_named_traps: list[str] = field(default_factory=list)
    unknown_traps: list[str] = field(default_factory=list)  # guard:name that is no claim's
    layout_errors: list[str] = field(default_factory=list)  # missing:<id> or unknown:<id>
    insensitive: list[str] = field(default_factory=list)
    # layout mistake -> claims whose verdict it changes, and those it makes false supported
    trap_strength: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not (
            self.false_supported
            or self.unearned_guards
            or self.unblocked_named_traps
            or self.unknown_traps
            or self.layout_errors
            or self.insensitive
        )


def _fs(outcomes: list[Outcome]) -> set[str]:
    return {o.claim_id for o in outcomes if o.false_supported}


def evaluate(pack: RulePack) -> Report:
    rep = Report(pack.ref, pack.sha256(), RULE_VERSION)
    # every synthetic layout must be read, and no other: a pack that skips one is not tested
    # on it, and an id with no synthetic file cannot be run (CodeRabbit on #260)
    have = {x.id for x in pack.layouts}
    rep.layout_errors = [f"missing:{i}" for i in sorted(set(carrier.LAYOUTS) - have)] + [
        f"unknown:{i}" for i in sorted(have - set(carrier.LAYOUTS))
    ]
    if rep.layout_errors:
        return rep
    by_layout = {x.id: run_case(pack, x.id) for x in pack.layouts}
    for lid, outs in by_layout.items():
        rep.layouts[lid] = [
            {"claim": o.claim_id, "expected": o.expected.value, "got": o.got.value,
             "trap": o.trap} for o in outs
        ]  # fmt: skip
        rep.false_supported += [f"{lid}:{c}" for c in sorted(_fs(outs))]
        rep.wrong += [f"{lid}:{o.claim_id}" for o in outs if o.got is not o.expected]

    # rule-kill: each guard must let every trap it names through once removed. A name that is
    # no claim's fails the gate, so a misspelled trap cannot skip its test.
    known = {c.id for c in CLAIMS}
    for g in pack.guards:
        rest = tuple(x for x in pack.guards if x.id != g.id)
        through: set[str] = set()
        for x in pack.layouts:
            through |= _fs(run_case(pack, x.id, guards=rest))
        rep.rule_kill[g.id] = sorted(through)
        if not through:
            rep.unearned_guards.append(g.id)
        for trap in g.blocks:
            if trap not in known:
                rep.unknown_traps.append(f"{g.id}:{trap}")
            elif trap not in through:
                rep.unblocked_named_traps.append(f"{g.id}:{trap}")

    # sensitivity: a SUPPORTED claim must not survive mutation of the records it rests on
    for x in pack.layouts:
        loaded = carrier.load_case(pack, x.id)
        for c in CLAIMS:
            o = decide(c, loaded.conn, pack.guards, loaded.record_types)
            if o.got is not Verdict.SUPPORTED:
                continue
            m = carrier.load_case(pack, x.id)
            _mutate(m.conn, set(o.cited_records))
            if decide(c, m.conn, pack.guards, m.record_types).got is Verdict.SUPPORTED:
                rep.insensitive.append(f"{x.id}:{c.id}")

    # layout mistakes: each must change some claim's verdict from the pack's own result
    for x in pack.layouts:
        for zone in ("UTC", "America/New_York", "America/Chicago"):
            if zone == x.zone:
                continue
            wrong = x.model_copy(update={"zone": zone})
            rep.trap_strength[f"{x.id}: zone read as {zone}"] = _shows(
                _with_layout(pack, x.id, wrong), by_layout[x.id]
            )
        flipped = {k: _flip(v) for k, v in x.direction_values.items()}
        rep.trap_strength[f"{x.id}: direction map flipped"] = _shows(
            _with_layout(pack, x.id, x.model_copy(update={"direction_values": flipped})),
            by_layout[x.id],
        )
    rep.gaps = [k for k, v in rep.trap_strength.items() if not v["changed"]]
    return rep


def _shows(outs: list[Outcome], baseline: list[Outcome]) -> dict[str, list[str]]:
    """Claims whose verdict the mistake changes from the same pack's own result, and claims
    it makes false supported against the gold."""
    before = {o.claim_id: o.got for o in baseline}
    return {
        "changed": sorted(o.claim_id for o in outs if o.got is not before[o.claim_id]),
        "false_supported": sorted(_fs(outs)),
    }


def _flip(v: str) -> str:
    return {"incoming": "outgoing", "outgoing": "incoming"}.get(v, v)


def _with_layout(pack: RulePack, file_layout: str, layout) -> list[Outcome]:
    loaded = carrier.read(carrier.render(file_layout), layout)
    return [decide(c, loaded.conn, pack.guards, loaded.record_types) for c in CLAIMS]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pack", type=Path)
    ap.add_argument("--json", action="store_true", help="print the full report as JSON")
    args = ap.parse_args(argv)
    rep = evaluate(load(args.pack))
    if args.json:
        print(json.dumps({**rep.__dict__, "passed": rep.passed}, indent=2, sort_keys=True))
    else:
        print(f"pack {rep.pack} sha256 {rep.pack_sha256[:12]} rules {rep.rule_version}")
        if rep.layout_errors:
            print(f"  layouts not matching the synthetic files: {rep.layout_errors}")
        for lid, rows in rep.layouts.items():
            right = sum(r["expected"] == r["got"] for r in rows)
            print(f"  {lid}: {right}/{len(rows)} claims as expected")
        print(f"  false supported: {len(rep.false_supported)} {rep.false_supported}")
        print(f"  other misses: {[w for w in rep.wrong if w not in rep.false_supported]}")
        for g, traps in rep.rule_kill.items():
            print(f"  without guard {g}: {traps or 'nothing gets through (unearned)'}")
        if rep.unknown_traps:
            print(f"  guards naming no claim: {rep.unknown_traps}")
        print(f"  insensitive supported claims: {rep.insensitive}")
        for k, v in rep.trap_strength.items():
            shown = f"changes {v['changed']}, false supported {v['false_supported']}"
            print(f"  layout mistake, {k}: {shown if v['changed'] else 'NOTHING SHOWS IT (gap)'}")
        print("PASS" if rep.passed else "DROP")
    return 0 if rep.passed else 1


if __name__ == "__main__":
    sys.exit(main())
