"""The validation run on public Hickman phones (eval/validation/PREREGISTERED*.md).

    python -m eval.validation.hickman_run --ufdr PHONE.ufdr --claims CLAIMS.jsonl --out DIR
    python -m eval.validation.hickman_run --phone ios17=IOS.zip --phone a14=A14.zip \
        --definitions HEADER.json --claims CLAIMS.jsonl --out DIR

`--ufdr` is one phone, the TARGET PHONE that SUBJECT-1 used (validation v1 to v4). Each `--phone`
(v5) is a package, a UFDR or a zip of one iLEAPP or ALEAPP output, picked by
core/ingest/pick.py; with two, the header's `phones` gives each phone's name and user.

It builds one case the way an expert would, then runs `mabillon audit` with its defaults:
1. checks the claims file, and the package's report.xml (--ufdr) or each package file
   (--phone-sha256), against the hashes it is given;
2. renders the claims as a numbered affidavit PDF (paragraph n is claim n's text, verbatim);
3. creates DIR/case.db in local mode, imports each phone, imports the affidavit, adds each
   claim to its paragraph, and sets the case up as the affidavit defines it: each phone gets its
   name (the TARGET PHONE), its user (SUBJECT-1, a stipulation) and the zone the header gives,
   when its package records none (a package that records another zone, or a LEAPP phone that
   kept more than one, stops the build); each other SUBJECT-<n> the claims name is a
   person. A person the affidavit's header defines by a telephone number ("SUBJECT-2 is the user
   of telephone number (919) 888-7386") is linked to each account whose identifier is that
   number, written any way (a WhatsApp id 19198887386@s.whatsapp.net too), never to an account
   by its display name;
4. runs the audit with the product's local components (no AI reviewer, no cloud), or with
   --cloud, with Claude (core/llm/cloud.py) for the two model jobs an audit of given claims
   runs: assumption filling and stance labeling. Stance goes through the product's cloud path
   (the signed cloud prompt, every request in the audit log, a sticky failure pauses the run);
   the filler gets the same logging and pausing here, until the product routes it to the cloud
   (CLAUDE.md, signed 2026-11-09). --max-usd stops the run once its estimated spend passes the
   figure, as a sticky failure would; out of API credit stops it the same way. Resume with the
   same DIR: finished claims reuse their stored answers and cost nothing;
5. writes DIR/report.html, DIR/run.json (versions, machine, times) and DIR/results.zip. If the
   report's own checks refuse it, run.json says why and the results go out without it.

The claims file holds claims only, never their answers: the run machine never sees the key.
Run it again with the same DIR to resume: a built case is kept, and the audit reuses the model
outputs of the claims it finished. A case built by an earlier SETUP is refused, never resumed.
--fake swaps in the eval's stand-in components (tests only).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import zipfile
from contextlib import closing, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from core.audit.assumption_filler import NATIVE_CALL_APP
from core.audit.checks._common import namespace
from core.contracts import ClaimType, DocKind
from core.db import apply_schema, connect

ACTOR = "expert:validation"
SOURCE_ID = "ios15"  # the default; --source-id names another phone (validation v4)
OWNER = "SUBJECT-1"
PHONE_NAME = "TARGET PHONE"  # the affidavit's name for the phone
# The people the affidavit defines, found in the claims text by this rule alone (never from the
# answers): every SUBJECT-<n> written in a claim.
SUBJECT = re.compile(r"\bSUBJECT-\d+\b")
# The affidavit's header defines these people by a telephone number (PREREGISTERED_v3.md, R4). The
# number is the definition, as the phone is SUBJECT-1's: a premise of the affidavit, not a claim.
DEFINED_NUMBERS = {"SUBJECT-2": "(919) 888-7386"}
# --definitions FILE replaces them with the affidavit header another claims writer wrote (v4,
# PREREGISTERED_v4.md): {"SUBJECT-<n>": "<telephone number>", ..., "phone_time_zone": "<zone>"},
# the zone optional and given to the case as the examiner's statement (--phone-zone).
ZONE_KEY = "phone_time_zone"
PHONES_KEY = "phones"
# An identifier that is a telephone number: digits with + ( ) - . and spaces, or a WhatsApp id.
_NUMBER_ID = re.compile(r"\+?[\d\s().-]+(?:@s\.whatsapp\.net)?")
TITLE = "AFFIDAVIT (VALIDATION V1, HICKMAN PUBLIC IMAGE, NOT A REAL CASE)"
# The batch 3 writer typed "content" for content_meaning; ClaimType has no "content". The claim
# type only picks which checks run; the signed answers do not depend on it.
TYPE_ALIASES = {"content": "content_meaning"}
RESULT_FILES = ("case.db", "run.json", "report.html", "progress.log")
# How build() sets the case up. A case built by an earlier setup is not resumed: run 1's case
# (setup 1) had no phone name and no SUBJECT-2; run 2's (setup 2) had no account for SUBJECT-2;
# setup 3 (v4) held one phone and did not record what its import read (setup 4 records each);
# setup 4 did not tie the case.db to its build, so a case.db restored from another build of the
# same packages (other claims, ids, types or zones) could not be told apart (setup 5 does, by a
# build id in both built.ok and the case's audit log; CodeRabbit on #269). Setup 5, on #269's
# branch only, could leave the id out of both; setup 6 always writes it, and a resume refuses a
# built.ok that records none.
SETUP = 6
BUILD_ACTION = "validation.build"


def stamp_build(conn) -> str:  # noqa: ANN001
    """Write a new build id to the case's audit log and return it, for built.ok to record."""
    import uuid

    from core.review import audit_log

    build_id = uuid.uuid4().hex
    audit_log.append(conn, datetime.now(UTC), ACTOR, BUILD_ACTION, {"build_id": build_id})
    conn.commit()
    return build_id


def open_existing(db: Path, missing: str | None = None) -> sqlite3.Connection:
    """Open a case.db read-write but never create it: a case.db moved away stops the run with
    `missing` (or the restore advice), not with an empty file left in its place (CodeRabbit on
    #269). The driver's cases are never encrypted."""
    try:
        conn = sqlite3.connect(f"{db.resolve().as_uri()}?mode=rw", uri=True)
    except sqlite3.OperationalError as e:
        raise SystemExit(
            missing
            or f"{db} is gone since the run checked it ({e}); restore the case.db it was built"
            " with, or use a new --out"
        ) from e
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def check_build(conn, out: Path, built: dict) -> None:  # noqa: ANN001
    """Stop unless the open case.db holds the build `built` records."""
    if not built.get("build_id"):
        raise SystemExit(
            f"{out}/built.ok records no build id, so its case.db cannot be tied to its"
            " build; use a new --out"
        )
    if stamped_build(conn) != built["build_id"]:
        raise SystemExit(
            f"{out}/case.db is not the case built.ok records (another build's case.db);"
            " restore the case.db it was built with, or use a new --out"
        )


