"""Message counts whose phone is a side, and "exchanged" claims the model gave as an event.

Synthetic case01 only, with a scripted fake model. On dev:item1 (PETROV's phone, his
confirmed stipulation) on March 21, 2026: PETROV's Telegram account sent 5551234 one message
at 1:05 p.m. EDT and 5551234 answered at 1:20 p.m.; on March 19 at 10:48 p.m. EDT the WhatsApp
id of (212) 555-0122 sent PETROV one message, with no answer.
"""

import json
import re
import sqlite3
from pathlib import Path

import pytest

from core.audit._llm_json import prompt_body
from core.audit.assumption_filler import LocalAssumptionFiller
from core.audit.assumptions import TemplateAssumptionBuilder
from core.audit.checks import CHECKS
from core.contracts import CheckOutcome, Claim, ClaimStatus, ClaimType
from eval.synthetic.generate import generate
from tests.checks.helpers import stipulate
from tests.fake_model import FakeModel

ROOT = Path(__file__).parents[1]
DRAFT = prompt_body((ROOT / "docs/prompts/assumptions.md").read_text("utf-8"))
PETROV, REYES = "person:petrov", "person:reyes"
ACCT_5551234 = "acct:item1:Telegram:5551234"
TG = {"as_written": "5551234", "app": "Telegram"}


def _case(tmp_path_factory, owners: bool) -> sqlite3.Connection:
    out = tmp_path_factory.mktemp("case01")
    db = out / "case01.db"
    generate(out, db)
    c = sqlite3.connect(db)
    if owners:
        stipulate(c, PETROV, "Daniel Petrov", "dev:item1")
        stipulate(c, REYES, "Marcus Reyes", "dev:item2")
    c.execute("PRAGMA foreign_keys = OFF")
    affidavit = (ROOT / "eval/synthetic/case01/affidavit_draft.md").read_text("utf-8")
    for label, text in re.findall(r"^(\d+)\. (.+)$", affidavit, re.M):
        c.execute(
            "INSERT INTO govdoc_paragraphs (id, govdoc_id, page, para_no, label, char_start,"
            " char_end, text) VALUES (?, 'gd', 1, ?, ?, 0, ?, ?)",
            (f"para:{label}", int(label), label, len(text), text),
        )
    return c


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    c = _case(tmp_path_factory, owners=True)
    yield c
    c.close()


@pytest.fixture(scope="module")
def no_owner(tmp_path_factory):
    """The same case with no confirmed owner of either phone."""
    c = _case(tmp_path_factory, owners=False)
    yield c
    c.close()


def P(template_id: str, **kw) -> dict:  # noqa: N802
    base = dict(
        people=[],
        accounts=[],
        handles=[],
        phones=[],
        channels=[],
        quoted_text="",
        count=None,
        duration=None,
        window=None,
    )
    return {"template_id": template_id, **base, **kw}


def W(as_written: str, start: str, end: str) -> dict:  # noqa: N802
    return {"as_written": as_written, "start": start, "end": end, "zone": "phone"}


MAR21 = W("On March 21, 2026", "2026-03-21T00:00", "2026-03-22T00:00")
# 1:05 p.m. holds only PETROV's message; his answer came at 1:20 p.m.
MAR21_ONE_WAY = W(
    "On March 21, 2026, between 1:00 p.m. and 1:10 p.m.", "2026-03-21T13:00", "2026-03-21T13:10"
)
MAR19 = W("On March 19, 2026", "2026-03-19T00:00", "2026-03-20T00:00")
EXCH = "On March 21, 2026, dev:item1 exchanged Telegram messages with the Telegram account 5551234."


def build(conn, text: str, props: list[dict], claim_type: ClaimType = ClaimType.COMMUNICATION):
    filler = LocalAssumptionFiller(
        FakeModel(json.dumps({"assumptions": props})), conn, template=DRAFT
    )
    c = Claim(
        id="X1", paragraph_id="para:5", text=text, claim_type=claim_type,
        status=ClaimStatus.ACCEPTED,
    )  # fmt: skip
    return TemplateAssumptionBuilder(filler).build(c), filler


def counts(made):
    return [a for a in made if a.template_id == "message_count"]


def tg(template_id: str = "message_count", window=MAR21, **kw) -> dict:
    """The model's answer for dev:item1 and the Telegram account 5551234."""
    kw = {"accounts": [TG], "phones": ["dev:item1"], "channels": ["Telegram"], **kw}
    return P(template_id, window=window, **kw)


