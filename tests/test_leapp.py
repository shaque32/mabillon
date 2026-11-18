"""iLEAPP and ALEAPP output import (core/ingest/leapp.py). UNVERIFIED format support: every
LAVA pair here is synthetic (eval/synthetic/leapp.py), written the way LEAPP's lavafuncs.py
writes one."""

from __future__ import annotations

import io
import json
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
    for t in ("2024-01-10T12:00:00Z", "2024-02-05T12:00:00Z"):
        lv.add("powerlogTimeZone", **{"Timestamp": t, "Time Zone Name": "America/New_York"})
    lv.add(
        "timezone_info",
        **{"Property": "Last Bootstrap Timezone", "Property Value": "America/New_York"},
    )
    lv.add("last_build", **{"Property": "ProductName", "Property Value": "iPhone OS"})
    lv.add("last_build", **{"Property": "ProductVersion", "Property Value": "17.1"})
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
            "Phone Account Package": "com.android.phone",
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
            "Phone Account Package": "com.android.phone",
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
            "Phone Account Package": "com.android.phone",
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


def test_refuses_a_database_that_unpacks_past_the_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    z = _ios().write_zip(tmp_path / "i.zip")
    monkeypatch.setattr(leapp, "MAX_DB_BYTES", 1024)
    with pytest.raises(ValueError, match="more than the 1,024"):
        LeappImporter(source_id="x").import_source(z, _db())


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


def test_the_phones_zone_and_os_are_read_when_it_recorded_one_zone(tmp_path: Path) -> None:
    conn = _db()
    LeappImporter(source_id="ios").import_source(_ios().write_zip(tmp_path / "i.zip"), conn)
    assert conn.execute("SELECT os_version, timezone FROM devices").fetchall() == [
        ("iPhone OS 17.1", "America/New_York")
    ]
    device = coverage.load(conn, "ios").payload["leapp"]["device"]
    assert device["zones_seen"][0]["rows"] == 3
    assert device["zones_seen"][0]["tables"] == ["powerlogtimezone", "timezone_info"]
    s = coverage.summary(conn, "ios")
    assert s is not None and "leapp_timezone" in {i.code for i in s.items}


def test_a_phone_that_recorded_two_zones_gets_none(tmp_path: Path) -> None:
    lv = _android()
    for t, z in (("2024-03-01T00:00:00Z", "America/New_York"),
                 ("2024-03-05T00:00:00Z", "America/Chicago"),
                 ("2024-03-06T00:00:00Z", "Not/AZone")):  # fmt: skip
        lv.add("get_battery_usage_v4", **{"Timestamp": t, "Timezone": z})
    lv.add("usagestatsVersion", **{"Property": "Android Version", "Property Value": "14"})
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    assert conn.execute("SELECT os_version, timezone FROM devices").fetchall() == [
        ("Android 14", None)
    ]
    device = coverage.load(conn, "and").payload["leapp"]["device"]
    assert [z["zone"] for z in device["zones_seen"]] == ["America/Chicago", "America/New_York"]
    assert device["zones_not_read"] == {"Not/AZone": 1}
    s = coverage.summary(conn, "and")
    item = next(i for i in s.items if i.code == "leapp_timezones_differ")
    assert item.level == "attention"
    assert "set-device-zone" in "".join(t for t, _q in item.parts)


def test_a_phone_with_no_zone_says_so(tmp_path: Path) -> None:
    conn = _db()
    LeappImporter(source_id="and").import_source(_android().write_zip(tmp_path / "a.zip"), conn)
    assert conn.execute("SELECT timezone FROM devices").fetchall() == [(None,)]
    s = coverage.summary(conn, "and")
    assert "leapp_no_timezone" in {i.code for i in s.items}


def test_chat_apps_are_read_through_leapps_conversation_view(tmp_path: Path) -> None:
    lv = _ios()
    group = "120363000000000000@g.us"
    for t, d, frm, text, chat in (
        ("2024-02-03T10:00:00Z", "Incoming", f"{ALICE[1:]}@s.whatsapp.net", "on my way", "7"),
        ("2024-02-03T10:01:00Z", "Outgoing", None, "see you", "7"),
        ("2024-02-03T10:02:00Z", "Incoming", group, "group hello", "8"),  # a group, not a person
        ("2024-02-03T10:03:00Z", "Pending", None, "queued", "7"),
    ):
        row = {"Timestamp": t, "Direction": d, "From ID": frm, "Message": text, "Chat ID": chat}
        lv.add("whatsAppMessages", **row, **{"Chat Name": "Alice"})
    conn = _db()
    LeappImporter(source_id="ios").import_source(lv.write_zip(tmp_path / "i.zip"), conn)
    rows = conn.execute(
        "SELECT m.locator, m.direction, m.body, a.identifier FROM messages m"
        " JOIN threads t ON t.id = m.thread_id LEFT JOIN accounts a ON a.id = m.sender_account_id"
        " WHERE t.app = 'WhatsApp' ORDER BY m.ts_utc"
    ).fetchall()
    assert rows == [
        ("whatsappmessages/rowid=1", "incoming", "on my way", f"{ALICE[1:]}@s.whatsapp.net"),
        ("whatsappmessages/rowid=2", "outgoing", "see you", None),  # the owner's id is not stated
        ("whatsappmessages/rowid=3", "incoming", "group hello", None),
        ("whatsappmessages/rowid=4", "unknown", "queued", None),
    ]
    payload = coverage.load(conn, "ios").payload
    # No other WhatsApp table holds records, but an iOS chat app is never read in full: the
    # phone's own call records (CallKit) hold app calls iLEAPP lists under no app.
    assert payload["apps_read_in_full"] == ["Native Messages", "unknown"]
    tables = {t["name"]: t for t in payload["tables"]}
    flags = tables["WhatsApp - Messages"]["flag_counts"]
    assert flags["direction_not_stated"] == 1 and flags["received_without_sender"] == 1


def test_a_chat_sender_named_only_by_display_name_is_no_account(tmp_path: Path) -> None:
    lv = _android()
    lv.add("instagramDirectMessages", **{"Timestamp": "2024-03-04T10:00:00Z",
           "Direction": "Incoming", "Sender Username": "Instagram User", "Message": "hey",
           "Thread": "t1"})  # fmt: skip
    lv.add("instagramDirectMessages", **{"Timestamp": "2024-03-04T10:01:00Z",
           "Direction": "Outgoing", "Sender Username": "me", "Message": "hi", "Thread": "t1",
           "Sender ID": "555"})  # fmt: skip
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    rows = conn.execute(
        "SELECT m.direction, a.identifier, a.device_id IS NOT NULL FROM messages m"
        " JOIN threads t ON t.id = m.thread_id LEFT JOIN accounts a ON a.id = m.sender_account_id"
        " WHERE t.app = 'Instagram' ORDER BY m.ts_utc"
    ).fetchall()
    # a sent row's Sender ID is the owner's account (checked on a UFDR of the same phone)
    assert rows == [("incoming", None, 0), ("outgoing", "555", 1)]
    s = coverage.summary(conn, "and")
    assert "sender_name_only" in {i.code for i in s.items}
    # no other Instagram table holds records, so Instagram is read in full
    assert "Instagram" in coverage.load(conn, "and").payload["apps_read_in_full"]


def test_artifacts_not_read_are_listed_so_absence_is_never_assumed(tmp_path: Path) -> None:
    conn = _db()
    LeappImporter(source_id="ios").import_source(_ios().write_zip(tmp_path / "i.zip"), conn)
    payload = coverage.load(conn, "ios").payload
    assert "Wifi Networks" in [e["name"] for e in payload["not_imported"]]
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


def test_a_real_column_named_rowid_never_stands_in_for_the_row_id() -> None:
    db = sqlite3.connect(":memory:")
    db.execute('CREATE TABLE t ("rowid" TEXT, body TEXT)')
    db.execute("INSERT INTO t VALUES ('not-a-row-id', 'hi')")
    art = leapp.Artifact("SMS", "SMS", "sms", "t", "m", {"body": "Body"}, 1, None)
    lava = leapp.Lava({}, db, "m", "d", "iLEAPP", None, [art])
    assert list(lava.rows(art)) == [(1, {"rowid": "not-a-row-id", "Body": "hi"})]
    db.execute('CREATE TABLE u ("rowid" TEXT, "_rowid_" TEXT, "oid" TEXT)')
    with pytest.raises(ValueError, match="hide its row ids"):
        list(lava.rows(leapp.Artifact("SMS", "SMS", "sms", "u", "m", {}, 0, None)))


def test_an_mms_keeps_every_receiver_it_names(tmp_path: Path) -> None:
    # Greptile on #264: an MMS to Carol with Bob in Cc lost Bob, so "no contact" with Bob
    # could pass. To, Cc and Bcc are all receivers.
    lv = _android()
    lv.add(
        "get_sms_mms_mms",
        **{"Date": "2024-03-02T10:00:00Z", "MSG ID": "77", "Thread ID": "9", "Direction": "Sent",
           "From Address": "insert-address-token", "To Address": "+15550000003",
           "Cc": "+15550000004", "Bcc": "+15550000005", "Body": "group pic"},
    )  # fmt: skip
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    got = conn.execute(
        "SELECT a.identifier FROM message_recipients r JOIN messages m ON m.id = r.message_id"
        " JOIN accounts a ON a.id = r.account_id WHERE m.locator LIKE '%msg_id=77' ORDER BY 1"
    ).fetchall()
    assert [g[0][-4:] for g in got] == ["0003", "0004", "0005"]


