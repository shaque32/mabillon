"""Who placed a call: the caller assumption code reads from a claim's plain words, and the caller
check that reads it against the call log's direction. Synthetic case01 with made-up calls added;
every number, name and wording is invented."""

import json
import sqlite3
from datetime import datetime

import pytest

from core.audit.assumption_filler import CallForm, LocalAssumptionFiller, _Account
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


# ---------------------------------------------------------------- filler 10


@pytest.mark.parametrize(
    ("words", "by"),
    [
        ("Marcus Reyes called PETROV on WhatsApp.", REYES),
        ("Marcus Reyes called PETROV via WhatsApp.", REYES),
        ("PETROV called Marcus Reyes on the WhatsApp app.", PETROV),
    ],
)
def test_the_call_s_own_app_may_follow_the_clause(conn, words, by):
    text = f"On June 8, 2026, at about 9:00 p.m. EDT, {words}"
    made, _ = fill(conn, text, channels=["call", "WhatsApp"],
                   window=W("June 8", "2026-06-08T20:52", "2026-06-08T21:09"))  # fmt: skip
    assert list(made["caller"].params.sent_by) == [by]
    assert list(made["caller"].params.channels) == ["WhatsApp", "call"]


@pytest.mark.parametrize(
    "words",
    [
        "Marcus Reyes called PETROV on WhatsApp after dinner.",
        "Marcus Reyes called PETROV on Telegram.",
    ],
)
def test_other_words_after_the_app_or_another_app_name_no_caller(conn, words):
    text = f"On June 8, 2026, at about 9:00 p.m. EDT, {words}"
    made, _ = fill(conn, text, channels=["call", "WhatsApp"],
                   window=W("June 8", "2026-06-08T20:52", "2026-06-08T21:09"))  # fmt: skip
    assert "caller" not in made


@pytest.mark.parametrize(
    "words",
    [
        "Item 1 called (212) 555-0199, and about six minutes later (212) 555-0199 called back.",
        "Item 1 called (212) 555-0199 and texted it an hour earlier.",
        "Item 1 called (212) 555-0199 within a minute of receiving its text.",
        "Item 1 called (212) 555-0199 and afterward deleted the call.",
    ],
)
def test_a_claim_that_times_one_act_from_another_gives_no_act_its_stated_time(conn, words):
    # The one time the claim states may be another act's, or an edge code does not widen,
    # so no range is read from it: the claim goes untested rather than tested in a borrowed
    # window.
    made, f = fill(conn, f"{AT} {words}")
    assert "record_time" not in made and "caller" not in made
    assert any("times one act from another" in d.reason for d in f.drops)


WA_AT = "On June 8, 2026, at about 9:00 p.m. EDT,"
WA_W = W("June 8, 2026", "2026-06-08T20:52", "2026-06-08T21:09")
GARAGE = f'{WA_AT} PETROV called "Marc Garage" on WhatsApp.'


def test_a_caller_row_keeps_the_clause_s_own_handle(conn):
    # The time range names the other side by the handle the clause writes: the caller row
    # keeps that handle, and the checks resolve it.
    made, _ = fill(conn, GARAGE, people=["PETROV"], handles=["Marc Garage"],
                   channels=["call", "WhatsApp"], window=WA_W)  # fmt: skip
    a = made["caller"]
    assert list(a.params.sent_by) == [PETROV] and list(a.params.handles) == ["Marc Garage"]
    assert not a.params.account_ids


def test_a_handle_that_is_not_the_clause_s_side_names_no_caller(conn):
    # A time range whose handle is not the one the clause writes tests another party: the
    # caller row would inherit it, so code names no caller (Greptile on #261).
    made, f = fill(conn, GARAGE, people=["PETROV"], handles=["Marc Garage"],
                   channels=["call", "WhatsApp"], window=WA_W)  # fmt: skip
    rt = dict(made["record_time"].params.model_dump(exclude_none=True))
    assert f._caller_params(claim(GARAGE), rt) is not None
    for other in (["Jenna"], ["Marc Garage", "Jenna"], ["Marc"]):
        assert f._caller_params(claim(GARAGE), {**rt, "handles": other}) is None