def stamped_build(conn) -> str | None:  # noqa: ANN001
    """The build id the case's audit log holds (the last one written), or None."""
    row = conn.execute(
        "SELECT payload_json FROM audit_log WHERE action = ? ORDER BY seq DESC LIMIT 1",
        (BUILD_ACTION,),
    ).fetchone()
    return json.loads(row[0]).get("build_id") if row else None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def report_xml_sha256(ufdr: Path) -> str:
    """The SHA-256 of the package's report.xml, streamed out of the zip."""
    from core.ingest.ufdr import find_report

    h = hashlib.sha256()
    with zipfile.ZipFile(ufdr) as z, z.open(find_report(z)) as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def load_claims(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if [r["para_no"] for r in rows] != list(range(1, len(rows) + 1)):
        raise SystemExit(f"{path}: paragraphs must run 1..n in order")
    if any("label" in r or "key_evidence" in r for r in rows):
        raise SystemExit(f"{path}: holds answers; the run machine gets claims only")
    for r in rows:
        r["claim_type"] = ClaimType(TYPE_ALIASES.get(r["claim_type"], r["claim_type"])).value
    return rows


def render_affidavit(claims: list[dict], path: Path) -> Path:
    """Claim n as printed paragraph n, laid out like the synthetic govdoc fixtures."""
    from eval.synthetic import govdocs as g

    paras = (g.Para(TITLE, heading=True),) + tuple(g.Para(c["text"], c["para_no"]) for c in claims)
    g._write(g._layout(paras, indent_style=False), path, TITLE)
    return path


def load_definitions(path: Path) -> dict:
    """The affidavit header a claims writer hands over. Refused unless every key is a
    SUBJECT-<n> other than a phone's user, defined by a telephone number; the phones' zone; or
    `phones`, the phones the affidavit names (validation v5): {source id: {"name": the name the
    document gives the phone, "owner": the SUBJECT-<n> who used it, "zone": optional}}."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SystemExit(f"--definitions: {e}") from None
    if not isinstance(raw, dict):
        raise SystemExit("--definitions: an object of names to strings")
    phones = raw.get(PHONES_KEY)
    if phones is not None:
        if not isinstance(phones, dict) or not phones:
            raise SystemExit(f"--definitions: {PHONES_KEY} is an object of source ids to phones")
        for sid, spec in phones.items():
            if (
                not isinstance(spec, dict)
                or not {"name", "owner"} <= spec.keys() <= {"name", "owner", "zone"}
                or not all(isinstance(v, str) and v.strip() for v in spec.values())
            ):
                raise SystemExit(
                    f"--definitions: phone {sid!r} needs a name and an owner (and may give a"
                    " zone), each a string"
                )
            if not SUBJECT.fullmatch(spec["owner"]):
                raise SystemExit(f"--definitions: phone {sid!r}'s owner is not a SUBJECT-<n>")
    owners = sorted({s["owner"] for s in phones.values()}) if phones else [OWNER]
    for key, value in raw.items():
        if key == PHONES_KEY:
            continue
        if not isinstance(value, str):
            raise SystemExit("--definitions: an object of names to strings")
        if key == ZONE_KEY:
            continue
        if not SUBJECT.fullmatch(key) or key in owners:
            # A phone's user is the phone's stipulated owner, never linked to accounts by a
            # number as well: on another phone, that number's records stay unlinked (fail closed).
            raise SystemExit(
                f"--definitions: {key!r} is not a SUBJECT-<n> other than {', '.join(owners)}"
            )
        if number_digits(value) is None:
            raise SystemExit(f"--definitions: {key} is defined by {value!r}, not a number")
    return raw


@dataclass(frozen=True)
class Phone:
    """One phone in the case: its package, the name the affidavit gives it, who used it (a
    stipulation), and the zone the examiner gives for it (used only when the package records
    none, and refused when the package records another)."""

    source_id: str
    path: Path
    name: str = PHONE_NAME
    owner: str = OWNER
    zone: str | None = None
    sha256: str | None = None  # the package file's expected SHA-256, checked on import

    def record(self) -> dict:
        return {
            "source_id": self.source_id,
            "file": self.path.name,
            "name": self.name,
            "owner": self.owner,
            "zone_given": self.zone,
        }


def _pairs(values: list[str], flag: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for v in values:
        key, sep, rest = v.partition("=")
        if not sep or not key or not rest:
            raise SystemExit(f"{flag}: write SOURCE_ID=VALUE, not {v!r}")
        if key in out:
            raise SystemExit(f"{flag}: {key} is given twice")
        out[key] = rest
    return out


def _sid(phone: dict) -> str:
    return phone["source_id"]


def _hashes(values: list[str]) -> dict[str, str]:
    """--phone-sha256 values, lowercased: sha256sum prints lowercase hex, a hash copied in
    uppercase is the same digest (Claude review on #267)."""
    return {k: v.strip().lower() for k, v in _pairs(values, "--phone-sha256").items()}


def phones_from(a, defs: dict | None) -> list[Phone]:  # noqa: ANN001
    """The case's phones, from --ufdr (one phone, the v1 to v4 setup) or each --phone, with
    names, owners and zones from the definitions' `phones` (needed when there are two)."""
    from core.zones import resolve_zone

    zone_all = (defs or {}).get(ZONE_KEY)
    # one zone written two ways is the same zone, as in every other zone check (Claude review)
    if zone_all and a.phone_zone and resolve_zone(zone_all) != resolve_zone(a.phone_zone):
        raise SystemExit(f"--phone-zone {a.phone_zone} differs from the definitions' {zone_all}")
    zone_all = a.phone_zone or zone_all
    if a.ufdr is not None:
        if a.phone:
            raise SystemExit("--ufdr names one phone; use --phone for each phone instead")
        paths = {a.source_id: str(a.ufdr)}
    else:
        if not a.phone:
            raise SystemExit("name the phone: --ufdr PACKAGE, or --phone SOURCE_ID=PACKAGE")
        if a.source_id != SOURCE_ID:
            raise SystemExit("--source-id goes with --ufdr; --phone names each source id")
        paths = _pairs(a.phone, "--phone")
    hashes = _hashes(a.phone_sha256 or [])
    if hashes.keys() - paths.keys():
        raise SystemExit(f"--phone-sha256: no phone {sorted(hashes.keys() - paths.keys())[0]}")
    specs = (defs or {}).get(PHONES_KEY)
    if specs is None:
        if len(paths) > 1:
            raise SystemExit(
                f"--definitions: two phones need {PHONES_KEY}, naming each phone and its user"
            )
        specs = {sid: {} for sid in paths}
    if specs.keys() != paths.keys():
        raise SystemExit(
            f"--definitions: {PHONES_KEY} names {sorted(specs)}, the packages are {sorted(paths)}"
        )
    for sid in sorted(specs):
        own = specs[sid].get("zone")
        if own and zone_all and resolve_zone(own) != resolve_zone(zone_all):
            # Neither silently wins: a phone's zone sets how every stated window on it is read
            # (Claude review on #267).
            raise SystemExit(
                f"--definitions: {PHONES_KEY}.{sid}.zone is {own}, but the zone given for"
                f" every phone is {zone_all}; give one"
            )
    phones = [
        Phone(
            source_id=sid,
            path=Path(path),
            name=specs[sid].get("name", PHONE_NAME),
            owner=specs[sid].get("owner", OWNER),
            zone=specs[sid].get("zone") or zone_all,
            sha256=hashes.get(sid),
        )
        for sid, path in paths.items()
    ]
    names = [" ".join(p.name.split()).casefold() for p in phones]
    if len(set(names)) != len(names):
        raise SystemExit("--definitions: two phones have the same name")
    owners = [p.owner for p in phones]
    if len(set(owners)) != len(owners):
        # A device-owner stipulation records a person per phone (core/review/actions), so one
        # SUBJECT-<n> on two phones would be two people of one name, and every claim naming
        # them would be refused (CodeRabbit on #267).
        raise SystemExit("--definitions: two phones have the same user; give each its own")
    return phones


def build(  # noqa: ANN001
    phones: list[Phone],
    claims: list[dict],
    out: Path,
    log,
    defined: dict[str, str] | None = None,
) -> tuple[list[dict], str]:
    """Build the case. Returns what each phone's import recorded (importer, file hash, zone)
    and the build id, stamped on the connection that built the case, so no other case.db put
    in its place between two connections can carry it (CodeRabbit on #269)."""
    from core.ingest.govdoc import PdfGovDocIngester
    from core.ingest.pick import report_importer
    from core.ingest.source_file import InputChanged
    from core.review import actions
    from core.timeline.records import zone as zone_info
    from core.zones import resolve_zone

    db = out / "case.db"
    db.unlink(missing_ok=True)
    conn = connect(db)
    # Closed on a refusal too: a SystemExit's traceback keeps this frame, and an open
    # connection locks case.db on Windows for the next build (CI on #267).
    try:
        apply_schema(conn)
        defined = DEFINED_NUMBERS if defined is None else defined
        imported = []
        for ph in phones:
            t = time.monotonic()
            importer = report_importer(ph.path)
            try:
                src = importer(source_id=ph.source_id, expected_sha256=ph.sha256).import_source(
                    ph.path, conn
                )
            except InputChanged as e:
                raise SystemExit(f"--phone-sha256: {e}") from None
            log(
                f"imported {src.file_name} as {ph.source_id}"
                f" ({importer.name}, {src.fidelity.value}) in {time.monotonic() - t:.0f} s"
            )
            rec = {**ph.record(), "importer": importer.name, "sha256": src.sha256}
            imported.append(rec)
            # The phone's name, zone and user are set right after its import, so a zone the run
            # cannot use stops it before the next import (Claude review on #267).
            dev = f"dev:{ph.source_id}"
            try:
                actions.name_device(conn, dev, [ph.name], ACTOR)
            except actions.ReviewError as e:
                raise SystemExit(f"--definitions: {ph.source_id}: {e}") from None
            (recorded,) = conn.execute(
                "SELECT timezone FROM devices WHERE id = ?", (dev,)
            ).fetchone()
            rec["zone_recorded"] = recorded
            rec["zone_set_by_examiner"] = False  # True only when the given zone is the case's
            if recorded and zone_info(resolve_zone(recorded)) is None:
                # A recorded zone this tool cannot read: the examiner's zone cannot replace the
                # source's, and every stated window on the phone would be refused, so the run
                # stops before any model call, given zone or not (Claude review on #267).
                raise SystemExit(
                    f"--phone-zone: the extraction records {ph.source_id}'s zone as"
                    f" {recorded!r}, which names no time zone this tool can read"
                )
            if recorded and ph.zone:
                # The source's own zone is kept; the examiner's must say the same, or the claims'
                # times and the phone's would be read in two zones.
                if resolve_zone(recorded) != resolve_zone(ph.zone):
                    raise SystemExit(
                        f"--phone-zone: the extraction records {ph.source_id}'s zone ({recorded}),"
                        f" not {ph.zone}"
                    )
                log(f"{ph.source_id}: the package records the zone given ({recorded})")
            elif len(seen := zones_seen(conn, ph.source_id)) > 1:
                # The package records no zone because the phone kept more than one (LEAPP's
                # leapp.device.zones_seen): one given zone would misread part of its times, and
                # with none every stated window on it would be refused, so the run stops here
                # rather than score a phone it cannot read (CodeRabbit on #267).
                raise SystemExit(
                    f"--phone-zone: {ph.source_id} recorded {len(seen)} zones"
                    f" ({', '.join(seen)}), so no one zone can be given for it"
                )
            elif ph.zone:
                if seen and resolve_zone(seen[0]) != resolve_zone(ph.zone):
                    # One zone in the phone's tables, left unrecorded only because some zone values
                    # could not be read: the given zone must still say the same (Claude review).
                    raise SystemExit(
                        f"--phone-zone: {ph.source_id}'s own tables name the zone {seen[0]},"
                        f" not {ph.zone}"
                    )
                # The examiner's statement of the zone, for a package that records none.
                try:
                    actions.set_device_zone(conn, dev, ph.zone, ACTOR)
                except actions.ReviewError as e:
                    raise SystemExit(f"--phone-zone: {e}") from None
                rec["zone_set_by_examiner"] = True
                log(f"{ph.source_id}: the phone's zone, as the examiner gives it: {ph.zone}")
            elif seen and not recorded:
                # One zone in the phone's tables, unrecorded only because some zone values could
                # not be read, and none given: every stated window on it would be refused, as
                # with two zones, so the run stops and names the zone to give (Claude review).
                raise SystemExit(
                    f"--phone-zone: {ph.source_id}'s tables name the zone {seen[0]} but the"
                    f" importer did not record it; give it with --phone-zone or in the header"
                )
            elif not recorded:
                log(
                    f"{ph.source_id}: no zone recorded or given; its times cannot be read as stated"
                )
            # A phone call log with rows but no call a check can read (each row placed by
            # another app, or of no direction or time) would leave the claims about its phone
            # calls unreadable: the run stops here, before any model call (gate G5b).
            stop, note = call_log_check(conn, ph.source_id, importer.name)
            if stop:
                raise SystemExit(f"{ph.source_id}: {stop}")
            if note:
                log(f"{ph.source_id}: {note}")
            actions.stipulate_device_owner(conn, dev, ph.owner, ACTOR)
        _, paragraphs = PdfGovDocIngester(DocKind.AFFIDAVIT).ingest(
            render_affidavit(claims, out / "affidavit.pdf"), conn
        )
        by_label = {p.label: p for p in paragraphs if p.label}
        for c in claims:
            para = by_label.get(str(c["para_no"]))
            if para is None:
                raise SystemExit(f"{c['claim_id']}: the ingester found no paragraph {c['para_no']}")
            kind = ClaimType(c["claim_type"])
            actions.add_claim(conn, c["claim_id"], para.id, c["text"], kind, ACTOR)
        owners = {ph.owner for ph in phones}
        others = sorted(set(SUBJECT.findall(" ".join(c["text"] for c in claims))) - owners)
        linked = {}
        for name in others:
            pid = actions.add_person(conn, name, ACTOR)
            if name in defined:
                linked[name] = link_defined_number(conn, pid, defined[name])
        build_id = stamp_build(conn)
    finally:
        conn.close()
    log(
        f"case built: {len(claims)} claims on {len(paragraphs)} paragraphs; "
        + "; ".join(f"{ph.name} is {ph.source_id}, used by {ph.owner}" for ph in phones)
        + f"; other people: {', '.join(others) or 'none'}"
        + "".join(f"; {n} linked to {len(ids)} accounts by number" for n, ids in linked.items())
    )
    return imported, build_id


def zones_seen(conn, source_id: str) -> list[str]:  # noqa: ANN001
    """The zones a LEAPP import found in the phone's own tables (leapp.device.zones_seen in its
    coverage record); empty for another importer, or when the phone's tables name none."""
    from core.ingest import coverage

    cov = coverage.load(conn, source_id)
    device = (cov.payload.get("leapp") or {}).get("device") or {} if cov else {}
    return sorted({z["zone"] for z in device.get("zones_seen", [])})


def _one_line(value: object) -> str:
    """A package's text, kept on one log line (a table name with a line break must not read
    as a separate driver entry; CodeRabbit on #269)."""
    return str(value).replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n")


def _marks(values: list[str]) -> str:
    """One SQL parameter mark per value."""
    return ", ".join("?" * len(values))


def _ts_ok(value: object) -> int:
    """1 when the caller check's time parser reads the stored value as a time, else 0."""
    from core.audit.checks._common import _ts

    try:
        return int(isinstance(value, str) and _ts(value) is not None)
    except (ValueError, TypeError, OverflowError):
        return 0


def call_log_check(  # noqa: ANN001
    conn, source_id: str, importer: str | None, *, owner_confirmed: bool = False
) -> tuple[str | None, str | None]:
    """(why the run stops, what to log) for the phone's own call log (v5 readiness gate G5b).

    It stops when a call log table of the phone (LEAPP's `get_calllog` or `callHistory`) holds
    rows but no phone call (app NATIVE_CALL_APP) was stored from it with a time and the other
    party on the side its direction names: every row was placed by another app (ALEAPP's
    Samsung samples name another package), had no direction, no other party or no readable
    time, so no check could read any of the phone's calls.
    Calls of a provider app in the same table (FaceTime on iOS) are not phone calls and do not
    count. It stops too when such a table holds records the import could not read at all.
    Otherwise it logs how many phone calls a check can read. A
    UFDR's coverage names no such table: never stopped here. A LEAPP phone (by `importer`, as
    the build recorded it) whose case holds no LEAPP coverage record stops: its call log
    cannot be checked. With `owner_confirmed` (on resume, after the build stipulated the
    owner), the phone's own accounts count only on a device with exactly one confirmed
    device_owner stipulation, as the caller check reads them: a stipulation withdrawn since the
    build stops the run."""
    from core.audit.checks.caller import _PLACED_BY_OTHER, _PLACED_BY_PHONE
    from core.ingest import coverage
    from core.ingest.leapp import IMPORTER_NAME, IOS_CALL_APPS, NATIVE_CALL_KEYS

    def is_native(key: object) -> bool:  # any ASCII case, as the importer reads it (CodeRabbit)
        return isinstance(key, str) and key.isascii() and key.lower() in native_keys

    native_keys = {k.lower() for k in NATIVE_CALL_KEYS}

    cov = coverage.load(conn, source_id)
    p = cov.payload if cov else {}
    leapp = p.get("leapp")
    if leapp is None:
        # a LEAPP phone whose record is gone (a case.db swapped on resume), or a phone whose
        # importer was not recorded, fails closed (CodeRabbit on #269)
        if importer == IMPORTER_NAME:
            return (
                "its LEAPP import left no coverage record in this case, so its call log cannot"
                " be checked; restore the case.db it was built with, or build it again with a"
                " new --out"
            ), None
        if importer is None:
            return (
                "the build did not record which importer read it, so its call log cannot be"
                " checked; build it again with a new --out"
            ), None
        return None, None  # another importer: no LEAPP call log tables
    unread = p.get("not_imported") or []
    if any("key" not in t for t in unread):
        # an import stored before each unread entry kept its artifact key: an unread call log
        # under another table name could not be told apart, so the case is rebuilt (CodeRabbit)
        return (
            "this case was imported before unread tables kept their artifact key, so an unread"
            " call log cannot be ruled out; build it again with a new --out"
        ), None

    def may_hold(t: dict) -> bool:
        # rows may be there: the importer says so, or the manifest counts some, or neither is
        # known (fail closed); a table known to be empty passes (CodeRabbit on #269)
        records, holds = t.get("records"), t.get("may_hold_records")
        return holds is True or (records or 0) > 0 or (holds is None and records is None)

    for t in unread:
        if not str(t.get("key") or "").strip() and may_hold(t):
            # an entry the manifest gives neither a key nor a table: a rebuild lists it again,
            # so the manifest is named instead; one known empty passes (CodeRabbit on #269)
            return (
                f"the LEAPP manifest lists an entry with neither an artifact key nor a table"
                f" ({_one_line(t.get('name') or 'no name')}, {t.get('records')} records) that"
                " may hold records, so an unread call log cannot be ruled out; check the LEAPP"
                " output before any model call"
            ), None
    # by the importer's own artifact keys, never by table name: a manifest may name its table
    # otherwise (CodeRabbit on #269). The tables are only for the locators of stored calls.
    native = {str(a.get("table")) for a in leapp.get("artifacts_read") or []
              if is_native(a.get("key"))}  # fmt: skip
    if not native and not any(is_native(t.get("key")) for t in unread):
        # no call log entry at all, read or not: claims about its calls would go untested
        # without a word (Claude review on #269)
        return (
            "its LEAPP output lists no phone call log (get_calllog or callHistory), so claims"
            " about its phone calls would go untested; check the LEAPP output before any model"
            " call"
        ), None
    for t in unread:
        records = t.get("records")
        if is_native(t.get("key")) and may_hold(t):
            return (
                f"its call log ({_one_line(t.get('table') or 'no table named')}, {records}"
                " records) was not read"
                f" ({_one_line(t.get('reason'))}); claims about its phone calls would go"
                " untested, so the run stops before any model call"
            ), None
    # The caller check puts the phone's owner on a call only through the phone's own accounts
    # (person_party: the accounts on the device a confirmed device_owner stipulation names):
    # with none, no call on it can be read, whatever its rows hold (CodeRabbit on #269).
    # On resume the owner was stipulated at build: it must still be one confirmed owner, since
    # a withdrawn stipulation leaves the accounts but no owner a check can read (CodeRabbit).
    (owned,) = conn.execute(
        "SELECT count(*) FROM accounts a JOIN devices d ON d.id = a.device_id"
        " WHERE d.source_id = ? AND (? = 0 OR (SELECT count(DISTINCT s.person_id)"
        " FROM stipulations s WHERE s.kind = 'device_owner' AND s.subject_id = d.id"
        " AND s.status = 'confirmed') = 1)",
        (source_id, int(owner_confirmed)),
    ).fetchone()
    # a call log the manifest counts records in but whose table gave no row: the calls it
    # counts were never read, so no check could find them (CodeRabbit on #269)
    got: dict[str, int] = {}
    for t in p.get("tables") or []:
        if isinstance(t, dict) and t.get("kind") == "calls":
            loc = str(t.get("header_locator") or "")
            got[loc] = got.get(loc, 0) + int(t.get("rows_read") or 0)
    for a in leapp.get("artifacts_read") or []:
        n = a.get("records")
        if is_native(a.get("key")) and isinstance(n, int) and n > 0:
            if got.get(str(a.get("table")), 0) == 0:
                return (
                    f"its call log ({_one_line(a.get('table'))}) counts {n} records in its"
                    " manifest but none was read; claims about its phone calls would go"
                    " untested, so the run stops before any model call"
                ), None
    by_phone, by_other = sorted(_PLACED_BY_PHONE), sorted(_PLACED_BY_OTHER)
    known = sorted(set(IOS_CALL_APPS.values()))
    # a time counts only when the caller check's own parser reads it (CodeRabbit on #269)
    conn.create_function("mabillon_ts_ok", 1, _ts_ok, deterministic=True)
    notes = []
    for t in p.get("tables") or []:
        if not isinstance(t, dict):
            continue
        table = str(t.get("header_locator") or "")
        read = int(t.get("rows_read") or 0)
        if t.get("kind") != "calls" or table not in native or read == 0:
            continue
        # this table's own rows only ("TABLE/rowid=N"), never another table whose name starts
        # with this one and a slash (CodeRabbit on #269)
        own = (len(table) + 1, f"{table}/", len(table) + 2)
        # a call a check can read, as the caller check reads it (_placed_by, by its own
        # direction sets): a known time, and the other side stored where the direction puts it
        # (not the phone's own line, whose account carries the phone's device), the phone's side
        # empty or its own (CodeRabbit and Claude review on #269). One pass gives the phone
        # calls, the readable ones, every call stored, and those of an app that is neither the
        # phone nor a known provider app (FaceTime).
        rows, sided, stored, unknown_app = conn.execute(
            "SELECT coalesce(sum(c.app = ?), 0), coalesce(sum(c.app = ?"  # noqa: S608 (marks only; values bound)
            " AND mabillon_ts_ok(c.ts_utc) AND CASE"
            f" WHEN c.direction IN ({_marks(by_phone)}) THEN t.id IS NOT NULL"
            " AND t.device_id IS NOT c.device_id"
            " AND (f.id IS NULL OR f.device_id IS c.device_id)"
            f" WHEN c.direction IN ({_marks(by_other)}) THEN f.id IS NOT NULL"
            " AND f.device_id IS NOT c.device_id"
            " AND (t.id IS NULL OR t.device_id IS c.device_id)"
            f" ELSE 0 END), 0), count(*), coalesce(sum(c.app NOT IN ({_marks(known)})), 0)"
            " FROM calls c"
            " LEFT JOIN accounts f ON f.id = c.from_account_id"
            " LEFT JOIN accounts t ON t.id = c.to_account_id"
            " WHERE c.source_id = ?"
            " AND substr(c.locator, 1, ?) = ? AND instr(substr(c.locator, ?), '/') = 0",
            (NATIVE_CALL_APP, NATIVE_CALL_APP, *by_phone, *by_other, *known, source_id, *own),
        ).fetchone()
        # no phone call to read, and a row that is no phone call, no call at all, a call of an
        # app Mabillon does not know as a provider (an iOS phone provider written another way
        # would read so), or fewer calls stored than rows read (the importer stores one call
        # per row, so a phone call may be gone): stop. A FaceTime-only history whose every row
        # is stored passes (Claude review and CodeRabbit on #269).
        if sided == 0 and (rows > 0 or stored < read or unknown_app > 0):
            flags = ", ".join(f"{k} {v}" for k, v in sorted((t.get("flag_counts") or {}).items()))
            return (
                f"its call log ({_one_line(table)}) has {read} rows but no phone call a check can"
                f" read was stored (flags: {_one_line(flags or 'none')}"
                + (
                    f"; {unknown_app} calls of an app not known as a call provider"
                    if unknown_app
                    else ""
                )
                + (f"; {stored} calls stored" if stored < read else "")
                + "); claims about its phone"
                " calls would go untested, so the run stops before any model call"
            ), None
        if sided and not owned:
            return (
                f"its call log ({_one_line(table)}) has {sided} phone calls with the other party"
                " stored, but the phone has no account of its own in the case (no line or handle"
                " the import tied to it"
                + (", or no one confirmed device owner" if owner_confirmed else "")
                + "), so no check can put its owner on a call; claims about"
                " its phone calls would go untested, so the run stops before any model call"
            ), None
        notes.append(f"{_one_line(table)}: {sided} of {read} rows are phone calls a check can read")
    return None, ("; ".join(notes) or None)


def number_digits(identifier: str, app: str | None = None) -> str | None:
    """The national digits of an identifier that is a telephone number, else None: '+1 (919)
    888-7386', '19198887386' and '19198887386@s.whatsapp.net' all give '9198887386'. Bare
    digits are a number only on a phone app or the call log (`app` None, or its namespace
    "tel"): on another app they are a user id (Codex on #169)."""
    ident = identifier.strip()
    if not _NUMBER_ID.fullmatch(ident):
        return None
    if (
        app is not None
        and not ident.startswith("+")
        and not ident.endswith("@s.whatsapp.net")
        and namespace(app) != "tel"
        and app != NATIVE_CALL_APP
    ):
        return None
    digits = re.sub(r"\D", "", identifier.split("@", 1)[0])
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits if len(digits) == 10 else None


def link_defined_number(conn, person_id: str, number: str) -> list[str]:  # noqa: ANN001
    """Link the person to every account whose identifier is the defined number (R4). A display
    name never links; nor does a number inside a longer identifier. Returns the account ids."""
    from core.review import actions

    want = number_digits(number)
    ids = [
        aid
        for aid, app, ident in conn.execute("SELECT id, app, identifier FROM accounts ORDER BY id")
        if ident and number_digits(ident, app or "") == want
    ]
    note = f"The affidavit defines {person_id} as the user of telephone number {number}."
    for aid in ids:
        actions.link_account(conn, aid, person_id, ACTOR, note)
    return ids


def machine() -> dict:
    info: dict = {"python": sys.version.split()[0], "platform": platform.platform()}
    smi = shutil.which("nvidia-smi")
    try:
        if smi is None:
            raise OSError("no nvidia-smi")
        info["gpu"] = subprocess.run(  # noqa: S603 - fixed arguments
            [smi, "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        info["gpu"] = None
    try:
        import llama_cpp

        info["llama_cpp_python"] = llama_cpp.__version__
        info["gpu_offload"] = bool(llama_cpp.llama_supports_gpu_offload())
    except ImportError:
        info["llama_cpp_python"] = None
    return info


# Dollars per million (input, output) tokens. A copy of eval/bench/claude_bench.py's table, which
# the installer does not ship; tests/test_validation_run.py checks the two agree.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


class Budgeted:
    """A cloud model that counts its spend and stops once it passes a cap. The cap and the
    out-of-credit stop both raise a sticky CloudError, which pauses the audit (CloudPaused):
    the answers stored so far are kept, and a resume picks up where it stopped."""

    def __init__(self, model, max_usd: float | None, spent_usd: float = 0.0) -> None:  # noqa: ANN001
        self._m = model
        self.name, self.sha256 = model.name, model.sha256
        self.params, self.where = model.params, getattr(model, "where", "cloud")
        self.max_usd = max_usd
        self.spent_usd = spent_usd
        self.calls = self.input_tokens = self.output_tokens = 0
        self._price = PRICES_PER_MTOK.get(model.name)

    def request(self, prompt: str, schema):  # noqa: ANN001, ANN201
        return self._m.request(prompt, schema)

    def prepare(self) -> None:
        prepare = getattr(self._m, "prepare", None)
        if prepare is not None:
            prepare()

    def _count(self, out) -> None:  # noqa: ANN001
        if out is None:
            return
        inp, outp = int(out.prompt_tokens or 0), int(out.completion_tokens or 0)
        self.input_tokens += inp
        self.output_tokens += outp
        if self._price is not None:
            self.spent_usd += (inp * self._price[0] + outp * self._price[1]) / 1_000_000

    def generate_json(self, prompt: str, schema, params=None):  # noqa: ANN001, ANN201
        from core.llm.cloud import CloudError

        if self.max_usd is not None and self.spent_usd >= self.max_usd:
            raise CloudError(
                f"the run's spend cap of ${self.max_usd:.2f} is reached"
                f" (${self.spent_usd:.2f} spent)",
                sticky=True,
            )
        self.calls += 1
        try:
            out = self._m.generate_json(prompt, schema, params)
        except CloudError as e:
            self._count(getattr(e, "response", None))
            raise
        self._count(out)
        return out

    def usage(self) -> dict:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "spent_usd": round(self.spent_usd, 2),
        }


def cloud_components(conn, model):  # noqa: ANN001, ANN201
    """The product's components with Claude filling assumptions and labeling stance."""
    from core import pipeline
    from core.audit import assumption_filler, stance

    # The product's cloud path for every job (#254): each request logged before it is sent,
    # and a sticky failure pauses the audit (core/audit/_local_model.py open_cloud_run).
    filler = assumption_filler.create(conn, cloud_model=model)
    labeler = stance.create(conn, cloud_model=model)
    return pipeline.real_components(conn, replace={"labeler": labeler}, filler=filler)


def owner_stop(conn, phones: list[dict]) -> str | None:  # noqa: ANN001
    """Why a case may not be audited: a phone's device no longer has the one confirmed owner
    the build stipulated (an owner changed since would leave the claims naming the defined owner
    with no person to find; CodeRabbit on #269), or None."""
    for p in phones:
        # by person id, so two confirmed owners of one name are two, and the one the
        # build stipulated (person:<device>:owner), not another of that name (CodeRabbit)
        owners = sorted(
            (str(n), str(pid), str(did))
            for (pid, n, did) in conn.execute(
                "SELECT DISTINCT s.person_id, pe.name, d.id FROM stipulations s"
                " JOIN devices d ON d.id = s.subject_id"
                " JOIN persons pe ON pe.id = s.person_id"
                " WHERE d.source_id = ? AND s.kind = 'device_owner'"
                " AND s.status = 'confirmed'",
                (_sid(p),),
            )
        )
        if [n for n, _, _ in owners] != [p.get("owner")]:
            names = ", ".join(n for n, _, _ in owners) or "no one"
            return (
                f"{_sid(p)}: its confirmed device owner is"
                f" {_one_line(names)}, not {p.get('owner')} as"
                " built; restore the case.db it was built with, or use a new --out"
            )
        (_, pid, did) = owners[0]
        if pid != f"person:{did}:owner":
            return (
                f"{_sid(p)}: its confirmed device owner is {p.get('owner')} under"
                f" {_one_line(pid)}, not the person the build stipulated; restore the"
                " case.db it was built with, or use a new --out"
            )
    return None


LOCK = "run.lock"  # held by the one invocation using DIR
AUDITED = "audited.db"  # the copy of the audited case the report and results.zip are made from
REFUSED = "the device owners or call log changed during the audit, so it is not scored"


def case_stop(conn, built: dict) -> str | None:  # noqa: ANN001
    """Why the case on `conn` no longer is the one `built` records as checked: a device owner
    changed (owner_stop) or a phone's call log that no longer passes gate G5b."""
    stop = owner_stop(conn, sorted(built.get("phones") or [], key=_sid))
    if stop:
        return stop
    for p in sorted(built.get("imported") or [], key=_sid):
        why, _ = call_log_check(conn, p["source_id"], p.get("importer"), owner_confirmed=True)
        if why:
            return f"{p['source_id']}: {why}"
    return None


def audit(out: Path, fake: bool, log, cloud_model=None, *, built: dict) -> dict:  # noqa: ANN001
    """Audit the case in out/case.db. `built` is the build record main() checked or wrote, not
    read again from disk, so a built.ok swapped together with its case.db is refused too. On
    success out/audited.db is a copy of the audited case, taken on the connection that ran the
    checks and the audit, which the report and results.zip are made from (never case.db read
    again by path; CodeRabbit on #269)."""
    from core import pipeline
    from core.review import audit_log

    (out / AUDITED).unlink(missing_ok=True)  # never ship an earlier attempt's copy

    # The case.db checked before the audit may have been swapped or changed since: the audit
    # runs only on the very case that record names, with the owners it was built with
    # (CodeRabbit on #269).
    conn = open_existing(out / "case.db")
    try:
        check_build(conn, out, built)
        # ...and each phone's call log still passes gate G5b on this connection, so a call row
        # changed since the build or resume check stops the run before any model call. A
        # change after this check is caught by the same check after the audit (CodeRabbit).
        stop = case_stop(conn, built)
        if stop:
            raise SystemExit(stop)
        if fake:
            from eval.pipeline_fakes import fake_components

            comps = fake_components()
        elif cloud_model is not None:
            comps = cloud_components(conn, cloud_model)
        else:
            comps = pipeline.real_components(conn)  # local model, no AI reviewer, no cloud
        # The run 3 plan keeps the challenge step off (on by default since #162), so run 3
        # changes only the filler and stays comparable to run 2. The audit's configuration
        # records it.
        comps.challenge = False

        def progress(done: int, total: int, d) -> None:  # noqa: ANN001
            spent = f" (${cloud_model.spent_usd:.2f} spent)" if cloud_model is not None else ""
            log(f"[{done}/{total}] {d.claim_id}: {d.verdict.value}{spent}")

        t = time.monotonic()
        result = pipeline.run_audit(conn, comps, progress=progress)

        # The audit reads its stipulations and calls in its own reads, after the check above:
        # an owner or a call row changed in between (or during the run) and still changed now
        # leaves this run's verdicts on a case the gates did not pass. The run is then marked
        # stopped, so no scorer or report takes it as the case's completed audit
        # (pipeline.last_run), while its finished claims stay reusable, and the run stops here
        # (CodeRabbit on #269). The check and the copy below read in one transaction, so the
        # copy holds the owners and call log the check passed.
        def unscored(why: str) -> None:
            """Store the run as stopped with `why`, so it is never the case's completed audit."""
            conn.rollback()  # end the read before the refusal is written
            with conn:
                conn.execute(
                    "UPDATE pipeline_runs SET status = 'stopped', note = ? WHERE id = ?",
                    (why, result.run_id),
                )
                audit_log.append(
                    conn,
                    datetime.now(UTC),
                    ACTOR,
                    pipeline.HALT_ACTION,
                    {"run_id": result.run_id, "error": why, "stopped": True},
                )

        try:
            if conn.in_transaction:  # the pipeline's own writes end before this read
                conn.commit()
            conn.execute("BEGIN")
            stop = case_stop(conn, built)
        except BaseException as e:
            # the check itself failed or was interrupted (a database locked by another writer,
            # Ctrl+C): the run was never verified, so it is stored as stopped where the database
            # allows it (CodeRabbit on #269); if even that write fails, the run keeps the
            # pipeline's completed status, but no audited.db, report or zip is made from it, and
            # the scorer scores only a published results.zip whose run.json names the audit
            with suppress(sqlite3.Error):
                unscored(f"the final check could not run, so it is not scored: {e}")
            raise
        if stop:
            unscored(f"{REFUSED}: {stop}")
            raise SystemExit(f"{REFUSED}: {stop}")
        try:
            with closing(sqlite3.connect(out / AUDITED)) as copy:
                conn.backup(copy)
        finally:
            conn.commit()
        tally: dict[str, int] = {}
        for d in result.decisions:
            tally[d.verdict.value] = tally.get(d.verdict.value, 0) + 1
        calls = {
            purpose: {"calls": n, "first_utc": first, "last_utc": last}
            for purpose, n, first, last in conn.execute(
                "SELECT r.purpose, COUNT(*), MIN(c.at_utc), MAX(c.at_utc) FROM model_calls c"
                " JOIN model_runs r ON r.id = c.model_run_id GROUP BY r.purpose"
            )
        }
    finally:
        conn.close()
    return {
        "run_id": result.run_id,
        "fake": result.fake,
        "challenge": comps.challenge,
        "verdicts": tally,
        "audit_seconds": round(time.monotonic() - t),
        "model_calls": calls,
        "model_outputs_reused": result.model_outputs_reused,
        "dropped_labels": result.dropped_labels,
        "unlabeled": result.unlabeled,
    }


def report(out: Path, log, db: str = "case.db") -> dict:  # noqa: ANN001
    """Write report.html. A report the invariants refuse is left out and said so: the audit's
    results are in case.db either way, and the score is read from there."""
    from core.audit.invariants import InvariantViolation
    from core.report.html import write_report

    path = out / "report.html"
    path.unlink(missing_ok=True)  # never ship a report from an earlier attempt
    conn = connect(out / db)
    try:
        write_report(conn, path)
    except InvariantViolation as e:
        log(f"report not written: {e}")
        return {"written": False, "error": str(e)}
    finally:
        conn.close()
    return {"written": True}


def model_config() -> dict | None:
    from core.audit._local_model import ModelConfigError, load_config

    try:
        cfg = load_config()
    except ModelConfigError:
        return None
    return {"name": cfg.name, "sha256": cfg.sha256, "n_ctx": cfg.n_ctx}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ufdr", type=Path, help="one phone's UFDR package (validation v1 to v4)")
    ap.add_argument(
        "--phone",
        action="append",
        metavar="SOURCE_ID=PACKAGE",
        help="a phone's package (UFDR, or a LEAPP output zip); repeat for each phone",
    )
    ap.add_argument(
        "--phone-sha256",
        action="append",
        metavar="SOURCE_ID=HEX",
        help="refuse a phone's package file with another hash",
    )
    ap.add_argument("--claims", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--claims-sha256", help="refuse a claims file with another hash")
    ap.add_argument(
        "--report-sha256", help="with --ufdr: refuse a package whose report.xml has another hash"
    )
    ap.add_argument("--fake", action="store_true", help="stand-in components (tests only)")
    ap.add_argument(
        "--cloud",
        metavar="MODEL",
        help="Claude for assumption filling and stance (e.g. claude-opus-5-5); the key comes"
        " from $MABILLON_ANTHROPIC_API_KEY",
    )
    ap.add_argument("--effort", default=None, help="the cloud model's effort (default: medium)")
    ap.add_argument(
        "--phone-zone",
        help="the phones' zone, as the examiner gives it, for a package that records none",
    )
    ap.add_argument(
        "--max-usd", type=float, help="with --cloud: stop once the run's spend passes this"
    )
    ap.add_argument("--source-id", default=SOURCE_ID, help="with --ufdr: the phone's source id")
    ap.add_argument(
        "--definitions",
        type=Path,
        help="the affidavit header as JSON (SUBJECT-<n> to a number, phone_time_zone, and"
        " phones: each source id's name and user); replaces the iOS 15 definitions",
    )
    a = ap.parse_args(argv)
    defined = None
    defs = None
    if a.definitions is not None:
        defs = load_definitions(a.definitions)
        defined = {k: v for k, v in defs.items() if k not in (ZONE_KEY, PHONES_KEY)}
    phones = phones_from(a, defs)
    if a.report_sha256 and a.ufdr is None:
        raise SystemExit("--report-sha256 goes with --ufdr; use --phone-sha256")
    if a.cloud and a.max_usd is not None and a.cloud not in PRICES_PER_MTOK:
        # Without a price the spend counter never moves, so the cap would never stop a call.
        raise SystemExit(f"--max-usd: no price for {a.cloud}; add it to PRICES_PER_MTOK")
    # What the case is built from, compared on a resume (the zone is given only at build).
    setup = {
        "source_id": a.source_id if a.ufdr is not None else None,
        "definitions": defs,
        "phones": [ph.record() for ph in phones],
    }
    a.out.mkdir(parents=True, exist_ok=True)
    # One invocation owns DIR at a time, from its first write through publication, so a
    # results.zip never mixes two attempts' files (CodeRabbit on #269).
    lock = a.out / LOCK
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise SystemExit(
            f"{lock} exists: another run is using {a.out}. If none is (a run killed outright"
            " leaves it behind), delete that file and run again."
        ) from None
    # The lock is ours from here on, so it is released even if the PID write fails.
    try:
        try:
            os.write(fd, f"{os.getpid()}\n".encode())
        finally:
            os.close(fd)
        return _attempt(a, phones, defs, defined, setup)
    finally:
        lock.unlink(missing_ok=True)


def _attempt(a, phones, defs, defined, setup) -> int:  # noqa: ANN001
    """One attempt on DIR, run while main() holds its lock."""
    # an earlier attempt's results never stand for this one, even if this one is refused
    (a.out / "results.zip").unlink(missing_ok=True)
    plog = (a.out / "progress.log").open("a", encoding="utf-8")

    def log(msg: str) -> None:
        line = f"{datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ} {msg}"
        print(line, flush=True)
        plog.write(line + "\n")
        plog.flush()

    from core import build as build_mod
    from core.audit.rules import RULE_VERSION

    run_path = a.out / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8")) if run_path.exists() else {}
    claims_sha = sha256_file(a.claims)
    if a.claims_sha256 and claims_sha != a.claims_sha256:
        raise SystemExit(f"{a.claims}: SHA-256 {claims_sha}, expected {a.claims_sha256}")
    claims = load_claims(a.claims)
    built = a.out / "built.ok"  # the inputs the case in DIR was built from
    # decided once: a built.ok that vanishes or appears mid-run never turns a resume into a
    # build (which deletes the checked case.db) or skips both (CodeRabbit on #269)
    resuming = built.exists()
    if resuming:
        was = json.loads(built.read_text(encoding="utf-8"))
        if was.get("setup", 1) != SETUP:
            raise SystemExit(
                f"{a.out} was set up by an earlier version of this run (setup"
                f" {was.get('setup', 1)}, now {SETUP}); use a new --out"
            )
        if was["claims_sha256"] != claims_sha:
            raise SystemExit(
                f"{a.out} was built from claims {was['claims_sha256']}; use a new --out"
            )
        if a.report_sha256 and was.get("report_xml_sha256") != a.report_sha256:
            raise SystemExit(
                f"{a.out} was built from report.xml {was.get('report_xml_sha256')}; use a new --out"
            )

        # Phones by source id, so a resume may name them in any order (Claude review on #267).
        was_p, now_p = sorted(was["phones"], key=_sid), sorted(setup["phones"], key=_sid)
        same_rest = all(was.get(k) == v for k, v in setup.items() if k != "phones")
        if was_p != now_p or not same_rest:
            was_zones = [p.get("zone_given") for p in was_p]
            unzoned = [{**p, "zone_given": z} for p, z in zip(now_p, was_zones, strict=False)]
            if same_rest and unzoned == was_p:
                raise SystemExit(  # the zone given at the command line is all that changed
                    f"--phone-zone: {a.out} was built with "
                    + (f"the zones {was_zones}" if any(was_zones) else "no zone given")
                    + "; resume with the same zones, or use a new --out"
                )
            raise SystemExit(
                f"{a.out} was built with another source id or definitions, or other phones;"
                " use a new --out"
            )
        # Each package's bytes, not just its file name: two packages of one name swapped
        # between phones must not resume a case built from the other (CodeRabbit on #267).
        given = {ph.source_id: ph for ph in phones}
        for p in was["imported"]:
            ph = given[p["source_id"]]
            # always the bytes now, never only the digest given: a size or time check would
            # pass a package swapped for one of the same size and copied time (CodeRabbit)
            try:
                h = sha256_file(ph.path)
            except OSError as e:
                raise SystemExit(f"{ph.source_id}: cannot read {ph.path} to resume: {e}") from None
            if p["sha256"] != h:
                raise SystemExit(
                    f"{a.out} was built from {p['file']} {p['sha256']}; use a new --out"
                )
            if ph.sha256 and ph.sha256 != h:
                raise SystemExit(f"--phone-sha256: {ph.path} has SHA-256 {h}, not {ph.sha256}")
        imported, report_sha = was["imported"], was.get("report_xml_sha256")
        # A case built before the call-log guard (gate G5b) resumes only when each phone's
        # stored import passes it too, so a paid resume never audits a phone whose calls no
        # check can read (CodeRabbit on #269).
        conn = open_existing(
            a.out / "case.db", f"{a.out}: built.ok is there but case.db is not; use a new --out"
        )
        try:
            # the case.db must hold the very imports built.ok records: one restored from another
            # run under the same phone names would pass the check with its own calls (CodeRabbit)
            for p in imported:
                row = conn.execute(
                    "SELECT sha256 FROM sources WHERE id = ?", (p["source_id"],)
                ).fetchone()
                if row is None or row[0] != p["sha256"]:
                    raise SystemExit(
                        f"{p['source_id']}: {a.out}/case.db does not hold the import built.ok"
                        f" records ({p['file']} {p['sha256']}); restore the case.db it was built"
                        " with, or use a new --out"
                    )
            # ...and is this very build's: another build of the same packages may hold other
            # claims, claim ids or types, or zones, none of which the sources show (CodeRabbit)
            check_build(conn, a.out, was)
            # ...and each phone's device still has the one confirmed owner it was built with:
            # an owner changed since would leave the claims naming the defined owner with no
            # person to find (CodeRabbit on #269)
            stop = owner_stop(conn, was_p)
            if stop:
                raise SystemExit(stop)
            checks = [
                (
                    p["source_id"],
                    *call_log_check(conn, p["source_id"], p.get("importer"), owner_confirmed=True),
                )
                for p in imported
            ]
        finally:
            conn.close()
        for sid, stop, note in checks:
            if stop:
                raise SystemExit(f"{sid}: {stop}")
            if note:
                log(f"{sid}: {note}")  # as a fresh build logs it (CodeRabbit on #269)
    run.setdefault("started_utc", f"{datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ}")
    run.update(
        build=build_mod.build_info(),
        rule_version=RULE_VERSION,
        model=None if a.fake else model_config(),
        machine=machine(),
        claims={"file": a.claims.name, "sha256": claims_sha, "n": len(claims)},
    )
    if not resuming:
        report_sha = None
        if a.ufdr is not None:
            log("checking the phone package's report.xml")
            report_sha = report_xml_sha256(a.ufdr)
            if a.report_sha256 and report_sha != a.report_sha256:
                raise SystemExit(f"report.xml SHA-256 {report_sha}, expected {a.report_sha256}")
        imported, build_id = build(phones, claims, a.out, log, defined)
        inputs = {
            "claims_sha256": claims_sha,
            "report_xml_sha256": report_sha,
            "setup": SETUP,
            **setup,
            "imported": imported,
            "build_id": build_id,
        }
        built.write_text(json.dumps(inputs), encoding="utf-8")
        was = inputs  # the record the audit checks the case.db against
    # From the build, or from built.ok on a resume: a run that stopped before run.json was
    # written still records what the case was built from (CodeRabbit on #267).
    run["phones"] = imported
    run["phone_zone_given"] = phones[0].zone if len(phones) == 1 else None
    run["source_id"] = setup["source_id"]
    run["definitions"] = defs
    if report_sha is not None:
        run["report_xml_sha256"] = report_sha
    run_path.write_text(json.dumps(run, indent=2), encoding="utf-8")
    from core.audit._llm_json import CloudPaused
    from core.pipeline import ComponentsMissing

    cloud_model = None
    if a.cloud and not a.fake:
        from core.llm import cloud

        cfg = cloud.load_config()
        cfg = cloud.CloudConfig(
            api_key=cfg.api_key, model=a.cloud, effort=a.effort or cloud.DEFAULT_EFFORT
        )
        spent_before = float(run.get("cloud", {}).get("spent_usd", 0.0))
        cloud_model = Budgeted(cloud.ClaudeModel(cfg), a.max_usd, spent_before)
        run["model"] = {"cloud": cfg.model, "effort": cfg.effort, "jobs": ["assumptions", "stance"]}
    try:
        try:
            run["audit"] = audit(a.out, a.fake, log, cloud_model, built=was)
        finally:
            if cloud_model is not None:
                total = run.setdefault("cloud", {"sessions": []})
                total["sessions"].append(cloud_model.usage())
                total["spent_usd"] = round(cloud_model.spent_usd, 2)
                run_path.write_text(json.dumps(run, indent=2), encoding="utf-8")
                log(f"cloud spend so far: ${cloud_model.spent_usd:.2f}")
    except CloudPaused as e:
        log(f"paused: {e}")
        plog.close()
        print(f"paused: {e}. Run the same command again to resume.")
        return 3
    except ComponentsMissing as e:
        raise SystemExit(f"audit: {e}") from e
    run["finished_utc"] = f"{datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ}"
    # The report and results.zip are made from the copy of the audited case, never case.db
    # read again by path, so they hold the audited build whatever case.db holds by then
    # (CodeRabbit on #269).
    run["report"] = report(a.out, log, AUDITED)
    run_path.write_text(json.dumps(run, indent=2), encoding="utf-8")
    plog.close()
    part = a.out / "results.zip.part"  # published only once written in full
    try:
        with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as z:
            for name in RESULT_FILES:
                if name == "case.db":  # always written, so a missing case stops the zip
                    try:
                        z.write(a.out / AUDITED, name)
                    except FileNotFoundError as e:
                        raise SystemExit(
                            f"{a.out / AUDITED} is missing; results.zip not published"
                        ) from e
                elif (a.out / name).exists():
                    z.write(a.out / name, name)
        part.replace(a.out / "results.zip")
    finally:
        part.unlink(missing_ok=True)
    print(f"done: {run['audit']['verdicts']}; results in {a.out / 'results.zip'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
