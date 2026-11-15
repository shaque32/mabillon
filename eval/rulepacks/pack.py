"""The rule pack format, its validator and its hash.

A pack can only read records and tighten checks. It has no field that widens a verdict path:
which claim types code may make SUPPORTED, and every other verdict rule, stay in
core/audit/rules.py, signed by Arsh. The closed set of things a pack may say:

- layouts: how each carrier layout's columns map to call records, and which time zone the
  printed times are in, with the header words that state it (zone_evidence);
- templates: which existing assumption templates its claims use (core/audit/assumptions.py);
  their checks are the human-written ones in core/audit/checks/;
- guards: record types on which no check may pass or fail (the result turns inconclusive),
  each naming the traps it blocks.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.audit.assumptions import TEMPLATES
from core.audit.checks import CHECKS

# Canonical record types a layout's type column maps to. Only voice-type rows become call
# records; sms rows are counted as skipped (a carrier SMS row has no content to check).
RecordType = Literal["voice", "sms", "voicemail", "forwarded"]
Direction = Literal["incoming", "outgoing", "unknown"]
CALL_TYPES: frozenset[str] = frozenset({"voice", "voicemail", "forwarded"})
# Header words that state a zone, and the zones each may mean. A layout's zone_evidence must be
# one of these and its zone one the words allow. Human-owned list: a drafter may not add to it.
ZONE_WORDS: dict[str, frozenset[str]] = {
    "UTC": frozenset({"UTC"}),
    "GMT": frozenset({"UTC"}),
    "(CT)": frozenset({"America/Chicago"}),
    "Central": frozenset({"America/Chicago"}),
    "(ET)": frozenset({"America/New_York"}),
    "Eastern": frozenset({"America/New_York"}),
}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Layout(_Strict):
    """One carrier's file layout. Direction is from the subscriber line the records are for."""

    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    headers: tuple[str, ...]  # the exact header row; a file with any other is refused
    date_col: str
    time_col: str
    datetime_format: str  # strptime format for "<date> <time>"
    zone: str  # IANA zone the printed times are in
    zone_evidence: str  # words in time_col's header that state that zone
    from_col: str
    to_col: str
    direction_col: str
    direction_values: dict[str, Direction]
    duration_col: str
    type_col: str
    type_values: dict[str, RecordType]

    @model_validator(mode="after")
    def _columns(self) -> Layout:
        cols = (
            self.date_col,
            self.time_col,
            self.from_col,
            self.to_col,
            self.direction_col,
            self.duration_col,
            self.type_col,
        )
        missing = [c for c in cols if c not in self.headers]
        if missing:
            raise ValueError(f"layout {self.id}: columns not in headers: {missing}")
        if not self.zone_evidence or self.zone_evidence not in self.time_col:
            raise ValueError(
                f"layout {self.id}: zone_evidence {self.zone_evidence!r} is not in the time "
                f"column's header {self.time_col!r}; a zone must be stated by the file"
            )
        allowed = ZONE_WORDS.get(self.zone_evidence)
        if allowed is None:
            raise ValueError(f"layout {self.id}: {self.zone_evidence!r} is not a known zone word")
        if self.zone not in allowed:
            raise ValueError(
                f"layout {self.id}: header says {self.zone_evidence!r}, which does not mean "
                f"{self.zone!r}"
            )
        try:
            ZoneInfo(self.zone)
        except (ZoneInfoNotFoundError, ValueError) as e:
            raise ValueError(f"layout {self.id}: unknown zone {self.zone!r}") from e
        return self


class Guard(_Strict):
    """No check may pass or fail on a record of these types: the result turns inconclusive."""

    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    text: str = Field(min_length=10)  # the plain-English rule card an examiner signs
    record_types: tuple[RecordType, ...] = Field(min_length=1)
    blocks: tuple[str, ...] = Field(min_length=1)  # trap ids this guard must block


class Signature(_Strict):
    role: Literal["examiner", "owner"]
    name: str
    signed_at_utc: str
    pack_sha256: str  # the hash of the pack without its signatures


class RulePack(_Strict):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+(-[a-z0-9.]+)?$")
    evidence_type: str
    status: Literal["reference", "draft", "signed"]
    drafted_by: str  # 'human:<name>' or 'ai:<session or model>'
    layouts: tuple[Layout, ...] = Field(min_length=1)
    templates: tuple[str, ...] = Field(min_length=1)
    guards: tuple[Guard, ...] = ()
    signatures: tuple[Signature, ...] = ()

    @model_validator(mode="after")
    def _known(self) -> RulePack:
        for t in self.templates:
            if t not in TEMPLATES:
                raise ValueError(f"unknown template {t!r}")
            for c in TEMPLATES[t].checks:
                if c not in CHECKS:
                    raise ValueError(f"template {t!r} names unknown check {c!r}")
        ids = [g.id for g in self.guards] + [x.id for x in self.layouts]
        if len(ids) != len(set(ids)):
            raise ValueError("guard and layout ids must be unique")
        if self.status == "signed":
            roles = {s.role for s in self.signatures}
            if roles != {"examiner", "owner"}:
                raise ValueError("a signed pack needs an examiner's and the owner's signature")
            if any(s.pack_sha256 != self.sha256() for s in self.signatures):
                raise ValueError("a signature is for another version of this pack")
        return self

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"

    def sha256(self) -> str:
        """Hash of the pack's content, signatures and status left out, so signing does not
        change what is signed."""
        body = self.model_dump(mode="json", exclude={"signatures", "status"})
        canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()

    def layout(self, layout_id: str) -> Layout:
        for x in self.layouts:
            if x.id == layout_id:
                return x
        raise KeyError(layout_id)

    def without_guard(self, guard_id: str) -> RulePack:
        return self.model_copy(update={"guards": tuple(g for g in self.guards if g.id != guard_id)})


def load(path: Path) -> RulePack:
    return RulePack.model_validate_json(path.read_text(encoding="utf-8"))
