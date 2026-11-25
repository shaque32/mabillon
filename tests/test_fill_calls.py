"""Who placed a call: the caller assumption code reads from a claim's plain words, and the caller
check that reads it against the call log's direction. Synthetic case01 with made-up calls added;
every number, name and wording is invented."""

import copy
import json
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from core.audit.assumption_filler import (
    CallForm,
    LocalAssumptionFiller,
    Reject,
    _Account,
)
from core.audit.assumptions import (
    CODE_MADE_NOTE,
    TEMPLATES,
    UNREAD_EVENT_NOTE,
    Proposal,
    TemplateAssumptionBuilder,
    instantiate,
    is_unread_event,
)
from core.audit.checks import CHECKS, run_checks
from core.audit.checks._common import calls_for_accounts
from core.audit.rules import decide_verdict
from core.contracts import CheckOutcome, CheckResult, ClaimType, Verdict
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


@pytest.mark.parametrize(
    ("words", "by"),
    [
        ("Item 1 received a second telephone call from (212) 555-0199.", "num"),
        ("Item 1 placed a third call to (212) 555-0199.", PETROV),
        ("(212) 555-0199 placed a second call to Item 1.", "num"),
        ("Item 1 received a first incoming call from (212) 555-0199.", "num"),
    ],
)
def test_an_ordinal_names_the_caller_and_keeps_the_expert_only_event(conn, words, by):
    # Who placed this call is read; the earlier call the ordinal states is not, so a core
    # event only an expert carries stays beside the checks (v5 pre-run replay, iOS 15 C07).
    made, _ = fill(conn, f"{AT} {words}")
    assert list(made["caller"].params.sent_by) == ([PETROV] if by == PETROV else sorted(NUM))
    assert made["event"].is_core and is_unread_event("event", made["event"].text)


def test_an_ordinal_on_the_call_s_app_keeps_the_event(conn):
    text = (
        "On June 8, 2026, at about 9:00 p.m. EDT, Marcus Reyes placed a second WhatsApp call"
        " to PETROV."
    )
    made, _ = fill(conn, text, channels=["call", "WhatsApp"],
                   window=W("June 8", "2026-06-08T20:52", "2026-06-08T21:09"))  # fmt: skip
    assert list(made["caller"].params.sent_by) == [REYES]
    assert made["event"].is_core


@pytest.mark.parametrize(
    "noun",
    [
        "a second WhatsApp call",
        "a second outgoing WhatsApp telephone call",
        "a second-WhatsApp call",
    ],
)
@pytest.mark.parametrize("length", [True, False])
def test_an_ordinal_beside_a_tested_length_keeps_the_event(conn, noun, length):
    # "a second" before a call is an ordinal, not a length the row tests, however many of the
    # call's words stand between (CodeRabbit on #279)
    tail = " that lasted two minutes." if length else "."
    text = f"On June 8, 2026, at about 9:00 p.m. EDT, Marcus Reyes placed {noun} to PETROV{tail}"
    tested = {"duration": {"as_written": "two minutes"}} if length else {}
    made, _ = fill(conn, text, channels=["call", "WhatsApp"], **tested,
                   window=W("June 8", "2026-06-08T20:52", "2026-06-08T21:09"))  # fmt: skip
    assert list(made["caller"].params.sent_by) == [REYES]
    assert bool(made["caller"].params.duration_s) == length and made["event"].is_core


@pytest.mark.parametrize("unread", [True, False])
def test_a_caller_read_through_an_ordinal_always_keeps_its_event(conn, monkeypatch, unread):
    # the caller row itself carries the ordinal's event, whatever the unread-words guard
    # makes of the wording: an app named "Talk and Text" stops its run (CodeRabbit on #279)
    if not unread:
        monkeypatch.setattr(LocalAssumptionFiller, "unread_words", lambda *a, **k: [])
    text = f"{AT} Item 1 placed a second call to (212) 555-0199."
    made, _ = fill(conn, text)
    assert list(made["caller"].params.sent_by) == [PETROV]
    assert made["event"].is_core and made["event"].text.endswith(UNREAD_EVENT_NOTE + CODE_MADE_NOTE)
    # with no event allowed, the ordinal gets no caller row
    answer = proposal(people=[], quoted_text="", channels=["call"],
                      window=W("June 1, 2026", "2026-06-01T20:52", "2026-06-01T21:09"))  # fmt: skip
    f = LocalAssumptionFiller(FakeModel(json.dumps({"assumptions": [answer.model_dump()]})), conn,
                              template="{claim} {paragraph} {templates} {channels}")  # fmt: skip
    every = list(TEMPLATES.values())
    no_event = [t for t in every if t.id != "event"]
    for words in (
        "Item 1 placed a second call to (212) 555-0199.",
        # a missed call written with an ordinal too (CodeRabbit on #279)
        "Item 1 missed a second incoming call from (212) 555-0199.",
    ):
        text = f"{AT} {words}"
        # the same claim reads a caller when the event is allowed, none when it is not
        assert "caller" in {p.template_id for p in f(claim(text, ClaimType.COMMUNICATION), every)}
        out = f(claim(text, ClaimType.COMMUNICATION), no_event)
        assert "caller" not in {p.template_id for p in out}


@pytest.mark.parametrize(
    "noun",
    [
        "a second, telephone call",
        "a second\u2014call",
        "a second (telephone) call",
    ],
)
@pytest.mark.parametrize("kind", [ClaimType.COMMUNICATION, ClaimType.TIMING])
def test_a_second_is_a_length_only_where_a_length_leads_into_it(conn, noun, kind):
    # "a second" is cut as a tested length only after "lasted", "for" and the like; anywhere
    # else it is an ordinal and keeps the event, whatever stands between it and "call" (Claude
    # review on #279: these were SUPPORTED on the time row alone)
    text = f"{AT} Item 1 placed {noun} to (212) 555-0199 that lasted about two minutes."
    made, _ = fill(conn, text, kind, duration={"as_written": "about two minutes"})
    assert made["record_time"].params.duration_s and made["event"].is_core


def test_a_missed_call_with_an_ordinal_tells_the_expert_of_the_unread_part(conn):
    # the missed event also carries the earlier call the ordinal states (Claude review on #279)
    # beside its own missed event, which the testability sheet check still counts
    def events(text):
        window = W("June 1, 2026", "2026-06-01T20:52", "2026-06-01T21:09")
        answer = proposal(people=[], quoted_text="", channels=["call"], window=window)
        model = FakeModel(json.dumps({"assumptions": [answer.model_dump()]}))
        f = LocalAssumptionFiller(
            model, conn, template="{claim} {paragraph} {templates} {channels}"
        )
        made = TemplateAssumptionBuilder(f).build(claim(f"{AT} {text}", ClaimType.COMMUNICATION))
        assert any(a.template_id == "caller" for a in made)
        return [is_unread_event(a.template_id, a.text) for a in made if a.template_id == "event"]

    assert sorted(events("Item 1 missed a second incoming call from (212) 555-0199.")) == [
        False,
        True,
    ]
    assert events("Item 1 missed an incoming call from (212) 555-0199.") == [False]


@pytest.mark.parametrize("length", ["90 second", "ninety second"])
def test_a_second_after_digits_is_a_length(conn, length):
    # "a 90 second WhatsApp call": a length the row tests, never an ordinal, as "a ninety
    # second WhatsApp call" reads (Claude review on #279)
    text = (
        f"On June 8, 2026, at about 9:00 p.m. EDT, Marcus Reyes placed a {length} WhatsApp call"
        " to PETROV."
    )
    made, f = fill(conn, text, ClaimType.TIMING, channels=["call", "WhatsApp"],
                   duration={"as_written": length},
                   window=W("June 8", "2026-06-08T20:52", "2026-06-08T21:09"))  # fmt: skip
    assert made["record_time"].params.duration_s, [d.reason for d in f.drops]
    assert "event" not in made


