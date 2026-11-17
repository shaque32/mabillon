"""Independent count of a LEAPP run's output (json and sqlite3 only, never Mabillon's importer).

Validation v5 reads its held-out phones through the LEAPP importer, so bar 8 compares Mabillon's
import counts with this reader's. Like dump_ufdr.py, it imports nothing from core/ on purpose,
and it was written from the LAVA format, not from the importer's code.

A LEAPP run (iLEAPP, ALEAPP) writes `_lava_data.lava`, a JSON manifest (parser_info,
lava_schema_version, profile_used, and artifacts by category, each with name, tablename, module,
column_map, record_count and source_path), and `_lava_artifacts.db`, one SQLite table per
artifact.

Usage: python3 -I -m eval.validation.dump_lava <lava_dir> <kinds.json> <out.json>
kinds.json maps each table read as a kind to that kind and its dedupe columns, if any:
    {"sms": {"kind": "message", "dedupe": "message_row_id"},
     "get_googlemessages": {"kind": "message",
                            "dedupe": ["conversation_id", "message_timestamp", "direction"]}}
A table with dedupe columns is counted by its distinct values of those columns, over rows where
none is null (iLEAPP's SMS table has one row per attachment); any other table by its rows. A
table may also be listed with "kind": "skip" (one that repeats another, such as ALEAPP's
get_sms_mms_combined): it is reported and never counted. The manifest's record_count
is reported beside the live count and never used as the count.
"""

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

MANIFEST = "_lava_data.lava"
DATABASE = "_lava_artifacts.db"
KINDS = ("message", "call", "contact")
SKIP = "skip"
VERSION = "1.0.0"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def manifest_tables(manifest: dict) -> dict[str, dict]:
    """Each artifact the manifest lists, by its table name."""
    out: dict[str, dict] = {}
    for category, artifacts in (manifest.get("artifacts") or {}).items():
        for art in artifacts if isinstance(artifacts, list) else artifacts.values():
            table = art.get("tablename")
            if not table:
                continue
            if table in out:
                raise SystemExit(f"dump_lava: the manifest lists table {table!r} twice")
            out[table] = {**art, "category": category}
    return out


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def count(conn: sqlite3.Connection, table: str, dedupe: str | list[str] | None) -> dict:
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({quote(table)})")]
    if not cols:
        raise SystemExit(f"dump_lava: table {table!r} is not in {DATABASE}")
    # Names are quoted, and each is one the database itself lists (sqlite_master, table_info).
    rows = conn.execute(f"SELECT COUNT(*) FROM {quote(table)}").fetchone()[0]  # noqa: S608
    out = {"rows": rows, "count": rows}
    if dedupe:
        keys = [dedupe] if isinstance(dedupe, str) else list(dedupe)
        by_case = {c.casefold(): c for c in cols}  # SQLite column names are case-insensitive
        for k in keys:
            if k.casefold() not in by_case:
                raise SystemExit(f"dump_lava: table {table!r} has no column {k!r}")
        keys = [by_case[k.casefold()] for k in keys]
        names = ", ".join(quote(k) for k in keys)
        no_null = " AND ".join(f"{quote(k)} IS NOT NULL" for k in keys)
        out["count"] = conn.execute(
            f"SELECT COUNT(*) FROM (SELECT DISTINCT {names} FROM {quote(table)}"  # noqa: S608
            f" WHERE {no_null})"
        ).fetchone()[0]
        out["null_dedupe_rows"] = (
            rows
            - conn.execute(
                f"SELECT COUNT(*) FROM {quote(table)} WHERE {no_null}"  # noqa: S608
            ).fetchone()[0]
        )
    return out


def read(lava_dir: Path, kinds: dict[str, dict]) -> dict:
    manifest_path, db_path = lava_dir / MANIFEST, lava_dir / DATABASE
    manifest = json.loads(manifest_path.read_text("utf-8"))
    listed = manifest_tables(manifest)
    # as_uri() escapes '#', '?' and '%' in the path, so mode=ro always applies (Greptile on #263).
    conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        # SQLite table names are case-insensitive, so a kinds entry "SMS" names table "sms".
        in_db = {
            r[0].casefold(): r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            if not r[0].casefold().startswith("sqlite_")
        }
        listed = {k.casefold(): v for k, v in listed.items()}
        tables: dict[str, dict] = {}
        totals = {k: 0 for k in KINDS}
        for table, spec in sorted(kinds.items()):
            kind = spec.get("kind")
            if kind not in (*KINDS, SKIP):
                raise SystemExit(f"dump_lava: {table!r} has kind {kind!r}, not one of {KINDS}")
            name = in_db.get(table.casefold())
            if name is None:
                # A table the importer reads but this run did not write: zero, said so.
                tables[table] = {"kind": kind, "present": False, "count": 0}
                continue
            got = count(conn, name, spec.get("dedupe"))
            art = listed.get(table.casefold(), {})
            tables[table] = {
                "kind": kind,
                "present": True,
                **got,
                "manifest_record_count": art.get("record_count"),
                "in_manifest": table.casefold() in listed,
                "source_path": art.get("source_path"),
            }
            if kind != SKIP:
                totals[kind] += got["count"]
        named = {t.casefold() for t in kinds}
        # Every written table no kind names, listed in the manifest or not: none is left out
        # of the count without being reported.
        unread = sorted(in_db[t] for t in in_db.keys() - named)
        unlisted = sorted(in_db[t] for t in in_db.keys() - listed.keys())
    finally:
        conn.close()
    parser = manifest.get("parser_info") or {}
    return {
        "dump_lava_version": VERSION,
        "manifest_sha256": sha256(manifest_path),
        "database_sha256": sha256(db_path),
        "leapp_name": parser.get("leapp_name"),
        "leapp_version": parser.get("leapp_version"),
        "lava_schema_version": manifest.get("lava_schema_version"),
        "profile_used": manifest.get("profile_used"),
        "counts": totals,
        "tables": tables,
        "tables_not_counted": unread,  # written, read as no kind
        "tables_not_in_manifest": unlisted,  # written, but the manifest lists no artifact
        "manifest_count_differs": sorted(
            t
            for t, v in tables.items()
            if v.get("present") and v.get("manifest_record_count") not in (None, v["rows"])
        ),
    }


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 3:
        raise SystemExit(__doc__)
    lava_dir, kinds_path, out = Path(args[0]), Path(args[1]), Path(args[2])
    kinds = json.loads(kinds_path.read_text("utf-8"))
    result = read(lava_dir, kinds)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", "utf-8")
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    main()