def test_a_message_said_to_refer_to_another_act_gets_no_range(conn):
    # The time the claim states may be the picture's, not the message's (Greptile on #261):
    # neither code nor the model's range dates the message by it.
    text = (f'{WA_AT} PETROV sent REYES a WhatsApp message reading "look at that," which'
            " was referring to the picture REYES sent at about 8:10 p.m.")  # fmt: skip
    made, f = fill(conn, text, people=["PETROV"], quoted_text="look at that",
                   channels=["WhatsApp"], window=WA_W)  # fmt: skip
    assert "record_time" not in made
    assert any("refers to" in d.reason for d in f.drops)


def test_what_a_message_refers_to_is_another_act():
    from core.audit.assumption_filler import _OTHER_ACT_RE

    # "the message ... was referring to the picture REYES sent at about 8:10 p.m.": the
    # time is the picture's, so code does not date the message by it.
    for words in ("was referring to the picture", "refers to", "referred to the file"):
        assert _OTHER_ACT_RE.search(words)


@pytest.mark.parametrize(
    ("words", "timed"),
    [
        ("which was referring to the picture REYES sent at about 8:10 p.m.", True),
        ("referring to the meeting on March 3, 2026", True),
        ("which referred to the call the night before", True),
        ("referring to the search", False),
        ('referring to "the 9 p.m. drop"', False),  # quoted words are the message's, not a time
    ],
)
def test_only_a_timed_refer_clause_lends_its_time(words, timed):
    from core.audit.assumption_filler import _times_what_it_refers_to

    assert _times_what_it_refers_to(f'PETROV texted REYES: "ok", {words}.') is timed


# ---------------------------------------------------------------- filler 11

GARAGE_IG = "acct:item1:Instagram:49800011122"
JENNA_IG = "acct:item1:Instagram:49800099999"
IG_AT = "On June 15, 2026, at about 9:00 p.m. EDT,"
IG_W = W("June 15, 2026", "2026-06-15T20:52", "2026-06-15T21:09")


def _add_instagram(c: sqlite3.Connection) -> None:
    # June 15, 9:00 p.m. EDT: the phone called the Instagram user "Marc Garage" (60 s).
    c.execute("PRAGMA foreign_keys = OFF")
    for acc, ident, name in [(GARAGE_IG, "49800011122", "Marc Garage"),
                             (JENNA_IG, "49800099999", "Jenna Wolfe")]:  # fmt: skip
        c.execute(
            "INSERT OR IGNORE INTO accounts VALUES (?, 'item1', ?, NULL, 'Instagram', ?, ?)",
            (acc, acc, ident, name),
        )
    c.execute(
        "INSERT OR IGNORE INTO calls VALUES ('c:ig', 'item1', 'c:ig', 'dev:item1', 'Instagram',"
        " NULL, ?, 'outgoing', '2026-06-16T01:00:00Z', 0, NULL, 60, 0)",
        (GARAGE_IG,),
    )


def ig_fill(
    conn: sqlite3.Connection, words: str, written: str = "49800011122"
) -> tuple[dict, LocalAssumptionFiller]:
    _add_instagram(conn)
    return fill(conn, f"{IG_AT} {words}", people=["PETROV"],
                accounts=[{"as_written": written, "app": "Instagram"}],
                channels=["call", "Instagram"], window=IG_W)  # fmt: skip


@pytest.mark.parametrize(
    "words",
    [
        'PETROV called the Instagram user "Marc Garage," user ID 49800011122.',
        'PETROV called the Instagram user "Marc Garage" (user ID 49800011122).',
        'PETROV called "Marc Garage," user ID 49800011122, on Instagram.',
    ],
)
def test_a_side_named_by_its_app_and_its_id_beside_its_name_gets_a_caller(
    conn: sqlite3.Connection, words: str
) -> None:
    made, f = ig_fill(conn, words)
    assert "record_time" in made, [d.reason for d in f.drops]
    a = made["caller"]
    assert list(a.params.sent_by) == [PETROV], [d.reason for d in f.drops]
    assert list(a.params.account_ids) == [GARAGE_IG]
    (r,) = run_checks(a, conn)
    assert r.outcome is CheckOutcome.PASS