@pytest.mark.parametrize(
    ("values", "zone"), [(["UTC"], "UTC"), (["UTC", "America/New_York"], None)]
)
def test_utc_is_a_zone_and_counts_against_another(tmp_path: Path, values, zone) -> None:
    # Greptile on #264: "UTC" was dropped as no zone, so a phone that recorded UTC and New York
    # was set to New York.
    lv = _android()
    for i, z in enumerate(values):
        lv.add(
            "get_battery_usage_v4", **{"Timestamp": f"2024-03-0{i + 1}T00:00:00Z", "Timezone": z}
        )
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    assert conn.execute("SELECT timezone FROM devices").fetchall() == [(zone,)]


def test_a_zone_value_that_cannot_be_read_sets_no_zone(tmp_path: Path) -> None:
    lv = _android()
    for i, z in enumerate(("America/New_York", "-0500")):
        lv.add(
            "get_battery_usage_v4", **{"Timestamp": f"2024-03-0{i + 1}T00:00:00Z", "Timezone": z}
        )
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    assert conn.execute("SELECT timezone FROM devices").fetchall() == [(None,)]
    s = coverage.summary(conn, "and")
    item = next(i for i in s.items if i.code == "leapp_timezone_not_read")
    text = "".join(t for t, _q in item.parts)
    assert item.level == "attention" and "'-0500'" in text and "America/New_York" in text


def _gm_lava(native: list[dict[str, str]], gm: list[dict[str, str]]) -> Lava:
    lv = Lava(leapp="ALEAPP")
    for i, r in enumerate(native):
        lv.add("get_sms_mms", **{"MSG ID": str(100 + i), "Thread ID": "2", **r})
    for r in gm:
        lv.add("get_googleMessages", **{"Message Type": "text/plain", **r})
    return lv


def _gm_imported(tmp_path: Path, lv: Lava) -> tuple[list[str], dict[str, int], set[str]]:
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    locs = [
        r[0]
        for r in conn.execute(
            "SELECT locator FROM messages WHERE locator LIKE 'get_googlemessages%' ORDER BY 1"
        )
    ]
    tables = {t["name"]: t for t in coverage.load(conn, "and").payload["tables"]}
    s = coverage.summary(conn, "and")
    assert s is not None
    flags = tables["GoogleMessages"].get("flag_counts") or {}
    return locs, flags, {i.code for i in s.items}


def test_a_google_messages_message_from_another_sender_is_never_taken_for_a_copy(
    tmp_path: Path,
) -> None:
    # CodeRabbit on #264: "OK" from Alice by SMS hid "OK" from Bob in Google Messages a second
    # later. The other party is now compared too ("+1919..." and "(919) ..." are one number).
    lv = _gm_lava(
        [{"Date": "2024-03-01T12:00:00Z", "Type": "Received", "Address": ALICE, "Body": "OK"}],
        [
            {"Message Timestamp": "2024-03-01T12:00:01Z", "Direction": "Incoming",
             "Message Sender": "(919) 555-0122", "Message": "OK", "Conversation ID": "8"},
            {"Message Timestamp": "2024-03-01T12:00:01Z", "Direction": "Incoming",
             "Message Sender": "(919) 555-0111", "Message": "OK", "Conversation ID": "9"},
        ],
    )  # fmt: skip
    locs, _, _ = _gm_imported(tmp_path, lv)
    assert locs == ["get_googlemessages/rowid=1"]  # Bob's is kept; Alice's copy is skipped


def test_one_sms_stands_for_at_most_one_google_messages_message(tmp_path: Path) -> None:
    # CodeRabbit on #264: one SMS at 12:00:00 hid two Google Messages messages, at :00 and :01.
    gm = {"Direction": "Incoming", "Message Sender": ALICE, "Message": "OK", "Conversation ID": "9"}
    lv = _gm_lava(
        [{"Date": "2024-03-01T12:00:00Z", "Type": "Received", "Address": ALICE, "Body": "OK"}],
        [{"Message Timestamp": f"2024-03-01T12:00:0{s}Z", **gm} for s in (0, 1)],
    )
    locs, flags, _ = _gm_imported(tmp_path, lv)
    assert locs == ["get_googlemessages/rowid=2"]
    assert flags["may_be_same_as_an_sms_or_mms_message"] == 1  # the SMS may be its copy


def test_a_trunk_0_number_is_a_possible_copy_of_an_sms_already_paired(tmp_path: Path) -> None:
    # CodeRabbit on #264: the SMS was paired with the "+44" Google Messages row, so the
    # "07911" row with the same text was kept unflagged, and a count could take one message
    # for two. A candidate already paired still makes a possible copy.
    gm = {"Direction": "Incoming", "Message": "OK", "Conversation ID": "9",
          "Message Timestamp": "2024-03-01T12:00:00Z"}  # fmt: skip
    lv = _gm_lava(
        [{"Date": "2024-03-01T12:00:00Z", "Type": "Received", "Address": "+447911123456",
          "Body": "OK"}],
        [{**gm, "Message Sender": "+44 7911 123456"},
         {**gm, "Message Sender": "07911 123456", "Message Timestamp": "2024-03-01T12:00:01Z"}],
    )  # fmt: skip
    locs, flags, codes = _gm_imported(tmp_path, lv)
    assert locs == ["get_googlemessages/rowid=2"]
    flag = "may_be_same_as_an_sms_or_mms_message"
    assert flags[flag] == 1 and flag in codes


@pytest.mark.parametrize(
    ("native", "gm", "possible"),
    [
        ("07911 123456", "+44 7911 123456", True),  # trunk 0 against the country code
        ("+44 7911 123456", "07911 123456", True),
        ("06 12 34 56 78", "+33 6 12 34 56 78", True),
        ("07911 123456", "+44 7911 654321", False),  # another number
        ("+44 7911 123456", "+44 7911 123456", False),  # the same number: a copy, skipped
    ],
)
def test_a_number_with_its_trunk_0_is_a_possible_copy_of_one_with_its_country_code(
    tmp_path: Path, native: str, gm: str, possible: bool
) -> None:
    # CodeRabbit on #264: "07911 123456" in the SMS table and "+44 7911 123456" in Google
    # Messages may be one person. That is never enough to skip the message as a copy, but it
    # is flagged as a possible copy so a count over it is inconclusive.
    lv = _gm_lava(
        [{"Date": "2024-03-01T12:00:00Z", "Type": "Received", "Address": native, "Body": "OK"}],
        [{"Message Timestamp": "2024-03-01T12:00:01Z", "Direction": "Incoming",
          "Message Sender": gm, "Message": "OK", "Conversation ID": "9"}],
    )  # fmt: skip
    locs, flags, codes = _gm_imported(tmp_path, lv)
    flag = "may_be_same_as_an_sms_or_mms_message"
    if native == gm:
        assert locs == []
    else:
        assert locs == ["get_googlemessages/rowid=1"]
        assert (flags.get(flag) == 1 and flag in codes) is possible


def test_a_sent_google_messages_message_is_a_copy_only_when_its_party_is_known(
    tmp_path: Path,
) -> None:
    # A sent message names the chat by display name. When the phone's contacts give that name
    # one number, and the chat heard from no one else, it is compared as sent to that number.
    # The chat's one sender alone is not enough (a group may have one sender so far: CodeRabbit
    # on #264), and with neither the party cannot be compared: both are kept and flagged.
    sent = {"Message Timestamp": "2024-03-01T12:00:00Z", "Direction": "Outgoing",
            "Message Sender": OWNER, "Other Participant/Conversation Name": "Alice Ames",
            "Message": "on my way", "Conversation ID": "9"}  # fmt: skip
    native = [{"Date": "2024-03-01T12:00:00Z", "Type": "Sent", "Address": ALICE,
               "Body": "on my way"}]  # fmt: skip
    heard = {"Message Timestamp": "2024-03-01T11:00:00Z", "Direction": "Incoming",
             "Message Sender": ALICE, "Message": "where", "Conversation ID": "9"}  # fmt: skip
    alice = {"Mimetype": "vnd.android.cursor.item/phone_v2", "Data 1": "(919) 555-0111",
             "Display Name": "Alice Ames", "Phone Number": "(919) 555-0111"}  # fmt: skip
    possible = "may_be_same_as_an_sms_or_mms_message"
    for n, (contact, gm, kept) in enumerate(
        [
            (True, [heard, sent], ["get_googlemessages/rowid=1"]),  # the copy is skipped
            (True, [sent], []),  # the contact alone names the party
            (False, [heard, sent], ["get_googlemessages/rowid=1", "get_googlemessages/rowid=2"]),
            (False, [sent], ["get_googlemessages/rowid=1"]),
        ]
    ):
        lv = _gm_lava(native, gm)
        if contact:
            lv.add("contacts", **alice)
        (tmp_path / str(n)).mkdir()
        locs, flags, codes = _gm_imported(tmp_path / str(n), lv)
        assert locs == kept, n
        if contact:
            assert possible not in flags, n
        else:
            assert flags[possible] == 1 and possible in codes, n


