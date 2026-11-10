"""Sender check: who sent the message with these exact words, judged by account identifier."""

from __future__ import annotations

from core.audit.checks._common import (
    TEXT_MATCH,
    CaseData,
    Key,
    Row,
    channel_ok,
    fmt_key,
    messages_with_text,
    parties,
    person_party,
    sentence_aligned,
    sentences,
)
from core.audit.checks.base import TemplateCheck
from core.contracts import AssumptionParams, CheckOutcome, CheckResult, MessageDirection


def _tied_people(data: CaseData) -> dict[Key, set[str]]:
    """Each account key a confirmed fact ties to a person: an expert-confirmed identity link,
    or a confirmed device_owner stipulation (the owner accounts of that phone). Proposed links
    and stipulations never count."""
    out: dict[Key, set[str]] = {}
    for _, account_id, pid in data.links:
        acc = data.accounts.get(account_id)
        if acc is not None:
            out.setdefault(acc.key, set()).add(pid)
    for _, device_id, pid, status in data.stipulations:
        if status != "confirmed":
            continue
        for acc in data.accounts.values():
            if acc.device_id == device_id:
                out.setdefault(acc.key, set()).add(pid)
    return out


def _someone_else(
    data: CaseData, row: Row, expected: set[Key], tied: dict[Key, set[str]]
) -> str | None:
    """Why a copy whose sender is not an expected account is from someone else, or None when
    no record or confirmed fact says so. One user may hold accounts no link names, so an
    account that is not the party's is not by itself another person's:
      (a) the sender is a phone's own account;
      (b) a confirmed link or stipulation ties the sender to a person none of whose confirmed
          accounts is expected;
      (c) the expected party is exactly the own accounts of the phone the copy is on, and that
          phone recorded the message as received."""
    acc = data.accounts[row.sender or ""]
    if any(a.is_owner and a.key == acc.key for a in data.accounts.values()):
        return f"{fmt_key(acc.key)} is a phone's own account"
    others = sorted(
        pid for pid in tied.get(acc.key, set()) if not person_party(data, pid).keys & expected
    )
    if others and len(others) == len(tied[acc.key]):
        return f"{fmt_key(acc.key)} is {', '.join(others)}'s, per a confirmed link or stipulation"
    info = data.sources.get(row.source_id)
    devices = set(info.device_ids) if info else set()
    own = {
        a.key for a in data.accounts.values() if a.device_id is not None and a.device_id in devices
    }
    if own and expected == own and row.direction == MessageDirection.INCOMING.value:
        return f"{row.source_id} recorded it as received, so its owner did not send it"
    return None


class SenderCheck(TemplateCheck):
    """Pass if every message carrying the words came from the party's accounts. Fail if every
    one came from someone else, which a record or a confirmed fact must show (_someone_else):
    an account no confirmed link ties to anyone is unknown, never someone else. Mixed or
    unknown senders are inconclusive. Display names are
    never compared: two handles on one user id are one sender, one name on two numbers is two.
    The check speaks about accounts; whether a person typed the words is a separate question.
    """

    name = "sender"
    # 1.0.2: curly quotes and runs of spaces fold (TEXT_MATCH). 1.1.0: a copy from an account
    # that is not the party's fails only when a record or a confirmed fact says it is someone
    # else's (_someone_else); otherwise it is unknown.
    # 1.2.0: a copy that holds the words only inside a longer sentence (sentence_aligned) is
    # unknown.
    version = "1.2.0"

    def evaluate(self, assumption_id: str, p: AssumptionParams, data: CaseData) -> CheckResult:
        sources = data.sources_for(p.device_ids)
        (party,) = parties(data, p)
        sender_ids = data.account_ids(party.keys)
        rows = [
            r
            for r in messages_with_text(data, p.quoted_text or "")
            if r.source_id in sources and channel_ok(r, p.channels)
        ]
        on = f" on {', '.join(p.channels)}" if p.channels else ""
        searched = (
            f"Messages{on} containing {p.quoted_text!r} ({TEXT_MATCH}) in {', '.join(sources)}; "
            f"expected sender {party.describe()}."
        )
        if not party.keys:
            return self.done(
                assumption_id,
                CheckOutcome.INCONCLUSIVE,
                searched,
                sentences("Could not resolve the expected sender to accounts", party.notes),
                [r.id for r in rows],
                sources,
            )
        if not rows:
            return self.done(
                assumption_id,
                CheckOutcome.INCONCLUSIVE,
                searched,
                "None found. Not found does not mean the message was never sent.",
                [],
                sources,
            )

        good, bad, unknown, lines = [], [], [], []
        tied = _tied_people(data)
        for row in rows:
            acc = data.accounts.get(row.sender or "")
            if row.id in data.forwarded:
                # never credit forwarded or quoted words to whoever forwarded them
                unknown.append(row.id)
                lines.append(
                    f"{row.id} on {row.app} is marked as forwarded or as carrying a forwarded "
                    "or quoted message; Mabillon has not verified who first wrote the words"
                )
                continue
            if not sentence_aligned(p.quoted_text or "", row.text or ""):
                # 'text me about it' in 'dont text me about it, use telegram'
                unknown.append(row.id)
                lines.append(
                    f"{row.id} on {row.app} holds the words only inside a longer sentence, so it"
                    f" may not say what the claim quotes; the whole message reads {row.text!r}"
                )
                continue
            if acc is None:
                unknown.append(row.id)
                lines.append(f"{row.id} on {row.app} has no recorded sender")
                continue
            lines.append(
                f"{row.id} on {row.app} was sent by {fmt_key(acc.key)} "
                f"({acc.display_name or 'no name'})"
            )
            if row.sender in sender_ids:
                good.append(row.id)
            elif why := _someone_else(data, row, party.keys, tied):
                bad.append(row.id)
                lines.append(why)
            else:
                unknown.append(row.id)
                lines.append(
                    f"no confirmed link ties {fmt_key(acc.key)} to anyone, and the record does "
                    f"not show who sent it, so it may be {party.label}'s"
                )
        if good and not bad and not unknown:
            outcome, verdict = CheckOutcome.PASS, f"Every copy came from {party.label}"
        elif bad and not good and not unknown:
            outcome, verdict = CheckOutcome.FAIL, f"No copy came from {party.label}"
        else:
            outcome = CheckOutcome.INCONCLUSIVE
            verdict = "The words match messages with different or unknown senders"
        detail = sentences(lines, verdict, party.notes)
        return self.done(assumption_id, outcome, searched, detail, [r.id for r in rows], sources)