def test_a_side_described_or_given_an_id_before_the_verb_names_no_caller(
    conn: sqlite3.Connection,
) -> None:
    made, _ = ig_fill(conn, 'the Instagram user "Marc Garage," user ID 49800011122, called PETROV.')
    # a side described by its app is read only after the verb, so no caller is read here
    assert "caller" not in made
    made, _ = ig_fill(conn, '"Marc Garage," user ID 49800011122, called PETROV on Instagram.')
    assert "caller" not in made  # an id beside the first side is not read either


NAMED = [{"as_written": "Marc Garage", "app": "Instagram"}]


@pytest.mark.parametrize(
    ("words", "people", "accounts", "form"),
    [
        # the id is another account than the name: the clause is read as one side, and the
        # caller is refused when the name and the id are not one account
        ('PETROV called the Instagram user "Marc Garage," user ID 49800099999.', ["PETROV"],
         [{"as_written": "49800099999", "app": "Instagram"}], True),
        ('PETROV called the Instagram user "Marc Garage," user ID 49800099999.', ["PETROV"],
         [*NAMED, {"as_written": "49800099999", "app": "Instagram"}], True),
        # another app's name describes the side
        ('PETROV called the Telegram user "Marc Garage," user ID 49800011122, on Instagram.',
         ["PETROV"], [{"as_written": "49800011122", "app": "Instagram"}], False),
        # a person, not an account, described as an app's user
        ("PETROV called the Instagram user REYES.", ["PETROV", "REYES"], [], False),
        # other words describe the side
        ('PETROV called the old Instagram user "Marc Garage."', ["PETROV"], NAMED, False),
    ],
)  # fmt: skip
def test_a_description_or_id_that_is_not_the_one_account_names_no_caller(
    conn: sqlite3.Connection,
    words: str,
    people: list[str],
    accounts: list[dict[str, str]],
    form: bool,
) -> None:
    _add_instagram(conn)
    text = f"{IG_AT} {words}"
    f = LocalAssumptionFiller(FakeModel("{}"), conn,
                              template="{claim} {paragraph} {templates} {channels}")  # fmt: skip
    read = f.call_form(claim(text), "Instagram")
    # the parser's own refusals leave the clause unread; the id case is read as one side
    if form:
        assert read is not None and read.one_account, read
    else:
        assert read is None, read
    made, f = fill(conn, text, people=people, accounts=accounts,
                   channels=["call", "Instagram"], window=IG_W)  # fmt: skip
    # the proposal itself is kept (its time is checked), so only the caller guard is tested
    assert "record_time" in made, [d.reason for d in f.drops]
    assert "caller" not in made


@pytest.mark.parametrize(
    "words",
    [
        'PETROV called "Marc Garage," user ID 49800011122) on Instagram.',
        'PETROV called "Marc Garage" (user ID 49800011122 on Instagram.',
        'PETROV called the Instagram user "Marc Garage" (user ID 49800011122.',
    ],
)
def test_an_id_in_unbalanced_brackets_names_no_caller(conn: sqlite3.Connection, words: str) -> None:
    made, f = ig_fill(conn, words)
    assert "record_time" in made, [d.reason for d in f.drops]
    assert "caller" not in made


SHORT_IG = "acct:item1:Instagram:lena"
LENA = [{"as_written": "Lena Okafor", "app": "Instagram"}]


def short_fill(conn: sqlite3.Connection, words: str) -> tuple[dict, LocalAssumptionFiller]:
    # "Lena Okafor" holds the short username lena; the phone called her at 9:00 p.m. as well.
    c = conn
    c.execute("PRAGMA foreign_keys = OFF")
    c.execute(
        "INSERT OR IGNORE INTO accounts VALUES (?, 'item1', ?, NULL, 'Instagram', 'lena',"
        " 'Lena Okafor')",
        (SHORT_IG, SHORT_IG),
    )
    c.execute(
        "INSERT OR IGNORE INTO calls VALUES ('c:ig:lena', 'item1', 'c:ig:lena', 'dev:item1',"
        " 'Instagram', NULL, ?, 'outgoing', '2026-06-16T01:00:00Z', 0, NULL, 60, 0)",
        (SHORT_IG,),
    )
    return fill(conn, f"{IG_AT} {words}", people=["PETROV"], accounts=LENA,
                channels=["call", "Instagram"], window=IG_W)  # fmt: skip


