"""Who placed a call: the caller assumption code reads from a claim's plain words, and the caller
check that reads it against the call log's direction. Synthetic case01 with made-up calls added;
every number, name and wording is invented."""

import json
import sqlite3
from datetime import datetime

import pytest

from core.audit.assumption_filler import LocalAssumptionFiller
from core.audit.assumptions import TEMPLATES, TemplateAssumptionBuilder, instantiate
from core.audit.checks import CHECKS, run_checks
from core.audit.rules import decide_verdict
from core.contracts import CheckOutcome, ClaimType, Verdict
from core.pipeline import load_stipulations
from eval.synthetic.generate import generate
from tests.checks.helpers import stipulate, window
from tests.fake_model import FakeModel
from tests.test_affidavit_wording import W, claim, proposal

PETROV, REYES = "person:petrov", "person:reyes"
# A number the case holds twice on the phone's own call log ("+1..." and bare digits), as an
# export can: one party.
NUM = ["acct:item1:unknown:+12125550199", "acct:item1:unknown:12125550199"]
OTHER = "acct:item1:unknown:+12125550188"
UNTIMED = "acct:item1:unknown:+12125550177"  # a number with one untimed call
PETROV_WA = "acct:item1:WhatsApp:12125550111@s.whatsapp.net"
REYES_WA = "acct:item1:WhatsApp:12125550122@s.whatsapp.net"
OWN_UNKNOWN = "acct:item1:unknown:+12125550111"  # the phone's own number on its call log

# (id, app, from, to, direction, UTC time, seconds). June 2026 holds no other case01 call.
CALLS = [
    # June 1, 9:00 p.m. EDT: the phone called the number (100 s), logged twice, once per form.
    ("c:out:a", "unknown", None, NUM[1], "outgoing", "2026-06-02T01:00:00Z", 100),
    ("c:out:b", "unknown", OWN_UNKNOWN, NUM[0], "outgoing", "2026-06-02T01:00:20Z", 98),
    # June 2, 9:00 p.m. EDT: the number called the phone (100 s).
    ("c:in", "unknown", NUM[0], None, "incoming", "2026-06-03T01:00:00Z", 100),
    # June 3, 9:00 p.m.: a call each way four minutes apart.
    ("c:mix:out", "unknown", None, NUM[0], "outgoing", "2026-06-04T01:00:00Z", 60),
    ("c:mix:in", "unknown", NUM[0], None, "incoming", "2026-06-04T01:04:00Z", 60),
    # June 4: the log does not say who placed it.
    ("c:unk", "unknown", NUM[0], None, "unknown", "2026-06-05T01:00:00Z", 60),
    # June 5: logged missed.
    ("c:missed", "unknown", NUM[0], None, "missed", "2026-06-06T01:00:00Z", None),
    # June 6: 'outgoing', yet the number sits on the calling side: the row contradicts itself.
    ("c:odd", "unknown", NUM[0], None, "outgoing", "2026-06-07T01:00:00Z", 60),
    # June 7: a call with no usable time, and one inside the window.
    ("c:notime", "unknown", UNTIMED, None, "incoming", None, 60),
    ("c:timed", "unknown", None, UNTIMED, "outgoing", "2026-06-08T01:00:00Z", 60),
    # June 8, 9:00 p.m.: REYES called PETROV on WhatsApp, on PETROV's phone.
    ("c:wa", "WhatsApp", REYES_WA, PETROV_WA, "incoming", "2026-06-09T01:00:00Z", 90),
    # June 9, 9:00 p.m.: another number called the phone; the claim's number has no call then.
    ("c:other", "unknown", OTHER, None, "incoming", "2026-06-10T01:00:00Z", 60),
    # June 11, 9:00 p.m.: the number called the phone (100 s), then the phone called it, its
    # length not recorded.
    ("c:len:in", "unknown", NUM[0], None, "incoming", "2026-06-12T01:00:00Z", 100),
    ("c:len:out", "unknown", None, NUM[0], "outgoing", "2026-06-12T01:03:00Z", None),
]