@pytest.mark.parametrize(
    "text",
    [
        "Item 1 called (212) 555-0199 for a second time, and the call lasted about two minutes.",
        "Item 1 placed a call that lasted about two minutes to (212) 555-0199 over a second line.",
        "Item 1 placed a call to (212) 555-0199 that lasted about two minutes, and a second call.",
        "Item 1 placed a call to (212) 555-0199 for about two minutes and a second time.",
        # a second call by ellipsis: "and a second" is no part of the tested "about two minutes"
        "Item 1 placed a call to (212) 555-0199 that lasted about two minutes, and a second to"
        " (212) 555-0199.",
        "Item 1 placed a call to (212) 555-0199 for about two minutes, and a second from"
        " (212) 555-0199.",
        "Item 1 placed a call to (212) 555-0199 that lasted about two minutes and a second.",
    ],
)
@pytest.mark.parametrize("kind", [ClaimType.COMMUNICATION, ClaimType.TIMING])
def test_a_second_followed_by_more_words_stays_an_ordinal(conn, text, kind):
    # a length lead before "a second" is not enough: its clause must end there, so "for a
    # second time" and "minutes, and a second call" state an earlier or another call no check
    # reads (Claude review on #279: these were SUPPORTED on the time row alone)
    made, _ = fill(conn, f"{AT} {text}", kind, duration={"as_written": "about two minutes"})
    assert made["record_time"].params.duration_s and made["event"].is_core


@pytest.mark.parametrize(
    "after",
    [
        " on Item 1",
        " in the evening",
        " to (212) 555-0199",
        "",  # ", and a second." may be a second call too (Claude review on #279)
        # punctuation before more words still leaves a second call (Claude review on #279)
        ", on Item 1",
        ", from (212) 555-0199",
        "; on Item 1",
        " \u2014 on Item 1",
    ],
)
@pytest.mark.parametrize("kind", [ClaimType.COMMUNICATION, ClaimType.TIMING])
def test_and_a_second_before_more_words_is_no_part_of_the_length(conn, after, kind):
    # ", and a second on Item 1" may be a second call by ellipsis, even where the model reads
    # "one minute, and a second" as the length (Claude review on #279)
    text = f"Item 1 placed a call to (212) 555-0199 that lasted one minute, and a second{after}."
    made, _ = fill(conn, f"{AT} {text}", kind, duration={"as_written": "one minute, and a second"})
    assert made["event"].is_core


@pytest.mark.parametrize(
    "text",
    [
        "Item 1 placed a 30 second call to (212) 555-0199 that lasted about two minutes.",
        "Item 1 placed a thirty second call to (212) 555-0199 that lasted about two minutes.",
        "Item 1 placed a 30-second call to (212) 555-0199 that lasted about two minutes.",
        "Item 1 placed a 30s call to (212) 555-0199 that lasted about two minutes.",
    ],
)
@pytest.mark.parametrize("kind", [ClaimType.COMMUNICATION, ClaimType.TIMING])
def test_a_length_no_row_tests_keeps_the_event(conn, text, kind):
    # the row tests "about two minutes"; "30 second" is a length no check reads, so the claim
    # never rests on the time row alone (Claude review on #279)
    made, _ = fill(conn, f"{AT} {text}", kind, duration={"as_written": "about two minutes"})
    assert made["record_time"].params.duration_s and made["event"].is_core


@pytest.mark.parametrize(
    ("text", "tested", "read", "unread"),
    [
        ("lasted one minute and a second.", (61, 61), ["one minute and a second"], []),
        # after a comma, "and a second" may be a second call (Claude review on #279)
        ("lasted one minute, and a second.", (61, 61), [], ["one minute", "and a second"]),
        # ", and a second on Item 1" may be a second call by ellipsis (Claude review on #279)
        ("lasted one minute, and a second on Item 1", (61, 61), [], ["one minute", "and a second"]),
        ("lasted a second.", (1, 1), ["a second"], []),
        ("for 1 minute and a second.", (61, 61), ["1 minute and a second"], []),
        ("for 1 minute, and a second.", (61, 61), [], ["1 minute", "and a second"]),
        ("lasted two minutes and 30 seconds.", (150, 150), ["two minutes and 30 seconds"], []),
        ("lasted a minute and a half.", (90, 119), ["a minute and a half"], []),
        ("placed a ninety second call", (90, 90), ["ninety second"], []),
        ("placed a 90 second call", (90, 90), ["90 second"], []),
        ("lasted thirty seconds", (30, 30), ["thirty seconds"], []),
        # a length is read only where it is the length a row tests (Claude review on #279):
        # "and a second" after the tested "one minute" is a second call
        ("lasted one minute, and a second.", (60, 119), ["one minute"], ["and a second"]),
        ("lasted one minute, and a second to Item 2.", (61, 61), [], ["one minute"]),
        ("for 1 minute, and a second to Item 2.", (61, 61), [], ["1 minute"]),
        ("for 1 minute and a second call.", (61, 61), [], ["1 minute"]),
        ("lasted a second.", (60, 60), [], ["a second"]),
        (
            "a 30 second call that lasted about two minutes",
            (90, 150),
            ["two minutes"],
            ["30 second"],
        ),
        (
            "a thirty second call that lasted two minutes",
            (120, 179),
            ["two minutes"],
            ["a thirty second"],
        ),  # fmt: skip
        # a comma after a unit never leads into a bare "a second" (CodeRabbit on #279)
        ("after one minute, a second call", (60, 119), ["one minute"], []),
        ("placed a second, telephone call", (1, 1), [], []),
        ("for a second time", (1, 1), [], []),
        ("over a second line", (1, 1), [], []),
        ("lasted two minutes, and a second call", (120, 179), ["two minutes"], []),
        ("the thirty-second call", (32, 32), [], []),
    ],
)
def test_a_stated_length_is_read_only_where_a_row_tests_it(text, tested, read, unread):
    from core.audit.assumption_filler import _tested_lengths_in

    spans, untested = _tested_lengths_in(text, {tested})
    assert sorted({text[a:b] for a, b in spans}) == sorted(read)
    # an ordinal-like "second" that may not be a length is no length at all: the unread-words
    # guard reads it as an ordinal
    assert [w for w in untested if not w.endswith("second") or w in unread] == unread


def test_the_ordinal_guards_stay_fast():
    # a run of hyphens or dashes after "second" is read in one way only: 13 "--" took 7 s
    # before, each more one about four times as long (Claude review on #279)
    # run apart under a hard timeout, so a regression fails instead of hanging the suite
    code = (
        "from core.audit.assumption_filler import _UNPLAIN_PHRASES_RE as r\n"
        "for t in ('PETROV sent a second ' + ' '.join(['--'] * 40) + ' x',"
        " 'a second' + '-' * 200):\n"
        "    r.findall(t)\n"
    )
    subprocess.run(  # noqa: S603 (the test's own code, run apart)
        [sys.executable, "-c", code],
        check=True,
        timeout=60,
        cwd=Path(__file__).resolve().parents[1],
    )


