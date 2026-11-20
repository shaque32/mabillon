"""The LEAPP side of the validation scorer (eval/validation/score_leapp.py), on synthetic LAVA
output imported by the real LEAPP importer: keys by LAVA row, and bar 8 table by table."""

from __future__ import annotations

import json
import sqlite3
import zipfile
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

from core.db import apply_schema
from core.ingest import leapp
from core.ingest.leapp import LeappImporter
from eval.synthetic.leapp import Lava
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


def _map(conn: sqlite3.Connection, phones: dict[str, LavaPhone], key: str) -> tuple[list[str], str]:
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
        "null_dedupe_rows": 0, "empty_key_adjustment": 0, "pass": True,
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


def _set_skipped(
    conn: sqlite3.Connection, sid: str, edit: Callable[[list[dict[str, Any]]], object]
) -> None:
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


ALICE = "+19195550111"
BOB = "+19195550122"


def _gm(**over: object) -> dict[str, object]:
    return {"direction": "Incoming", "message": "hi", "message_type": "text/plain",
            "message_timestamp": 100, "message_sender": ALICE,
            "other_participantconversation_name": "Alice Ames", **over}  # fmt: skip


def _sms(**over: object) -> tuple[str, list[dict[str, object]]]:
    return "get_sms_mms", [{"type": "Received", "body": "hi", "date": 101, "address": ALICE,
                            **over}]  # fmt: skip


def _mms(
    *parts: tuple[str | None, str | None], **over: object
) -> tuple[str, list[dict[str, object]]]:
    """An MMS as ALEAPP writes it: one row per part (body, media)."""
    row = {"direction": "Received", "date": 100, "from_address": ALICE, "to_address": "+1919555",
           **over}  # fmt: skip
    return "get_sms_mms_mms", [{**row, "body": b, "media": m} for b, m in parts]


PATH = "/data/user_de/0/com.android.providers.telephony/app_parts/PART_1_a.jpg"


