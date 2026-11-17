"""The plain LEAPP reader validation v5's bar 8 counts against: a synthetic LAVA output made
here (invented tables, rows and names), never a real LEAPP run."""

import ast
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from eval.validation import dump_lava

KINDS = {
    "sms": {"kind": "message", "dedupe": "message_row_id"},
    "whatsapp_messages": {"kind": "message"},
    "call_history": {"kind": "call"},
    "contacts": {"kind": "contact"},
    "telegram_messages": {"kind": "message"},  # read by the importer, not written by this run
}


@pytest.fixture
def lava(tmp_path: Path) -> Path:
    db = sqlite3.connect(tmp_path / dump_lava.DATABASE)
    db.executescript(
        "CREATE TABLE sms (message_row_id INTEGER, body TEXT, attachment TEXT);"
        # one message with two attachments is two rows; a row with no id is reported
        " INSERT INTO sms VALUES (1, 'hi', NULL), (2, 'pic', 'a.jpg'), (2, 'pic', 'b.jpg'),"
        " (NULL, 'odd', NULL);"
        " CREATE TABLE whatsapp_messages (ts INTEGER, body TEXT);"
        " INSERT INTO whatsapp_messages VALUES (1700000000, 'yo'), (1700000060, 'ok');"
        " CREATE TABLE call_history (ts INTEGER); INSERT INTO call_history VALUES (1), (2), (3);"
        " CREATE TABLE contacts (name TEXT); INSERT INTO contacts VALUES ('Marc Garage');"
        " CREATE TABLE wifi (ssid TEXT); INSERT INTO wifi VALUES ('home');"
    )
    db.commit()
    db.close()

    def art(name: str, table: str, n: int) -> dict:
        return {"name": name, "tablename": table, "module": "m", "column_map": {},
                "record_count": n, "source_path": "/x"}  # fmt: skip

    manifest = {
        "parser_info": {"leapp_name": "iLEAPP", "leapp_version": "9.9.9"},
        "lava_schema_version": "0.1",
        "profile_used": "synthetic",
        "artifacts": {
            "SMS": [art("SMS", "sms", 4)],
            "WhatsApp": [art("WhatsApp", "whatsapp_messages", 5)],  # manifest says 5, table has 2
            "Calls": [art("Calls", "call_history", 3)],
            "Contacts": [art("Contacts", "contacts", 1)],
            "Wifi": [art("Wifi", "wifi", 1)],
        },
    }
    (tmp_path / dump_lava.MANIFEST).write_text(json.dumps(manifest), "utf-8")
    return tmp_path


def test_counts_come_from_the_tables_with_attachments_deduped(lava: Path) -> None:
    r = dump_lava.read(lava, KINDS)
    assert r["counts"] == {"message": 2 + 2, "call": 3, "contact": 1}
    sms = r["tables"]["sms"]
    assert sms["rows"] == 4 and sms["count"] == 2 and sms["null_dedupe_rows"] == 1
    assert r["tables"]["telegram_messages"] == {"kind": "message", "present": False, "count": 0}
    assert r["leapp_name"] == "iLEAPP" and len(r["database_sha256"]) == 64


def test_the_manifest_count_is_reported_never_used(lava: Path) -> None:
    r = dump_lava.read(lava, KINDS)
    assert r["tables"]["whatsapp_messages"]["count"] == 2
    assert r["tables"]["whatsapp_messages"]["manifest_record_count"] == 5
    assert r["manifest_count_differs"] == ["whatsapp_messages"]
    assert r["tables_not_counted"] == ["wifi"]


def test_a_bad_kind_or_dedupe_column_stops_the_reader(lava: Path) -> None:
    with pytest.raises(SystemExit, match="not one of"):
        dump_lava.read(lava, {"sms": {"kind": "note"}})
    with pytest.raises(SystemExit, match="no column"):
        dump_lava.read(lava, {"sms": {"kind": "message", "dedupe": "row"}})


def test_the_database_is_opened_read_only(lava: Path) -> None:
    before = (lava / dump_lava.DATABASE).read_bytes()
    dump_lava.read(lava, KINDS)
    assert (lava / dump_lava.DATABASE).read_bytes() == before


def test_the_reader_imports_only_the_standard_library() -> None:
    tree = ast.parse(open(dump_lava.__file__, encoding="utf-8").read())
    names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)
             for a in n.names}  # fmt: skip
    names |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert names <= set(sys.stdlib_module_names), names


def test_a_folder_name_with_uri_marks_still_opens_read_only(lava: Path, tmp_path: Path) -> None:
    # "?" cannot be in a Windows folder name; "#" and "%" can, and break a URI as well
    odd = tmp_path / ("phone#1 x%20" if sys.platform == "win32" else "phone#1 ?x%20")
    odd.mkdir()
    for name in (dump_lava.MANIFEST, dump_lava.DATABASE):
        (odd / name).write_bytes((lava / name).read_bytes())
    before = sorted(p.name for p in odd.parent.iterdir())
    assert dump_lava.read(odd, KINDS)["counts"]["call"] == 3
    assert sorted(p.name for p in odd.parent.iterdir()) == before  # no stray file made


def test_a_composite_dedupe_key_and_a_skipped_table(lava: Path) -> None:
    db = sqlite3.connect(lava / dump_lava.DATABASE)
    db.executescript(
        "CREATE TABLE parts (conv INTEGER, ts INTEGER, dir TEXT, body TEXT);"
        # one message in two parts, a second message, and a part with no timestamp
        " INSERT INTO parts VALUES (1, 100, 'in', 'a'), (1, 100, 'in', 'b'), (1, 101, 'out', 'c'),"
        " (2, NULL, 'in', 'd');"
        " CREATE TABLE combined (body TEXT); INSERT INTO combined VALUES ('hi'), ('pic');"
    )
    db.commit()
    db.close()
    kinds = {"parts": {"kind": "message", "dedupe": ["conv", "ts", "dir"]},
             "combined": {"kind": "skip"}}  # fmt: skip
    r = dump_lava.read(lava, kinds)
    assert r["tables"]["parts"]["count"] == 2 and r["tables"]["parts"]["null_dedupe_rows"] == 1
    assert r["tables"]["combined"]["count"] == 2
    assert r["counts"]["message"] == 2  # the skipped table repeats another and is not counted


def test_table_names_match_whatever_their_case_and_no_written_table_goes_unreported(
    lava: Path,
) -> None:
    db = sqlite3.connect(lava / dump_lava.DATABASE)
    db.execute("CREATE TABLE stray_chats (body TEXT)")  # written, but no manifest entry
    db.execute("INSERT INTO stray_chats VALUES ('x')")
    db.commit()
    db.close()
    kinds = {
        "SMS": {"kind": "message", "dedupe": "MESSAGE_ROW_ID"},
        "Call_History": {"kind": "call"},
    }
    r = dump_lava.read(lava, kinds)
    assert r["counts"] == {"message": 2, "call": 3, "contact": 0}
    assert r["tables"]["SMS"]["present"] and r["tables"]["SMS"]["in_manifest"]
    assert r["tables_not_counted"] == ["contacts", "stray_chats", "whatsapp_messages", "wifi"]
    assert r["tables_not_in_manifest"] == ["stray_chats"]