def _zip_with(tmp_path: Path, lv: Lava, change) -> Path:
    """lv's LAVA pair with its manifest changed by `change(manifest)`."""
    import io
    import json

    manifest, data = lv.build()
    change(manifest)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("LEAPP_Reports_x/_lava_data.lava", json.dumps(manifest))
        z.writestr("LEAPP_Reports_x/_lava_artifacts.db", data)
    path = tmp_path / "a.zip"
    path.write_bytes(buf.getvalue())
    return path


def _artifact(manifest: dict, key: str) -> dict:
    return next(
        a for arts in manifest["artifacts"].values() for a in arts if a["artifact_key"] == key
    )


@pytest.mark.parametrize("broken", ["view", "table"])
def test_a_table_not_read_through_leaves_its_app_unread(tmp_path: Path, broken: str) -> None:
    # CodeRabbit on #264: an Instagram table with no usable conversation view, or one missing
    # from the database, counted as read, so Instagram was read in full.
    lv = _android()
    row = {"Timestamp": "2024-03-04T10:00:00Z", "Direction": "Incoming", "Sender ID": "9"}
    lv.add("instagramDirectMessages", **row, Message="hey", Thread="t1")

    def change(m: dict) -> None:
        a = _artifact(m, "instagramDirectMessages")
        if broken == "view":
            # a copy: the synthetic manifest shares its view with every build
            view = {k: v for k, v in a["data_views"]["conversation"].items() if k != "textColumn"}
            a["data_views"] = {"conversation": view}
        else:
            a["tablename"] = "not_there"

    conn = _db()
    LeappImporter(source_id="and").import_source(_zip_with(tmp_path, lv, change), conn)
    payload = coverage.load(conn, "and").payload
    assert "Instagram" not in payload["apps_read_in_full"]
    assert "Native Messages" in payload["apps_read_in_full"]
    failed = [e for e in payload["not_imported"] if e.get("read_failed")]
    assert [e["name"] for e in failed] == ["Instagram - Direct Messages"]
    assert all(a["key"] != "instagramDirectMessages" for a in payload["leapp"]["artifacts_read"])
    s = coverage.summary(conn, "and")
    item = next(i for i in s.items if i.code == "leapp_artifact_not_read")
    assert item.level == "attention" and "could not be read" in item.plain


def test_a_missing_sms_table_leaves_the_phones_messages_unread(tmp_path: Path) -> None:
    def change(m: dict) -> None:
        _artifact(m, "get_sms_mms_mms")["tablename"] = "not_there"

    conn = _db()
    LeappImporter(source_id="and").import_source(_zip_with(tmp_path, _android(), change), conn)
    assert "Native Messages" not in coverage.load(conn, "and").payload["apps_read_in_full"]


@pytest.mark.parametrize(
    ("status", "fidelity"),
    [("Complete", "full_extraction"), ("In Progress", "unknown"), (None, "unknown")],
)
def test_a_run_that_did_not_complete_is_no_full_extraction(
    tmp_path: Path, status: str | None, fidelity: str
) -> None:
    # CodeRabbit on #264: LEAPP writes "In Progress" when a run starts and "Complete" when it
    # ends, so a stopped run's tables may be cut short.
    lv = _android()
    lv.status = status  # type: ignore[assignment]
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    assert conn.execute("SELECT fidelity FROM sources").fetchone() == (fidelity,)


def test_the_report_names_the_leapp_reader_not_the_ufdr_reader(tmp_path: Path) -> None:
    # CodeRabbit on #264: a LEAPP import's limitation said "UFDR reader" and "Cellebrite Reader".
    from core.report.html import _limitations, sources

    conn = _db()
    LeappImporter(source_id="and").import_source(_android().write_zip(tmp_path / "a.zip"), conn)
    text = _limitations(conn, sources(conn))
    assert "iLEAPP and ALEAPP reader, which is not yet verified" in text
    assert "UFDR reader" not in text and "Cellebrite Reader" not in text


def test_photos_that_cannot_be_told_apart_are_kept_and_flagged(tmp_path: Path) -> None:
    # CodeRabbit on #264: the two stores name a photo's file differently, so attachments are
    # compared by number only. Alice's MMS photo has two Google Messages messages with one photo
    # each a second apart: which one is the copy cannot be told, so both are kept, and the three
    # rows are listed as possible copies (a count over them is inconclusive).
    lv = Lava(leapp="ALEAPP")
    lv.add("get_sms_mms_mms", **{"Date": "2024-03-01T12:00:00Z", "Direction": "Received",
           "From Address": ALICE, "To Address": OWNER, "Media": "PART_1_a.jpg", "MSG ID": "50",
           "Thread ID": "2"})  # fmt: skip
    for s, f in ((0, "a"), (1, "b")):
        lv.add("get_googleMessages", **{"Message Timestamp": f"2024-03-01T12:00:0{s}Z",
               "Direction": "Incoming", "Message Sender": ALICE, "Message Type": "image/jpeg",
               "Attachment Location": f"/cache/part_{f}.bin", "Conversation ID": "9"})  # fmt: skip
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    locs = [r[0] for r in conn.execute("SELECT locator FROM messages ORDER BY 1")]
    assert locs == [
        "get_googlemessages/rowid=1",
        "get_googlemessages/rowid=2",
        "get_sms_mms_mms/msg_id=50",
    ]
    copies = set(coverage.load(conn, "and").payload["numbered_copy_records"])
    assert copies == {f"msg:and:{loc}" for loc in locs}
    # With one Google Messages message for it, the photo's copy is skipped as before.
    (tmp_path / "b").mkdir()
    lv.tables["get_googleMessages"].pop()
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "b" / "a.zip"), conn)
    locs = [r[0] for r in conn.execute("SELECT locator FROM messages ORDER BY 1")]
    assert locs == ["get_sms_mms_mms/msg_id=50"]


def test_one_table_read_through_never_hides_another_with_the_same_key(tmp_path: Path) -> None:
    # CodeRabbit on #264: two manifest entries can share a key; a missing Instagram table must
    # leave Instagram unread even when another entry with that key was read.
    lv = _android()
    row = {"Timestamp": "2024-03-04T10:00:00Z", "Direction": "Incoming", "Sender ID": "9"}
    lv.add("instagramDirectMessages", **row, Message="hey", Thread="t1")

    def change(m: dict) -> None:
        a = _artifact(m, "instagramDirectMessages")
        m["artifacts"].setdefault("Instagram", []).append({**a, "tablename": "not_there"})

    conn = _db()
    LeappImporter(source_id="and").import_source(_zip_with(tmp_path, lv, change), conn)
    payload = coverage.load(conn, "and").payload
    assert "Instagram" not in payload["apps_read_in_full"]
    assert [e["table"] for e in payload["not_imported"] if e.get("read_failed")] == ["not_there"]


@pytest.mark.parametrize(
    ("a", "b", "same", "maybe"),
    [
        ("+19195550111", "(919) 555-0111", True, False),
        ("+19195550111", "0019195550111", True, False),
        ("0019195550111", "9195550111", True, False),
        # CodeRabbit on #264: an unmarked leading digit may be part of another national number
        ("17912345678", "7912345678", False, True),
        ("+19195550111", "+919195550111", False, False),  # two country codes: never by suffix
        ("+19195550111", "+19195550112", False, False),
        ("07911 123456", "+44 7911 123456", False, True),
        ("Bob@Example.com", "bob@example.com", True, False),
    ],
)
def test_two_handles_are_one_party_only_when_they_can_be(
    a: str, b: str, same: bool, maybe: bool
) -> None:
    ka, kb = leapp._party_key(a), leapp._party_key(b)
    assert ka and kb and leapp._same_party(ka, kb) is same
    assert leapp._maybe_same_party(ka, kb) is maybe


def test_an_artifact_with_no_stated_count_is_empty_only_when_its_table_is(tmp_path: Path) -> None:
    # CodeRabbit on #264: a missing record count was read as zero.
    lv = _android()
    z = lv.write_zip(tmp_path / "a.zip")
    with z.open("rb") as f:
        lava = leapp.read_lava(f, z.name)
    sms = next(a for a in lava.artifacts if a.key == "get_sms_mms")
    from dataclasses import replace

    assert leapp._may_hold_records(lava, replace(sms, record_count=None))
    # a count of 0 is not taken on trust when the table holds a row (CodeRabbit on #269)
    assert leapp._may_hold_records(lava, replace(sms, record_count=0))
    assert leapp._may_hold_records(lava, replace(sms, record_count=None, table="not_there"))
    assert not leapp._may_hold_records(lava, replace(sms, record_count=0, table="not_there"))
    lv.tables["get_sms_mms"] = []  # the table is written with no rows
    z = lv.write_zip(tmp_path / "b.zip")
    with z.open("rb") as f:
        empty = leapp.read_lava(f, z.name)
    sms = next(a for a in empty.artifacts if a.key == "get_sms_mms")
    assert not leapp._may_hold_records(empty, replace(sms, record_count=None))


