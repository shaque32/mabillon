"""Whether a case's model steps run on the cloud model, decided per case.

Each case needs the expert's explicit choice before the app proposes claims or starts the audit
(chosen): Fast (the cloud model, the recommended choice at setup for an ordinary case, CLAUDE.md)
or on this computer. Nothing is pre-chosen and the attestation is never pre-ticked, since it is
the expert's statement. A case runs every model step (stance labels, assumption filling, claim
proposal, the AI reviewer and the testability step) on the cloud model (core/llm/cloud.py) only
when all of these hold, and otherwise on the local model:
1. The expert attested, for this case, that its protective order allows cloud AI.
2. The expert did not mark the case as possibly containing CSAM. Such material stays in the
   government's control (18 U.S.C. 3509(m)), so a marked case never uses cloud, whatever (1) says.
3. An Anthropic key is set up on this computer (the expert's own; Mabillon runs no server).
4. The configured model, at its configured effort, passed Mabillon's signed stance test with the
   cloud stance prompt it would read (core/audit/prompts/stance_cloud.md; core/llm/cloud.py,
   PROBE_PASSED). Opus 5.5 at medium effort is listed (signed by Arsh 2026-10-20).

Then every answer of every model step in the case comes from the cloud model; a step's answers
never mix models. If
the cloud model stops answering, the audit pauses (core/audit/_local_model.py, CloudPort) and
the expert resumes to retry it, or turns cloud AI off here and runs the case again locally.
Every request is logged in the case's audit log before it is sent (SentLog).

The choice lives only in the case's hash-chained audit log (inside the case database, so an
encrypted case keeps it encrypted): the latest set_cloud entry by an expert, with who made it,
when, and the words they agreed to. Nothing about it is written to the readable case.json.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from core import db
from core.llm import cloud as cloud_llm
from core.review.actions import _expert

ACTION = "set_cloud"
# Approved by Arsh 2026-11-10 07:27Z. A case attested under an earlier text reads as not chosen
# (case_cloud), so the expert chooses again rather than drifting to either side.
ATTESTATION = (
    "This case's protective order (or the court's or the government's written consent) allows "
    "excerpts of its evidence to be sent to Anthropic for AI processing. The Anthropic key used "
    "for it belongs to an organization with zero data retention in writing. My client has given "
    "informed consent."
)
FAST = "Fast: Opus through Anthropic"
LOCAL = "On this computer"
# Approved by Arsh 2026-11-10 07:27Z, the setup page's explanation of Fast.
FAST_EXPLAINED = (
    "With Fast, Mabillon sends one question at a time to Anthropic: the claim, the assumption "
    "being tested, one record and the messages around it, and for a group chat its member list. "
    "Never your files or the case database. Under a zero-retention account Anthropic keeps no "
    "prompts or answers after it replies, except content its safety systems flag (kept up to 2 "
    "years) or what the law requires, and it never trains on them. Every request is recorded in "
    "the case's audit log before it is sent. If the cloud model stops answering, the audit "
    "pauses and you choose to retry or run the whole case on this computer."
)
CSAM_NOTE = "This case may contain child sexual abuse material."


@dataclass(frozen=True)
class CloudChoice:
    use: bool
    why: str  # one plain sentence for the screen, the run's config and the report
    config: cloud_llm.CloudConfig | None = None

    def record(self) -> dict[str, Any]:
        out: dict[str, Any] = {"use": self.use, "why": self.why}
        if self.config is not None:
            out["model"] = self.config.model
            out["effort"] = self.config.effort
        return out


def case_cloud(conn: sqlite3.Connection) -> dict[str, Any]:
    """The case's current cloud choice: the latest set_cloud entry an expert made in its audit
    log, or {} if there is none. Cloud counts as allowed only when that entry carries the
    attestation text word for word; anything else reads as not allowed."""
    try:
        row = conn.execute(
            "SELECT at_utc, actor, payload_json FROM audit_log WHERE action = ?"
            " AND actor LIKE 'expert:%' ORDER BY seq DESC LIMIT 1",
            (ACTION,),
        ).fetchone()
    except db.OperationalError:
        return {}
    if row is None:
        return {}
    try:
        payload = json.loads(row[2])
    except ValueError:
        return {}
    if not isinstance(payload, dict):
        return {}
    csam = payload.get("csam") is True
    asked = payload.get("allowed") is True and not csam
    allowed = asked and payload.get("attestation") == ATTESTATION
    # chosen: the expert picked a side under the current text. Asking for cloud under another
    # attestation text is no choice at all: the case waits for the expert to choose again.
    out: dict[str, Any] = {"allowed": allowed, "csam": csam, "chosen": allowed or not asked}
    if allowed:
        out["attested_by"] = row[1]
        out["attested_at"] = row[0]
    return out


def chosen(conn: sqlite3.Connection) -> bool:
    """Has an expert chosen where this case's AI runs (Fast or on this computer)? The app's
    audit and claim proposal wait for this, so no case drifts to either side by accident."""
    return case_cloud(conn).get("chosen") is True


def choose(
    conn: sqlite3.Connection,
    load: Callable[[], cloud_llm.CloudConfig] = cloud_llm.load_config,
) -> CloudChoice:
    """The cloud decision for one case, from its audit log and the expert's key."""
    c = case_cloud(conn)
    if c.get("csam") is True:
        return CloudChoice(False, "Local model: the case is marked as possibly containing CSAM, "
                                  "so it never uses cloud AI.")  # fmt: skip
    if c.get("allowed") is not True:
        return CloudChoice(False, "Local model: nobody has attested that this case's protective "
                                  "order allows cloud AI.")  # fmt: skip
    try:
        cfg = load()
    except cloud_llm.CloudConfigError as e:
        return CloudChoice(False, f"Local model: cloud AI is allowed for this case, but {e}.")
    version = _stance_prompt_version()
    if (cfg.model, cfg.effort, version) not in cloud_llm.PROBE_PASSED:
        return CloudChoice(
            False,
            f"Local model: cloud AI is allowed for this case, but {cfg.model} ({cfg.effort} "
            "effort) has not passed "
            "Mabillon's signed stance test with the cloud stance prompt, so the local model "
            "labels it.",
        )
    who = str(c["attested_by"]).removeprefix("expert:")
    when = str(c["attested_at"])[:10]
    return CloudChoice(
        True,
        f"Cloud model {cfg.model} ({cfg.effort} effort) for every model step, attested by "
        f"{who} on {when}; if it stops answering, the audit pauses rather than mix in local "
        "answers.",
        cfg,
    )


def _stance_prompt_version() -> str | None:
    from core.audit._llm_json import PromptMissingError, load_prompt, prompt_version
    from core.audit.stance import CLOUD_PROMPT_FILE

    try:
        return prompt_version(load_prompt(CLOUD_PROMPT_FILE))
    except PromptMissingError:
        return None


def set_cloud(
    conn: sqlite3.Connection,
    actor: str,
    *,
    allowed: bool,
    csam: bool,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, Any]:
    """Record the expert's cloud choice for a case in its audit log (inside the case database,
    so an encrypted case keeps it encrypted; nothing goes in the readable case.json)."""
    from core.casework.cases import _logged

    _expert(actor)
    payload: dict[str, Any] = {"allowed": bool(allowed) and not csam, "csam": bool(csam)}
    if payload["allowed"]:
        payload["attestation"] = ATTESTATION
    if csam:
        payload["csam_note"] = CSAM_NOTE
    _logged(conn, clock(), actor, ACTION, payload)
    return case_cloud(conn)