@pytest.mark.parametrize("length", ["one minute and a second", "1 minute and a second"])
def test_a_length_written_a_second_is_still_read_as_one(conn, length):
    text = (
        "On June 8, 2026, at about 9:00 p.m. EDT, Marcus Reyes placed a WhatsApp call to PETROV"
        f" that lasted {length}."
    )
    made, f = fill(conn, text, channels=["call", "WhatsApp"],
                   duration={"as_written": length},
                   window=W("June 8", "2026-06-08T20:52", "2026-06-08T21:09"))  # fmt: skip
    assert "caller" in made and "event" not in made, [d.reason for d in f.drops]


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
        # an ordinal anywhere but right after the article
        "Item 1 placed a telephone second call to (212) 555-0199.",
        "Item 1 placed second call to (212) 555-0199.",
        "Item 1 called a second time (212) 555-0199.",
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


@pytest.mark.parametrize(
    "words",
    [
        'PETROV called the party displayed as "Marc Garage" on WhatsApp.',
        'PETROV placed a WhatsApp call to the contact shown as "Marc Garage".',
        'PETROV placed an outgoing call to the account displayed as "Marc Garage" on WhatsApp.',
        # a saved contact, or a phone number, is a part no check reads (Claude review on #279)
        'PETROV called the contact displayed as "Marc Garage" on WhatsApp.',
        'PETROV called the number displayed as "Marc Garage" on WhatsApp.',
    ],
)
def test_a_side_named_by_what_the_log_shows_gets_a_caller(conn, words):
    # "the party displayed as "X"": the name the log shows for the other side, read as that
    # side (v5 pre-run replay, iOS 15 D14 and D27)
    made, f = fill(conn, f"{WA_AT} {words}", people=["PETROV"], handles=["Marc Garage"],
                   channels=["call", "WhatsApp"], window=WA_W)  # fmt: skip
    a = made["caller"]
    assert list(a.params.sent_by) == [PETROV], [d.reason for d in f.drops]
    assert list(a.params.handles) == ["Marc Garage"]
    # "displayed as" is plain naming (`_RECORDS_SAY_RE`): the claim reads as it does with the
    # name alone, 'called "Marc Garage"'; "shown" is a word no check reads (CodeRabbit on #279)
    bare, _ = fill(conn, GARAGE, people=["PETROV"], handles=["Marc Garage"],
                   channels=["call", "WhatsApp"], window=WA_W)  # fmt: skip
    unread = any(w in words for w in ("shown", "contact", "number"))
    assert ("event" in made) == unread
    assert "event" not in bare
    if unread:
        assert made["event"].is_core
        # no caller row without the event an expert carries
        answer = proposal(people=["PETROV"], handles=["Marc Garage"], quoted_text="",
                          channels=["call", "WhatsApp"], window=WA_W)  # fmt: skip
        model = FakeModel(json.dumps({"assumptions": [answer.model_dump()]}))
        f = LocalAssumptionFiller(
            model, conn, template="{claim} {paragraph} {templates} {channels}"
        )
        no_event = [t for t in TEMPLATES.values() if t.id != "event"]
        out = f(claim(f"{WA_AT} {words}", ClaimType.COMMUNICATION), no_event)
        assert "caller" not in {p.template_id for p in out}


@pytest.mark.parametrize(
    "words",
    [
        'PETROV had a WhatsApp call with the contact displayed as "Marc Garage".',
        'PETROV had a WhatsApp call with the number shown as "Marc Garage".',
        'PETROV received a WhatsApp call from the contact displayed as "Marc Garage".',
        # "caller" is a word no check reads, as "shown" is (Claude review on #279)
        'PETROV placed a WhatsApp call to the caller displayed as "Marc Garage".',
        # a saved contact written by name, with no "displayed as" (Claude review on #279)
        'PETROV called the contact "Marc Garage" on WhatsApp.',
        "PETROV called the contact named Marc Garage on WhatsApp.",
        'PETROV called his contact saved as "Marc Garage" on WhatsApp.',
        'PETROV called the contact entry "Marc Garage" on WhatsApp.',
        'PETROV called Contact "Marc Garage" on WhatsApp.',
        # with no quote, an article or possessive before "contact" is enough
        "PETROV called the contact Marc Garage on WhatsApp.",
        "PETROV called his contact Marc Garage on WhatsApp.",
        # punctuation between "contact" and the name, or the contact written after it
        'PETROV called his contact, "Marc Garage", on WhatsApp.',
        'PETROV called the contact: "Marc Garage" on WhatsApp.',
        'PETROV called "Marc Garage" (a contact) on WhatsApp.',
    ],
)
@pytest.mark.parametrize("kind", [ClaimType.COMMUNICATION, ClaimType.TIMING])
def test_a_contact_or_number_by_what_the_log_shows_keeps_the_event_on_every_path(conn, words, kind):
    # a saved contact, or a phone number, is a part no check reads, whether or not a caller row
    # is made (Claude review on #279: "had a call with the contact displayed as" kept none)
    made, _ = fill(conn, f"{WA_AT} {words}", kind, people=["PETROV"], handles=["Marc Garage"],
                   channels=["call", "WhatsApp"], window=WA_W)  # fmt: skip
    assert made["event"].is_core


@pytest.mark.parametrize(
    "words",
    [
        # a side named as a phone number, in more ways than 'the number "X"' (Claude review
        # on #279, left for this follow-up)
        'PETROV called the phone number "Marc Garage" on WhatsApp.',
        'PETROV called the WhatsApp number "Marc Garage".',
        'PETROV called the number: "Marc Garage" on WhatsApp.',
        'PETROV called the number, "Marc Garage", on WhatsApp.',
        'PETROV called the number for "Marc Garage" on WhatsApp.',
        'PETROV called "Marc Garage" (a number) on WhatsApp.',
        'PETROV called "Marc Garage", a number, on WhatsApp.',
        "PETROV called the number Marc Garage on WhatsApp.",
        # a saved contact, in more ways than 'the contact "X"'
        "PETROV called contact Marc Garage on WhatsApp.",
        'PETROV called the contact with the name "Marc Garage" on WhatsApp.',
        'PETROV placed a WhatsApp call to the party displayed as "Marc Garage", who is his'
        " contact.",
        'PETROV called "Marc Garage" on WhatsApp, his contact.',
        'PETROV called "Marc Garage" on WhatsApp, a contact of REYES.',
        'PETROV called "Marc Garage" \u2014 his contact \u2014 on WhatsApp.',
        'PETROV called "Marc Garage" (a contact of REYES) on WhatsApp.',
        'PETROV called "Marc Garage", his WhatsApp contact.',
        # right after a quoted name any words may follow, as in filler 14 (Claude review on
        # #282: these regressed)
        'PETROV called "Marc Garage", a contact of his, on WhatsApp.',
        'PETROV called "Marc Garage", his contact for years, on WhatsApp.',
        'PETROV called "Marc Garage", a contact that he saved, on WhatsApp.',
        'PETROV called "Marc Garage", his contact between 2024 and 2026, on WhatsApp.',
        # more separators, naming words and words before the noun (Claude review on #282)
        'PETROV called the number saved for "Marc Garage" on WhatsApp.',
        'PETROV called "Marc Garage", who\'s his contact, on WhatsApp.',
        'PETROV called "Marc Garage" -- his contact -- on WhatsApp.',
        'PETROV called "Marc Garage"; his contact, on WhatsApp.',
        'PETROV called "Marc Garage", his saved WhatsApp Business contact.',
        # an owner after a capitalised word (CodeRabbit on #282)
        'PETROV called "Marc Garage" on WhatsApp, a contact of his.',
        # a quoted name after "the number called" (CodeRabbit on #282)
        'PETROV had a WhatsApp call with the number called "Marc Garage".',
        # later in the sentence, in brackets after a quote, a bare "number", a plural (Claude
        # review on #282)
        'PETROV called "Marc Garage" on WhatsApp at that time, his contact.',
        'PETROV called "Marc Garage" (a contact with whom he spoke) on WhatsApp.',
        'PETROV called "Marc Garage" (a contact of item 1) on WhatsApp.',
        "PETROV called number Marc Garage on WhatsApp.",
        'PETROV called the numbers "Marc Garage" on WhatsApp.',
    ],
)
@pytest.mark.parametrize("kind", [ClaimType.COMMUNICATION, ClaimType.TIMING])
def test_more_ways_to_name_a_contact_or_number_keep_the_event(conn, words, kind):
    # each names the other side as a saved contact or a phone number, which no check reads,
    # so a timing claim can never rest on its time row alone (filler 15)
    made, _ = fill(conn, f"{WA_AT} {words}", kind, people=["PETROV"], handles=["Marc Garage"],
                   channels=["call", "WhatsApp"], window=WA_W)  # fmt: skip
    assert made["event"].is_core