def _add_calls(c: sqlite3.Connection) -> None:
    c.execute("PRAGMA foreign_keys = OFF")
    for acc, dev in [
        (NUM[0], None),
        (NUM[1], None),
        (OTHER, None),
        (UNTIMED, None),
        (OWN_UNKNOWN, "dev:item1"),
    ]:
        ident = acc.rsplit(":", 1)[1]
        c.execute(
            "INSERT INTO accounts VALUES (?, 'item1', ?, ?, 'unknown', ?, NULL)",
            (acc, acc, dev, ident),
        )
    for cid, app, frm, to, direction, ts, dur in CALLS:
        c.execute(
            "INSERT INTO calls VALUES (?, 'item1', ?, 'dev:item1', ?, ?, ?, ?, ?, 0, NULL, ?, 0)",
            (cid, cid, app, frm, to, direction, ts, dur),
        )


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    out = tmp_path_factory.mktemp("case01")
    generate(out, out / "case01.db")
    c = sqlite3.connect(out / "case01.db")
    stipulate(c, PETROV, "Daniel Petrov", "dev:item1")
    stipulate(c, REYES, "Marcus Reyes", "dev:item2")
    _add_calls(c)
    yield c
    c.close()


def day(d: int, h: int = 20, m: int = 52, h2: int = 21, m2: int = 9):
    return window(datetime(2026, 6, d, h, m), datetime(2026, 6, d, h2, m2))


def caller(conn, d: int, by: str, *, people=(PETROV,), accounts=NUM, **kw):
    params = {"person_ids": list(people), "window": day(d), "channels": ["call"],
              "device_ids": ["dev:item1"], "sent_by": [by] if by != "num" else list(accounts),
              **({"account_ids": list(accounts)} if accounts else {}), **kw}  # fmt: skip
    a = instantiate("CT", "caller", params)
    return CHECKS["caller"].run(a, conn)


# ---------------------------------------------------------------- the check


def test_the_phone_placed_it_passes_on_every_copy(conn):
    r = caller(conn, 1, PETROV)
    assert r.outcome is CheckOutcome.PASS, r.detail
    assert set(r.record_ids) == {"c:out:a", "c:out:b"}
    assert "may be one call stored twice" in r.detail


def test_a_reversed_direction_fails(conn):
    # The claim says the number called; the log says the phone did.
    r = caller(conn, 1, "num")
    assert r.outcome is CheckOutcome.FAIL, r.detail
    assert "not seen" in r.detail  # what the log does not hold is not read as absent
    assert caller(conn, 2, "num").outcome is CheckOutcome.PASS
    assert caller(conn, 2, PETROV).outcome is CheckOutcome.FAIL


@pytest.mark.parametrize("d", [3, 4, 6])
def test_mixed_unknown_or_contradictory_rows_are_inconclusive(conn, d):
    # both ways in the window; direction unknown; a row whose sides contradict its direction
    for by in (PETROV, "num"):
        assert caller(conn, d, by).outcome is CheckOutcome.INCONCLUSIVE, (d, by)


def test_a_matching_call_with_no_usable_time_may_be_in_the_window(conn):
    for by in (PETROV, "num"):
        r = caller(conn, 7, by, accounts=[UNTIMED])
        assert r.outcome is CheckOutcome.INCONCLUSIVE, (by, r.detail)
        assert "no usable time" in r.detail


def test_missed_agrees_with_the_other_side_calling_and_never_fails(conn):
    assert caller(conn, 5, "num").outcome is CheckOutcome.PASS
    r = caller(conn, 5, PETROV)
    assert r.outcome is CheckOutcome.INCONCLUSIVE, r.detail


def test_a_stated_length_picks_the_call(conn):
    assert caller(conn, 3, PETROV, duration_s=(50, 70)).outcome is CheckOutcome.INCONCLUSIVE
    assert caller(conn, 1, PETROV, duration_s=(99, 101)).outcome is CheckOutcome.PASS
    r = caller(conn, 1, PETROV, duration_s=(10, 20))
    assert r.outcome is CheckOutcome.INCONCLUSIVE and not r.record_ids


def test_a_call_of_unknown_length_may_be_the_stated_one_and_never_lets_a_fail_stand(conn):
    # The claim: the phone placed a 100 s call. The 100 s call was incoming, but the outgoing
    # call has no recorded length, so it may be the claimed call.
    r = caller(conn, 11, PETROV, duration_s=(99, 101))
    assert r.outcome is CheckOutcome.INCONCLUSIVE, r.detail
    assert "no recorded length" in r.detail and "c:len:out" in r.record_ids
    assert caller(conn, 11, "num", duration_s=(99, 101)).outcome is CheckOutcome.INCONCLUSIVE