# ------------------------------------------------ the phone written as a side is its owner


@pytest.mark.parametrize("template_id", ["message_count", "event"])
def test_the_phone_that_exchanged_messages_is_its_exact_owner(conn, template_id):
    # The model named only the account and the phone, as a count or as one event. The phone
    # stands as a side, so it is PETROV through his confirmed stipulation; with no number the
    # claim is at least two messages, one each way (ruling R3).
    text = EXCH
    made, filler = build(conn, text, [tg(template_id)])
    (a,) = made
    assert a.template_id == "message_count", filler.drops
    assert a.params.person_ids == (PETROV,) and a.params.account_ids == (ACCT_5551234,)
    assert a.params.each_way and (a.params.count_op, a.params.expected_count) == ("ge", 2)
    assert a.text.endswith("Filled from the claim's wording.")
    r = CHECKS["count"].run(a, conn)
    assert r.outcome is CheckOutcome.PASS, r.detail
    assert "sent 1 of them" in r.detail


def test_messages_one_way_only_never_pass_an_exchange(conn):
    # The window holds PETROV's message and not the answer: the count stays inconclusive (the
    # check's own rule: one side's silence is never a fail, and never a pass).
    text = (
        "On March 21, 2026, between 1:00 p.m. and 1:10 p.m., dev:item1 exchanged Telegram"
        " messages with the Telegram account 5551234."
    )
    for template_id in ("message_count", "event"):
        made, filler = build(conn, text, [tg(template_id, window=MAR21_ONE_WAY)])
        (a,) = counts(made)
        assert a.params.each_way, filler.drops
        r = CHECKS["count"].run(a, conn)
        assert r.outcome is CheckOutcome.INCONCLUSIVE, r.detail
        assert "Not finding a message each way" in r.detail


def test_the_phone_as_the_sender_or_the_recipient_of_one_sides_count(conn):
    # Ruling R2 with the phone written as one side: only that side's messages are counted.
    sent = (
        "On March 21, 2026, dev:item1 sent the Telegram account 5551234 exactly one Telegram"
        " message."
    )
    got = (
        "On March 21, 2026, the Telegram account 5551234 sent dev:item1 exactly one Telegram"
        " message."
    )
    for text, sender in ((sent, (PETROV,)), (got, (ACCT_5551234,))):
        made, filler = build(conn, text, [tg(count={"value": 1})], ClaimType.COUNT)
        (a,) = made
        assert a.params.sent_by == sender, filler.drops
        assert a.params.person_ids == (PETROV,)
        r = CHECKS["count"].run(a, conn)
        assert r.outcome is CheckOutcome.PASS, r.detail


@pytest.mark.parametrize(
    "text",
    [
        # the phone is where, not with whom
        "On March 21, 2026, the Telegram account 5551234 exchanged Telegram messages on dev:item1.",
        "On March 21, 2026, on dev:item1, the Telegram account 5551234 exchanged Telegram"
        " messages.",
        # someone else exchanged them on the phone
        "On March 21, 2026, REYES exchanged Telegram messages with the Telegram account 5551234 on"
        " dev:item1.",
        # the phone named, then a different phone
        "On March 21, 2026, dev:item1 exchanged Telegram messages with the Telegram account"
        " 5551234 on dev:item2.",
        # the phone is not the subject of "sent"
        "On March 21, 2026, on dev:item1, the Telegram account 5551234 sent exactly one Telegram"
        " message.",
        # the phone's someone is not the phone's side
        "On March 21, 2026, a friend of dev:item1 sent the Telegram account 5551234 exactly one"
        " Telegram message.",
    ],
)
def test_a_phone_not_written_as_a_side_adds_no_side(conn, text):
    count = {"value": 1} if "exactly one" in text else None
    made, filler = build(conn, text, [tg(count=count)], ClaimType.COUNT)
    assert not counts(made), [a.params for a in made]
    assert filler.drops


def test_no_side_is_added_for_a_phone_with_no_confirmed_owner(no_owner):
    text = EXCH
    made, filler = build(no_owner, text, [tg()])
    assert not counts(made), [a.params for a in made]