def test_a_table_that_cannot_be_read_may_hold_records(tmp_path: Path) -> None:
    # A row probe that SQLite cannot answer (a corrupt page) does not stop the import: the
    # table is not known to be empty (CodeRabbit on #269).
    from dataclasses import replace

    z = _android().write_zip(tmp_path / "a.zip")
    with z.open("rb") as f:
        lava = leapp.read_lava(f, z.name)
    real = lava.db

    class Corrupt:
        def execute(self, sql: str, *args: object) -> sqlite3.Cursor:
            if sql.startswith('SELECT 1 FROM "'):
                raise sqlite3.DatabaseError("database disk image is malformed")
            return real.execute(sql, *args)

    broken = replace(lava, db=Corrupt())
    sms = next(a for a in lava.artifacts if a.key == "get_sms_mms")
    assert leapp._may_hold_records(broken, replace(sms, record_count=0))


def test_a_manifest_table_name_matches_the_table_whatever_its_case(tmp_path: Path) -> None:
    # SQLite names are not case-sensitive: a manifest naming the table in other case still finds
    # it, so a count of 0 does not hide its rows (CodeRabbit on #269).
    from dataclasses import replace

    z = _android().write_zip(tmp_path / "a.zip")
    with z.open("rb") as f:
        lava = leapp.read_lava(f, z.name)
    sms = next(a for a in lava.artifacts if a.key == "get_sms_mms")
    upper = replace(sms, table=sms.table.upper(), record_count=0)
    assert upper.table != sms.table
    assert lava.has_table(upper)
    assert leapp._may_hold_records(lava, upper)


def test_a_negative_record_count_is_unknown(tmp_path: Path) -> None:
    # A count below 0 says nothing about the table: it is read as unknown, so a missing table
    # with it may hold records (CodeRabbit on #269).
    manifest, data = _android().build()
    for entries in manifest["artifacts"].values():
        for e in entries:
            if e["artifact_key"] == "get_sms_mms":
                e["record_count"] = -1
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("LEAPP_Reports_x/_lava_data.lava", json.dumps(manifest))
        z.writestr("LEAPP_Reports_x/_lava_artifacts.db", data)
    buf.seek(0)
    lava = leapp.read_lava(buf, "a.zip")
    sms = next(a for a in lava.artifacts if a.key == "get_sms_mms")
    from dataclasses import replace

    assert sms.record_count is None
    assert leapp._may_hold_records(lava, replace(sms, table="not_there"))


def _lava_zip(tmp_path: Path, edit) -> Path:  # noqa: ANN001
    manifest, data = _android().build()
    edit(manifest)
    path = tmp_path / "edited.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("LEAPP_Reports_x/_lava_data.lava", json.dumps(manifest))
        z.writestr("LEAPP_Reports_x/_lava_artifacts.db", data)
    return path


def _lava_with(tmp_path: Path, edit) -> leapp.Lava:  # noqa: ANN001
    return leapp.read_lava(io.BytesIO(_lava_zip(tmp_path, edit).read_bytes()), "a.zip")


@pytest.mark.parametrize("spelling", [str.upper, str])
def test_a_manifest_that_names_one_table_twice_is_refused(tmp_path: Path, spelling) -> None:  # noqa: ANN001
    # Two entries for one table (in any case) would store each of its rows twice: the import
    # stops rather than guess which entry to read (CodeRabbit on #269).
    def twice(manifest):  # noqa: ANN001, ANN202
        entries = next(v for v in manifest["artifacts"].values() if v)
        entries.append({**entries[0], "tablename": spelling(entries[0]["tablename"])})

    with pytest.raises(ValueError, match="twice"):
        _lava_with(tmp_path, twice)


def test_a_table_shared_by_entries_mabillon_never_reads_is_not_refused(tmp_path: Path) -> None:
    # Two entries Mabillon does not read can name one table: no row of it is stored, so the
    # import goes on (Claude review on #269).
    def shared(manifest):  # noqa: ANN001, ANN202
        entries = next(v for v in manifest["artifacts"].values() if v)
        base = {**entries[0], "artifact_key": "notReadHere", "name": "Not read"}
        entries.extend([base, {**base, "tablename": base["tablename"].upper()}])

    lava = _lava_with(tmp_path, shared)
    assert sum(a.key == "notReadHere" for a in lava.artifacts) == 2


def test_a_manifest_table_name_in_other_case_reads_as_the_database_spells_it(
    tmp_path: Path,
) -> None:
    # A manifest naming GET_CALLLOG reads get_calllog, and its locators name get_calllog, the
    # LAVA table; an entry with no key takes the database's spelling as its key. Tables whose
    # names differ in non-ASCII letters stay distinct, as SQLite keeps them (CodeRabbit on #269).
    manifest, data = _android().build()
    for entries in manifest["artifacts"].values():
        for e in entries:
            if e["artifact_key"] == "get_calllog":
                e["tablename"] = e["tablename"].upper()
    entries = next(v for v in manifest["artifacts"].values() if v)
    for name in ("calls_\u00c4", "calls_\u00e4"):
        # only the ASCII letters change case (str.upper would fold the non-ASCII one too)
        entries.append({"name": name, "tablename": "CALLS_" + name[-1], "record_count": 1})
    db = sqlite3.connect(":memory:")
    db.deserialize(data)
    for name in ("calls_\u00c4", "calls_\u00e4"):
        db.execute(f'CREATE TABLE "{name}" (who TEXT)')
        db.execute(f'INSERT INTO "{name}" VALUES (?)', (name,))
    db.commit()
    data = db.serialize()
    db.close()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("LEAPP_Reports_x/_lava_data.lava", json.dumps(manifest))
        z.writestr("LEAPP_Reports_x/_lava_artifacts.db", data)
    buf.seek(0)
    lava = leapp.read_lava(buf, "a.zip")
    calls = next(a for a in lava.artifacts if a.key == "get_calllog")
    assert calls.table == "get_calllog"
    for name in ("calls_\u00c4", "calls_\u00e4"):
        # each entry finds its own table, as SQLite folds only ASCII letters
        art = next(a for a in lava.artifacts if a.name == name)
        assert (art.table, art.key) == (name, name)
        quoted = art.table.replace(chr(34), chr(34) * 2)
        assert lava.db.execute(f'SELECT who FROM "{quoted}"').fetchall() == [(name,)]  # noqa: S608


@pytest.mark.parametrize(
    ("key", "count", "stored_key", "holds"),
    [("get_calllog", 1, "get_calllog", True), ("get_calllog", None, "get_calllog", True),
     ("get_calllog", False, "get_calllog", True), ("get_calllog", 0.0, "get_calllog", True),
     ("GET_CALLLOG", 1, "get_calllog", True), ("CallHistory", 2, "callHistory", True),
     ("get_calllog", 0, "get_calllog", False), (["get_calllog"], 1, None, True),
     ("get_sms_mms", 1, "get_sms_mms", True)],
)  # fmt: skip
def test_an_entry_listed_with_no_table_is_recorded_as_not_imported(
    tmp_path: Path,
    key,  # noqa: ANN001
    count,  # noqa: ANN001
    stored_key,  # noqa: ANN001
    holds,  # noqa: ANN001
) -> None:
    # An entry with no table name is never read: the import goes on, and the coverage lists it
    # as not imported, holding records unless its count is the integer 0, so a run's call-log
    # check can stop on it and the call log is not read in full (CodeRabbit and Claude review
    # on #269).
    def tableless(manifest):  # noqa: ANN001, ANN202
        entries = next(v for v in manifest["artifacts"].values() if v)
        entries.append({"name": "Call logs", "artifact_key": key, "record_count": count})

    def imported(edit):  # noqa: ANN001, ANN202
        lv = Lava(leapp="ALEAPP")
        lv.add("get_calllog", **{"Call Date": "2024-03-01T15:00:00Z", "Partner": BOB,
                                 "Phone Account Address": OWNER, "Duration in Secs": "5",
                                 "Raw Call Type (as stored)": "2",
                                 "Phone Account Package": "com.android.phone"})  # fmt: skip
        manifest, data = lv.build()
        edit(manifest)
        path = tmp_path / "t.zip"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("LEAPP_Reports_x/_lava_data.lava", json.dumps(manifest))
            z.writestr("LEAPP_Reports_x/_lava_artifacts.db", data)
        conn = _db()
        LeappImporter(source_id="t").import_source(path, conn)
        return coverage.load(conn, "t").payload

    assert "unknown" in imported(lambda m: None)["apps_read_in_full"]  # read in full as is
    p = imported(tableless)
    (entry,) = [t for t in p["not_imported"] if t["table"] is None]
    assert (entry["key"], entry["may_hold_records"]) == (stored_key, holds)
    native_unread = holds and stored_key in leapp.NATIVE_CALL_KEYS
    assert ("unknown" in p["apps_read_in_full"]) is not native_unread


@pytest.mark.parametrize(("count", "in_full"), [(1, False), (None, False), (0, True)])
def test_an_unread_entry_of_an_apps_key_keeps_the_app_partial_whatever_its_category(
    tmp_path: Path,
    count,  # noqa: ANN001
    in_full: bool,
) -> None:
    # CodeRabbit on #269: an entry of a chat app's own key that was not read marks that app,
    # even when its category's first word does not name the app.
    lv = _android()
    _telegram(lv, "hi")

    def change(m: dict) -> None:
        m["artifacts"].setdefault("Social Media", []).append(
            {"name": "Messages", "artifact_key": "get_telegramMessages", "record_count": count}
        )

    conn = _db()
    LeappImporter(source_id="and").import_source(_zip_with(tmp_path, lv, change), conn)
    payload = coverage.load(conn, "and").payload
    assert ("Telegram" in payload["apps_read_in_full"]) is in_full


