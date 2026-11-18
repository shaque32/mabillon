"""Synthetic iLEAPP and ALEAPP output (a LAVA manifest and database), for tests only.

It writes what LEAPP's `scripts/lavafuncs.py` writes for an artifact: a table named from the
sanitized function name, columns named from the sanitized headers, a `column_map` back to the
headers, datetime columns as INTEGER UTC epochs, and a manifest entry per artifact. The headers
and their order are LEAPP's own for the artifacts Mabillon reads (iLEAPP `sms`, `callHistory`,
`addressBook`; ALEAPP `get_sms_mms`, `get_sms_mms_mms`, `get_googleMessages`, `get_calllog`,
`contacts`; and the chat and call tables below). Every value is made up.
"""

from __future__ import annotations

import io
import json
import re
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

Header = str | tuple[str, str]

HEADERS: dict[str, tuple[Header, ...]] = {
    "sms": (
        ("Message Timestamp", "datetime"), ("Read Timestamp", "datetime"),
        ("Delivered Timestamp", "datetime"), ("Attachment Timestamp", "datetime"),
        "From Me", "Sender", "Chat Contact ID", "Message", ("Attachment File", "media"),
        "Chat Name", "Chat Participants", "Service", "Message Direction", "Message Sent",
        "Message Delivered", "Message Read", "Account", "Account Login", "Destination Caller ID",
        "Attachment Name", "Attachment Mimetype", "Attachment Size (Bytes)", "Message Row ID",
        ("Message GUID", "hash"), "Chat ID",
    ),
    "callHistory": (
        ("Starting Timestamp", "datetime"), ("Ending Timestamp", "datetime"), "Service Provider",
        "Call Type", "Call Direction", ("Phone Number", "phonenumber"), "Answered",
        "Call Duration", "FaceTime Data", "Disconnected Cause", "ISO Country Code", "Location",
    ),
    "addressBook": (
        ("Creation Date", "datetime"), ("Modification Date", "datetime"), "First Name",
        "Last Name", "Display Name", "Company", ("Phone Numbers", "phonenumber"),
        "Email addresses",
    ),
    "get_sms_mms": (
        ("Date", "datetime"), ("Date Sent", "datetime"), "Type", "Address", "Body", "MSG ID",
        "Thread ID", "Contact ID", "Read", "Service Center", "Error Code",
    ),
    "get_sms_mms_mms": (
        ("Date", "datetime"), ("Date Sent", "datetime"), "Direction", "From Address", "Body",
        ("Media", "media"), "MSG ID", "Thread ID", "Read", "To Address", "Cc", "Bcc",
    ),
    "get_googleMessages": (
        ("Message Timestamp", "datetime"), "Direction", ("Message Sender", "phonenumber"),
        "Other Participant/Conversation Name", "Message", "Message Type", "Attachment Byte Size",
        "Attachment Location", "Conversation ID",
    ),
    "get_calllog": (
        ("Call Date", "datetime"), "Phone Account Address", "SIM ICCID", "Phone Account Package",
        ("Partner", "phonenumber"), "Raw Call Type (as stored)", "Type", "Duration in Secs",
        "Partner Location", "Country ISO", "Data", "Mime Type", "Transcription", "Deleted",
    ),
    "contacts": (
        "Mimetype", "Data 1", "Display Name", "Phone Number", "Email Address", "Source File",
    ),
    "wifiNetworks": (("Last Joined", "datetime"), "SSID", "BSSID"),
    # device tables Mabillon reads the phone's zone and OS from
    "powerlogTimeZone": (
        ("Timestamp", "datetime"), "Time Zone Name", "Seconds From GMT (as stored)",
        "Is In DST (as stored)", "Country Code", "Locale ID", "Trigger",
        "Time Offset (seconds)", "Source File",
    ),
    "timezone_info": ("Property", "Property Value"),
    "last_build": ("Property", "Property Value"),
    "get_battery_usage_v4": (
        ("Timestamp", "datetime"), "Application", "Package Name", "Hidden",
        ("Boot Timestamp", "datetime"), "Timezone", "Total Power", "Consumed Power",
        "% Of Consumed", "Foreground Usage (Seconds)", "Background Usage (Seconds)",
        "Battery Level (%)", "Battery Status",
    ),
    "usagestatsVersion": ("Property", "Property Value"),
    # chat apps, read through LEAPP's conversation view
    "whatsAppMessages": (
        ("Timestamp", "datetime"), "Direction", "From ID", "Chat Name", "Message",
        ("Attachment File", "media"), "Local User or Chat Name", "Receiver", "To ID", "Thumb",
        "Starred?", "Metadata Field 17 (forward count, observed)",
        "Metadata Field 21 (forwarder, observed)", "Latitude", "Longitude", "Chat ID",
    ),
    "instagramDirectMessages": (
        ("Timestamp", "datetime"), ("Media Taken At", "datetime"), "Direction",
        "Sender Username", "Message", "Thread", "Item Type (as stored)",
        "Content Type (as stored)", "Media URL", "Media Owner Username", "Sender ID",
        "Thread ID", "Item ID",
    ),
    "get_telegramMessages": (
        ("Timestamp", "datetime"), "Dialog ID", "Chat", "Direction", "Sender ID", "Sender",
        "Message", "Record Origin", ("Recorded Media Path", "media"), "Media File",
        "Read State", "Message ID", "Recovery Method", "Recovery Location", "Source File",
    ),
    "snapchatMessages": (
        ("Creation Timestamp", "datetime"), ("Read Timestamp", "datetime"),
        "Message Direction", "Sender Username", "Message Text", ("Media", "media"),
        "Created On Device", "Record Origin", "Sender Display Name", "Sender ID",
        "Conversation Participants", "Content Type (as stored)", "Message State Type",
        "Is Saved", "Is Viewed By User", "Remote Media Count", "Quoted Server Message ID",
        "Conversation ID", "Client Message ID", "Server Message ID", "Local Media ID",
        "Recovery Method", "Recovery Location",
    ),
    # app calls
    "get_whatsapp_call_logs": (
        ("Call Start Timestamp", "datetime"), ("Call End Timestamp", "datetime"),
        "Call Duration", "Group Name", "Call Direction", "Caller", "Caller JID", "Call Type",
    ),
    "get_Viber": (
        ("Call Start Time", "datetime"), ("Phone Number", "phonenumber"), "Call Direction",
        ("Call End Time (computed: start + duration)", "datetime"),
        "Viber Call Type (as stored)",
    ),
    "get_line_calls": (
        ("Start Time", "datetime"), ("End Time", "datetime"), "To ID", "From ID", "Direction",
        "Call Type", "Android User",
    ),
    "whatsAppCallHistory": (
        ("Starting Timestamp", "datetime"), ("Ending Timestamp", "datetime"),
        "Duration H:M:S", "Direction", "Disconnected cause", "Contact ID",
        "Incoming (as stored)", "Video Call", "Missed", "Missed Reason (as stored)",
        "Bytes Sent", "Bytes Received", "Call ID", "Group JID", "Aggregate Event ID",
        "Contact Fullname", ("Phone Number", "phonenumber"),
    ),
    "lineCalls": (
        ("Call Started", "datetime"), ("Call Ended", "datetime"), "Direction", "Contact",
        "Contact MID", "Type (as stored)", "Duration (seconds)", "Result (as stored)",
        "Cause (as stored)", "Message ID", "Account ID",
    ),
}  # fmt: skip
# LEAPP's conversation view for the chat artifacts above (the manifest's data_views), with the
# columns named as the database names them.
DATA_VIEWS: dict[str, dict[str, Any]] = {
    "whatsAppMessages": {
        "conversationDiscriminatorColumn": "chat_id", "conversationLabelColumn": "chat_name",
        "textColumn": "message", "directionColumn": "direction",
        "directionSentValue": "Outgoing", "timeColumn": "timestamp", "senderColumn": "from_id",
        "mediaColumn": "attachment_file",
    },
    "instagramDirectMessages": {
        "conversationDiscriminatorColumn": "thread", "textColumn": "message",
        "directionColumn": "direction", "directionSentValue": "Outgoing",
        "timeColumn": "timestamp", "senderColumn": "sender_username",
    },
    "snapchatMessages": {
        "conversationDiscriminatorColumn": "conversation_id", "textColumn": "message_text",
        "directionColumn": "message_direction", "directionSentValue": "Outgoing",
        "timeColumn": "creation_timestamp", "senderColumn": "sender_username",
        "mediaColumn": "media",
    },
}  # fmt: skip
NAMES = {
    "sms": ("SMS & iMessage", "SMS"),
    "callHistory": ("Call History", "Call History"),
    "addressBook": ("Contacts", "Address Book"),
    "get_sms_mms": ("SMS & MMS", "SMS Messages"),
    "get_sms_mms_mms": ("SMS & MMS", "MMS Messages"),
    "get_googleMessages": ("Google Messages", "GoogleMessages"),
    "get_calllog": ("Call Logs", "Call logs "),
    "contacts": ("Contacts", "Contacts"),
    "wifiNetworks": ("WiFi", "Wifi Networks"),
    "powerlogTimeZone": ("PowerLog", "PowerLog - Time Zone"),
    "timezone_info": ("Identifiers", "App Store Preferences"),
    "last_build": ("IOS Build", "iOS Information"),
    "get_battery_usage_v4": ("Settings Services", "battery_usage_v4"),
    "usagestatsVersion": ("Device Information", "OS Version"),
    "whatsAppMessages": ("WhatsApp", "WhatsApp - Messages"),
    "instagramDirectMessages": ("Instagram", "Instagram - Direct Messages"),
    "get_telegramMessages": ("Telegram", "Telegram - Messages"),
    "snapchatMessages": ("Snapchat", "Snapchat - Messages (arroyo.db)"),
    "get_whatsapp_call_logs": ("WhatsApp", "WhatsApp - Call Logs"),
    "get_Viber": ("Viber", "Viber - Call Logs"),
    "get_line_calls": ("Line", "Line - Call Logs"),
    "whatsAppCallHistory": ("WhatsApp", "WhatsApp - Call History"),
    "lineCalls": ("Line", "Line - Calls"),
}