@pytest.mark.parametrize(
    "text",
    [
        # a phone written as a number is the side a check reads, never an unread word
        "On June 1, the number (212) 555-0199 called Item 1.",
        "Item 1 called (212) 555-0199, the number (212) 555-0199 on the log.",
        "Item 1 called the phone number +1 212 555 0199.",
        # a number of calls, or "contact" as a communication, is no side
        "Item 1 placed a number of calls to (212) 555-0199.",
        "Item 1 placed a call to (212) 555-0199, a contact that lasted about two minutes.",
        "Item 1 placed a call to (212) 555-0199, a contact for two minutes.",
        "the contact between PETROV and REYES",
        "Item 1 called (212) 555-0199, the number of calls being one.",
        # "called" after "number" is the call's verb; "contact" as a verb; a count's "number"
        # (Claude review on #282)
        "An unknown number called PETROV on WhatsApp.",
        "On June 1, the number called Item 1 twice.",
        "REYES told PETROV to contact Marc Garage.",
        "On June 1, Item 1 called REYES. Contact PETROV later.",
        "PETROV sent REYES 12 messages, a number the log confirms.",
        "Item 1 called REYES 4 times, a number the call log shows.",
        # a count's "number" after a relative word, a capitalised word or in brackets, and
        # "number called" in capitals (Claude review on #282)
        "Item 1 called REYES 4 times, which was the number of calls.",
        "Item 1 called REYES 4 times, which is the number the log shows.",
        "Item 1 called REYES 4 times, which is the contact the log shows.",
        "Item 1 called REYES, which was the number of calls.",
        "Item 1 called REYES 4 times on WhatsApp, a number the log shows.",
        "Item 1 called REYES 4 times (a number the log shows).",
        "AN UNKNOWN NUMBER CALLED PETROV ON WHATSAPP.",
        "THE NUMBER CALLED ITEM 1 TWICE.",
        # "contact" as the communication after a person the checks read, after a quoted
        # message, "contact called" as the call's verb, and "between" in capitals (Claude
        # review on #282)
        "On June 8, PETROV called REYES, a contact on WhatsApp.",
        "PETROV called REYES on WhatsApp, the contact.",
        "PETROV called REYES, which was the contact.",
        "PETROV called REYES on WhatsApp, a WhatsApp contact.",
        'PETROV wrote "ok" to REYES, his contact.',
        "On June 1, a contact called Item 1.",
        "His contact called REYES on June 1.",
        "THE CONTACT BETWEEN PETROV AND REYES.",
    ],
)
def test_a_phone_number_or_a_contact_as_a_communication_stays_plain(conn, text):
    f = LocalAssumptionFiller(
        FakeModel("{}"), conn, template="{claim} {paragraph} {templates} {channels}"
    )
    out = f.unread_words(text, (), set())
    assert not any("contact" in w or "number" in w for w in out), (text, out)


@pytest.mark.parametrize(
    "words",
    [
        'PETROV placed a WhatsApp call to the party shown as "Marc Garage".',
        'PETROV placed a WhatsApp call to the caller displayed as "Marc Garage".',
        'PETROV placed a WhatsApp call to the contact displayed as "Marc Garage".',
    ],
)
def test_a_side_named_by_unread_words_keeps_its_event_without_the_guard(conn, monkeypatch, words):
    # the caller row itself carries the event for "shown", "caller" or "contact", whatever the
    # unread-words guard makes of the wording (Claude review on #279)
    monkeypatch.setattr(LocalAssumptionFiller, "unread_words", lambda *a, **k: [])
    made, _ = fill(conn, f"{WA_AT} {words}", people=["PETROV"], handles=["Marc Garage"],
                   channels=["call", "WhatsApp"], window=WA_W)  # fmt: skip
    assert made["caller"] and made["event"].is_core
    plain, _ = fill(conn, f'{WA_AT} PETROV placed a WhatsApp call to the party displayed as'
                    ' "Marc Garage".', people=["PETROV"], handles=["Marc Garage"],
                    channels=["call", "WhatsApp"], window=WA_W)  # fmt: skip
    assert "event" not in plain


def test_a_saved_contact_stays_unread_beside_a_contact_row(conn):
    # a contact_entry row names one saved contact, and the words may name another, so every
    # saved-contact or shown-number phrase stays unread beside one (CodeRabbit on #279)
    f = LocalAssumptionFiller(
        FakeModel("{}"), conn, template="{claim} {paragraph} {templates} {channels}"
    )
    text = 'Item 1 holds the contact "Alice", and Item 1 called the contact "Marc Garage".'
    assert "the contact" in f.unread_words(text, (), {"contact"})
    both = 'Item 1 holds the contact displayed as "Marc" with the number displayed as "garage".'
    out = f.unread_words(both, (), {"contact"})
    assert "contact displayed as" in out and "number displayed as" in out


def test_an_ordinal_keeps_its_event_beside_a_model_event(conn):
    # a model's event about something else says nothing of the earlier call the ordinal
    # states, so code's unread event still stands beside it (Claude review on #279)
    window = W("June 1, 2026", "2026-06-01T20:52", "2026-06-01T21:09")
    answer = proposal(people=[], quoted_text="", channels=["call"], window=window)
    event = {**answer.model_dump(), "template_id": "event"}
    model = FakeModel(json.dumps({"assumptions": [answer.model_dump(), event]}))
    f = LocalAssumptionFiller(model, conn, template="{claim} {paragraph} {templates} {channels}")
    text = f"{AT} Item 1 placed a second call to (212) 555-0199."
    made = TemplateAssumptionBuilder(f).build(claim(text, ClaimType.COMMUNICATION))
    assert any(a.template_id == "caller" for a in made)
    assert any(is_unread_event(a.template_id, a.text) for a in made)


def test_the_ordinal_event_copies_the_call_it_reads(conn, monkeypatch):
    # the unread event names this call's time row's parties and window, never those of
    # another core row that comes first in the list, such as a model's event (Claude review
    # on #279)
    seen: list[list[Proposal]] = []
    real = LocalAssumptionFiller._add_caller

    def first_another_row(self, claim_, out, allowed_ids):
        rt = next(p for p in out if p.template_id == "record_time")
        other = Proposal("event", {**rt.params, "person_ids": [REYES], "account_ids": []},
                         is_core=True)  # fmt: skip
        made = real(self, claim_, [other, *out], allowed_ids)
        seen.append(made)
        return made

    monkeypatch.setattr(LocalAssumptionFiller, "_add_caller", first_another_row)
    fill(conn, f"{AT} Item 1 placed a second call to (212) 555-0199.")
    (made,) = seen
    rt = next(p for p in made if p.template_id == "record_time")
    (event,) = [p for p in made if p.unread]
    for key in ("person_ids", "account_ids", "window"):
        assert event.params.get(key) == rt.params.get(key), key