def test_a_call_log_key_in_other_case_is_read_as_the_call_log(tmp_path: Path) -> None:
    # SQLite ignores ASCII case in names, so a call log keyed GET_CALLLOG is the call log: it
    # takes the key's own spelling, is read, and the run's check finds it (CodeRabbit on #269).
    def upper(manifest):  # noqa: ANN001, ANN202
        for entries in manifest["artifacts"].values():
            for e in entries:
                if e["artifact_key"] == "get_calllog":
                    e["artifact_key"] = "GET_CALLLOG"

    lava = _lava_with(tmp_path, upper)
    assert "get_calllog" in {a.key for a in lava.artifacts}
    assert "GET_CALLLOG" not in {a.key for a in lava.artifacts}
    # and the import stores its calls under the call log's key (CodeRabbit on #269)
    conn = _db()
    LeappImporter(source_id="up").import_source(_lava_zip(tmp_path, upper), conn)
    p = coverage.load(conn, "up").payload["leapp"]
    assert "get_calllog" in {a["key"] for a in p["artifacts_read"]}
    assert conn.execute("SELECT count(*) FROM calls WHERE locator LIKE 'get_calllog/%'").fetchone()[
        0
    ]


@pytest.mark.parametrize("blank", ["", " ", "\t"])
def test_a_key_of_only_spaces_takes_its_tables_name(tmp_path: Path, blank: str) -> None:
    # CodeRabbit on #269: a blank key names nothing, so the entry is keyed by its table, as one
    # with no key is, and a call log so listed is read as the call log.
    def blanked(manifest):  # noqa: ANN001, ANN202
        for entries in manifest["artifacts"].values():
            for e in entries:
                if e["artifact_key"] == "get_calllog":
                    e["artifact_key"] = blank

    conn = _db()
    LeappImporter(source_id="b").import_source(_lava_zip(tmp_path, blanked), conn)
    p = coverage.load(conn, "b").payload["leapp"]
    assert "get_calllog" in {a["key"] for a in p["artifacts_read"]}
    assert conn.execute("SELECT count(*) FROM calls WHERE locator LIKE 'get_calllog/%'").fetchone()[
        0
    ]


def test_a_call_duration_that_is_not_a_decimal_number_is_unknown(tmp_path: Path) -> None:
    # "²" passes str.isdigit but int() refuses it: the call is kept with no duration, and the
    # import goes on (CodeRabbit on #269).
    lv = Lava(leapp="ALEAPP")
    for i, dur in enumerate(["²", str(2**63), "9" * 5000, str(2**63 - 1), "5"]):
        lv.add("get_calllog", **{"Call Date": f"2024-03-01T15:0{i}:00Z",
                                 "Partner": "+19195550111", "Duration in Secs": dur,
                                 "Phone Account Address": "+19195550100",
                                 "Raw Call Type (as stored)": "2",
                                 "Phone Account Package": "com.android.phone"})  # fmt: skip
    conn = _db()
    LeappImporter(source_id="d").import_source(lv.write_zip(tmp_path / "d.zip"), conn)
    got = conn.execute("SELECT duration_s FROM calls ORDER BY ts_utc").fetchall()
    assert got == [(None,), (None,), (None,), (2**63 - 1,), (5,)]
    # each length the row states but Mabillon could not read is flagged at its row, and the
    # coverage summary shows it (Claude review and CodeRabbit on #269)
    (t,) = coverage.load(conn, "d").payload["tables"]
    assert t["flag_counts"].get("duration_not_readable") == 3
    assert len(t["flagged_locators"]["duration_not_readable"]) == 3
    s = coverage.summary(conn, "d")
    assert s is not None
    (item,) = [i for i in s.attention if i.code == "duration_not_readable"]
    assert "3 records" in item.plain and len(item.locators) == 3


def test_an_ios_call_duration_sqlite_cannot_hold_is_unknown(tmp_path: Path) -> None:
    # Any importer path: a duration past SQLite's integer range is stored as unknown, and the
    # call is kept (CodeRabbit on #269).
    lv = Lava(leapp="iLEAPP")
    for i, dur in enumerate([str(2**63), "9" * 5000, "00:02:05"]):
        lv.add("callHistory", **{"Starting Timestamp": f"2024-02-01T16:0{i}:00Z",
                                 "Service Provider": "com.apple.Telephony",
                                 "Call Type": "Phone Call", "Call Direction": "Outgoing",
                                 "Phone Number": ALICE, "Answered": "Yes",
                                 "Call Duration": dur})  # fmt: skip
    conn = _db()
    LeappImporter(source_id="ios").import_source(lv.write_zip(tmp_path / "i.zip"), conn)
    got = conn.execute("SELECT duration_s FROM calls ORDER BY ts_utc").fetchall()
    assert got == [(None,), (None,), (125,)]
    # both unreadable lengths are flagged, so the coverage says why each is unknown
    (t,) = coverage.load(conn, "ios").payload["tables"]
    assert t["flag_counts"].get("duration_not_readable") == 2


def test_an_app_call_duration_int_refuses_is_unknown_not_rounded() -> None:
    # 5000 zeros then 2**53 + 1: parse_duration refuses it, and the float fallback would round
    # it to 2**53, a wrong length a duration check could select on (CodeRabbit on #269).
    assert leapp._seconds("0" * 5000 + "9007199254740993") is None
    assert leapp._seconds("83.0") == 83
    assert leapp._seconds("00:01:44") == 104
    assert leapp._seconds("104") == 104


def test_a_received_message_that_does_not_name_the_phones_line_names_no_receivers(
    tmp_path: Path,
) -> None:
    # Claude review on #264: an iOS group message with no Destination Caller ID was stored as
    # to the other members only, and an ALEAPP received MMS as to the numbers it names, so a
    # check between its sender and the phone's owner found nothing and held nothing open.
    lv = Lava(leapp="iLEAPP")
    lv.add("sms", **{"Message Timestamp": "2024-02-02T10:00:00Z", "From Me": "0",
                     "Sender": ALICE, "Message": "hello all", "Message Row ID": "13",
                     "Chat Participants": f"{ALICE},{BOB}", "Chat ID": "4"})  # fmt: skip
    conn = _db()
    LeappImporter(source_id="ios").import_source(lv.write_zip(tmp_path / "i.zip"), conn)
    assert conn.execute("SELECT count(*) FROM message_recipients").fetchone() == (0,)
    flags = coverage.load(conn, "ios").payload["tables"][0]["flag_counts"]
    assert flags["received_without_own_account"] == 1
    conn = _db()
    LeappImporter(source_id="and").import_source(_android().write_zip(tmp_path / "a.zip"), conn)
    got = conn.execute(
        "SELECT count(*) FROM message_recipients r JOIN messages m ON m.id = r.message_id"
        " WHERE m.locator = 'get_sms_mms_mms/msg_id=40'"
    ).fetchone()
    assert got == (0,)


def test_a_call_with_no_direction_keeps_the_call_log_from_being_read_in_full(
    tmp_path: Path,
) -> None:
    # Claude review on #264: a voicemail or blocked call is stored with neither side, so no
    # check finds it; the call log was still listed as read in full.
    lv = _android()
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    assert "unknown" not in coverage.load(conn, "and").payload["apps_read_in_full"]
    lv.tables["get_calllog"] = [
        r for r in lv.tables["get_calllog"] if r.get("Raw Call Type (as stored)") != "6"
    ]
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "b.zip"), conn)
    assert "unknown" in coverage.load(conn, "and").payload["apps_read_in_full"]


def test_a_call_that_names_neither_side_keeps_the_call_log_from_being_read_in_full(
    tmp_path: Path,
) -> None:
    # CodeRabbit on #264: an incoming call with no number on either end (a withheld caller, and
    # no line of the phone's own) is stored with neither side, so no check finds it either.
    lv = _android()
    lv.tables["get_calllog"] = [
        r for r in lv.tables["get_calllog"] if r.get("Raw Call Type (as stored)") != "6"
    ]
    lv.tables["get_calllog"][0] = {
        **lv.tables["get_calllog"][0],
        "Partner": "",
        "Phone Account Address": "",
    }
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    sides = conn.execute(
        "SELECT COUNT(*) FROM calls WHERE from_account_id IS NULL AND to_account_id IS NULL"
    ).fetchone()
    assert sides == (1,)
    assert "unknown" not in coverage.load(conn, "and").payload["apps_read_in_full"]


def test_an_unread_artifact_with_no_stated_count_is_named_as_holding_records(
    tmp_path: Path,
) -> None:
    # Claude review on #264: the not-imported item named only artifacts with a count above
    # zero, so one with rows but no stated count went unnamed.
    def no_count(m: dict) -> None:
        _artifact(m, "wifiNetworks")["record_count"] = None

    conn = _db()
    LeappImporter(source_id="ios").import_source(_zip_with(tmp_path, _ios(), no_count), conn)
    s = coverage.summary(conn, "ios")
    assert s is not None
    item = next(i for i in s.items if i.code == "not_imported")
    text = "".join(t for t, _q in item.parts)
    assert "Wifi Networks" in text.split("Those holding records", 1)[1]


