"""Check a draft pack against the sample files only: does it validate, and how does each
layout read its sample? This is the one tool a drafting session runs (DRAFTING.md). It knows
nothing of claims or traps, so it cannot be used to tune a pack to them.

    python -m eval.rulepacks.check_layout <pack.json>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from eval.rulepacks.pack import RulePack
from eval.rulepacks.reader import read

SAMPLES = Path(__file__).parent / "formats" / "samples"


def check(pack: RulePack, samples: Path = SAMPLES) -> dict[str, dict[str, object]]:
    """Each layout's reading of its sample file: the reader's coverage, and the first rows as
    stored, or the error that stopped it."""
    out: dict[str, dict[str, object]] = {}
    for x in pack.layouts:
        path = samples / f"{x.id}.csv"
        if not path.is_file():
            out[x.id] = {"error": f"no sample file {path.name}"}
            continue
        try:
            loaded = read(path.read_text(encoding="utf-8"), x)
        except ValueError as e:
            out[x.id] = {"error": str(e)}
            continue
        rows = loaded.conn.execute(
            "SELECT id, ts_raw, ts_utc, direction, duration_s FROM calls ORDER BY rowid LIMIT 5"
        ).fetchall()
        out[x.id] = {
            "coverage": loaded.coverage,
            "first_calls": [
                {"id": r[0], "raw": r[1], "utc": r[2], "direction": r[3], "seconds": r[4],
                 "type": loaded.record_types[r[0]]} for r in rows
            ],
        }  # fmt: skip
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pack", type=Path)
    args = ap.parse_args(argv)
    try:
        pack = RulePack.model_validate_json(args.pack.read_text(encoding="utf-8"))
    except ValidationError as e:
        print(f"INVALID\n{e}")
        return 1
    res = check(pack)
    print(json.dumps({"pack": pack.ref, "sha256": pack.sha256(), "layouts": res}, indent=2))
    return 1 if any("error" in v for v in res.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