@pytest.mark.parametrize(
    "words",
    [
        'PETROV called the Instagram user "Lena Okafor" username lena.',
        'PETROV called the Instagram user "Lena Okafor" (username: lena).',
    ],
)
def test_a_short_username_is_read_after_its_label(conn: sqlite3.Connection, words: str) -> None:
    made, f = short_fill(conn, words)
    assert "record_time" in made, [d.reason for d in f.drops]
    a = made["caller"]
    assert list(a.params.sent_by) == [PETROV], [d.reason for d in f.drops]
    assert list(a.params.account_ids) == [SHORT_IG]
    (r,) = run_checks(a, conn)
    assert r.outcome is CheckOutcome.PASS


@pytest.mark.parametrize(
    "words",
    [
        'PETROV called the Instagram user "Lena Okafor" lena.',  # no label: a plain word
        'PETROV called the Instagram user "Lena Okafor" username Lena.',  # not the identifier
    ],
)
def test_a_short_username_without_its_label_names_no_caller(
    conn: sqlite3.Connection, words: str
) -> None:
    made, f = short_fill(conn, words)
    assert "record_time" in made, [d.reason for d in f.drops]
    assert "caller" not in made
    _, tokens = f._party_tokens(f"{IG_AT} {words}", "Instagram")
    assert ("acct", "lena") not in tokens.values()  # an unlabelled short word is no party


def test_a_short_username_of_another_account_names_no_caller(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        "INSERT OR IGNORE INTO accounts VALUES ('acct:item1:Instagram:zoe1', 'item1',"
        " 'acct:item1:Instagram:zoe1', NULL, 'Instagram', 'zoe1', 'Zoe Brandt')"
    )
    # the name is Lena's account and the id is Zoe's: two accounts, so no caller is read
    words = 'PETROV called the Instagram user "Lena Okafor" username zoe1.'
    made, f = short_fill(conn, words)
    assert "record_time" in made, [d.reason for d in f.drops]
    assert "caller" not in made


def test_an_identifier_that_begins_with_id_is_read_as_written(conn: sqlite3.Connection) -> None:
    acc = "acct:item1:Instagram:id42"
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        "INSERT OR IGNORE INTO accounts VALUES (?, 'item1', ?, NULL, 'Instagram', 'id42',"
        " 'Ivy Dunmore')",
        (acc, acc),
    )
    conn.execute(  # an account "42": "id42" must never be read as it
        "INSERT OR IGNORE INTO accounts VALUES ('acct:item1:Instagram:42', 'item1',"
        " 'acct:item1:Instagram:42', NULL, 'Instagram', '42', 'Forty Two')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO calls VALUES ('c:ig:ivy', 'item1', 'c:ig:ivy', 'dev:item1',"
        " 'Instagram', NULL, ?, 'outgoing', '2026-06-16T01:00:00Z', 0, NULL, 60, 0)",
        (acc,),
    )
    made, f = fill(conn, f'{IG_AT} PETROV called the Instagram user "Ivy Dunmore" username id42.',
                   people=["PETROV"], accounts=[{"as_written": "Ivy Dunmore", "app": "Instagram"}],
                   channels=["call", "Instagram"], window=IG_W)  # fmt: skip
    a = made["caller"]
    assert list(a.params.account_ids) == [acc], [d.reason for d in f.drops]
    (r,) = run_checks(a, conn)
    assert r.outcome is CheckOutcome.PASS


def _parse(conn: sqlite3.Connection, words: str, app: str = "Instagram") -> CallForm | None:
    f = LocalAssumptionFiller(FakeModel("{}"), conn,
                              template="{claim} {paragraph} {templates} {channels}")  # fmt: skip
    return f.call_form(claim(f"{IG_AT} {words}"), app)


def test_a_stated_length_after_the_id_is_read(conn: sqlite3.Connection) -> None:
    _add_instagram(conn)
    read = _parse(
        conn,
        'PETROV called the Instagram user "Marc Garage," user ID 49800011122, '
        "that lasted about one minute.",
    )
    assert read is not None and read.one_account and read.length == "about one minute", read


def test_the_app_tail_takes_the_app_s_alias(conn: sqlite3.Connection) -> None:
    read = _parse(conn, 'PETROV called the Teams user "Ann Vole" on Teams.', "Microsoft Teams")
    assert read is not None and read.caller == "a", read


