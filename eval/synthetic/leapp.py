"""Synthetic iLEAPP and ALEAPP output (a LAVA manifest and database), for tests only.

It writes what LEAPP's `scripts/lavafuncs.py` writes for an artifact: a table named from the
sanitized function name, columns named from the sanitized headers, a `column_map` back to the
headers, datetime columns as INTEGER UTC epochs, and a manifest entry per artifact. The headers
and their order are LEAPP's own for the artifacts Mabillon reads (iLEAPP `sms`, `callHistory`,
`addressBook`; ALEAPP `get_sms_mms`, `get_sms_mms_mms`, `get_googleMessages`, `get_calllog`,
`contacts`). Every value
is made up.
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
            "processing_status": "Complete",
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