def test_the_app_named_beside_call_scopes_the_calls(conn):
    p = {"people": (PETROV, REYES), "accounts": ()}
    assert caller(conn, 8, REYES, channels=["call", "WhatsApp"], **p).outcome is CheckOutcome.PASS
    r = caller(conn, 8, REYES, channels=["call", "Telegram"], **p)
    assert r.outcome is CheckOutcome.INCONCLUSIVE and not r.record_ids


def test_a_call_with_someone_else_is_not_this_call(conn):
    r = caller(conn, 9, "num")
    assert r.outcome is CheckOutcome.INCONCLUSIVE and not r.record_ids
    assert "Not found does not mean" in r.detail


def test_two_persons_on_the_owner_s_phone(conn):
    # PETROV owns item1 and REYES item2, by confirmed stipulation: REYES's WhatsApp account is
    # the one item1 recorded calling.
    p = {"people": (PETROV, REYES), "accounts": ()}
    assert caller(conn, 8, REYES, **p).outcome is CheckOutcome.PASS
    assert caller(conn, 8, PETROV, **p).outcome is CheckOutcome.FAIL


def test_an_unconfirmed_owner_reads_no_side(conn):
    conn.execute("UPDATE stipulations SET status = 'proposed' WHERE subject_id = 'dev:item1'")
    try:
        r = caller(conn, 1, PETROV)
        assert r.outcome is CheckOutcome.INCONCLUSIVE
        assert "not confirmed" in r.detail
    finally:
        conn.execute("UPDATE stipulations SET status = 'confirmed' WHERE subject_id = 'dev:item1'")


def test_the_template_needs_one_calling_side_and_the_call_channel():
    base = {"person_ids": [PETROV], "account_ids": NUM, "window": day(1), "channels": ["call"]}
    assert not TEMPLATES["caller"].problems(
        instantiate("CT", "caller", {**base, "sent_by": NUM}).params
    )
    for bad in [
        {**base, "sent_by": [NUM[0]]},  # part of the accounts
        {**base, "sent_by": [PETROV, NUM[0]]},  # both sides
        {**base, "sent_by": [PETROV], "channels": ["WhatsApp"]},  # no call channel
        {**base, "sent_by": [PETROV], "account_ids": []},  # one party
    ]:
        with pytest.raises(ValueError):
            instantiate("CT", "caller", bad)


# ---------------------------------------------------------------- reading the claim


def fill(conn, text: str, kind=ClaimType.COMMUNICATION, *, items=None, **change):
    if items is None:
        answer = {**proposal(people=[], quoted_text="", channels=["call"],
                             window=W("June 1, 2026", "2026-06-01T20:52", "2026-06-01T21:09"))
                  .model_dump(), **change}  # fmt: skip
        items = [answer]
    f = LocalAssumptionFiller(FakeModel(json.dumps({"assumptions": items})), conn,
                              template="{claim} {paragraph} {templates} {channels}")  # fmt: skip
    made = TemplateAssumptionBuilder(f).build(claim(text, kind))
    return {a.template_id: a for a in made}, f


AT = "On June 1, 2026, at about 9:00 p.m. EDT,"


@pytest.mark.parametrize(
    ("words", "by"),
    [
        ("Item 1 placed an outgoing telephone call to (212) 555-0199.", PETROV),
        ("Item 1 made a call to (212) 555-0199.", PETROV),
        ("Item 1 called (212) 555-0199.", PETROV),
        ("(212) 555-0199 placed a call to Item 1.", "num"),
        ("(212) 555-0199 called Item 1.", "num"),
        ("Item 1 received an incoming call from (212) 555-0199.", "num"),
    ],
)
def test_a_plain_form_names_the_caller(conn, words, by):
    made, _ = fill(conn, f"{AT} {words}")
    a = made["caller"]
    assert a.is_core and a.text.endswith("Filled from the claim's wording.")
    assert list(a.params.sent_by) == ([PETROV] if by == PETROV else sorted(NUM))
    assert set(a.params.person_ids) == {PETROV} and set(a.params.account_ids) == set(NUM)
    assert a.params.window == made["record_time"].params.window
    assert "event" not in made