def test_another_call_keeps_its_event_without_the_guard(conn, monkeypatch):
    # "another call" states an earlier call as "a second call" does (Claude review on #279)
    monkeypatch.setattr(LocalAssumptionFiller, "unread_words", lambda *a, **k: [])
    made, _ = fill(conn, f"{AT} Item 1 placed another call to (212) 555-0199.")
    assert made["caller"] and is_unread_event("event", made["event"].text)


@pytest.mark.parametrize(
    "words",
    [
        # a phrase only once the app's name is blanked is still read (Claude review on #279)
        'PETROV placed his last WhatsApp call to "Marc Garage".',
        # the quote after "back" is a party's name, not a reply's words
        'PETROV placed a WhatsApp call back to "Marc Garage".',
        'PETROV placed a WhatsApp call back to the party displayed as "Marc Garage".',
        'PETROV called back the party displayed as "Marc Garage" on WhatsApp.',
        'PETROV called back "Marc Garage" on WhatsApp.',
        # a saved contact after the name, or "for" before it; a side named as a number
        'PETROV called "Marc Garage", his contact, on WhatsApp.',
        'PETROV called "Marc Garage", a contact, on WhatsApp.',
        'PETROV called the contact for "Marc Garage" on WhatsApp.',
        'PETROV placed a WhatsApp call to the number "Marc Garage".',
    ],
)
def test_words_beside_an_app_or_a_quoted_party_stay_unread(conn, words):
    made, _ = fill(conn, f"{WA_AT} {words}", ClaimType.TIMING, people=["PETROV"],
                   handles=["Marc Garage"], channels=["call", "WhatsApp"], window=WA_W)  # fmt: skip
    assert made["event"].is_core


def test_a_reply_to_a_quoted_party_with_its_message_quoted_is_plain(conn):
    # the quoted message after the party is still the reply's words (Android 13 D093 form)
    f = LocalAssumptionFiller(
        FakeModel("{}"), conn, template="{claim} {paragraph} {templates} {channels}"
    )
    text = 'SUBJECT-1 replied to "DFIR Two" on LINE, "Lol. Good luck with that."'
    assert "replied" not in f.unread_words(text, (), set())
    assert "back" in f.unread_words('PETROV placed a call back to "Marc Garage".', (), set())


def test_unread_words_are_whole_words(conn):
    # the words `plain_tokens` reads keep their offsets after app and message words are
    # blanked (Claude review on #279)
    f = LocalAssumptionFiller(
        FakeModel("{}"), conn, template="{claim} {paragraph} {templates} {channels}"
    )
    text = "Item 1 placed a Skype call and sent a video message, the first, reading back later."
    out = f.unread_words(text, (), {"call"})
    assert "reading" in out and "rea" not in out
    reply = 'SUBJECT-1 replied to "DFIR Two" at 9:14 p.m. EDT, "Lol."'
    assert "replied" not in f.unread_words(reply, (), set())
    # a reply's own "back" before its quoted words stays plain
    assert "back" not in f.unread_words('REYES texted back "ok".', (), set())
    assert not any(
        "contact" in w for w in f.unread_words("PETROV had a contact for two minutes.", (), set())
    )


def test_one_length_stated_for_two_calls_keeps_the_event(conn):
    # a tested length covers one stated length only (Claude review on #279)
    text = (
        f"{AT} Item 1 placed a call to (212) 555-0199 that lasted 100 seconds and a call of 100"
        " seconds."
    )
    made, _ = fill(conn, text, ClaimType.TIMING, duration={"as_written": "100 seconds"})
    assert made["record_time"].params.duration_s and made["event"].is_core


@pytest.mark.parametrize(
    "length",
    ["1 min. 40 sec.", "1 min., 40 sec.", "one min. and a second.", "1 min. and a second."],
)
def test_an_abbreviated_length_is_read_whole(conn, length):
    text = f"{AT} Item 1 placed a call to (212) 555-0199 that lasted {length}"
    made, f = fill(conn, text, ClaimType.TIMING, duration={"as_written": length.rstrip(".")})
    assert made["record_time"].params.duration_s, [d.reason for d in f.drops]
    assert "event" not in made, [d.reason for d in f.drops]


def test_contact_as_a_communication_is_plain(conn):
    # "a contact that lasted" or "the contact between" is no saved contact (Claude review on
    # #279)
    f = LocalAssumptionFiller(
        FakeModel("{}"), conn, template="{claim} {paragraph} {templates} {channels}"
    )
    for text in (
        "Item 1 placed a call to (212) 555-0199, a contact that lasted about two minutes.",
        "the contact between PETROV and REYES",
    ):
        assert not any("contact" in w for w in f.unread_words(text, (), set())), text
    # a lower-case address after "the contact" is still a saved contact (CodeRabbit on #279)
    out = f.unread_words("Item 1 called the contact marc@example.org on Skype.", (), set())
    assert any("contact" in w for w in out)
    # a contact or a number written inside a quoted message is the message's words, never the
    # claim's; written after a quoted name, it is the claim's (CodeRabbit on #279)
    for text in (
        'PETROV wrote "Alex (a contact) will call." on Telegram.',
        'PETROV wrote "Ask Alex, his contact, to call." on Telegram.',
        "PETROV wrote \"call the number 'Alex' gave you\" on Telegram.",
    ):
        out = f.unread_words(text, (), set())
        assert not any("contact" in w or "number" in w for w in out), (text, out)
    for text, word in (
        ('PETROV called "Marc Garage", his contact, on WhatsApp.', "contact"),
        ('PETROV called "Marc Garage" (a contact) on WhatsApp.', "contact"),
        ('PETROV called the number "Marc Garage" on WhatsApp.', "number"),
        # a handle after "the number" (CodeRabbit on #282)
        ("PETROV called the number @northstar on WhatsApp.", "number"),
        # a quoted name after "number called", and the call's word in capitals (CodeRabbit on
        # #282)
        ('PETROV had a WhatsApp call with the number called "Marc Garage".', "number"),
        ("PETROV CALLED CONTACT MARC GARAGE ON WHATSAPP.", "contact"),
        ("PETROV PLACED A CALL TO CONTACT MARC GARAGE ON WHATSAPP.", "contact"),
        ("PETROV called contact Marc Garage on WhatsApp.", "contact"),
        # a message's word before a bare "contact", and a plural (Claude review on #282)
        ('PETROV called "Marc Garage" on WhatsApp at 9:14 p.m., his contact.', "contact"),
        ("PETROV texted contact Marc Garage on WhatsApp.", "contact"),
        ("PETROV sent a message to contact Marc Garage on WhatsApp.", "contact"),
        ('PETROV called the numbers "Marc Garage" and "Bob" on WhatsApp.', "numbers"),
        # "called" after a call's word names the number (Claude review on #282)
        ("PETROV called the number called Marc Garage on WhatsApp.", "number"),
    ):
        assert any(word in w.split() for w in f.unread_words(text, (), set())), text


