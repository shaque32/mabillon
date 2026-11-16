"""iLEAPP and ALEAPP output import (core/ingest/leapp.py). UNVERIFIED format support: every
LAVA pair here is synthetic (eval/synthetic/leapp.py), written the way LEAPP's lavafuncs.py
writes one."""

from __future__ import annotations

import sqlite3
import zipfile
from pathlib import Path

import pytest

from core.db import apply_schema
from core.ingest import coverage, leapp, tested
from core.ingest.leapp import LeappImporter, looks_like_leapp_zip
from core.ingest.pick import report_importer
from core.ingest.ufdr import UfdrImporter
from eval.synthetic.leapp import Lava

OWNER = "+19195550100"
ALICE = "+19195550111"
BOB = "bob@example.com"


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    apply_schema(conn)
    return conn


def _ios() -> Lava:
    lv = Lava(leapp="iLEAPP")
    # one received message, one sent message with two attachments (two rows), one group message
    lv.add(
        "sms",
        **{
            "Message Timestamp": "2024-02-01T15:04:05Z",
            "From Me": "0",
            "Sender": ALICE,
            "Chat Contact ID": ALICE,
            "Message": "meet at 6",
            "Chat Participants": ALICE,
            "Service": "iMessage",
            "Destination Caller ID": OWNER,
            "Message Row ID": "11",
            "Chat ID": "3",
        },
    )
    for name in ("a.jpg", "b.jpg"):
        lv.add(
            "sms",
            **{
                "Message Timestamp": "2024-02-01T15:06:00Z",
                "From Me": "1",
                "Chat Contact ID": ALICE,
                "Message": "ok\ufffc",  # iOS marks where the attachment sits
                "Chat Participants": ALICE,
                "Service": "iMessage",
                "Account": f"P:{OWNER}",
                "Destination Caller ID": OWNER,
                "Attachment Name": name,
                "Message Row ID": "12",
                "Chat ID": "3",
            },
        )
    lv.add(
        "sms",
        **{
            "Message Timestamp": "2024-02-02T10:00:00Z",
            "From Me": "0",
            "Sender": BOB,
            "Chat Contact ID": "chat123",
            "Chat Name": "Crew",
            "Message": "hello all",
            "Chat Participants": f"{ALICE},{BOB}",
            "Service": "iMessage",
            "Destination Caller ID": OWNER,
            "Message Row ID": "13",
            "Chat ID": "4",
        },
    )
    lv.add(
        "callHistory",
        **{
            "Starting Timestamp": "2024-02-01T16:00:00Z",
            "Service Provider": "com.apple.Telephony",
            "Call Type": "Phone Call",
            "Call Direction": "Outgoing",
            "Phone Number": ALICE,
            "Answered": "Yes",
            "Call Duration": "00:02:05",
        },
    )
    lv.add(
        "callHistory",
        **{
            "Starting Timestamp": "2024-02-01T17:00:00Z",
            "Service Provider": "com.apple.Telephony",
            "Call Type": "Phone Call",
            "Call Direction": "Incoming",
            "Phone Number": ALICE,
            "Answered": "No",
            "Call Duration": "00:00:00",
        },
    )
    lv.add(
        "addressBook",
        **{
            "First Name": "Alice",
            "Last Name": "Ames",
            "Phone Numbers": f"Mobile: {ALICE}\rhome: +19195550112",
            "Email addresses": "work: alice@example.com",
        },
    )
    lv.add("wifiNetworks", **{"SSID": "home"})
    return lv