@pytest.mark.parametrize(
    ("parts", "native", "why"),
    [
        ([_gm()], _sms(), None),
        ([_gm(message_timestamp=97)], _sms(), "more than 2 seconds"),
        ([_gm(message="hi!")], _sms(), "its text is not"),
        # runs of white space read as one space, as the importer compares text
        ([_gm(message="see  you\nsoon")], _sms(body="see you soon"), None),
        ([_gm(direction="Outgoing")], _sms(), "its direction is not"),
        ([_gm(direction="Outgoing", other_participantconversation_name="(919) 555-0111")],
         _sms(type="Sent"), None),
        ([_gm(message_timestamp=None)], _sms(), "a time is missing"),
        ([_gm(), _gm(message=None, message_timestamp=101)], _sms(), "the rows disagree on it"),
        # two texts in one group may be two messages: the importer never pairs it
        ([_gm(), _gm(message="there")], _sms(body="hi there"), "joins several texts"),
        # an ALEAPP MMS part whose file was not found holds its path in body: an attachment
        ([_gm(message=None, message_type="image/jpeg")], _mms((PATH, None)), None),
        ([_gm(message=None, message_type="image/jpeg")],
         _mms(("/storage/emulated/0/x/parts/PART_9.jpg", None)), None),
        ([_gm(message=None, message_type="image/jpeg")], _sms(body=""),
         "has 1 attachment(s), the SMS or MMS 0"),
        # a multi-part MMS: its text parts and its media parts, every row of the msg_id
        ([_gm(message="look"), _gm(message=None, message_type="image/jpeg",
                                    attachment_location="/d/p/c.jpg"),
          _gm(message=None, message_type="image/png")],
         _mms(("look", None), (None, "media/abc.jpg"), (PATH, None)), None),
        ([_gm(message="look"), _gm(message=None, message_type="image/jpeg")],
         _mms(("look", None), (None, "media/abc.jpg"), (PATH, None)),
         "has 1 attachment(s), the SMS or MMS 2"),
        # the other party: a received message's sender against the SMS's address
        ([_gm(message_sender=BOB)], _sms(), "its other party is not"),
        ([_gm(message_sender="Bob")], _sms(), "cannot be compared"),
        ([_gm(message_sender="(919) 555-0111")], _sms(), None),
        ([_gm()], _mms(("hi", None), from_address="insert-address-token"), "cannot be compared"),
        # a sent message named by display name: the phone's contacts give its number
        ([_gm(direction="Outgoing")], _sms(type="Sent"), None),
        ([_gm(direction="Outgoing", other_participantconversation_name="Bob Barr")],
         _sms(type="Sent"), "cannot be compared"),
        ([_gm(direction="Outgoing")], _sms(type="Sent", address=BOB), "its other party is not"),
        ([_gm(direction="Outgoing", other_participantconversation_name=ALICE)],
         _mms(("hi", None), direction="Sent", to_address=f"{ALICE},{BOB}"), "cannot be compared"),
        # times in whole seconds, as the importer compares them
        ([_gm(message_timestamp=100.1)], _sms(date=102.9), None),
        ([_gm(message_timestamp=100.9)], _sms(date=103.0), "more than 2 seconds"),
        # every part of an MMS within the limit
        ([_gm()], ("get_sms_mms_mms", [{**_mms(("hi", None))[1][0]},
                                       {**_mms((None, None))[1][0], "date": 110}]),
         "more than 2 seconds"),
        # an MMS's direction is its Direction column, never another column named type
        ([_gm()], _mms(("hi", None), type="Sent"), None),
        ([_gm()], _sms(type=None, direction="Received"), "its direction is not"),
        # a part type outside text/ (the importer's test is case-sensitive) is an attachment
        ([_gm(message_type="Text/Plain")], _sms(), "has 1 attachment(s), the SMS or MMS 0"),
        ([_gm()], None, "is not in the LAVA tables"),
        ([_gm()], ("get_sms_mms", []), "is not in the LAVA tables"),
        ([_gm()], ("get_sms_mms", [_sms()[1][0], _sms()[1][0]]), "is not in the LAVA tables"),
    ],
)  # fmt: skip
def test_a_pair_is_confirmed_only_when_every_field_agrees(parts, native, why):
    contacts = {"Alice Ames": [score_leapp._handle(ALICE) or ""]}
    got = score_leapp._pair_problem(parts, native, contacts)
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


def _zip(tmp_path: Path, members: dict[str, bytes]) -> Path:
    path = tmp_path / "p.zip"
    with zipfile.ZipFile(path, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)
    return path


def test_the_phone_zip_is_read_as_lava_names_its_files(tmp_path):
    manifest, data = _android().build()
    good = data
    other = _ios().build()[1]
    # a .json manifest, and the database its lava_db_name names beside it; a stale default-named
    # database elsewhere in the zip is never the one read
    m = json.dumps({**manifest, "lava_db_name": "x.db"}).encode()
    zipped = _zip(tmp_path, {"out/_lava_data.json": m, "out/x.db": good,
                             "old/_lava_artifacts.db": other})  # fmt: skip
    folder = tmp_path / "f"
    folder.mkdir()
    score_leapp._extract(zipped, folder)
    assert (folder / dump_lava.DATABASE).read_bytes() == good
    assert json.loads((folder / dump_lava.MANIFEST).read_text("utf-8"))["lava_db_name"] == "x.db"


@pytest.mark.parametrize(
    ("members", "why"),
    [
        ({"a/_lava_data.lava": b"{}", "b/_lava_data.json": b"{}"}, "holds 2 LEAPP manifests"),
        ({"a/_lava_artifacts.db": b""}, "holds 0 LEAPP manifests"),
        ({"a/_lava_data.lava": b"{}", "_lava_artifacts.db": b""}, "but not _lava_artifacts.db"),
        ({"a/_lava_data.lava": b"[1]", "a/_lava_artifacts.db": b""}, "is not a LEAPP manifest"),
        ({"a/_lava_data.lava": b"\xff", "a/_lava_artifacts.db": b""}, "is not a LEAPP manifest"),
    ],
)
def test_a_phone_zip_without_one_manifest_and_its_database_is_refused(tmp_path, members, why):
    folder = tmp_path / "f"
    folder.mkdir()
    with pytest.raises(SystemExit, match=why):
        score_leapp._extract(_zip(tmp_path, members), folder)