def test_a_side_named_two_ways_is_named_once(conn):
    # the form before the name and the form after it find the same noun (Claude review on
    # #282)
    f = LocalAssumptionFiller(
        FakeModel("{}"), conn, template="{claim} {paragraph} {templates} {channels}"
    )
    out = f.unread_words('PETROV called "Marc Garage" (his phone number) on WhatsApp.', (), set())
    assert [w for w in out if "number" in w] == ["his phone number"], out


def test_unread_words_name_each_word_once(conn):
    f = LocalAssumptionFiller(
        FakeModel("{}"), conn, template="{claim} {paragraph} {templates} {channels}"
    )
    out = f.unread_words("Item 1 placed a call that lasted a second, and a second.", (), set())
    assert len(out) == len(set(out))


def test_a_shown_name_that_is_a_person_or_a_received_handle_names_no_caller(conn):
    # the descriptor names an account side only, never a person
    text = "On June 8, 2026, at about 9:00 p.m. EDT, PETROV called the party displayed as REYES."
    made, _ = fill(conn, text, people=["PETROV", "REYES"], channels=["call", "WhatsApp"],
                   window=WA_W)  # fmt: skip
    assert "caller" not in made
    # the handle side placed the call: a caller row names persons or accounts only, and code
    # never decides which account a handle is (the checks resolve it), so no caller is made
    text = f'{WA_AT} PETROV received a WhatsApp call from the party displayed as "Marc Garage".'
    made, _ = fill(conn, text, people=["PETROV"], handles=["Marc Garage"],
                   channels=["call", "WhatsApp"], window=WA_W)  # fmt: skip
    assert "caller" not in made
    # a descriptor the form does not hold
    for words in ('PETROV called the party known as "Marc Garage" on WhatsApp.',
                  'PETROV called the party displayed "Marc Garage" on WhatsApp.'):  # fmt: skip
        made, _ = fill(conn, f"{WA_AT} {words}", people=["PETROV"], handles=["Marc Garage"],
                       channels=["call", "WhatsApp"], window=WA_W)  # fmt: skip
        assert "caller" not in made, words


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
def test_answered_or_connected_before_a_tested_length_still_names_the_caller(
    conn: sqlite3.Connection, joined: str
) -> None:
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


@pytest.mark.parametrize(
    "joined", ["that lasted", "that was answered and lasted", "that connected and lasted"]
)
def test_the_length_forms_follow_the_call_s_app(conn: sqlite3.Connection, joined: str) -> None:
    # CodeRabbit on #273: the app tail ("... on WhatsApp") must stop before every length form.
    text = (
        "On June 8, 2026, at about 9:00 p.m. EDT, Marcus Reyes placed a call to PETROV on"
        f" WhatsApp {joined} about one minute and 30 seconds."
    )
    made, f = fill(conn, text, channels=["call", "WhatsApp"],
                   window=W("June 8", "2026-06-08T20:52", "2026-06-08T21:09"),
                   duration={"as_written": "about one minute and 30 seconds"})  # fmt: skip
    assert list(made["caller"].params.sent_by) == [REYES], f.drops
    assert "event" not in made, made["event"].text


@pytest.mark.parametrize(
    ("joined", "read"),
    [
        ("that connected for", True),
        ("that was connected and lasted", True),
        ("and PETROV was connected for", False),
        ("that was connected by PETROV for", False),
    ],
)
def test_only_the_call_s_own_connected_needs_no_event_on_a_fill(
    conn: sqlite3.Connection, joined: str, read: bool
) -> None:
    # CodeRabbit on #273: through the whole fill, a connecting act no row tests gets a core
    # event, and the call's own "connected" beside a tested length does not.
    length = "about one minute and 30 seconds"
    text = (
        "On June 8, 2026, at about 9:00 p.m. EDT, Marcus Reyes placed a call to PETROV on"
        f" WhatsApp {joined} {length}."
    )
    made, f = fill(conn, text, channels=["call", "WhatsApp"],
                   window=W("June 8", "2026-06-08T20:52", "2026-06-08T21:09"),
                   duration={"as_written": length})  # fmt: skip
    assert "record_time" in made, f.drops
    if read:
        assert "event" not in made, made["event"].text
    else:
        assert made["event"].is_core, f.drops
        assert "states more than its checks read" in made["event"].text
        assert "connected" in f.unread_words(text, tests={"length", "call"})


def test_connected_with_no_tested_length_is_left_for_the_expert(conn: sqlite3.Connection) -> None:
    # "connected" is read only beside a length a row tests; alone, no check reads it.
    made, _ = fill(conn, f"{AT} Item 1 placed a call to (212) 555-0199 that connected.")
    assert "caller" not in made
    made, _ = fill(conn, f"{AT} Item 1 placed a connected call to (212) 555-0199.")
    assert "caller" not in made


def test_a_connected_call_of_another_length_is_not_supported(conn: sqlite3.Connection) -> None:
    text = (
        f"{AT} Item 1 placed a call to (212) 555-0199 that connected and lasted about ten minutes."
    )
    v = verdict(conn, text, 1, duration={"as_written": "about ten minutes"})
    assert v.verdict is not Verdict.SUPPORTED, v.reasons


OWNER_ONLY = {"template_id": "person_identity", "people": ["PETROV"]}


def test_an_owner_identity_naming_no_account_is_refused(conn: sqlite3.Connection) -> None:
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


def test_an_identity_naming_an_account_or_a_person_who_owns_no_phone_is_kept(
    conn: sqlite3.Connection,
) -> None:
    _, f = fill(conn, f"{AT} Item 1 called (212) 555-0199.")
    f._owner_identity_names_nothing(["person:volkov"], [], [])  # owns no phone: still open
    f._owner_identity_names_nothing([], [], [])
    f._owner_identity_names_nothing([PETROV, "person:volkov"], [], [])
    # two owners: Item 1 is PETROV's, not REYES's, so the row may say more (Claude review on
    # #273)
    f._owner_identity_names_nothing([PETROV, REYES], ["dev:item1"], [])
    f._owner_identity_names_nothing([PETROV, REYES], [], [])
    with pytest.raises(Reject, match="names no account or handle"):
        f._owner_identity_names_nothing([PETROV], ["dev:item1"], ["WhatsApp", "call"])
    # a row naming an account is never refused this way, and is built
    with_account = {"template_id": "person_identity", "people": ["PETROV"],
                    "accounts": [{"as_written": "12125550111@s.whatsapp.net",
                                  "app": "WhatsApp"}]}  # fmt: skip
    text = "PETROV uses the WhatsApp account 12125550111@s.whatsapp.net."
    made, f = fill(conn, text, ClaimType.IDENTITY, items=[with_account])
    assert "person_identity" in made, f.drops
    assert list(made["person_identity"].params.account_ids)


def test_an_owner_identity_that_could_say_more_than_the_stipulation_is_kept(
    conn: sqlite3.Connection,
) -> None:
    # Claude review on #273: "Item 2's account belongs to PETROV" when PETROV owns Item 1 says
    # more than his stipulation, and so does an app none of his phones holds an account on.
    _, f = fill(conn, f"{AT} Item 1 called (212) 555-0199.")
    f._owner_identity_names_nothing([PETROV], ["dev:item2"], [])
    f._owner_identity_names_nothing([PETROV], [], ["Signal"])
    # a phone with two confirmed owners: the stipulation does not say which one is meant
    data = copy.copy(f.data)
    data.stipulations = [
        *f.data.stipulations,
        ("stip:x", "dev:item1", "person:volkov", "confirmed"),
    ]
    f._data = data
    f._owner_identity_names_nothing([PETROV], [], [])