def test_two_texts_from_one_sender_in_one_second_are_flagged_as_maybe_several(
    tmp_path: Path,
) -> None:
    # Claude review on #264: parts are grouped by the whole second with no message id, so "ok"
    # and "on my way" sent in one second import as one message; a count over it must not pass.
    gm = {"Message Timestamp": "2024-03-05T10:00:00Z", "Direction": "Incoming",
          "Message Sender": ALICE, "Conversation ID": "9"}  # fmt: skip
    lv = _gm_lava([], [{**gm, "Message": "ok"}, {**gm, "Message": "on my way"}])
    locs, flags, codes = _gm_imported(tmp_path, lv)
    assert locs == ["get_googlemessages/rowid=1"]
    assert flags["may_be_several_messages"] == 1 and "may_be_several_messages" in codes


def test_texts_from_one_second_never_confirm_a_copy_of_an_sms(tmp_path: Path) -> None:
    # CodeRabbit on #264: a group that may be several messages joined matched an SMS with the
    # same joined text and was skipped as its copy. It is kept, and both are possible copies.
    gm = {"Message Timestamp": "2024-03-05T10:00:00Z", "Direction": "Incoming",
          "Message Sender": ALICE, "Conversation ID": "9"}  # fmt: skip
    sms = {"Date": "2024-03-05T10:00:00Z", "Type": "Received", "Address": ALICE,
           "Body": "ok\non my way"}  # fmt: skip
    lv = _gm_lava([sms], [{**gm, "Message": "ok"}, {**gm, "Message": "on my way"}])
    locs, flags, _codes = _gm_imported(tmp_path, lv)
    assert locs == ["get_googlemessages/rowid=1"]
    assert flags["may_be_same_as_an_sms_or_mms_message"] == 1


def _calls(conn: sqlite3.Connection, app: str) -> list[tuple]:
    return conn.execute(
        "SELECT c.locator, c.direction, f.identifier, t.identifier, c.duration_s FROM calls c"
        " LEFT JOIN accounts f ON f.id = c.from_account_id"
        " LEFT JOIN accounts t ON t.id = c.to_account_id"
        " WHERE c.app = ? ORDER BY c.ts_utc",
        (app,),
    ).fetchall()


def test_android_app_calls_are_read_and_odd_calls_keep_their_app_unread(tmp_path: Path) -> None:
    lv = _android()
    jid = f"{ALICE[1:]}@s.whatsapp.net"
    for t, d, caller, group in (
        ("2024-03-05T10:00:00Z", "Incoming", jid, None),
        ("2024-03-05T10:05:00Z", "Outgoing", jid, None),
        ("2024-03-05T10:10:00Z", "Incoming", jid, "Family"),  # a group call
    ):
        lv.add("get_whatsapp_call_logs", **{"Call Start Timestamp": t, "Call Direction": d,
               "Caller JID": caller, "Call Duration": "65", "Group Name": group})  # fmt: skip
    lv.add("get_Viber", **{"Call Start Time": "2024-03-05T11:00:00Z", "Phone Number": ALICE,
           "Call Direction": "Outgoing",
           "Call End Time (computed: start + duration)": "2024-03-05T11:02:00Z"})  # fmt: skip
    lv.add("get_line_calls", **{"Start Time": "2024-03-05T12:00:00Z", "From ID": "u123",
           "End Time": "2024-03-05T12:00:30Z", "Direction": "Incoming"})  # fmt: skip
    lv.add("get_line_calls", **{"Start Time": "2024-03-05T12:10:00Z", "From ID": "u123",
           "To ID": "u456", "Direction": "Outgoing"})  # fmt: skip
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    tw = "get_whatsapp_call_logs/rowid="
    assert _calls(conn, "WhatsApp") == [
        (f"{tw}1", "incoming", jid, None, 65),
        (f"{tw}2", "outgoing", None, jid, 65),  # the owner's own id is not stated
        (f"{tw}3", "unknown", None, None, 65),  # a group call's parties are not read
    ]
    assert _calls(conn, "Viber") == [("get_viber/rowid=1", "outgoing", None, ALICE, 120)]
    assert _calls(conn, "Line") == [
        ("get_line_calls/rowid=1", "incoming", "u123", None, 30),
        # To ID was empty on every checked call, so a call that names one is not read
        ("get_line_calls/rowid=2", "unknown", None, None, None),
    ]
    payload = coverage.load(conn, "and").payload
    # a call stored with neither side keeps its app from being read in full, and a call table
    # alone holds none of an app's messages (Viber; Claude review on #268)
    assert payload["apps_read_in_full"] == ["Native Messages"]
    tables = {t["name"]: t for t in payload["tables"]}
    assert tables["WhatsApp - Call Logs"]["flag_counts"]["group_call_parties_not_read"] == 1
    assert tables["Line - Call Logs"]["flag_counts"]["call_not_incoming_outgoing_or_missed"] == 1


def test_ios_app_calls_read_missed_calls_and_never_make_an_app_read_in_full(
    tmp_path: Path,
) -> None:
    lv = _ios()
    for t, d, missed in (
        ("2024-02-05T10:00:00Z", "Incoming", "No"),
        ("2024-02-05T10:05:00Z", "Incoming", "Yes"),
        ("2024-02-05T10:10:00Z", "Incoming", "Maybe"),  # a value that was not checked
        ("2024-02-05T10:15:00Z", "Outgoing", "No"),
    ):
        lv.add("whatsAppCallHistory", **{"Starting Timestamp": t, "Direction": d,
               "Missed": missed, "Contact ID": "c1", "Duration H:M:S": "00:01:05"})  # fmt: skip
    for t, result in (("2024-02-05T11:00:00Z", "NORMAL"), ("2024-02-05T11:05:00Z", "CANCELED")):
        lv.add("lineCalls", **{"Call Started": t, "Direction": "Outgoing", "Account ID": "u1",
               "Contact MID": "u9", "Duration (seconds)": "12",
               "Result (as stored)": result})  # fmt: skip
    conn = _db()
    LeappImporter(source_id="ios").import_source(lv.write_zip(tmp_path / "i.zip"), conn)
    tw = "whatsappcallhistory/rowid="
    assert _calls(conn, "WhatsApp") == [
        (f"{tw}1", "incoming", "c1", None, 65),
        (f"{tw}2", "missed", "c1", None, 65),
        (f"{tw}3", "unknown", None, None, 65),
        (f"{tw}4", "outgoing", None, "c1", 65),
    ]
    assert _calls(conn, "Line") == [
        ("linecalls/rowid=1", "outgoing", "u1", "u9", 12),
        ("linecalls/rowid=2", "unknown", None, None, 12),  # only NORMAL calls were checked
    ]
    assert coverage.load(conn, "ios").payload["apps_read_in_full"] == ["Native Messages", "unknown"]


def test_telegram_recovered_rows_are_possible_copies(tmp_path: Path) -> None:
    lv = _android()
    for t, d, sid, origin in (
        ("2024-03-06T10:00:00Z", "Incoming", "777", "Live"),
        ("2024-03-06T10:01:00Z", "Outgoing", "111", "Live"),
        ("2024-03-06T10:00:00Z", "Incoming", "777", "Recovered"),
    ):
        lv.add("get_telegramMessages", **{"Timestamp": t, "Direction": d, "Sender ID": sid,
               "Sender": "Al", "Message": "hi", "Dialog ID": "42", "Chat": "Al",
               "Record Origin": origin})  # fmt: skip
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    rows = conn.execute(
        "SELECT m.locator, m.direction, a.identifier, a.device_id IS NOT NULL FROM messages m"
        " JOIN threads t ON t.id = m.thread_id LEFT JOIN accounts a ON a.id = m.sender_account_id"
        " WHERE t.app = 'Telegram' ORDER BY m.locator"
    ).fetchall()
    tg = "get_telegrammessages/rowid="
    assert rows == [
        (f"{tg}1", "incoming", "777", 0),
        (f"{tg}2", "outgoing", "111", 1),  # a sent row's Sender ID is the owner's
        (f"{tg}3", "incoming", "777", 0),
    ]
    payload = coverage.load(conn, "and").payload
    assert payload["numbered_copy_records"] == [f"msg:and:{tg}3"]
    assert "Telegram" in payload["apps_read_in_full"]


