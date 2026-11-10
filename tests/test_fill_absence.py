"""No contact between a phone and one other party, on synthetic case01 with a scripted model.

"There was no contact between the TARGET PHONE and (212) 555-0144": the phone written as a side
stands for that phone's own accounts on it, through its exact owner by confirmed stipulation (a
person whose accounts are exactly the phone's own), and never for whoever held it. Code reads
both sides from the claim's words, and the model's one party must be the one the claim writes.
Everything else is refused. Every value here is invented by the synthetic generator.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.audit._llm_json import prompt_body
from core.audit.assumption_filler import LocalAssumptionFiller
from core.audit.assumptions import TemplateAssumptionBuilder
from core.audit.checks import CHECKS
from core.contracts import CheckOutcome, Claim, ClaimStatus, ClaimType
from core.review import actions
from eval.synthetic.generate import generate
from tests.checks.helpers import check, stipulate, text, window
from tests.fake_model import FakeModel

ROOT = Path(__file__).parents[1]
DRAFT = prompt_body((ROOT / "docs/prompts/assumptions.md").read_text("utf-8"))
PETROV, REYES, SMITH = "person:petrov", "person:reyes", "person:smith"
EXPERT = "expert:Test Expert"
AT = datetime(2026, 10, 26, 12, tzinfo=UTC)
JAKE = ["acct:item1:Phone:+12125550144", "acct:item1:SMS:+12125550144"]
MARC_WA = "acct:item1:WhatsApp:12125550122@s.whatsapp.net"


@pytest.fixture(scope="module")
def base(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("case01")
    db = out / "case01.db"
    generate(out, db)
    c = sqlite3.connect(db)
    actions.name_device(c, "dev:item1", ["TARGET PHONE"], EXPERT, lambda: AT)
    c.commit()
    c.close()
    return db


def _open(base: Path, tmp_path: Path, *, owner: bool = True) -> sqlite3.Connection:
    db = tmp_path / "case.db"
    shutil.copy(base, db)
    c = sqlite3.connect(db)
    if owner:
        stipulate(c, PETROV, "Daniel Petrov", "dev:item1")
        stipulate(c, REYES, "Marcus Reyes", "dev:item2")
    c.execute("PRAGMA foreign_keys = OFF")
    return c


@pytest.fixture
def conn(base, tmp_path):
    c = _open(base, tmp_path)
    yield c
    c.close()


def P(**kw) -> dict:  # noqa: N802
    base = dict(people=[], accounts=[], handles=[], phones=[], channels=[], quoted_text="",
                count=None, duration=None, window=None)  # fmt: skip
    return {"template_id": "no_contact", **base, **kw}


def W(as_written: str, start: str, end: str) -> dict:  # noqa: N802
    return {"as_written": as_written, "start": start, "end": end, "zone": "phone"}


def acc(as_written: str, app: str) -> dict:
    return {"as_written": as_written, "app": app}


def build(conn: sqlite3.Connection, claim_text: str, prop: dict, paragraph: str = ""):
    """The no_contact assumptions built for a claim of these words from this model answer,
    and the filler (for its drops)."""
    conn.execute("DELETE FROM govdoc_paragraphs WHERE id = 'para:abs'")
    if paragraph:
        conn.execute(
            "INSERT INTO govdoc_paragraphs (id, govdoc_id, page, para_no, label, char_start,"
            " char_end, text) VALUES ('para:abs', 'gd', 1, 1, '1', 0, ?, ?)",
            (len(paragraph), paragraph),
        )
    filler = LocalAssumptionFiller(
        FakeModel(json.dumps({"assumptions": [prop]})), conn, template=DRAFT
    )
    c = Claim(id="X1", paragraph_id="para:abs", text=claim_text, claim_type=ClaimType.ABSENCE,
              status=ClaimStatus.ACCEPTED)  # fmt: skip
    made = TemplateAssumptionBuilder(filler).build(c)
    return [a for a in made if a.template_id == "no_contact"], filler


def run(conn: sqlite3.Connection, a):
    return CHECKS["absence"].run(a, conn)


def full_extraction(conn: sqlite3.Connection) -> None:
    conn.execute("UPDATE sources SET fidelity = 'full_extraction' WHERE kind != 'govdoc'")


# ---------------------------------------------------------------- the phone as a side


def test_a_number_on_no_app_is_searched_on_every_app_not_only_the_models(conn):
    # The model wrote the number on the call log's app; the claim names no app, so contact
    # with the number by SMS counts too (the adversary: a reading that searched one app and
    # missed contact on another).
    claim = (
        "There was no contact between the TARGET PHONE and (212) 555-0144 before March 12, 2026."
    )
    prop = P(accounts=[acc("(212) 555-0144", "Phone")], phones=["TARGET PHONE"],
             window=W("before March 12, 2026", "", "2026-03-12T00:00"))  # fmt: skip
    (a,), filler = build(conn, claim, prop)
    p = a.params
    assert p.person_ids == (PETROV,), filler.drops
    assert p.account_ids == tuple(JAKE)  # the SMS account too, not only the model's Phone one
    assert p.device_ids == ("dev:item1",) and p.channels == ()
    assert a.text.endswith("Filled from the claim's wording.")
    r = run(conn, a)
    assert r.outcome is CheckOutcome.FAIL
    assert "every channel, calls included" in r.searched
    assert "on SMS" in r.detail  # found on an app the model did not write


def test_a_claim_naming_one_app_searches_only_that_app(conn):
    # On March 22, 2026 the phone has an SMS and a call with the number, and no WhatsApp.
    claim = (
        "There was no WhatsApp contact between the TARGET PHONE and (212) 555-0122 on"
        " March 22, 2026."
    )
    prop = P(accounts=[acc("(212) 555-0122", "WhatsApp")], phones=["TARGET PHONE"],
             channels=["WhatsApp"],
             window=W("on March 22, 2026", "2026-03-22T00:00", "2026-03-23T00:00"))  # fmt: skip
    (a,), filler = build(conn, claim, prop)
    assert a.params.channels == ("WhatsApp",), filler.drops
    assert a.params.person_ids == (PETROV,) and a.params.account_ids == (MARC_WA,)
    # A curated report cannot show an absence: the finding says what was searched and why.
    r = run(conn, a)
    assert r.outcome is CheckOutcome.INCONCLUSIVE
    assert r.searched.startswith("Messages and calls on WhatsApp between")
    assert "item1" in r.searched and "window" in r.searched
    assert "curated report, which cannot show that something is absent" in r.detail
    assert "Not found does not mean there was no contact" in r.detail
    # A full extraction spanning the day: no WhatsApp record, so it holds.
    full_extraction(conn)
    r = run(conn, a)
    assert r.outcome is CheckOutcome.PASS, text(r)
    assert "Every source is a full extraction whose records span the window" in r.detail


def test_the_same_claim_on_every_app_finds_the_sms_and_the_call(conn):
    claim = "There was no contact between the TARGET PHONE and (212) 555-0122 on March 22, 2026."
    prop = P(accounts=[acc("(212) 555-0122", "Phone")], phones=["TARGET PHONE"],
             window=W("on March 22, 2026", "2026-03-22T00:00", "2026-03-23T00:00"))  # fmt: skip
    (a,), filler = build(conn, claim, prop)
    assert MARC_WA in a.params.account_ids and a.params.channels == (), filler.drops
    full_extraction(conn)
    r = run(conn, a)
    assert r.outcome is CheckOutcome.FAIL
    assert "on SMS" in r.detail and "on Phone" in r.detail


def test_a_model_channel_named_only_by_the_phones_name_is_not_the_claims_scope(conn):
    # The model wrote channels ["Phone"]; "Phone" is in the claim only inside "the TARGET
    # PHONE", so the claim leaves every app open, and the SMS contact is found.
    claim = "There was no contact between the TARGET PHONE and (212) 555-0122 on March 22, 2026."
    prop = P(accounts=[acc("(212) 555-0122", "Phone")], phones=["TARGET PHONE"],
             channels=["Phone"],
             window=W("on March 22, 2026", "2026-03-22T00:00", "2026-03-23T00:00"))  # fmt: skip
    (a,), filler = build(conn, claim, prop)
    assert a.params.channels == (), filler.drops
    full_extraction(conn)
    r = run(conn, a)
    assert r.outcome is CheckOutcome.FAIL
    assert "on SMS" in r.detail


def test_a_person_with_the_phone_is_the_phones_owner_and_that_person(conn):
    claim = "The TARGET PHONE never communicated with REYES over Telegram."
    prop = P(people=["REYES"], phones=["TARGET PHONE"], channels=["Telegram"])
    (a,), filler = build(conn, claim, prop)
    assert a.params.person_ids == (PETROV, REYES), filler.drops
    assert a.params.channels == ("Telegram",)
    assert a.params.window is not None and a.params.window.raw.startswith("never: from")
    assert run(conn, a).outcome is CheckOutcome.FAIL  # they wrote on Telegram


def test_an_address_on_the_app_the_claim_names(conn):
    # An app whose accounts are addresses (as Wickr's are), with one message each side of
    # 10:00 a.m. on March 22, 2026 (EDT).
    conn.executescript(
        "INSERT INTO accounts VALUES ('acct:item1:Wickr Pro:dan@example.com', 'item1', 'x',"
        " 'dev:item1', 'Wickr Pro', 'dan@example.com', NULL);"
        "INSERT INTO accounts VALUES ('acct:item1:Wickr Pro:kay@example.org', 'item1', 'x',"
        " NULL, 'Wickr Pro', 'kay@example.org', NULL);"
        "INSERT INTO threads VALUES ('thr:wickr', 'item1', 'x', 'dev:item1', 'Wickr Pro', NULL);"
        "INSERT INTO messages (id, source_id, locator, thread_id, sender_account_id, direction,"
        " ts_utc, ts_raw, body) VALUES ('msg:w1', 'item1', 'w1', 'thr:wickr',"
        " 'acct:item1:Wickr Pro:dan@example.com', 'outgoing', '2026-03-22T13:30:00Z', 'r', 'hi');"
        "INSERT INTO message_recipients VALUES ('msg:w1', 'acct:item1:Wickr Pro:kay@example.org',"
        " NULL);"
    )
    # The phone's own accounts gained one: its owner is still exactly those accounts.
    claim = (
        "On March 22, 2026, there was no Wickr contact between the TARGET PHONE and"
        " kay@example.org after 10:00 a.m. EDT."
    )
    prop = P(accounts=[acc("kay@example.org", "Wickr Pro")], phones=["TARGET PHONE"],
             channels=["Wickr Pro"],
             window=W("after 10:00 a.m. EDT", "2026-03-22T10:00", "2026-03-23T00:00"))  # fmt: skip
    (a,), filler = build(conn, claim, prop)
    assert a.params.person_ids == (PETROV,), filler.drops
    assert a.params.account_ids == ("acct:item1:Wickr Pro:kay@example.org",)
    assert run(conn, a).outcome is CheckOutcome.INCONCLUSIVE  # 9:30 a.m. is outside the range
    conn.execute("UPDATE messages SET ts_utc = '2026-03-22T14:30:00Z' WHERE id = 'msg:w1'")
    assert run(conn, a).outcome is CheckOutcome.FAIL
    # An address with no app named never picks the app it is an account on.
    made, filler = build(
        conn,
        "There was no contact between the TARGET PHONE and kay@example.org before March 12, 2026.",
        P(accounts=[acc("kay@example.org", "Wickr Pro")], phones=["TARGET PHONE"]),
    )
    assert not made


# ---------------------------------------------------------------- refused, never guessed


def _refused(conn, claim: str, prop: dict, paragraph: str = "") -> list[str]:
    made, filler = build(conn, claim, prop, paragraph)
    assert not made, [a.text for a in made]
    return [d.reason for d in filler.drops]


C_NUMBER = "There was no contact between the TARGET PHONE and (212) 555-0144 before March 12, 2026."
P_NUMBER = P(accounts=[acc("(212) 555-0144", "Phone")], phones=["TARGET PHONE"])


def test_no_confirmed_owner_stipulation_refuses(base, tmp_path):
    c = _open(base, tmp_path, owner=False)
    try:
        assert any("no one person" in r for r in _refused(c, C_NUMBER, P_NUMBER))
        # A proposed stipulation is not ownership yet.
        stipulate(c, PETROV, "Daniel Petrov", "dev:item1")
        c.execute("UPDATE stipulations SET status = 'proposed'")
        assert _refused(c, C_NUMBER, P_NUMBER)
    finally:
        c.close()


def test_an_owner_with_accounts_beyond_the_phone_refuses(conn):
    # The owner's accounts would no longer be exactly the phone's own: an expert's link to an
    # account elsewhere would widen the phone's side.
    conn.execute(
        "INSERT INTO identity_links (id, account_id, person_id, status, tier, basis) VALUES"
        " ('link:x', 'acct:item2:Telegram:7001077', ?, 'confirmed', 'confirmed', 'test')",
        (PETROV,),
    )
    assert any("no one person" in r for r in _refused(conn, C_NUMBER, P_NUMBER))


def test_two_phones_refuse(conn):
    actions.name_device(conn, "dev:item2", ["SECOND PHONE"], EXPERT, lambda: AT)
    claim = (
        "There was no contact between the TARGET PHONE or the SECOND PHONE and (212) 555-0144"
        " before March 12, 2026."
    )
    _refused(conn, claim, P(accounts=[acc("(212) 555-0144", "Phone")], phones=["TARGET PHONE"]))
    _refused(conn, claim, P(accounts=[acc("(212) 555-0144", "Phone")],
                            phones=["TARGET PHONE", "SECOND PHONE"]))  # fmt: skip


def test_a_phone_the_case_does_not_hold_refuses(conn):
    claim = (
        "There was no contact between the BURNER PHONE and (212) 555-0144 before March 12, 2026."
    )
    reasons = _refused(conn, claim, P(accounts=[acc("(212) 555-0144", "Phone")],
                                      phones=["BURNER PHONE"]))  # fmt: skip
    assert any("matches 0 devices" in r for r in reasons)
    # The model gave no phone, and the claim writes none the case holds: nothing is read.
    _refused(conn, claim, P(accounts=[acc("(212) 555-0144", "Phone")]))


def test_a_phone_and_nobody_else_stays_refused(conn):
    claim = "The TARGET PHONE had no WhatsApp contact on March 22, 2026."
    day = W("on March 22, 2026", "2026-03-22T00:00", "2026-03-23T00:00")
    _refused(conn, claim, P(phones=["TARGET PHONE"], channels=["WhatsApp"], window=day))
    # The model's one party is the phone's own owner: still only one side.
    _refused(conn, claim, P(people=["PETROV"], phones=["TARGET PHONE"], channels=["WhatsApp"],
                            window=day))  # fmt: skip


def test_the_phones_own_number_is_no_other_party(conn):
    claim = (
        "There was no contact between the TARGET PHONE and (212) 555-0111 before March 12, 2026."
    )
    reasons = _refused(conn, claim, P(accounts=[acc("(212) 555-0111", "Phone")],
                                      phones=["TARGET PHONE"]))  # fmt: skip
    assert any("phone's own accounts" in r for r in reasons), reasons


def test_the_models_party_must_be_the_claims(conn):
    # The model took REYES from the paragraph; the claim writes a number.
    reasons = _refused(conn, C_NUMBER, P(people=["REYES"], phones=["TARGET PHONE"]),
                       paragraph="REYES used the TARGET PHONE.")  # fmt: skip
    assert any("not the one party the claim writes" in r for r in reasons), reasons


@pytest.mark.parametrize(
    "claim",
    [
        # A name in another clause, or someone named through the party (Codex on #169).
        "There was no contact between the TARGET PHONE and (212) 555-0144 after REYES left.",
        "On March 22, 2026, there was no contact between the TARGET PHONE and (212) 555-0144"
        " after 10:00 a.m. while REYES was away.",
        "There was no contact between the TARGET PHONE and REYES's phone before March 12, 2026.",
        # A second party, a kind of contact or a direction the check does not read.
        "There was no contact between the TARGET PHONE, REYES and (212) 555-0144 before"
        " March 12, 2026.",
        "The TARGET PHONE never called (212) 555-0144.",
        "The TARGET PHONE never texted (212) 555-0144.",
        "The TARGET PHONE never sent anything to (212) 555-0144.",
        "The TARGET PHONE never communicated with (212) 555-0144 about the car.",
    ],
)
def test_wording_beyond_plain_contact_refuses(conn, claim):
    _refused(conn, claim, P(accounts=[acc("(212) 555-0144", "Phone")], phones=["TARGET PHONE"]))


def test_a_wider_app_named_by_a_narrower_word_refuses(conn):
    # iOS "Native Messages" holds SMS too: "by iMessage" read on it would fail on texts.
    conn.executescript(
        "INSERT INTO accounts VALUES ('acct:item1:Native Messages:+12125550144', 'item1', 'x',"
        " NULL, 'Native Messages', '+12125550144', NULL);"
        "INSERT INTO threads VALUES ('thr:nm', 'item1', 'x', 'dev:item1', 'Native Messages',"
        " NULL);"
    )
    claim = "The TARGET PHONE never communicated by iMessage with (212) 555-0144."
    for prop in (
        P(phones=["TARGET PHONE"]),
        P(accounts=[acc("(212) 555-0144", "Phone")], phones=["TARGET PHONE"]),
    ):
        # Refused whichever guard comes first: the word beyond the app's own name, or the
        # wider app itself.
        _refused(conn, claim, prop)


# ---------------------------------------------------------------- readings that do not change


def test_two_real_parties_and_a_phone_keep_their_reading(conn):
    # The phone scopes the search; it is not a third party.
    claim = (
        "On the TARGET PHONE, there was no contact between PETROV and REYES between March 20"
        " and March 23, 2026."
    )
    prop = P(people=["PETROV", "REYES"], phones=["TARGET PHONE"],
             window=W("between March 20 and March 23, 2026", "2026-03-20T00:00",
                      "2026-03-24T00:00"))  # fmt: skip
    (a,), filler = build(conn, claim, prop)
    assert a.params.person_ids == (PETROV, REYES) and not a.params.account_ids, filler.drops
    assert a.params.device_ids == ("dev:item1",)
    # A person and a number with the phone: the phone's owner is not added.
    claim = (
        "On the TARGET PHONE, there was no contact between REYES and (212) 555-0144 between"
        " March 20 and March 23, 2026."
    )
    prop = P(people=["REYES"], accounts=[acc("(212) 555-0144", "Phone")],
             phones=["TARGET PHONE"],
             window=W("between March 20 and March 23, 2026", "2026-03-20T00:00",
                      "2026-03-24T00:00"))  # fmt: skip
    (a,), filler = build(conn, claim, prop)
    assert a.params.person_ids == (REYES,), filler.drops
    assert PETROV not in a.params.person_ids and a.params.device_ids == ("dev:item1",)


# ---------------------------------------------------------------- the check's own coverage


def test_a_party_with_no_account_on_the_named_app_is_never_a_pass(conn):
    # SMITH's only account is an SMS number: finding no Instagram contact with SMITH shows
    # nothing, even on a full extraction that spans the range.
    conn.execute("INSERT INTO persons VALUES (?, 'John Smith', 'expert:test')", (SMITH,))
    conn.execute(
        "INSERT INTO identity_links (id, account_id, person_id, status, tier, basis) VALUES"
        " ('link:s', 'acct:item1:SMS:+12125550182', ?, 'confirmed', 'confirmed', 'test')",
        (SMITH,),
    )
    full_extraction(conn)
    w = window(datetime(2026, 3, 1), datetime(2026, 3, 3))
    r = check(conn, "no_contact", person_ids=[PETROV, SMITH], channels=["Instagram"],
              device_ids=["dev:item1"], window=w)  # fmt: skip
    assert r.outcome is CheckOutcome.INCONCLUSIVE, text(r)
    assert "person:smith has no Instagram account in the searched sources" in r.detail
    # Every channel: SMITH's SMS account is searched, and the check reads as before.
    r = check(conn, "no_contact", person_ids=[PETROV, SMITH], device_ids=["dev:item1"],
              window=w)  # fmt: skip
    assert "has no" not in r.detail