# ---------------------------------------------------------------- more call wordings


AT24 = "On June 24, 2026, at about 9:00 p.m. EDT,"
W24 = W("June 24, 2026", "2026-06-24T20:52", "2026-06-24T21:09")


def _wa_out(conn: sqlite3.Connection) -> None:
    # June 24, 9:00 p.m. EDT: PETROV's phone called REYES on WhatsApp.
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        "INSERT OR IGNORE INTO calls VALUES ('c:wa:out', 'item1', 'c:wa:out', 'dev:item1',"
        " 'WhatsApp', ?, ?, 'outgoing', '2026-06-25T01:00:00Z', 0, NULL, 60, 0)",
        (PETROV_WA, REYES_WA),
    )


def from_phone_fill(
    conn: sqlite3.Connection, words: str, phone: str
) -> tuple[dict, LocalAssumptionFiller]:
    _wa_out(conn)
    rt = proposal(people=["PETROV", "Marcus Reyes"], phones=[phone], quoted_text="",
                  channels=["call", "WhatsApp"], window=W24).model_dump()  # fmt: skip
    return fill(conn, f"{AT24} {words}", items=[rt])


def test_a_call_placed_from_the_owner_s_phone_names_its_caller(conn: sqlite3.Connection) -> None:
    # validation iOS 15 C11: "SUBJECT-1 placed a WhatsApp call from the TARGET PHONE to ..."
    made, f = from_phone_fill(conn, "PETROV placed a WhatsApp call from Item 1 to Marcus Reyes.",
                              "Item 1")  # fmt: skip
    a = made["caller"]
    assert list(a.params.sent_by) == [PETROV], [d.reason for d in f.drops]
    assert list(a.params.device_ids) == ["dev:item1"]
    (r,) = run_checks(a, conn)
    assert r.outcome is CheckOutcome.PASS, r.detail


@pytest.mark.parametrize(
    ("words", "phone"),
    [
        # REYES does not own Item 1: who used the phone is not what its log says
        ("Marcus Reyes placed a WhatsApp call from Item 1 to PETROV.", "Item 1"),
        # PETROV does not own Item 2
        ("PETROV placed a WhatsApp call from Item 2 to Marcus Reyes.", "Item 2"),
    ],
)
def test_a_call_placed_from_a_phone_its_caller_does_not_own_names_no_caller(
    conn: sqlite3.Connection, words: str, phone: str
) -> None:
    made, _ = from_phone_fill(conn, words, phone)
    assert "caller" not in made


@pytest.mark.parametrize(
    "words",
    [
        # validation v4 D103: '"ThisIs DfirTwo," live:.cid.5638f9306b7b8594, that lasted ...'
        'PETROV called the Instagram user "Marc Garage," 49800011122.',
        'PETROV called "Marc Garage" (49800011122) on Instagram.',
    ],
)
def test_an_id_with_no_label_beside_its_name_gets_a_caller(
    conn: sqlite3.Connection, words: str
) -> None:
    made, f = ig_fill(conn, words)
    a = made["caller"]
    assert list(a.params.account_ids) == [GARAGE_IG], [d.reason for d in f.drops]
    (r,) = run_checks(a, conn)
    assert r.outcome is CheckOutcome.PASS


def test_an_id_with_no_label_of_another_account_names_no_caller(conn: sqlite3.Connection) -> None:
    _add_instagram(conn)
    words = 'PETROV called the Instagram user "Marc Garage," 49800099999.'
    made, f = fill(conn, f"{IG_AT} {words}", people=["PETROV"],
                   accounts=[*NAMED, {"as_written": "49800099999", "app": "Instagram"}],
                   channels=["call", "Instagram"], window=IG_W)  # fmt: skip
    assert "caller" not in made


# ---------------------------------------------------------------- a blank side on the phone


def time_row(
    conn: sqlite3.Connection, d: int, people: tuple[str, ...] = (PETROV,), accounts: list[str] = NUM
) -> CheckResult:
    params = {"person_ids": list(people), "account_ids": list(accounts), "window": day(d),
              "channels": ["call"], "device_ids": ["dev:item1"]}  # fmt: skip
    return CHECKS["time"].run(instantiate("CT", "record_time", params), conn)


def test_a_call_row_with_the_phone_s_side_blank_is_the_owner_s_call(
    conn: sqlite3.Connection,
) -> None:
    # validation iOS 15 B06: the log names only the other side of a call on the phone, so
    # "SUBJECT-1 placed a Telegram call to SUBJECT-2" found no row between the two.
    r = time_row(conn, 2)  # c:in: from the number, to no account
    assert r.outcome is CheckOutcome.PASS, r.detail
    assert list(r.record_ids) == ["c:in"]
    r = time_row(conn, 1)  # c:out:a leaves the phone's side blank, c:out:b names it
    assert set(r.record_ids) == {"c:out:a", "c:out:b"}, r.detail


def test_a_row_read_through_the_owner_s_stipulation_says_so(conn: sqlite3.Connection) -> None:
    r = time_row(conn, 2)
    note = r.detail.split("name only the other side")[0]
    assert "c:in" in note.split(", ") and "c:out:b" not in note, r.detail  # c:out:b names both
    assert "device_owner stipulation" in r.detail


def test_an_owner_with_no_accounts_is_never_given_a_row(conn: sqlite3.Connection) -> None:
    # Claude review on #273: as the caller check, a side with no accounts in the data reads
    # no call
    from core.audit.checks._common import CaseData
    from core.audit.checks.timing import _owners_calls

    params = {"person_ids": [PETROV], "account_ids": NUM, "window": day(2), "channels": ["call"]}
    p = instantiate("CT", "record_time", params).params
    data = CaseData(conn)
    rows = [r for r in calls_for_accounts(data, set(NUM)) if r.id == "c:in"]
    assert _owners_calls(data, p, rows, [set(), set(NUM)]) == set()
    assert _owners_calls(data, p, rows, [{OWN_UNKNOWN}, set(NUM)]) == {"c:in"}


@pytest.mark.parametrize(
    ("words", "plain"),
    [
        ("the call connected and lasted two minutes", True),
        ("a call that connected, lasting two minutes", True),
        ("the call connected for two minutes", True),
        ("PETROV connected REYES with the caller on a call lasting two minutes", False),
        (
            "PETROV connected, at 9:00 p.m., REYES with the caller on a call lasting two minutes",
            False,
        ),
        ("a call that connected, that lasted two minutes", True),
        ("which connected for two minutes", True),
        # Claude review on #273: the object forms read before any party is blanked
        ("PETROV connected (212) 555-0199 and Marcus Reyes on a call lasting two minutes", False),
        ("PETROV connected Marcus Reyes and (212) 555-0199 on a call lasting two minutes", False),
        ("Item 1 connected Marcus Reyes for two minutes", False),
        ("PETROV connected Marcus Reyes, lasting two minutes", False),
        ("the call connected Marcus Reyes and PETROV for two minutes", False),
        ("Marcus Reyes was connected for about one minute and 40 seconds", False),
        ("the call was connected for two minutes", True),
        ("a call that was connected and lasted two minutes", True),
        ("the WhatsApp call was connected for a minute and a half by PETROV with REYES", False),
        ("the call connected for two minutes, placed by PETROV", False),
        # an account is never the verb (CodeRabbit on #273)
        ("the call to @connected lasted two minutes", True),
        ("the call to connected@example.org lasted two minutes", True),
        ("PETROV connected @connected with REYES on a call lasting two minutes", False),
        ("PETROV connected(@northstar, REYES) on a call lasting two minutes", False),
        ("PETROV connected(connected@example.org, REYES) on a call lasting two minutes", False),
        ("the call to live:connected lasted two minutes", True),
        ("the call to connected.com lasted two minutes", True),
    ],
)
def test_only_the_call_s_own_connected_is_plain_beside_a_length(
    conn: sqlite3.Connection, words: str, plain: bool
) -> None:
    f = LocalAssumptionFiller(FakeModel("{}"), conn,
                              template="{claim} {paragraph} {templates} {channels}")  # fmt: skip
    text = f"On June 1, 2026, at about 9:00 p.m. EDT, {words}."
    assert ("connected" not in f.unread_words(text, tests={"length", "call"})) is plain