def test_telegram_call_notices_are_calls_not_messages(tmp_path: Path) -> None:
    # Claude review on #268: ALEAPP writes Telegram calls as chat rows; on the Android 13 phone
    # each one matched a UFDR Telegram call on time, direction, caller and length.
    lv = _android()
    for t, d, sid, text in (
        ("2024-03-06T10:00:00Z", "Outgoing", "111",
         "[Phone call (call id 638, outcome hung up, duration seconds 105)]"),
        ("2024-03-06T10:05:00Z", "Incoming", "777",
         "[Phone call (call id 585, outcome hung up, duration seconds 9)]"),
        ("2024-03-06T10:10:00Z", "Incoming", "777",
         "[Phone call (call id 586, outcome missed, duration seconds 0)]"),
        ("2024-03-06T10:15:00Z", "Incoming", "777", "hi"),
    ):  # fmt: skip
        lv.add("get_telegramMessages", **{"Timestamp": t, "Direction": d, "Sender ID": sid,
               "Message": text, "Dialog ID": "42", "Record Origin": "Live"})  # fmt: skip
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    tg = "get_telegrammessages/rowid="
    assert _calls(conn, "Telegram") == [
        (f"{tg}1", "outgoing", "111", None, 105),
        (f"{tg}2", "incoming", "777", None, 9),
        (f"{tg}3", "unknown", None, None, None),  # only answered calls were checked
    ]
    bodies = conn.execute(
        "SELECT m.body FROM messages m JOIN threads t ON t.id = m.thread_id"
        " WHERE t.app = 'Telegram'"
    ).fetchall()
    assert bodies == [("hi",)]
    payload = coverage.load(conn, "and").payload
    assert "Telegram" not in payload["apps_read_in_full"]  # a call with no sides
    flags = {t["name"]: t for t in payload["tables"]}["Telegram - Messages"]["flag_counts"]
    assert flags["call_notice_read_as_call"] == 3


def test_a_call_log_row_from_another_app_keeps_every_chat_app_partial(tmp_path: Path) -> None:
    # Claude review on #268: a VoIP app can write its calls to Android's call log, where they
    # are stored under the call log, not the app.
    lv = _android()
    lv.add("get_telegramMessages", **{"Timestamp": "2024-03-06T10:00:00Z", "Message": "hi",
           "Direction": "Incoming", "Sender ID": "777", "Dialog ID": "42",
           "Record Origin": "Live"})  # fmt: skip
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    assert "Telegram" in coverage.load(conn, "and").payload["apps_read_in_full"]
    lv.tables["get_calllog"][0] = {
        **lv.tables["get_calllog"][0],
        "Phone Account Package": "org.telegram.messenger",
    }
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "b.zip"), conn)
    payload = coverage.load(conn, "and").payload
    assert "Telegram" not in payload["apps_read_in_full"]
    flags = {t["name"]: t for t in payload["tables"]}["Call logs "]["flag_counts"]
    assert flags["call_placed_by_another_app"] == 1
    # another app's call is not a phone call, so it keeps neither side (Claude review on #268)
    assert _calls(conn, "unknown")[0] == ("get_calllog/rowid=1", "incoming", None, None, 42)


def test_a_length_that_is_not_a_finite_number_is_no_length() -> None:
    assert leapp._seconds("inf") is None and leapp._seconds("1e999") is None
    assert leapp._seconds("00:01:05") == 65 and leapp._seconds("83.0") == 83


def test_ios_snapchat_messages_are_read_by_username(tmp_path: Path) -> None:
    lv = _ios()
    for origin in ("Live", "Recovered"):
        lv.add("snapchatMessages", **{"Creation Timestamp": "2024-02-06T10:00:00Z",
               "Message Direction": "Incoming", "Sender Username": "al.snap",
               "Message Text": "yo", "Conversation ID": "c1",
               "Record Origin": origin})  # fmt: skip
    conn = _db()
    LeappImporter(source_id="ios").import_source(lv.write_zip(tmp_path / "i.zip"), conn)
    rows = conn.execute(
        "SELECT m.direction, m.body, a.identifier FROM messages m"
        " JOIN threads t ON t.id = m.thread_id LEFT JOIN accounts a ON a.id = m.sender_account_id"
        " WHERE t.app = 'Snapchat'"
    ).fetchall()
    assert rows == [("incoming", "yo", "al.snap")] * 2
    # iLEAPP writes recovered rows here too (3 of 21 on the iOS 15 phone; Claude review on #268)
    copies = coverage.load(conn, "ios").payload["numbered_copy_records"]
    assert copies == ["msg:ios:snapchatmessages/rowid=2"]


@pytest.mark.parametrize(
    ("key", "column", "app"),
    [
        ("get_calllog", "Partner", "unknown"),
        ("get_sms_mms", "Address", "Native Messages"),
        ("get_telegramMessages", "Record Origin", "Telegram"),
        ("get_Viber", "Phone Number", "Viber"),
    ],
)
def test_a_table_missing_a_column_is_not_read_at_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, key: str, column: str, app: str
) -> None:
    from eval.synthetic import leapp as synth

    headers = tuple(h for h in synth.HEADERS[key] if (h if isinstance(h, str) else h[0]) != column)
    monkeypatch.setitem(synth.HEADERS, key, headers)
    lv = _android()
    lv.add("get_telegramMessages", **{"Timestamp": "2024-03-06T10:00:00Z", "Message": "hi",
           "Direction": "Incoming", "Sender ID": "777", "Dialog ID": "42"})  # fmt: skip
    lv.add("get_Viber", **{"Call Start Time": "2024-03-05T11:00:00Z", "Phone Number": ALICE,
           "Call Direction": "Outgoing"})  # fmt: skip
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    payload = coverage.load(conn, "and").payload
    failed = [e for e in payload["not_imported"] if e.get("read_failed")]
    assert [e["name"] for e in failed] == [synth.NAMES[key][1]]
    assert app not in payload["apps_read_in_full"]
    tables = {t["name"]: t for t in payload["tables"]}
    # listed only as not read, never as a table read with no rows (Claude review on #268)
    assert synth.NAMES[key][1] not in tables


def test_aleapp_whatsapp_calls_never_make_whatsapp_read_in_full(tmp_path: Path) -> None:
    # Claude review on #268: a group call started outside a group chat has no Group Name, and
    # ALEAPP does not read its participants, so it cannot be told from a two-party call.
    lv = _android()
    lv.add("get_whatsapp_call_logs", **{"Call Start Timestamp": "2024-03-05T10:00:00Z",
           "Call Direction": "Incoming", "Caller JID": f"{ALICE[1:]}@s.whatsapp.net"})  # fmt: skip
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    assert coverage.load(conn, "and").payload["apps_read_in_full"] == ["Native Messages"]


def _telegram(lv: Lava, text: str, direction: str = "Incoming", sender: str | None = "777",
              origin: str = "Live") -> None:  # fmt: skip
    lv.add("get_telegramMessages", **{"Timestamp": "2024-03-06T10:00:00Z", "Message": text,
           "Direction": direction, "Sender ID": sender, "Dialog ID": "42",
           "Record Origin": origin})  # fmt: skip


def _telegram_flags(payload: dict) -> dict:
    return {t["name"]: t for t in payload["tables"]}["Telegram - Messages"]["flag_counts"]


def test_a_call_notice_length_that_cannot_be_read_is_unknown_and_flagged(tmp_path: Path) -> None:
    # CodeRabbit on #269: a notice's stated length past SQLite's range, or with more digits than
    # int() reads, keeps the call with length unknown and flagged, and the import goes on.
    lv = _android()
    for secs in (str(2**63), "9" * 5000, "40"):
        _telegram(lv, f"[Phone call (call id 9, outcome hung up, duration seconds {secs})]")
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    got = conn.execute("SELECT duration_s FROM calls WHERE app = 'Telegram'").fetchall()
    assert sorted(got, key=str) == sorted([(None,), (None,), (40,)], key=str)
    assert _telegram_flags(coverage.load(conn, "and").payload)["duration_not_readable"] == 2


def test_a_message_that_only_starts_like_a_call_notice_stays_a_message(tmp_path: Path) -> None:
    # Claude review on #268: only LEAPP's own notice shape is read as a call.
    # CodeRabbit on #268: so does one that opens like a notice but is not one in full.
    lv = _android()
    typed = ("[Phone call me later]", "[Phone call (call id 638, please call tomorrow]")
    for text in typed:
        _telegram(lv, text)
    _telegram(lv, "[Phone call (call id 999)]")  # a notice whose record holds no outcome
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    assert _calls(conn, "Telegram") == [
        ("get_telegrammessages/rowid=3", "unknown", None, None, None)
    ]
    bodies = conn.execute(
        "SELECT m.body FROM messages m JOIN threads t ON t.id = m.thread_id"
        " WHERE t.app = 'Telegram' ORDER BY m.locator"
    ).fetchall()
    assert bodies == [(t,) for t in typed]
    # Claude review on #268: one that opens like a notice is flagged and keeps Telegram partial
    payload = coverage.load(conn, "and").payload
    assert _telegram_flags(payload)["call_notice_shape_not_checked"] == 1
    assert "Telegram" not in payload["apps_read_in_full"]


def test_a_notice_in_a_shape_not_checked_stays_a_message_and_keeps_the_app_partial(
    tmp_path: Path,
) -> None:
    # Claude review on #268: an outcome or field ALEAPP may write that was not checked.
    lv = _android()
    for text in (
        "[Phone call (call id 77, outcome declined, duration seconds 0)]",
        "[Phone call (call id 78, video, outcome hung up, duration seconds 40)]",
    ):
        _telegram(lv, text)
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    assert _calls(conn, "Telegram") == []
    payload = coverage.load(conn, "and").payload
    assert _telegram_flags(payload)["call_notice_shape_not_checked"] == 2
    assert "Telegram" not in payload["apps_read_in_full"]