def test_missed_adds_an_event_only_an_expert_carries(conn):
    made, _ = fill(conn, f"{AT} Item 1 missed an incoming call from (212) 555-0199.")
    assert list(made["caller"].params.sent_by) == sorted(NUM)
    assert made["event"].is_core and TEMPLATES["event"].checks == ()


def test_a_stated_length_must_be_the_time_range_s(conn):
    text = (
        f"{AT} Item 1 placed a call to (212) 555-0199 that lasted about one minute and 40 seconds."
    )
    made, _ = fill(conn, text, duration={"as_written": "about one minute and 40 seconds"})
    assert made["caller"].params.duration_s == made["record_time"].params.duration_s
    # the model gave no length: the caller would test a call the time range does not pick
    made, _ = fill(conn, text)
    assert "caller" not in made


@pytest.mark.parametrize(
    "words",
    [
        # direction words the verb does not allow
        "Item 1 placed an incoming call to (212) 555-0199.",
        "Item 1 received an outgoing call from (212) 555-0199.",
        "Item 1 missed an outgoing call from (212) 555-0199.",
        # words the forms do not hold
        "Item 1 returned a call to (212) 555-0199.",
        "Item 1 attempted a call to (212) 555-0199.",
        "Item 1 placed a call to (212) 555-0199 that was answered and lasted about two minutes.",
        "Item 1 placed a call to (212) 555-0199 that connected.",
        "Item 1 called (212) 555-0199 back.",
        "Item 1 called (212) 555-0199 and PETROV.",
        "Item 1 did not call (212) 555-0199.",
        "Item 1 never called (212) 555-0199.",
        "(212) 555-0199 was called by Item 1.",
        "a call was placed from Item 1 to (212) 555-0199.",
        "Item 1 placed two calls to (212) 555-0199.",
        "Item 1 placed a video call to (212) 555-0199.",
        "Item 1 placed a call to (212) 555-0199, who did not answer.",
        # an ordinal states an earlier call no check reads
        "Item 1 received a second telephone call from (212) 555-0199.",
        "Item 1 placed a third call to (212) 555-0199.",
        # no direction at all
        "Item 1 had a call with (212) 555-0199.",
        "Item 1 and (212) 555-0199 spoke by phone.",
    ],
)
def test_wording_that_is_not_a_plain_form_names_no_caller(conn, words):
    made, _ = fill(conn, f"{AT} {words}")
    assert "caller" not in made, made["caller"].text


def test_a_lead_that_limits_the_call_names_no_caller(conn):
    made, _ = fill(conn, f"{AT} in Spanish, Item 1 called (212) 555-0199.")
    assert "caller" not in made


def test_a_phone_without_one_exact_owner_names_no_caller(conn):
    conn.execute("UPDATE stipulations SET status = 'proposed' WHERE subject_id = 'dev:item1'")
    try:
        made, _ = fill(conn, f"{AT} Item 1 called (212) 555-0199.")
        assert "record_time" in made and "caller" not in made
    finally:
        conn.execute("UPDATE stipulations SET status = 'confirmed' WHERE subject_id = 'dev:item1'")


def test_two_persons_read_by_name(conn):
    text = "On June 8, 2026, at about 9:00 p.m. EDT, Marcus Reyes placed a WhatsApp call to PETROV."
    made, _ = fill(conn, text, channels=["call", "WhatsApp"],
                   window=W("June 8", "2026-06-08T20:52", "2026-06-08T21:09"))  # fmt: skip
    assert list(made["caller"].params.sent_by) == [REYES]
    assert set(made["caller"].params.person_ids) == {PETROV, REYES}


def test_the_claims_app_scopes_the_caller_when_the_model_writes_only_call(conn):
    # The model wrote only "call"; the claim names WhatsApp, so a call on another app between
    # the two is never the claim's call.
    text = "On June 8, 2026, at about 9:00 p.m. EDT, Marcus Reyes placed a WhatsApp call to PETROV."
    made, _ = fill(conn, text, channels=["call"],
                   window=W("June 8", "2026-06-08T20:52", "2026-06-08T21:09"))  # fmt: skip
    assert list(made["caller"].params.channels) == ["WhatsApp", "call"]