def _android() -> Lava:
    lv = Lava(leapp="ALEAPP")
    lv.add(
        "get_sms_mms",
        **{
            "Date": "2024-03-01T12:00:00Z",
            "Type": "Received",
            "Address": ALICE,
            "Body": "where are you",
            "MSG ID": "5",
            "Thread ID": "2",
        },
    )
    lv.add(
        "get_sms_mms",
        **{
            "Date": "2024-03-01T12:01:00Z",
            "Type": "Sent",
            "Address": ALICE,
            "Body": "on my way",
            "MSG ID": "6",
            "Thread ID": "2",
        },
    )
    lv.add(
        "get_sms_mms",
        **{
            "Date": "2024-03-01T12:02:00Z",
            "Type": "Draft",
            "Address": ALICE,
            "Body": "never sent",
            "MSG ID": "7",
            "Thread ID": "2",
        },
    )
    for body, media in (
        ("look", None),
        (None, "media/abc.jpg"),
        # a part whose file ALEAPP did not find: its path is in Body, never text
        ("/data/user_de/0/com.android.providers.telephony/app_parts/PART_1_x.jpg", None),
    ):
        lv.add(
            "get_sms_mms_mms",
            **{
                "Date": "2024-03-02T09:00:00Z",
                "Direction": "Received",
                "From Address": ALICE,
                "Body": body,
                "Media": media,
                "MSG ID": "40",
                "Thread ID": "2",
                "To Address": OWNER,
            },
        )
    # Google Messages: a copy of SMS 5 one second later (skipped), and an RCS message only here
    lv.add(
        "get_googleMessages",
        **{
            "Message Timestamp": "2024-03-01T12:00:01Z",
            "Direction": "Incoming",
            "Message Sender": ALICE,
            "Other Participant/Conversation Name": "Alice Ames",
            "Message": "where are you",
            "Message Type": "text/plain",
            "Conversation ID": "9",
        },
    )
    for text, kind, loc in (("photo", "text/plain", None), (None, "image/jpeg", "/d/p/c.jpg")):
        lv.add(
            "get_googleMessages",
            **{
                "Message Timestamp": "2024-03-03T08:00:00Z",
                "Direction": "Outgoing",
                "Message Sender": OWNER,
                "Other Participant/Conversation Name": "(919) 555-0111",
                "Message": text,
                "Message Type": kind,
                "Attachment Location": loc,
                "Conversation ID": "9",
            },
        )
    lv.add(
        "get_calllog",
        **{
            "Call Date": "2024-03-01T13:00:00Z",
            "Phone Account Address": OWNER,
            "Partner": ALICE,
            "Raw Call Type (as stored)": "1",
            "Type": "Incoming<i>icon</i>",
            "Duration in Secs": "42",
            "Deleted": "0",
        },
    )
    lv.add(
        "get_calllog",
        **{
            "Call Date": "2024-03-01T14:00:00Z",
            "Phone Account Address": OWNER,
            "Partner": ALICE,
            "Raw Call Type (as stored)": "5",  # rejected on the phone
            "Duration in Secs": "0",
            "Deleted": "0",
        },
    )
    lv.add(
        "get_calllog",
        **{
            "Call Date": "2024-03-01T15:00:00Z",
            "Phone Account Address": OWNER,
            "Partner": ALICE,
            "Raw Call Type (as stored)": "6",  # blocked
            "Duration in Secs": "0",
            "Deleted": "0",
        },
    )
    lv.add(
        "contacts",
        **{
            "Mimetype": "vnd.android.cursor.item/phone_v2",
            "Data 1": ALICE,
            "Display Name": "Alice Ames",
            "Phone Number": ALICE,
        },
    )
    return lv


# ---------------------------------------------------------------- no source kind needed


def test_pick_reads_a_leapp_zip_and_leaves_ufdr_alone(tmp_path: Path) -> None:
    z = _ios().write_zip(tmp_path / "ios_leapp.zip")
    assert looks_like_leapp_zip(z)
    assert report_importer(z) is LeappImporter
    plain = tmp_path / "package.zip"
    with zipfile.ZipFile(plain, "w") as zf:
        zf.writestr("report.xml", "<project/>")
    assert not looks_like_leapp_zip(plain)
    assert report_importer(plain) is UfdrImporter


def test_refuses_a_zip_without_one_manifest_and_its_database(tmp_path: Path) -> None:
    bad = tmp_path / "no_db.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr(
            "out/_lava_data.lava", '{"artifacts": {}, "parser_info": {"leapp_name": "iLEAPP"}}'
        )
    with pytest.raises(ValueError, match="not _lava_artifacts.db"):
        LeappImporter(source_id="x").import_source(bad, _db())
    two = tmp_path / "two.zip"
    with zipfile.ZipFile(two, "w") as zf:
        zf.writestr("a/_lava_data.lava", "{}")
        zf.writestr("b/_lava_data.lava", "{}")
    with pytest.raises(ValueError, match="2 LEAPP manifests"):
        LeappImporter(source_id="x").import_source(two, _db())