def sanitize(name: str) -> str:
    """LEAPP's sanitize_sql_name."""
    s = re.sub(r"[^\w\s]", "", name)
    s = re.sub(r"\s+", "_", s)
    if s and not s[0].isalpha() and s[0] != "_":
        s = "_" + s
    return s.lower()


def epoch(iso: str) -> int:
    """'2024-02-01T15:04:05Z' -> the INTEGER epoch LAVA stores."""
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(UTC).timestamp())


@dataclass
class Lava:
    leapp: str = "iLEAPP"  # or "ALEAPP"
    version: str = "2026.4.7-dev"
    input_type: str = "tar"
    profile_used: bool = False
    status: str = "Complete"  # processing_status; LEAPP writes "In Progress" until a run ends
    tables: dict[str, list[dict[str, Any]]] = field(default_factory=dict)  # key -> rows by header

    def add(self, key: str, **values: Any) -> None:
        self.tables.setdefault(key, []).append(values)

    def build(self) -> tuple[dict[str, Any], bytes]:
        """(manifest, database bytes)."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "_lava_artifacts.db"
            db = sqlite3.connect(path)
            artifacts: dict[str, list[dict[str, Any]]] = {}
            for key, rows in self.tables.items():
                headers = HEADERS[key]
                cols, cmap = [], {}
                for h in headers:
                    name, kind = (h, None) if isinstance(h, str) else h
                    s = sanitize(name)
                    cmap[s] = name
                    cols.append((s, "INTEGER" if kind == "datetime" else "TEXT", name, kind))
                table = sanitize(key)
                db.execute(
                    f'CREATE TABLE "{table}" (' + ", ".join(f'"{c[0]}" {c[1]}' for c in cols) + ")"
                )
                for r in rows:
                    vals = []
                    for _s, _t, name, kind in cols:
                        v = r.get(name)
                        if kind == "datetime" and isinstance(v, str) and v:
                            v = epoch(v)
                        vals.append(v)
                    db.execute(f'INSERT INTO "{table}" VALUES ({", ".join("?" * len(cols))})', vals)  # noqa: S608  (synthetic table names)
                category, name = NAMES[key]
                artifacts.setdefault(category, []).append(
                    {
                        "artifact_key": key,
                        "name": name,
                        "tablename": table,
                        "module": key,
                        "column_map": cmap,
                        "record_count": len(rows),
                        "source_path": f"/synthetic/{key}.db",
                        **(
                            {"data_views": {"conversation": dict(DATA_VIEWS[key])}}
                            if key in DATA_VIEWS
                            else {}
                        ),
                    }
                )
            db.commit()
            db.close()
            data = path.read_bytes()
        manifest = {
            "lava_schema_version": 2,
            "parser_info": {"leapp_name": self.leapp, "leapp_version": self.version},
            "param_input": "/synthetic/extraction.tar",
            "param_output": "/synthetic/out",
            "param_type": self.input_type,
            "param_profile": None,
            "profile_used": self.profile_used,
            "case_data": {},
            "processing_status": self.status,
            "lava_db_name": "_lava_artifacts.db",
            "modules": [],
            "artifacts": artifacts,
            "meta": {"modules": []},
        }
        return manifest, data

    def write_zip(self, path: Path, folder: str = "LEAPP_Reports_2026-11-16_Monday_120000") -> Path:
        manifest, data = self.build()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(f"{folder}/_lava_data.lava", json.dumps(manifest, indent=1))
            z.writestr(f"{folder}/_lava_artifacts.db", data)
            z.writestr(f"{folder}/_HTML/index.html", "<html></html>")
        path.write_bytes(buf.getvalue())
        return path