def test_a_blank_side_is_never_a_party_who_does_not_own_the_phone(conn: sqlite3.Connection) -> None:
    # REYES owns Item 2, not Item 1, where the call is logged
    r = time_row(conn, 2, people=(REYES,))
    assert r.outcome is CheckOutcome.INCONCLUSIVE, r.detail
    assert "None found" in r.detail


# ---------------------------------------------------------------- a person's number

AT2 = "On June 2, 2026, at about 9:00 p.m. EDT,"
RT2 = proposal(people=["Marcus Reyes"], accounts=[{"as_written": "(212) 555-0199", "app": "call"}],
               phones=["Item 1"], quoted_text="", channels=["call"],
               window=W("June 2", "2026-06-02T20:52", "2026-06-02T21:09")).model_dump()  # fmt: skip
TIE = {"template_id": "person_identity", "people": ["Marcus Reyes"],
       "accounts": [{"as_written": "(212) 555-0199", "app": "call"}], "handles": [],
       "phones": [], "channels": ["call"], "quoted_text": "", "count": None,
       "duration": None, "window": None}  # fmt: skip


@pytest.mark.parametrize(
    "words",
    [
        # validation v4 D022 and D023
        "Item 1 received a call from Marcus Reyes's number, (212) 555-0199.",
        "Marcus Reyes at (212) 555-0199 called Item 1.",
    ],
)
def test_a_person_s_number_is_timed_as_the_number(conn: sqlite3.Connection, words: str) -> None:
    text = f"{AT2} {words}"
    made, f = fill(conn, text, items=[RT2, TIE])
    rt = made["record_time"]
    assert REYES not in rt.params.person_ids, [d.reason for d in f.drops]
    assert set(rt.params.account_ids) == set(NUM)
    assert list(rt.params.device_ids) == ["dev:item1"]
    (r,) = run_checks(rt, conn)
    assert r.outcome is CheckOutcome.PASS, r.detail
    # whose number it is stays the identity row's to test, and who placed the call an event
    # row's, which no check covers: the call found with the number never carries the claim
    assert list(made["person_identity"].params.person_ids) == [REYES]
    event = made["event"]
    assert event.is_core and TEMPLATES["event"].checks == ()
    assert REYES in event.params.person_ids
    assumptions = list(made.values())
    checks = [x for a in assumptions for x in run_checks(a, conn)]
    v = decide_verdict(claim(text), assumptions, [], checks, load_stipulations(conn), "run")
    assert v.verdict is Verdict.UNPROVEN, v.reasons
    assert any("belongs to person:reyes" in x for x in v.reasons), v.reasons
    assert any("The event the claim states" in x for x in v.reasons), v.reasons


def test_a_person_s_number_keeps_the_claimed_caller_for_the_expert(
    conn: sqlite3.Connection,
) -> None:
    # Claude review on #273: on June 1 the log holds only calls Item 1 placed. Written with
    # the number alone the reversed caller is CONTRADICTED; written with the person beside the
    # number no caller row is read, and the event row keeps the direction from being skipped.
    rt = {**RT2, "window": W("June 1", "2026-06-01T20:52", "2026-06-01T21:09")}
    text = "On June 1, 2026, at about 9:00 p.m. EDT, Marcus Reyes at (212) 555-0199 called Item 1."
    made, _ = fill(conn, text, items=[rt, TIE])
    assert "caller" not in made
    assert made["event"].is_core
    assumptions = list(made.values())
    checks = [x for a in assumptions for x in run_checks(a, conn)]
    v = decide_verdict(claim(text), assumptions, [], checks, load_stipulations(conn), "run")
    assert v.verdict is Verdict.UNPROVEN, v.reasons


def test_an_owner_row_with_a_time_says_who_held_the_phone_and_is_kept(
    conn: sqlite3.Connection,
) -> None:
    # Claude review on #273: "PETROV was using Item 1 at 9 p.m." is not his stipulation
    june8 = W("June 8", "2026-06-08T20:52", "2026-06-08T21:09")
    rt = proposal(people=[], quoted_text="", channels=["call", "WhatsApp"], window=june8)
    timed = {**OWNER_ONLY, "window": june8}
    text = "On June 8, 2026, at about 9:00 p.m. EDT, Marcus Reyes placed a WhatsApp call to PETROV."
    made, f = fill(conn, text, items=[rt.model_dump(), timed])
    assert "person_identity" in made, [d.reason for d in f.drops]


def test_a_person_s_number_on_two_calls_is_left_as_written(conn: sqlite3.Connection) -> None:
    # Claude review on #273: one event row holds one call's window
    text = f"{AT2} Item 1 received a call from Marcus Reyes's number, (212) 555-0199."
    f2 = LocalAssumptionFiller(FakeModel("{}"), conn,
                               template="{claim} {paragraph} {templates} {channels}")  # fmt: skip
    rows = [
        proposal_row
        for proposal_row in f2._person_s_number(
            claim(text),
            [
                Proposal("record_time", {"person_ids": [REYES], "account_ids": NUM,
                                         "channels": ["call"], "window": day(2)}),
                Proposal("record_time", {"person_ids": [REYES], "account_ids": NUM,
                                         "channels": ["call"], "window": day(3)}),
                Proposal("person_identity", {"person_ids": [REYES], "account_ids": NUM}),
            ],
            {"event", "record_time", "person_identity"},
        )
    ]  # fmt: skip
    assert all(REYES in r.params["person_ids"] for r in rows if r.template_id == "record_time")
    assert not any(r.template_id == "event" for r in rows)


def test_an_identity_claim_keeps_its_owner_row_for_the_expert(conn: sqlite3.Connection) -> None:
    # Claude review on #273: for an identity claim the owner row is the claim itself
    row = {"template_id": "person_identity", "people": ["PETROV"], "accounts": [],
           "handles": [], "phones": ["Item 1"], "channels": [], "quoted_text": "",
           "count": None, "duration": None, "window": None}  # fmt: skip
    made, f = fill(conn, "PETROV is the user of Item 1.", ClaimType.IDENTITY, items=[row])
    assert "person_identity" in made, [d.reason for d in f.drops]


@pytest.mark.parametrize(
    ("words", "items"),
    [
        # no identity row ties the person to the number
        ("Item 1 received a call from Marcus Reyes's number, (212) 555-0199.", [RT2]),
        # the person and the number are written as two parties
        ("Item 1 had a call with Marcus Reyes and (212) 555-0199.", [RT2, TIE]),
    ],
)
def test_a_person_not_written_as_the_number_s_holder_stays_a_party(
    conn: sqlite3.Connection, words: str, items: list[dict]
) -> None:
    made, f = fill(conn, f"{AT2} {words}", items=items)
    assert REYES in made["record_time"].params.person_ids, [d.reason for d in f.drops]