def test_a_notice_with_no_direction_is_flagged_once(tmp_path: Path) -> None:
    # Claude review on #268: direction_not_stated already says why it has no sides.
    lv = _android()
    _telegram(lv, "[Phone call (call id 638, outcome hung up, duration seconds 105)]",
              direction="")  # fmt: skip
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    flags = _telegram_flags(coverage.load(conn, "and").payload)
    assert flags["direction_not_stated"] == 1
    assert "call_not_incoming_outgoing_or_missed" not in flags


def test_a_notice_with_a_negative_length_is_not_a_checked_call(tmp_path: Path) -> None:
    # CodeRabbit on #268: only a length of zero or more was seen.
    lv = _android()
    _telegram(lv, "[Phone call (call id 638, outcome hung up, duration seconds -1)]")
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    assert _calls(conn, "Telegram") == [
        ("get_telegrammessages/rowid=1", "unknown", None, None, None)
    ]
    flags = _telegram_flags(coverage.load(conn, "and").payload)
    assert flags["call_not_incoming_outgoing_or_missed"] == 1


def test_two_entries_on_one_table_each_read_their_own_column_map() -> None:
    # CodeRabbit on #268: the column cache holds stored names, mapped per entry.
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE t (a TEXT, b TEXT)")
    lava = leapp.Lava({}, db, "m", "d", "ALEAPP", None, [])
    one = leapp.Artifact("x", "1", "k1", "t", "m", {"a": "A"}, None, None)
    two = leapp.Artifact("x", "2", "k2", "t", "m", {"a": "Z"}, None, None)
    assert lava.headers(one) == {"A", "b"} and lava.headers(two) == {"Z", "b"}


def test_a_recovered_call_notice_is_a_possible_copy(tmp_path: Path) -> None:
    # Claude review on #268: a recovered call may repeat a live one, so a count over it is
    # inconclusive, as for a recovered message.
    lv = _android()
    _telegram(lv, "[Phone call (call id 638, outcome hung up, duration seconds 105)]",
              origin="Recovered")  # fmt: skip
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    payload = coverage.load(conn, "and").payload
    assert payload["numbered_copy_records"] == ["call:and:get_telegrammessages/rowid=1"]


def test_a_placed_call_notice_with_no_sender_is_flagged(tmp_path: Path) -> None:
    # Claude review on #268: the notice is stored with no sides and says why.
    lv = _android()
    _telegram(lv, "[Phone call (call id 638, outcome hung up, duration seconds 105)]",
              direction="Outgoing", sender=None)  # fmt: skip
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    assert _calls(conn, "Telegram") == [
        ("get_telegrammessages/rowid=1", "unknown", None, None, 105)
    ]
    assert _telegram_flags(coverage.load(conn, "and").payload)["sent_without_own_account"] == 1


def test_an_ios_call_with_no_sides_keeps_the_call_log_partial_whatever_its_app(
    tmp_path: Path,
) -> None:
    # Claude review on #268: a FaceTime row in the phone's own call table that names no
    # direction kept only FaceTime partial, though it is in the call log too.
    lv = _ios()
    lv.add("callHistory", **{"Starting Timestamp": "2024-02-05T10:00:00Z",
           "Service Provider": "com.apple.FaceTime", "Phone Number": ALICE})  # fmt: skip
    conn = _db()
    LeappImporter(source_id="ios").import_source(lv.write_zip(tmp_path / "i.zip"), conn)
    assert "unknown" not in coverage.load(conn, "ios").payload["apps_read_in_full"]


def test_a_call_log_row_naming_no_package_keeps_its_sides_and_is_flagged(
    tmp_path: Path,
) -> None:
    # Claude review on #268: a row with no package may be another app's call, so no chat app is
    # read in full, but it is kept as a phone call.
    lv = _android()
    _telegram(lv, "hi")
    del lv.tables["get_calllog"][2:]  # the fixture's call with no direction
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "base.zip"), conn)
    assert "unknown" in coverage.load(conn, "and").payload["apps_read_in_full"]
    lv.tables["get_calllog"][0] = {**lv.tables["get_calllog"][0], "Phone Account Package": None}
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    payload = coverage.load(conn, "and").payload
    assert "Telegram" not in payload["apps_read_in_full"]
    # nor is the call log itself held in full (Claude review on #268)
    assert "unknown" not in payload["apps_read_in_full"]
    flags = {t["name"]: t for t in payload["tables"]}["Call logs "]["flag_counts"]
    assert flags["call_package_not_stated"] == 1
    assert "call_placed_by_another_app" not in flags
    assert _calls(conn, "unknown")[0] == ("get_calllog/rowid=1", "incoming", ALICE, OWNER, 42)


def test_a_chat_app_whose_listed_call_table_was_not_read_is_not_read_in_full(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Claude review on #268: with a call table listed for the app but not read (absent
    # included), the app's calls are not held, so its chats alone are not the app in full.
    lv = _android()
    _telegram(lv, "hi")
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    assert "Telegram" in coverage.load(conn, "and").payload["apps_read_in_full"]
    spec = leapp.CallSpec("Telegram", "Start", "Direction", "Partner")
    monkeypatch.setitem(leapp.CALL_SPECS, ("ALEAPP", "get_telegram_calls"), spec)
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "b.zip"), conn)
    assert "Telegram" not in coverage.load(conn, "and").payload["apps_read_in_full"]


def test_an_sms_table_refused_for_its_columns_never_stands_for_a_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # CodeRabbit on #268: the SMS table was refused, yet its row still made the Google Messages
    # copy of it be skipped, so the message was in neither table.
    from eval.synthetic import leapp as synth

    lv = _gm_lava(
        [{"Date": "2024-03-01T12:00:00Z", "Type": "Received", "Address": ALICE, "Body": "OK"}],
        [{"Message Timestamp": "2024-03-01T12:00:01Z", "Direction": "Incoming",
          "Message Sender": ALICE, "Message": "OK", "Conversation ID": "9"}],
    )  # fmt: skip
    assert _gm_imported(tmp_path, lv)[0] == []  # a copy of the SMS, skipped
    headers = tuple(h for h in synth.HEADERS["get_sms_mms"] if h != "Thread ID")
    monkeypatch.setitem(synth.HEADERS, "get_sms_mms", headers)
    assert _gm_imported(tmp_path, lv)[0] == ["get_googlemessages/rowid=1"]


def test_an_outgoing_whatsapp_call_with_an_unchecked_missed_value_has_no_sides(
    tmp_path: Path,
) -> None:
    # CodeRabbit on #268: only "No", and "Yes" on an incoming call, were checked.
    lv = _ios()
    for missed in ("No", "Maybe", "Yes"):
        lv.add("whatsAppCallHistory", **{"Starting Timestamp": "2024-02-05T10:15:00Z",
               "Direction": "Outgoing", "Missed": missed, "Contact ID": "c1"})  # fmt: skip
    conn = _db()
    LeappImporter(source_id="ios").import_source(lv.write_zip(tmp_path / "i.zip"), conn)
    directions = [r[1:4] for r in _calls(conn, "WhatsApp")]
    assert sorted(directions) == [
        ("outgoing", None, "c1"), ("unknown", None, None), ("unknown", None, None)
    ]  # fmt: skip


def test_a_telegram_only_run_holds_calls_and_no_chat_app_in_full(tmp_path: Path) -> None:
    # CodeRabbit on #268: with no call log in the run, Telegram was read in full, and the calls
    # stored from its call notices were not named among the kinds read.
    lv = Lava(leapp="ALEAPP")
    lv.add("get_telegramMessages", **{"Timestamp": "2024-03-06T10:00:00Z", "Direction": "Outgoing",
           "Sender ID": "111", "Dialog ID": "42", "Record Origin": "Live",
           "Message": "[Phone call (call id 1, outcome hung up, duration seconds 5)]"})  # fmt: skip
    conn = _db()
    LeappImporter(source_id="and").import_source(lv.write_zip(tmp_path / "a.zip"), conn)
    payload = coverage.load(conn, "and").payload
    assert payload["apps_read_in_full"] == []
    assert "calls" in payload["categories_read"]
    assert "calls" not in payload["categories_not_found"]


@pytest.mark.parametrize("second", [False, True])
def test_an_unread_call_log_entry_keeps_every_chat_app_partial(
    tmp_path: Path, second: bool
) -> None:
    # CodeRabbit on #268: one call log entry read through must not hide another that was not,
    # since a VoIP app's calls can sit in the call log rather than the app's own tables.
    lv = _android()
    lv.add("get_telegramMessages", **{"Timestamp": "2024-03-06T10:00:00Z", "Direction": "Outgoing",
           "Sender ID": "111", "Dialog ID": "42", "Record Origin": "Live",
           "Message": "hi"})  # fmt: skip

    def change(m: dict) -> None:
        if second:
            a = _artifact(m, "get_calllog")
            m["artifacts"].setdefault("Call Logs", []).append({**a, "tablename": "not_there"})

    conn = _db()
    LeappImporter(source_id="and").import_source(_zip_with(tmp_path, lv, change), conn)
    payload = coverage.load(conn, "and").payload
    assert ("Telegram" in payload["apps_read_in_full"]) is not second