def test_an_account_both_sides_hold_counts_no_direction(conn):
    # 7001001 is the phone's own Telegram account, so it is on PETROV's side too: whichever way
    # the filler reads it, a count by direction never passes or fails.
    text = EXCH.replace("5551234", "7001001")
    made, _ = build(conn, text, [tg(accounts=[{"as_written": "7001001", "app": "Telegram"}])])
    for a in counts(made):
        r = CHECKS["count"].run(a, conn)
        assert r.outcome is CheckOutcome.INCONCLUSIVE, r.detail


# ------------------------------------------------ bounds, received and quoted limits


@pytest.mark.parametrize(
    "text, value, op",
    [
        ("On March 21, 2026, dev:item1 sent the Telegram account 5551234 at least one Telegram"
         " message.", 1, "ge"),
        ("On March 21, 2026, dev:item1 sent the Telegram account 5551234 more than one Telegram"
         " message.", 1, None),
        ("On March 21, 2026, dev:item1 sent the Telegram account 5551234 about two Telegram"
         " messages.", 2, None),
        ("On March 21, 2026, dev:item1 and the Telegram account 5551234 exchanged over two"
         " Telegram messages.", 2, None),
    ],
)  # fmt: skip
def test_only_an_exact_or_at_least_bound_is_read(conn, text, value, op):
    # "more than", "about" and "over" are not one exact comparison: they stay refused (B19's
    # kind of wording), with the phone as a side or not.
    made, filler = build(conn, text, [tg(count={"value": value})], ClaimType.COUNT)
    if op is None:
        assert not counts(made), [a.params for a in made]
        assert any("approximate or strict" in d.reason for d in filler.drops), filler.drops
    else:
        (a,) = counts(made)
        assert a.params.count_op == op and a.params.sent_by == (PETROV,)


@pytest.mark.parametrize(
    "text",
    [
        "On March 21, 2026, on dev:item1, REYES received exactly one Telegram message from PETROV.",
        "On March 21, 2026, on dev:item1, the Telegram group received exactly one Telegram message"
        " from PETROV.",
        "On March 21, 2026, exactly one Telegram message from PETROV was received by REYES on"
        " dev:item1.",
    ],
)
def test_a_received_count_stays_refused(conn, text):
    # "received" is not the signed R2 form: which side the count keeps is not read from it
    # (a group as the receiver would count the group's members).
    other = {"handles": ["Telegram group"]} if "group" in text else {"people": ["PETROV", "REYES"]}
    if "group" in text:
        other["people"] = ["PETROV"]
    prop = P("message_count", phones=["dev:item1"], channels=["Telegram"], count={"value": 1},
             window=MAR21, **other)  # fmt: skip
    made, filler = build(conn, text, [prop], ClaimType.COUNT)
    assert not counts(made), [a.params for a in made]
    assert any("one side sent or received" in d.reason for d in filler.drops), filler.drops


@pytest.mark.parametrize(
    "text",
    [
        'On March 21, 2026, dev:item1 exchanged "urgent" Telegram messages with the Telegram'
        " account 5551234.",
        "On March 21, 2026, dev:item1 exchanged Telegram messages with the Telegram account"
        ' 5551234 "about the car".',
        'On March 21, 2026, dev:item1 sent the Telegram account 5551234 exactly one "urgent"'
        " Telegram message.",
        'On March 21, 2026, in "the second chat", dev:item1 exchanged Telegram messages with the'
        " Telegram account 5551234.",
    ],
)
def test_quoted_words_that_limit_the_messages_refuse_the_count(conn, text):
    # The check reads no message content, so words in quotation marks that limit which
    # messages count are a limit like any other, not blanks.
    count = {"value": 1} if "exactly one" in text else None
    made, filler = build(conn, text, [tg(count=count)], ClaimType.COUNT)
    assert not counts(made), [a.params for a in made]


# ------------------------------------------------ a WhatsApp id is its number


def test_a_number_written_for_a_whatsapp_id_is_that_side(conn):
    text = "On March 19, 2026, dev:item1 exchanged WhatsApp messages with (212) 555-0122."
    prop = P("event", accounts=[{"as_written": "(212) 555-0122", "app": "WhatsApp"}],
             phones=["dev:item1"], channels=["WhatsApp"], window=MAR19)  # fmt: skip
    made, filler = build(conn, text, [prop])
    (a,) = counts(made)
    assert a.params.account_ids == ("acct:item1:WhatsApp:12125550122@s.whatsapp.net",)
    assert a.params.each_way and a.params.person_ids == (PETROV,), filler.drops
    # that day 0122 wrote and PETROV did not answer: not a pass
    r = CHECKS["count"].run(a, conn)
    assert r.outcome is CheckOutcome.INCONCLUSIVE, r.detail


