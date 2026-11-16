"""The plain LEAPP reader validation v5's bar 8 counts against: a synthetic LAVA output made
here (invented tables, rows and names), never a real LEAPP run."""

import ast
import json
import sqlite3
import sys

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
def lava(tmp_path):
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


def test_counts_come_from_the_tables_with_attachments_deduped(lava):
    r = dump_lava.read(lava, KINDS)
    assert r["counts"] == {"message": 2 + 2, "call": 3, "contact": 1}
    sms = r["tables"]["sms"]
    assert sms["rows"] == 4 and sms["count"] == 2 and sms["null_dedupe_rows"] == 1
    assert r["tables"]["telegram_messages"] == {"kind": "message", "present": False, "count": 0}
    assert r["leapp_name"] == "iLEAPP" and len(r["database_sha256"]) == 64


def test_the_manifest_count_is_reported_never_used(lava):
    r = dump_lava.read(lava, KINDS)
    assert r["tables"]["whatsapp_messages"]["count"] == 2
    assert r["tables"]["whatsapp_messages"]["manifest_record_count"] == 5
    assert r["manifest_count_differs"] == ["whatsapp_messages"]
    assert r["tables_not_counted"] == ["wifi"]


def test_a_bad_kind_or_dedupe_column_stops_the_reader(lava):
    with pytest.raises(SystemExit, match="not one of"):
        dump_lava.read(lava, {"sms": {"kind": "note"}})
    with pytest.raises(SystemExit, match="no column"):
        dump_lava.read(lava, {"sms": {"kind": "message", "dedupe": "row"}})


def test_the_database_is_opened_read_only(lava):
    before = (lava / dump_lava.DATABASE).read_bytes()
    dump_lava.read(lava, KINDS)
    assert (lava / dump_lava.DATABASE).read_bytes() == before


def test_the_reader_imports_only_the_standard_library():
    tree = ast.parse(open(dump_lava.__file__, encoding="utf-8").read())
    names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)
             for a in n.names}  # fmt: skip
    names |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert names <= set(sys.stdlib_module_names), names