def test_the_model_is_never_offered_the_caller_template(conn):
    f = LocalAssumptionFiller(FakeModel(json.dumps({"assumptions": []})), conn,
                              template="{claim} {paragraph} {templates} {channels}")  # fmt: skip
    TemplateAssumptionBuilder(f).build(claim(f"{AT} Item 1 called (212) 555-0199."))
    (prompt,), (schema,) = f.model.prompts, f.model.schemas
    assert "caller" not in prompt
    enum = schema["properties"]["assumptions"]["items"]["properties"]["template_id"]["enum"]
    assert "caller" not in enum and "record_time" in enum
    # and a model's answer naming it is refused
    item = {**proposal(people=[], quoted_text="", channels=["call"],
                       window=W("June 1, 2026", "2026-06-01T20:52", "2026-06-01T21:09"))
            .model_dump(), "template_id": "caller"}  # fmt: skip
    made, f = fill(conn, f"{AT} Item 1 had a call with (212) 555-0199.", items=[item])
    assert "caller" not in made
    assert any("filled by code" in d.reason or "not allowed" in d.reason for d in f.drops)


# ---------------------------------------------------------------- end to end


def verdict(conn, text: str, day_: int, **change):
    w = W(f"June {day_}", f"2026-06-{day_:02}T20:52", f"2026-06-{day_:02}T21:09")
    made, _ = fill(conn, text.replace("June 1", f"June {day_}"), window=w, **change)
    assumptions = list(made.values())
    checks = [r for a in assumptions for r in run_checks(a, conn)]
    c = claim(text.replace("June 1", f"June {day_}"))
    return decide_verdict(c, assumptions, [], checks, load_stipulations(conn), "run")


def test_a_reversed_claim_is_contradicted_and_a_true_one_supported_by_checks(conn):
    true = verdict(conn, f"{AT} Item 1 called (212) 555-0199.", 1)
    assert true.verdict is Verdict.SUPPORTED, true.reasons
    reversed_ = verdict(conn, f"{AT} (212) 555-0199 called Item 1.", 1)
    assert reversed_.verdict is Verdict.CONTRADICTED, reversed_.reasons
    # calls both ways in the window: neither reading is decided
    for text in (f"{AT} Item 1 called (212) 555-0199.", f"{AT} (212) 555-0199 called Item 1."):
        assert verdict(conn, text, 3).verdict is Verdict.UNPROVEN


def test_a_missed_call_stays_for_the_expert(conn):
    v = verdict(conn, f"{AT} Item 1 missed an incoming call from (212) 555-0199.", 5)
    assert v.verdict is Verdict.UNPROVEN
    assert any("event" in r for r in v.reasons), v.reasons


def test_a_timing_claim_that_states_a_direction_is_not_supported_on_its_time_alone(conn):
    # Before the caller assumption, the time check alone carried this (rule 3c').
    v = verdict(conn, f"{AT} Item 1 called (212) 555-0199.", 3)
    assert v.verdict is Verdict.UNPROVEN


# ---------------------------------------------------------------- one side of a count


def test_a_count_with_the_phone_as_one_side_reads_both_sides(conn):
    text = "On June 8, 2026, Item 1 had two WhatsApp calls with Marcus Reyes."
    item = proposal(people=["Marcus Reyes"], quoted_text="", phones=["Item 1"],
                    channels=["call", "WhatsApp"], count={"value": 2},
                    window=W("On June 8, 2026", "2026-06-08T00:00",
                             "2026-06-09T00:00"))  # fmt: skip
    count = {**item.model_dump(), "template_id": "message_count"}
    made, f = fill(conn, text, ClaimType.COUNT, items=[count])
    assert set(made["message_count"].params.person_ids) == {PETROV, REYES}, f.drops


def test_a_person_beside_a_phone_in_the_lead_is_still_one_side(conn):
    text = "On June 8, 2026, on Item 1, Marcus Reyes had two WhatsApp calls with Jonathan."
    item = proposal(people=["Marcus Reyes"], quoted_text="", phones=["Item 1"],
                    channels=["call", "WhatsApp"], count={"value": 2},
                    window=W("On June 8, 2026", "2026-06-08T00:00",
                             "2026-06-09T00:00"))  # fmt: skip
    count = {**item.model_dump(), "template_id": "message_count"}
    made, _ = fill(conn, text, ClaimType.COUNT, items=[count])
    assert "message_count" not in made