def test_an_id_touching_its_label_s_colon_gets_a_caller(conn: sqlite3.Connection) -> None:
    made, f = ig_fill(conn, 'PETROV called the Instagram user "Marc Garage," user ID:49800011122.')
    assert list(made["caller"].params.account_ids) == [GARAGE_IG], [d.reason for d in f.drops]


def test_a_written_id_keeps_no_label_the_id_tail_reads(conn: sqlite3.Connection) -> None:
    short_fill(conn, 'PETROV called the Instagram user "Lena Okafor" username lena.')
    _add_instagram(conn)  # before the filler reads its accounts
    f = LocalAssumptionFiller(FakeModel("{}"), conn,
                              template="{claim} {paragraph} {templates} {channels}")  # fmt: skip
    for written in ("username lena", "user name: lena"):
        acc = _Account(as_written=written, app="Instagram")
        assert f._accounts(acc, ["dev:item1"]) == {SHORT_IG}, written
    for written in ("user ID number 49800011122", "ID number: 49800011122"):
        # every label the id tail reads (`_ID_LABEL`), "number" after it included
        acc = _Account(as_written=written, app="Instagram")
        assert f._accounts(acc, ["dev:item1"]) == {GARAGE_IG}, written


@pytest.mark.parametrize(
    "ident",
    [
        "username:lena.2",
        "username lena.2",
        "username lena:x",
        "username lena..2",
        "username lena.-x",
    ],
)
def test_an_id_that_only_begins_with_a_known_id_names_no_caller(
    conn: sqlite3.Connection, ident: str
) -> None:
    made, f = short_fill(conn, f'PETROV called the Instagram user "Lena Okafor" {ident}.')
    assert "record_time" in made, [d.reason for d in f.drops]
    assert "caller" not in made  # lena.2 is not lena


# One WhatsApp number held under two keys, its display name on one of them (ruling R6: one party).
DUNN_WA = ["acct:item1:WhatsApp:+19195550142", "acct:item1:WhatsApp:19195550142@s.whatsapp.net"]


def test_a_name_and_its_number_held_under_two_keys_get_a_caller(conn: sqlite3.Connection) -> None:
    c = conn
    c.execute("PRAGMA foreign_keys = OFF")
    for acc, name in [(DUNN_WA[0], "Owen Dunn"), (DUNN_WA[1], None)]:
        c.execute(
            "INSERT OR IGNORE INTO accounts VALUES (?, 'item1', ?, NULL, 'WhatsApp', ?, ?)",
            (acc, acc, acc.split(":", 3)[3], name),
        )
    c.execute(
        "INSERT OR IGNORE INTO calls VALUES ('c:wa:dunn', 'item1', 'c:wa:dunn', 'dev:item1',"
        " 'WhatsApp', NULL, ?, 'outgoing', '2026-06-21T01:00:00Z', 0, NULL, 60, 0)",
        (DUNN_WA[1],),
    )
    made, f = fill(
        conn,
        'On June 20, 2026, at about 9:00 p.m. EDT, PETROV called the WhatsApp user "Owen Dunn,"'
        " ID +1 919 555 0142.",
        people=["PETROV"],
        accounts=[{"as_written": "+1 919 555 0142", "app": "WhatsApp"}],
        channels=["call", "WhatsApp"],
        window=W("June 20, 2026", "2026-06-20T20:52", "2026-06-20T21:09"),
    )
    assert "record_time" in made, [d.reason for d in f.drops]
    a = made["caller"]
    assert sorted(a.params.account_ids) == sorted(DUNN_WA), [d.reason for d in f.drops]
    (r,) = run_checks(a, conn)
    assert r.outcome is CheckOutcome.PASS


# ---------------------------------------------------------------- coverage recount (2026-11-21)

LENGTH = "about one minute and 40 seconds"