def test_a_database_over_the_size_limit_is_refused_before_it_is_unpacked(tmp_path, monkeypatch):
    zipped = _android().write_zip(tmp_path / "a.zip")
    monkeypatch.setattr(score_leapp, "MAX_DB_BYTES", 1000)
    folder = tmp_path / "f"
    folder.mkdir()
    with pytest.raises(SystemExit, match="unpacks to .* bytes, over 1,000"):
        score_leapp._extract(zipped, folder)
    assert not (folder / dump_lava.DATABASE).exists()


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
    assert "| get_googlemessages | message | 1 | 1 | 2 | +0 | yes |" in md


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


# ---------------------------------------------------------------- review findings on #271


def _one_phone(tmp_path: Path, lv: Lava) -> tuple[sqlite3.Connection, dict[str, LavaPhone]]:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    apply_schema(conn)
    zipped = lv.write_zip(tmp_path / "and.zip")
    LeappImporter(source_id="and").import_source(zipped, conn)
    return conn, {"and": _phone(tmp_path, "and", zipped)}


def test_the_google_messages_copy_of_a_multi_part_mms_is_confirmed(tmp_path):
    # MMS 40 is three rows (text, media, a part's path); its Google Messages copy is three
    # parts with the same text and two attachments, a second later
    lv = _android()
    for text, kind, loc in (("look", "text/plain", None), (None, "image/jpeg", "/d/p/a.jpg"),
                            (None, "image/jpeg", None)):  # fmt: skip
        lv.add(
            "get_googleMessages",
            **{"Message Timestamp": "2024-03-02T09:00:01Z", "Direction": "Incoming",
               "Message Sender": "+19195550111", "Other Participant/Conversation Name": "Alice",
               "Message": text, "Message Type": kind, "Attachment Location": loc,
               "Conversation ID": "9"},
        )  # fmt: skip
    conn, phones = _one_phone(tmp_path, lv)
    skipped = _skipped(conn, phones)
    assert sorted(skipped["and"]["confirmed"].values()) == [
        "get_sms_mms/msg_id=5",
        *["get_sms_mms_mms/msg_id=40"] * 3,
    ]
    assert skipped["and"]["not_confirmed"] == []
    got = score_leapp.import_counts(conn, phones, skipped)
    assert got["pass"], got["phones"]["and"]["tables"]["get_googlemessages"]
    ids, why = _map(conn, phones, "lava:and:get_googlemessages:6")
    assert why == "" and _locators(conn, ids) == {"get_sms_mms_mms/msg_id=40"}


def test_a_skipped_copy_paired_with_another_partys_sms_is_not_confirmed(case):
    # SMS 5 ("where are you", from Alice) stands for the Google Messages copy; the same text
    # from another number is not that message, however close in time
    conn, phones = case
    with closing(sqlite3.connect(phones["and"].folder / dump_lava.DATABASE)) as db:
        db.execute("UPDATE get_sms_mms SET address = '+19195550122' WHERE msg_id = '5'")
        db.commit()
    skipped = _skipped(conn, phones)
    assert skipped["and"]["not_confirmed"][0]["why"] == "its other party is not the SMS or MMS's"
    assert not score_leapp.import_counts(conn, phones, skipped)["pass"]