def test_refuses_another_leapp_tool(tmp_path: Path) -> None:
    lv = _ios()
    lv.leapp = "RLEAPP"
    z = lv.write_zip(tmp_path / "r.zip")
    with pytest.raises(ValueError, match="iLEAPP and\\s+ALEAPP output only|ALEAPP output only"):
        LeappImporter(source_id="x").import_source(z, _db())


def test_times_are_leapp_utc_epochs_kept_raw() -> None:
    ts = leapp._time(1706799845)
    assert ts.utc is not None and ts.utc.isoformat() == "2024-02-01T15:04:05+00:00"
    assert ts.offset_min == 0 and ts.raw == "1706799845 (LEAPP UTC epoch)"
    bad = leapp._time("not a time")
    assert bad.utc is None and bad.raw == "not a time"
    assert leapp._time("").utc is None


def test_format_notice_names_the_tool_and_is_not_tested() -> None:
    check = tested.at_import("leapp", "s", "f.zip", "2026.4.7-dev", "ALEAPP")
    assert check.format == "ALEAPP output"
    assert not check.tested
    assert "Untested export format" in check.notice


# ---------------------------------------------------------------- import


def test_ios_messages_calls_and_contacts(tmp_path: Path) -> None:
    conn = _db()
    src = LeappImporter(source_id="ios").import_source(_ios().write_zip(tmp_path / "i.zip"), conn)
    assert src.kind.value == "leapp" and src.tool_name == "iLEAPP"
    assert src.fidelity.value == "full_extraction"
    # iMessage and SMS take the app every importer gives a phone's own messages
    assert conn.execute("SELECT DISTINCT app FROM threads").fetchall() == [("Native Messages",)]
    msgs = conn.execute(
        "SELECT m.locator, m.direction, m.body, m.ts_utc, m.ts_offset_min, a.identifier"
        " FROM messages m LEFT JOIN accounts a ON a.id = m.sender_account_id ORDER BY m.locator"
    ).fetchall()
    assert msgs == [
        ("sms/message_row_id=11", "incoming", "meet at 6", "2024-02-01T15:04:05Z", 0, ALICE),
        ("sms/message_row_id=12", "outgoing", "ok", "2024-02-01T15:06:00Z", 0, OWNER),
        ("sms/message_row_id=13", "incoming", "hello all", "2024-02-02T10:00:00Z", 0, BOB),
    ]
    # two attachment rows are one message with two attachments
    assert conn.execute("SELECT file_name FROM attachments ORDER BY 1").fetchall() == [
        ("a.jpg",),
        ("b.jpg",),
    ]
    # the owner's line is the owner's account, and receives incoming messages
    own = conn.execute("SELECT identifier FROM accounts WHERE device_id IS NOT NULL").fetchall()
    assert own == [(OWNER,)]
    recips = conn.execute(
        "SELECT m.locator, a.identifier FROM message_recipients r JOIN messages m"
        " ON m.id = r.message_id JOIN accounts a ON a.id = r.account_id ORDER BY 1, 2"
    ).fetchall()
    assert recips == [
        ("sms/message_row_id=11", OWNER),
        ("sms/message_row_id=12", ALICE),
        ("sms/message_row_id=13", OWNER),
        ("sms/message_row_id=13", ALICE),
    ]
    assert conn.execute("SELECT title FROM threads ORDER BY title").fetchall() == [
        (ALICE,),
        ("Crew",),
    ]
    calls = conn.execute(
        "SELECT c.app, c.direction, c.duration_s, f.identifier, t.identifier FROM calls c"
        " LEFT JOIN accounts f ON f.id = c.from_account_id"
        " LEFT JOIN accounts t ON t.id = c.to_account_id ORDER BY c.ts_utc"
    ).fetchall()
    assert calls == [
        ("unknown", "outgoing", 125, None, ALICE),
        ("unknown", "missed", 0, ALICE, None),
    ]
    contacts = conn.execute("SELECT name, identifier FROM contacts ORDER BY identifier").fetchall()
    assert contacts == [
        ("Alice Ames", ALICE),
        ("Alice Ames", "+19195550112"),
        ("Alice Ames", "alice@example.com"),
    ]