@pytest.mark.parametrize("joined", ["that was answered and lasted", "that connected and lasted"])
def test_answered_or_connected_before_a_tested_length_still_names_the_caller(conn, joined):
    # validation dev iOS 15 C06: "... placed a Signal call to the TARGET PHONE that was
    # answered and lasted about one and a half minutes" got no caller row, so rule 3e kept it
    # unproven. A tested length is never below one second, so the call it finds connected.
    text = f"{AT} Item 1 placed a call to (212) 555-0199 {joined} {LENGTH}."
    made, f = fill(conn, text, duration={"as_written": LENGTH})
    assert list(made["caller"].params.sent_by) == [PETROV], f.drops
    assert made["caller"].params.duration_s == made["record_time"].params.duration_s
    assert "event" not in made, made["event"].text  # "answered"/"connected" are read
    v = verdict(conn, text, 1, duration={"as_written": LENGTH})
    assert v.verdict is Verdict.SUPPORTED, v.reasons
    # the same words with the other side calling: the log says the phone placed it
    reversed_ = text.replace(
        "Item 1 placed a call to (212) 555-0199", "(212) 555-0199 placed a call to Item 1"
    )
    assert (
        verdict(conn, reversed_, 1, duration={"as_written": LENGTH}).verdict is Verdict.CONTRADICTED
    )


def test_connected_with_no_tested_length_is_left_for_the_expert(conn):
    # "connected" is read only beside a length a row tests; alone, no check reads it.
    made, _ = fill(conn, f"{AT} Item 1 placed a call to (212) 555-0199 that connected.")
    assert "caller" not in made
    made, _ = fill(conn, f"{AT} Item 1 placed a connected call to (212) 555-0199.")
    assert "caller" not in made


def test_a_connected_call_of_another_length_is_not_supported(conn):
    text = (
        f"{AT} Item 1 placed a call to (212) 555-0199 that connected and lasted about ten minutes."
    )
    v = verdict(conn, text, 1, duration={"as_written": "about ten minutes"})
    assert v.verdict is not Verdict.SUPPORTED, v.reasons


OWNER_ONLY = {"template_id": "person_identity", "people": ["PETROV"]}


def test_an_owner_identity_naming_no_account_is_refused(conn):
    # validation v4 D077: the model added "The account belongs to SUBJECT-1" (no account, no
    # handle) beside a passing time and caller row. Nothing can test it, and it kept a true
    # claim unproven. PETROV owns Item 1 by confirmed stipulation, which already says the
    # phone's own accounts are his.
    text = "On June 8, 2026, at about 9:00 p.m. EDT, Marcus Reyes placed a WhatsApp call to PETROV."
    rt = {
        **proposal(
            people=[],
            quoted_text="",
            channels=["call", "WhatsApp"],
            window=W("June 8", "2026-06-08T20:52", "2026-06-08T21:09"),
        ).model_dump()
    }
    made, f = fill(conn, text, items=[rt, OWNER_ONLY])
    assert "person_identity" not in made
    assert any("person_identity names no account or handle" in d.reason for d in f.drops)
    assert list(made["caller"].params.sent_by) == [REYES]
    assumptions = list(made.values())
    checks = [r for a in assumptions for r in run_checks(a, conn)]
    v = decide_verdict(claim(text), assumptions, [], checks, load_stipulations(conn), "run")
    assert v.verdict is Verdict.SUPPORTED, v.reasons
    # before: the owner row stood beside them, untestable, and the claim stayed unproven
    kept = [*assumptions, instantiate("X", "person_identity", {"person_ids": [PETROV]})]
    v = decide_verdict(claim(text), kept, [], checks, load_stipulations(conn), "run")
    assert v.verdict is Verdict.UNPROVEN


def test_an_identity_naming_an_account_or_a_person_who_owns_no_phone_is_kept(conn):
    _, f = fill(conn, f"{AT} Item 1 called (212) 555-0199.")
    f._owner_identity_names_nothing(["person:volkov"])  # owns no phone: who he is stays open
    f._owner_identity_names_nothing([])
    f._owner_identity_names_nothing([PETROV, "person:volkov"])
    with pytest.raises(Exception, match="names no account or handle"):
        f._owner_identity_names_nothing([PETROV, REYES])
    # a row naming an account is never refused this way
    rt = {**proposal(people=[], quoted_text="", channels=["call"],
                     window=W("June 1, 2026", "2026-06-01T20:52", "2026-06-01T21:09"))
          .model_dump()}  # fmt: skip
    with_account = {"template_id": "person_identity", "people": ["PETROV"],
                    "accounts": [{"as_written": "(212) 555-0199", "app": "unknown"}]}  # fmt: skip
    _, f = fill(conn, f"{AT} Item 1 called (212) 555-0199.", items=[rt, with_account])
    assert not any("names no account or handle" in d.reason for d in f.drops)