def test_a_number_no_side_holds_still_refuses_the_exchange(conn):
    text = (
        "On March 19, 2026, dev:item1 exchanged WhatsApp messages with (212) 555-0122 and"
        " (212) 555-0155."
    )
    prop = P("event", accounts=[{"as_written": "(212) 555-0122", "app": "WhatsApp"}],
             phones=["dev:item1"], channels=["WhatsApp"], window=MAR19)  # fmt: skip
    made, _ = build(conn, text, [prop])
    assert not counts(made), [a.params for a in made]


# ------------------------------------------------ an event read as the exchange


@pytest.mark.parametrize(
    "text, props",
    [
        # not an exchange: an event stays an event
        ("On March 21, 2026, dev:item1 deleted two Telegram messages it had sent to the Telegram"
         " account 5551234.", [tg("event")]),
        # two events: which one is the exchange is not known
        ("On March 21, 2026, dev:item1 exchanged Telegram messages with the Telegram account"
         " 5551234.", [tg("event"), tg("event", accounts=[])]),
        # a role is interpretation, never read as a count
        ("On March 21, 2026, dev:item1 exchanged Telegram messages with the Telegram account"
         " 5551234.", [tg("role", people=["PETROV"])]),
        # the event names words of a message: the count reads none
        ("On March 21, 2026, dev:item1 exchanged Telegram messages with the Telegram account"
         ' 5551234, one reading "ok".', [tg("event", quoted_text="ok")]),
    ],
)  # fmt: skip
def test_only_one_plain_exchange_event_is_read_as_a_count(conn, text, props):
    made, filler = build(conn, text, props, ClaimType.COMMUNICATION)
    assert not counts(made), [a.params for a in made]


def test_an_exchange_event_with_a_stated_count_is_still_compared(conn):
    # The model's count rides along with its event and is compared as the claim writes it.
    text = (
        "On March 21, 2026, dev:item1 exchanged exactly two Telegram messages with the Telegram"
        " account 5551234."
    )
    made, filler = build(conn, text, [tg("event", count={"value": 2})])
    (a,) = counts(made)
    assert a.params.each_way and (a.params.count_op, a.params.expected_count) == ("eq", 2)
    assert not [x for x in made if x.template_id == "event"], filler.drops
    assert CHECKS["count"].run(a, conn).outcome is CheckOutcome.PASS


@pytest.mark.parametrize(
    "text, value",
    [
        ('On March 21, 2026, PETROV and REYES exchanged "urgent" Telegram messages on dev:item1.',
         None),
        ("On March 21, 2026, PETROV and REYES exchanged Telegram messages on dev:item1, the"
         ' "first ones".', None),
        ("On March 21, 2026, on dev:item1, PETROV sent REYES exactly one Telegram message"
         ' "about the car".', 1),
    ],
)  # fmt: skip
def test_quoted_limits_refuse_a_count_between_two_people(conn, text, value):
    # The same hole without the phone as a side: before, quoted words were blanked and the
    # exchange read as plain.
    prop = P("message_count", people=["PETROV", "REYES"], phones=["dev:item1"],
             channels=["Telegram"], count=None if value is None else {"value": value},
             window=MAR21)  # fmt: skip
    made, filler = build(conn, text, [prop], ClaimType.COUNT)
    assert not counts(made), [a.params for a in made]
    assert any("quotes words the count does not read" in d.reason for d in filler.drops)


def test_a_sides_quoted_name_is_read_as_that_side(conn):
    # 'the Telegram user "@alex92"': the quotation marks hold the account's own name, so the
    # exchange is still plain.
    text = (
        'On March 21, 2026, dev:item1 exchanged Telegram messages with the Telegram user "@alex92".'
    )
    made, filler = build(conn, text, [tg(accounts=[], handles=["@alex92"])])
    (a,) = counts(made)
    assert a.params.each_way and a.params.person_ids == (PETROV,), filler.drops
    assert CHECKS["count"].run(a, conn).outcome is CheckOutcome.PASS