def test_rows_with_an_empty_dedupe_value_count_as_the_importer_reads_them(tmp_path):
    lv = _android()
    # an SMS with no MSG ID is a record of its own, named by its row id
    lv.add(
        "get_sms_mms",
        **{
            "Date": "2024-03-04T12:00:00Z",
            "Type": "Received",
            "Address": "+19195550111",
            "Body": "no id",
            "Thread ID": "2",
        },
    )
    # a two-part RCS message with no sender is one message, its parts grouped as the importer
    # groups them (an empty value is one value)
    for text, kind, loc in (("pic", "text/plain", None), (None, "image/jpeg", "/d/p/z.jpg")):
        lv.add(
            "get_googleMessages",
            **{"Message Timestamp": "2024-03-05T08:00:00Z", "Direction": "Incoming",
               "Message Sender": None, "Other Participant/Conversation Name": "Group",
               "Message": text, "Message Type": kind, "Attachment Location": loc,
               "Conversation ID": "12"},
        )  # fmt: skip
    conn, phones = _one_phone(tmp_path, lv)
    got = score_leapp.import_counts(conn, phones, _skipped(conn, phones))
    t = got["phones"]["and"]["tables"]
    assert (t["get_sms_mms"]["null_dedupe_rows"], t["get_sms_mms"]["empty_key_adjustment"]) == (
        1,
        1,
    )
    assert t["get_googlemessages"]["empty_key_adjustment"] == 1
    assert got["pass"], t
    # a key on the second part names the message the first part named
    ids, why = _map(conn, phones, "lava:and:get_googlemessages:5")
    assert why == "" and _locators(conn, ids) == {"get_googlemessages/rowid=4"}
    ids, why = _map(conn, phones, "lava:and:get_sms_mms:4")
    assert why == "" and _locators(conn, ids) == {"get_sms_mms/rowid=4"}


def test_a_real_column_named_rowid_is_never_a_row_id_locator():
    rows = [{score_leapp.ROWID: 3, "rowid": "7", "OID": "8", "msg_id": "5"}]
    got = score_leapp._candidates("t", rows)
    assert got == {"t/rowid=3", "t/msg_id=5"}


def test_repeated_empty_dedupe_values_are_each_a_record_and_a_lost_one_fails(tmp_path):
    # three SMS rows with msg_id "", " " and NULL: the importer makes three records, the reader
    # counts "" and " " as two values and leaves NULL out
    lv = _android()
    for i, mid in enumerate(("", " ", None)):
        lv.add("get_sms_mms", **{"Date": f"2024-03-04T12:0{i}:00Z", "Type": "Received",
                                 "Address": "+19195550111", "Body": f"empty {i}",
                                 "MSG ID": mid, "Thread ID": "2"})  # fmt: skip
    conn, phones = _one_phone(tmp_path, lv)
    got = score_leapp.import_counts(conn, phones, _skipped(conn, phones))
    t = got["phones"]["and"]["tables"]["get_sms_mms"]
    assert (t["mabillon"], t["reader"], t["empty_key_adjustment"]) == (6, 5, 1)
    assert got["pass"]
    conn.execute("DELETE FROM messages WHERE source_id = 'and' AND locator = 'get_sms_mms/rowid=5'")
    assert not score_leapp.import_counts(conn, phones, _skipped(conn, phones))["pass"]


@pytest.mark.parametrize("rows", [[1, "2"], [1, None], [True], "1"])
def test_a_skipped_entry_whose_rows_are_not_row_ids_is_not_confirmed(case, rows):
    conn, phones = case
    _set_skipped(conn, "and", lambda s: s[0].update(rows=rows))
    assert _skipped(conn, phones)["and"]["not_confirmed"][0]["why"] == (
        "its rows are not all row ids"
    )


def test_a_key_on_a_table_the_importer_does_not_read_says_so(case):
    conn, phones = case
    ids, why = _map(conn, phones, "lava:ios:wifinetworks:1")
    assert ids == [] and "a table the importer does not read" in why


def test_a_phone_path_that_is_not_a_zip_file_is_refused_cleanly(tmp_path):
    record, zips = _record(tmp_path)
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    record["phones"][0]["sha256"] = hickman_run.sha256_file(bad)
    with pytest.raises(SystemExit, match="is not a zip file"):
        score_leapp.open_phones(
            record, {**zips, "and": bad}, score_leapp.KINDS_FILE, tmp_path / "w"
        )
    with pytest.raises(SystemExit, match="--phone and: .* is not a file"):
        score_leapp.open_phones(
            record, {**zips, "and": tmp_path / "missing.zip"}, score_leapp.KINDS_FILE,
            tmp_path / "w2",
        )  # fmt: skip
