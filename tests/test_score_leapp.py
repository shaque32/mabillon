"""The LEAPP side of the validation scorer (eval/validation/score_leapp.py), on synthetic LAVA
output imported by the real LEAPP importer: keys by LAVA row, and bar 8 table by table."""

from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from core.db import apply_schema
from core.ingest import leapp
from core.ingest.leapp import LeappImporter
from eval.validation import dump_lava, hickman_run, score_hickman, score_leapp
from eval.validation.score_leapp import LavaPhone
from tests.test_leapp import _android, _ios


def _phone(tmp_path: Path, sid: str, zipped: Path) -> LavaPhone:
    folder = tmp_path / f"lava-{sid}"
    folder.mkdir()
    score_leapp._extract(zipped, folder)
    kinds, _ = score_leapp.load_kinds(score_leapp.KINDS_FILE)
    reader = dump_lava.read(folder, kinds)
    folded = {dump_lava.fold(t): s for t, s in kinds.items()}
    return LavaPhone(sid, folder, score_leapp._sha256(zipped), reader, folded)


@pytest.fixture
def case(tmp_path: Path) -> tuple[sqlite3.Connection, dict[str, LavaPhone]]:
    """An Android and an iOS phone in one case, as a two-phone v5 run holds them."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    apply_schema(conn)
    phones = {}
    for sid, lv in (("and", _android()), ("ios", _ios())):
        zipped = lv.write_zip(tmp_path / f"{sid}.zip")
        LeappImporter(source_id=sid).import_source(zipped, conn)
        phones[sid] = _phone(tmp_path, sid, zipped)
    return conn, phones


def _skipped(conn: sqlite3.Connection, phones: dict[str, LavaPhone]) -> dict:
    return {sid: score_leapp.confirm_skipped(conn, p) for sid, p in phones.items()}


def _map(conn, phones, key: str) -> tuple[list[str], str]:  # noqa: ANN001
    conns = {sid: p.connect() for sid, p in phones.items()}
    try:
        tables = {sid: score_leapp._tables(c) for sid, c in conns.items()}
        return score_leapp._map_one(conn, key, phones, conns, tables, _skipped(conn, phones))
    finally:
        for c in conns.values():
            c.close()


def _locators(conn: sqlite3.Connection, ids: list[str]) -> set[str]:
    out = set()
    for t in score_leapp.RECORD_TABLES:
        for i in ids:
            out |= {r[0] for r in conn.execute(f"SELECT locator FROM {t} WHERE id = ?", (i,))}  # noqa: S608
    return out


@pytest.mark.parametrize(
    ("key", "locator"),
    [
        ("lava:and:get_sms_mms:1", "get_sms_mms/msg_id=5"),
        # the MMS is three rows; any of them is the one message
        ("lava:and:get_sms_mms_mms:1", "get_sms_mms_mms/msg_id=40"),
        ("lava:and:get_sms_mms_mms:3", "get_sms_mms_mms/msg_id=40"),
        # the RCS message is two rows (text and photo), imported once
        ("lava:and:get_googlemessages:3", "get_googlemessages/rowid=2"),
        # the Google Messages copy of SMS 5 maps to SMS 5, its pair confirmed
        ("lava:and:get_googlemessages:1", "get_sms_mms/msg_id=5"),
        ("lava:and:get_calllog:2", "get_calllog/rowid=2"),
        ("lava:and:contacts:1", "contacts/rowid=1"),
        # the iOS message with two attachments is two rows of one message
        ("lava:ios:sms:3", "sms/message_row_id=12"),
        ("lava:ios:sms:2", "sms/message_row_id=12"),
        # a table name in other case is the same table, as SQLite reads it
        ("lava:ios:SMS:1", "sms/message_row_id=11"),
    ],
)
def test_a_lava_row_maps_to_the_one_record_it_made(case, key, locator):
    conn, phones = case
    ids, why = _map(conn, phones, key)
    assert why == ""
    assert _locators(conn, ids) == {locator}
    assert all(f":{key.split(':')[1]}:" in i for i in ids)  # that phone's record, never the other's


@pytest.mark.parametrize(
    ("key", "why"),
    [
        ("ufdr:source_index:4", "not a LAVA key"),
        ("lava:and:get_sms_mms:0", "not a LAVA key"),
        ("lava:pixel:get_sms_mms:1", "phone 'pixel' is not one the run read"),
        ("lava:and:sms:1", "phone and has no table 'sms'"),
        ("lava:and:get_sms_mms:99", "get_sms_mms has no row 99"),
    ],
)
def test_a_key_that_names_no_row_is_listed_with_why(case, key, why):
    conn, phones = case
    ids, got = _map(conn, phones, key)
    assert ids == []
    assert why in got


def test_a_key_whose_record_is_gone_matches_nothing(case):
    conn, phones = case
    conn.execute("DELETE FROM calls WHERE locator = 'get_calllog/rowid=2' AND source_id = 'and'")
    assert _map(conn, phones, "lava:and:get_calllog:2") == ([], "no record matches")


def test_bar_8_compares_every_table_of_both_phones_and_passes(case):
    conn, phones = case
    got = score_leapp.import_counts(conn, phones, _skipped(conn, phones))
    assert got["pass"]
    a = got["phones"]["and"]["tables"]
    assert a["get_googlemessages"] == {
        "kind": "message", "mabillon": 1, "skipped_confirmed": 1, "reader": 2,
        "null_dedupe_rows": 0, "pass": True,
    }  # fmt: skip
    assert (a["get_sms_mms"]["mabillon"], a["get_sms_mms"]["reader"]) == (3, 3)
    assert (a["get_sms_mms_mms"]["mabillon"], a["get_sms_mms_mms"]["reader"]) == (1, 1)
    assert (a["contacts"]["mabillon"], a["contacts"]["reader"]) == (1, 1)
    i = got["phones"]["ios"]["tables"]
    assert (i["sms"]["mabillon"], i["sms"]["reader"]) == (3, 3)
    assert "get_sms_mms_combined" not in a  # a skip table is never compared
    assert got["phones"]["and"]["skipped_rows_confirmed"] == 1


def test_bar_8_fails_on_a_record_missing_from_one_table(case):
    conn, phones = case
    conn.execute("DELETE FROM calls WHERE locator = 'get_calllog/rowid=1' AND source_id = 'and'")
    got = score_leapp.import_counts(conn, phones, _skipped(conn, phones))
    assert not got["pass"] and not got["phones"]["and"]["pass"]
    assert got["phones"]["ios"]["pass"]
    assert not got["phones"]["and"]["tables"]["get_calllog"]["pass"]


def test_bar_8_fails_on_a_record_from_a_table_the_reader_does_not_count(case):
    conn, phones = case
    # a call beside every counted one, from an app call table the kinds file does not read
    cur = conn.execute("SELECT * FROM calls WHERE locator = 'get_calllog/rowid=1'")
    row = dict(zip([d[0] for d in cur.description], cur.fetchone(), strict=True))
    row |= {"id": "call:and:extra", "locator": "googlevoice_calls/rowid=1"}
    marks = ", ".join("?" * len(row))
    conn.execute(f"INSERT INTO calls ({', '.join(row)}) VALUES ({marks})", list(row.values()))  # noqa: S608
    got = score_leapp.import_counts(conn, phones, _skipped(conn, phones))
    assert got["phones"]["and"]["records_from_tables_not_counted"] == {"googlevoice_calls": 1}
    assert not got["pass"]


def _set_skipped(conn: sqlite3.Connection, sid: str, edit) -> None:  # noqa: ANN001
    (raw,) = conn.execute(
        "SELECT payload_json FROM source_coverage WHERE source_id = ?", (sid,)
    ).fetchone()
    payload = json.loads(raw)
    edit(payload["leapp"]["google_messages_skipped"])
    conn.execute(
        "UPDATE source_coverage SET payload_json = ? WHERE source_id = ?",
        (json.dumps(payload), sid),
    )


def test_a_skipped_copy_paired_with_the_wrong_sms_is_not_confirmed(case):
    # the scorer checks each pair from the LAVA rows: SMS 6 is sent, "on my way"
    conn, phones = case
    _set_skipped(conn, "and", lambda s: s[0].update(same_as="get_sms_mms/msg_id=6"))
    skipped = _skipped(conn, phones)
    assert skipped["and"]["confirmed"] == {}
    assert skipped["and"]["not_confirmed"][0]["why"] == "its direction is not the SMS or MMS's"
    got = score_leapp.import_counts(conn, phones, skipped)
    assert not got["pass"]
    assert _map(conn, phones, "lava:and:get_googlemessages:1") == (
        [],
        "skipped by the importer as a copy whose pair was not confirmed",
    )


def test_one_sms_standing_for_two_skipped_copies_is_never_confirmed(case):
    conn, phones = case
    _set_skipped(conn, "and", lambda s: s.append({**s[0], "locator": "get_googlemessages/rowid=2",
                                                   "rows": [2, 3]}))  # fmt: skip
    skipped = _skipped(conn, phones)
    assert skipped["and"]["confirmed"] == {}
    assert {p["why"] for p in skipped["and"]["not_confirmed"]} == {
        "the SMS or MMS it names stands for another skipped row too"
    }


def test_a_skipped_row_the_table_does_not_hold_is_not_confirmed(case):
    conn, phones = case
    _set_skipped(conn, "and", lambda s: s[0].update(rows=[77]))
    assert _skipped(conn, phones)["and"]["not_confirmed"][0]["why"] == (
        "its rows are not in the table"
    )


def _gm(**over) -> dict:  # noqa: ANN003
    return {"direction": "Incoming", "message": "hi", "message_type": "text/plain",
            "message_timestamp": 100, **over}  # fmt: skip


def _sms(**over) -> dict:  # noqa: ANN003
    return {"type": "Received", "body": "hi", "date": 101, "__table__": "get_sms_mms", **over}


@pytest.mark.parametrize(
    ("parts", "native", "why"),
    [
        ([_gm()], _sms(), None),
        ([_gm(message_timestamp=97)], _sms(), "more than 2 seconds"),
        ([_gm(message="hi!")], _sms(), "its text is not"),
        ([_gm(direction="Outgoing")], _sms(), "its direction is not"),
        ([_gm(direction="Outgoing")], _sms(type="Sent"), None),
        ([_gm(message_timestamp=None)], _sms(), "a time is missing"),
        ([_gm(), _gm(message=None, message_timestamp=101)], _sms(), "the rows disagree on it"),
        # an ALEAPP MMS part whose file was not found holds its path in body: an attachment
        (
            [_gm(message=None, message_type="image/jpeg")],
            {"direction": "Received", "body": "/data/user_de/0/x/app_parts/PART_1_a.jpg",
             "media": "", "date": 100, "__table__": "get_sms_mms_mms"},
            None,
        ),
        (
            [_gm(message=None, message_type="image/jpeg")],
            _sms(body=""),
            "one side has an attachment",
        ),
        ([_gm()], None, "is not one row"),
    ],
)  # fmt: skip
def test_a_pair_is_confirmed_only_when_every_field_agrees(parts, native, why):
    got = score_leapp._pair_problem(parts, native)
    assert got is None if why is None else why in (got or "")


def test_the_kinds_file_reads_exactly_the_tables_the_importer_reads():
    # bar 8 must count every table the importer reads, and nothing it never reads
    kinds, _ = score_leapp.load_kinds(score_leapp.KINDS_FILE)
    importer = {
        k[1].lower() for k in (*leapp.SPECS, *leapp.CHAT_SPECS, *leapp.CALL_SPECS,
                               *leapp.SAME_RECORDS)
    }  # fmt: skip
    assert {dump_lava.fold(t) for t in kinds} == importer
    skips = {dump_lava.fold(t) for t, s in kinds.items() if s["kind"] == "skip"}
    assert skips == {k[1].lower() for k in leapp.SAME_RECORDS}


def _record(tmp_path: Path) -> tuple[dict, dict[str, Path]]:
    zips = {sid: lv.write_zip(tmp_path / f"{sid}.zip") for sid, lv in
            (("and", _android()), ("ios", _ios()))}  # fmt: skip
    phones = [{"source_id": s, "importer": "leapp", "sha256": hickman_run.sha256_file(z)}
              for s, z in zips.items()]  # fmt: skip
    return {"phones": phones}, zips


def test_each_phone_is_the_file_the_run_read(tmp_path):
    record, zips = _record(tmp_path)
    work = tmp_path / "w"
    work.mkdir()
    got = score_leapp.open_phones(record, zips, score_leapp.KINDS_FILE, work)
    assert sorted(got) == ["and", "ios"]
    assert got["and"].reader["leapp_name"] == "ALEAPP"
    with pytest.raises(SystemExit, match=r"is not the ios file the run read"):
        score_leapp.open_phones(
            record, {**zips, "ios": zips["and"]}, score_leapp.KINDS_FILE, tmp_path / "w2"
        )
    with pytest.raises(SystemExit, match=r"exactly the run's phones \['and', 'ios'\]"):
        score_leapp.open_phones(record, {"and": zips["and"]}, score_leapp.KINDS_FILE, work)


def test_a_phone_zip_with_two_databases_is_refused(tmp_path):
    zipped = _android().write_zip(tmp_path / "a.zip")
    with zipfile.ZipFile(zipped, "a") as z:
        z.writestr("other/_lava_artifacts.db", b"")
    folder = tmp_path / "f"
    folder.mkdir()
    with pytest.raises(SystemExit, match="holds 2 _lava_artifacts.db, not one"):
        score_leapp._extract(zipped, folder)


def test_a_run_mixing_leapp_and_ufdr_phones_is_refused():
    assert score_leapp.is_leapp_run({"phones": [{"importer": "leapp"}]})
    assert not score_leapp.is_leapp_run({"phones": [{"importer": "ufdr"}]})
    assert not score_leapp.is_leapp_run({})  # a v4 run.json names no phones
    with pytest.raises(SystemExit, match="mixes LEAPP and UFDR"):
        score_leapp.is_leapp_run({"phones": [{"importer": "leapp"}, {"importer": "ufdr"}]})


# ---------------------------------------------------------------- the whole scorer on a run

CLAIMS = [
    {"claim_id": "C01", "page": 1, "para_no": 1, "claim_type": "communication",
     "text": "On March 1, 2024, the TARGET PHONE called (919) 555-0111."},
    {"claim_id": "C02", "page": 1, "para_no": 2, "claim_type": "content",
     "text": 'SUBJECT-1 wrote "on my way" to SUBJECT-2 on March 1, 2024.'},
]  # fmt: skip


def _gold(claim_id: str, verdict: str, keys: list[str]) -> dict:
    text = next(c["text"] for c in CLAIMS if c["claim_id"] == claim_id)
    return {
        "claim_id": claim_id, "page": 1, "para_no": 1, "text": text, "claim_type": "content",
        "cross_device": False, "gold_verdict": verdict, "core_assumptions": [],
        "key_evidence": keys, "trap": None, "rationale": "synthetic", "labeled_by": "test",
        "labeled_at": "2026-11-20T00:00:00Z",
    }  # fmt: skip


@pytest.fixture(scope="module")
def leapp_run(tmp_path_factory) -> tuple[Path, Path, Path, Path]:
    tmp = tmp_path_factory.mktemp("leapp_score")
    zipped = _android().write_zip(tmp / "and.zip")
    claims = tmp / "claims.jsonl"
    claims.write_text("".join(json.dumps(c) + "\n" for c in CLAIMS), encoding="utf-8")
    run = tmp / "run"
    args = ["--phone", f"and={zipped}", "--claims", str(claims), "--out", str(run), "--fake",
            "--phone-zone", "America/New_York"]  # fmt: skip
    assert hickman_run.main(args) == 0
    keys = tmp / "keys"
    keys.mkdir()
    gold = [
        _gold("C01", "supported", ["lava:and:get_calllog:1", "lava:and:contacts:1"]),
        _gold("C02", "supported", ["lava:and:get_sms_mms:2", "lava:and:get_googlemessages:1",
                                   "lava:and:get_sms_mms:42"]),
    ]  # fmt: skip
    (keys / "gold.jsonl").write_text("".join(json.dumps(g) + "\n" for g in gold), "utf-8")
    return run / "results.zip", keys, zipped, tmp


def test_a_leapp_run_is_scored_with_its_phones_and_bar_8_by_table(leapp_run):
    results, keys, zipped, tmp = leapp_run
    out = tmp / "score"
    args = ["--results", str(results), "--keys", str(keys), "--out", str(out)]
    assert score_hickman.main([*args, "--phone", f"and={zipped}"]) == 0
    s = json.loads((out / "score.json").read_text("utf-8"))
    assert s["scorer_version"] == "1.6.0"
    assert s["source"]["kind"] == "leapp"
    assert s["source"]["phones_sha256"] == {"and": hickman_run.sha256_file(zipped)}
    m = s["key_mapping"]
    assert m["keys"] == 5
    assert m["unmapped"] == [
        {"claim_id": "C02", "key": "lava:and:get_sms_mms:42", "why": "get_sms_mms has no row 42"}
    ]
    assert set(m["groups"]["C02"]) == {"lava:and:get_sms_mms:2", "lava:and:get_googlemessages:1"}
    assert s["import_counts"]["pass"] and s["v4_bars"]["8_import_counts"]["pass"]
    md = (out / "score.md").read_text("utf-8")
    assert md.startswith("# Validation score (LEAPP phones: and)")
    assert "### and: PASS" in md
    assert "| get_googlemessages | message | 1 | 1 | 2 | yes |" in md


def test_a_leapp_run_is_never_scored_with_a_ufdr_dump_or_without_its_phones(leapp_run):
    results, keys, zipped, tmp = leapp_run
    base = ["--results", str(results), "--keys", str(keys), "--out", str(tmp / "s2")]
    with pytest.raises(SystemExit, match="--phone for each phone, not --dump"):
        score_hickman.main([*base, "--dump", str(tmp)])
    with pytest.raises(SystemExit, match="--phone for each phone, not --dump"):
        score_hickman.main(base)
    other = _ios().write_zip(tmp / "other.zip")
    with pytest.raises(SystemExit, match="is not the and file the run read"):
        score_hickman.main([*base, "--phone", f"and={other}"])
    assert not (tmp / "s2" / "score.json").exists()