def test_android_messages_calls_and_contacts(tmp_path: Path) -> None:
    conn = _db()
    z = _android().write_zip(tmp_path / "a.zip")
    LeappImporter(source_id="and").import_source(z, conn)
    msgs = conn.execute(
        "SELECT m.locator, t.app, m.direction, m.body FROM messages m"
        " JOIN threads t ON t.id = m.thread_id ORDER BY m.locator"
    ).fetchall()
    nm = "Native Messages"
    assert msgs == [
        # the Google Messages copy of SMS 5 is skipped; the RCS message is imported once
        ("get_googlemessages/rowid=2", nm, "outgoing", "photo"),
        ("get_sms_mms/msg_id=5", nm, "incoming", "where are you"),
        ("get_sms_mms/msg_id=6", nm, "outgoing", "on my way"),
        ("get_sms_mms/msg_id=7", nm, "unknown", "never sent"),  # a draft is never "sent"
        ("get_sms_mms_mms/msg_id=40", nm, "incoming", "look"),
    ]
    assert conn.execute("SELECT file_name FROM attachments ORDER BY 1").fetchall() == [
        ("PART_1_x.jpg",),
        ("c.jpg",),
        ("media/abc.jpg",),
    ]
    rcs = conn.execute(
        "SELECT a.identifier FROM message_recipients r JOIN accounts a ON a.id = r.account_id"
        " WHERE r.message_id LIKE '%googlemessages%'"
    ).fetchall()
    assert rcs == [("(919) 555-0111",)]
    calls = conn.execute(
        "SELECT c.direction, c.duration_s, f.identifier, t.identifier, c.deleted_flag FROM calls c"
        " LEFT JOIN accounts f ON f.id = c.from_account_id"
        " LEFT JOIN accounts t ON t.id = c.to_account_id ORDER BY c.ts_utc"
    ).fetchall()
    assert calls == [
        ("incoming", 42, ALICE, OWNER, 0),
        ("missed", 0, ALICE, OWNER, 0),  # rejected: placed by the other side, not answered
        ("unknown", 0, None, None, 0),  # blocked
    ]
    s = coverage.summary(conn, "and")
    assert s is not None
    codes = {i.code for i in s.items}
    assert "format_unverified" in codes
    for code in (
        "not_sent_or_received",
        "media_file_not_in_extraction",
        "call_type_not_incoming_outgoing_or_missed",
        "rows_skipped_same_as_an_sms_or_mms_message",
    ):
        assert code in codes, code
    payload = coverage.load(conn, "and").payload
    tables = {t["name"]: t for t in payload["tables"]}
    assert tables["SMS Messages"]["flag_counts"]["not_sent_or_received"] == 1
    assert tables["MMS Messages"]["flag_counts"]["rows_grouped_into_one_message"] == 2
    assert tables["GoogleMessages"]["rows_skipped"] == {"same_as_an_sms_or_mms_message": 1}
    # each skipped Google Messages message names the SMS it matched, for a reader to re-check
    assert payload["leapp"]["google_messages_skipped"] == [
        {
            "locator": "get_googlemessages/rowid=1",
            "rows": [1],
            "same_as": "get_sms_mms/msg_id=5",
            "seconds_apart": -1,
        }
    ]


def test_artifacts_not_read_are_listed_so_absence_is_never_assumed(tmp_path: Path) -> None:
    conn = _db()
    LeappImporter(source_id="ios").import_source(_ios().write_zip(tmp_path / "i.zip"), conn)
    payload = coverage.load(conn, "ios").payload
    assert [e["name"] for e in payload["not_imported"]] == ["Wifi Networks"]
    s = coverage.summary(conn, "ios")
    item = next(i for i in s.items if i.code == "not_imported")
    text = "".join(t for t, _q in item.parts)
    assert "Wifi Networks" in text and "not shown to be absent" in text


def test_a_profile_run_cannot_show_absence(tmp_path: Path) -> None:
    lv = _ios()
    lv.profile_used = True
    conn = _db()
    src = LeappImporter(source_id="p").import_source(lv.write_zip(tmp_path / "p.zip"), conn)
    assert src.fidelity.value == "curated_report"


def test_refuses_changed_bytes_and_a_second_import(tmp_path: Path) -> None:
    z = _ios().write_zip(tmp_path / "i.zip")
    conn = _db()
    with pytest.raises(ValueError, match="not the file that was received"):
        LeappImporter(source_id="i", expected_sha256="0" * 64).import_source(z, conn)
    assert conn.execute("SELECT count(*) FROM sources").fetchone() == (0,)
    LeappImporter(source_id="i").import_source(z, conn)
    with pytest.raises(ValueError, match="already in this case"):
        LeappImporter(source_id="i").import_source(z, conn)
