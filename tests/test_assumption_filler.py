"""The assumption filler on synthetic case01, with a scripted fake model.

The fake answers what a good model should, and the tests check that code turns those words
into the parameters the check tests use (tests/checks/test_case01.py), that the checks then
find what they find there, and that wrong or unsupported values are dropped.
"""

import json
import re
import sqlite3
from datetime import UTC
from datetime import datetime as D
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from core.audit._llm_json import prompt_body
from core.audit.assumption_filler import (
    LocalAssumptionFiller,
    Reject,
    _Account,
    _in_quotes,
    _ProposalOut,
    _states_seconds,
    check_window,
    count_op,
    coverage_gap,
    date_mentions,
    only_addressed,
    stated_part_day,
)
from core.audit.assumptions import TEMPLATES, Proposal, TemplateAssumptionBuilder, is_code_made
from core.audit.checks import CHECKS
from core.contracts import CheckOutcome, Claim, ClaimStatus, ClaimType, ModelCallOutcome
from eval.synthetic.generate import generate
from tests.checks.helpers import stipulate
from tests.fake_model import FakeModel

ROOT = Path(__file__).parents[1]
DRAFT = prompt_body((ROOT / "docs/prompts/assumptions.md").read_text("utf-8"))
GOLD = {
    d["claim_id"]: d
    for d in map(
        json.loads, (ROOT / "eval/gold/case01/gold.jsonl").read_text(encoding="utf-8").splitlines()
    )
}
PETROV, REYES = "person:petrov", "person:reyes"
NORTHSTAR = ["acct:item1:Telegram:5551234", "acct:item2:Telegram:5551234"]
MARC_0122 = ["acct:item1:Phone:+12125550122"]


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    out = tmp_path_factory.mktemp("case01")
    db = out / "case01.db"
    generate(out, db)
    c = sqlite3.connect(db)
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
    yield c
    c.close()


def claim(cid: str) -> Claim:
    g = GOLD[cid]
    return Claim(
        id=cid,
        paragraph_id=f"para:{g['para_no']}",
        text=g["text"],
        claim_type=ClaimType(g["claim_type"]),
        status=ClaimStatus.ACCEPTED,
    )


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


def W(as_written: str, start: str, end: str, zone: str = "phone") -> dict:  # noqa: N802
    return {"as_written": as_written, "start": start, "end": end, "zone": zone}


MARC = {"as_written": "+1 (212) 555-0122", "app": "Phone"}
DP_GARAGE = {"as_written": "dp_garage", "app": "Instagram"}

# What a good model answers for each claim the check tests cover.
GOOD = {
    "C01": [P("contact_entry", phones=["Item 1"], quoted_text="Marc Garage", accounts=[MARC])],
    "C02": [
        P("same_account", handles=["@alex92", "@northstar"], channels=["Telegram"]),
        P(
            "event",
            people=["PETROV"],
            channels=["Telegram"],
            phones=["Item 1"],
            window=W(
                "Between February 20 and March 28, 2026", "2026-02-20T00:00", "2026-03-29T00:00"
            ),
        ),
    ],
    "C03": [
        P(
            "message_count",
            phones=["Item 1"],
            people=["PETROV"],
            handles=["@northstar"],
            channels=["Telegram"],
            count={"value": 13},
            window=W(
                "From March 10 through March 31, 2026", "2026-03-10T00:00", "2026-04-01T00:00"
            ),
        )
    ],
    "C04": [
        P(
            "no_contact",
            people=["PETROV"],
            handles=["@northstar"],
            window=W(
                "first made contact with @northstar on March 12, 2026",
                "2026-01-01T00:00",
                "2026-03-12T00:00",
            ),
        )
    ],
    "C05": [
        P("sender", people=["PETROV"], quoted_text="need 2 more by friday"),
        P(
            "record_time",
            people=["PETROV"],
            quoted_text="need 2 more by friday",
            window=W("On March 12, 2026", "2026-03-12T00:00", "2026-03-13T00:00"),
        ),
    ],
    "C09": [
        P(
            "record_time",
            channels=["call"],
            people=["PETROV"],
            accounts=[MARC],
            phones=["Item 1"],
            duration={"as_written": "about two minutes"},
            window=W("At about 7:58 p.m. on March 9, 2026", "2026-03-09T19:50", "2026-03-09T20:06"),
        )
    ],
    "C10": [
        P(
            "record_time",
            people=["PETROV", "REYES"],
            quoted_text="its done",
            window=W("At 2:31 a.m. on March 5, 2026", "2026-03-05T02:31", "2026-03-05T02:32"),
        )
    ],
    "C11": [
        P(
            "record_time",
            people=["PETROV"],
            quoted_text="move it tonight",
            window=W(
                "At 10:05 p.m. on March 14, 2026, REYES received a phone call warning him "
                "about police activity at his shop, and after that call",
                "2026-03-14T22:05",
                "2026-03-15T00:00",
            ),
        )
    ],
    "C14": [
        P(
            "no_contact",
            people=["PETROV", "REYES"],
            window=W("between March 20 and March 23, 2026", "2026-03-20T00:00", "2026-03-24T00:00"),
        )
    ],
    "C16": [
        P("sender", accounts=[DP_GARAGE], quoted_text="got the money, come get it"),
        P(
            "record_time",
            accounts=[DP_GARAGE],
            quoted_text="got the money, come get it",
            window=W("On March 18, 2026", "2026-03-18T00:00", "2026-03-19T00:00"),
        ),
    ],
}

# The outcome tests/checks/test_case01.py pins for each claim's checks.
EXPECTED = {
    "C01": [CheckOutcome.PASS],
    "C02": [CheckOutcome.PASS],
    "C03": [CheckOutcome.PASS],
    "C04": [CheckOutcome.FAIL],
    "C05": [CheckOutcome.PASS, CheckOutcome.PASS],
    "C09": [CheckOutcome.PASS],
    "C10": [CheckOutcome.FAIL],
    "C11": [CheckOutcome.FAIL],
    "C14": [CheckOutcome.FAIL],
    "C16": [CheckOutcome.PASS, CheckOutcome.PASS],
}


def by_claim(answers: dict[str, list[dict]]):
    def reply(prompt: str) -> str:
        for cid, props in answers.items():
            if f"[CLAIM START]\n{GOLD[cid]['text']}\n[CLAIM END]" in prompt:
                return json.dumps({"assumptions": props})
        return json.dumps({"assumptions": []})

    return reply


def build(conn, cid: str, answers: dict[str, list[dict]] | None = None):
    filler = LocalAssumptionFiller(FakeModel(by_claim(answers or GOOD)), conn, template=DRAFT)
    builder = TemplateAssumptionBuilder(filler)
    return builder.build(claim(cid)), filler, builder


# What code adds to a good answer from the claim's own words. C10 and C11 quote PETROV's
# message ("PETROV texted REYES 'its done'", "PETROV sent the Telegram message 'move it
# tonight'"), so each gets PETROV's sender assumption too, which passes: PETROV sent it, at
# another time than the claim says.
CODE_ADDS: dict[str, list[tuple[str, CheckOutcome | None]]] = {
    "C10": [("sender", CheckOutcome.PASS)],
    # "warning him about police activity" is the call's content, which no check reads
    "C11": [("sender", CheckOutcome.PASS), ("event", None)],
    # "two days after the seizure" is a part no check reads, so code adds an event only an
    # expert can carry (filler 12, `unread_words`); it has no check, so no outcome.
    "C04": [("event", None)],
    # "the number saved as \"Marc Garage\"" is a contact entry this answer keeps no row for
    # (Claude review on #265: "saved" is plain only beside a kept contact_entry row)
    "C09": [("event", None)],
}


@pytest.mark.parametrize("cid", sorted(GOOD))
def test_good_answers_become_checkable_assumptions(conn, cid):
    assumptions, filler, builder = build(conn, cid)
    assert not filler.drops, filler.drops
    assert not builder.rejected, builder.rejected
    assert sorted(a.template_id for a in assumptions) == sorted(
        [p["template_id"] for p in GOOD[cid]] + [t for t, _ in CODE_ADDS.get(cid, [])]
    )
    outcomes = []
    for a in assumptions:
        assert a.is_core
        for name in TEMPLATES[a.template_id].checks:  # event, meaning, role: stance only
            outcomes.append(CHECKS[name].run(a, conn).outcome)
    added = [o for _, o in CODE_ADDS.get(cid, []) if o is not None]
    assert sorted(outcomes) == sorted(EXPECTED[cid] + added)


def test_a_contact_entry_keeps_the_one_account_it_names(conn):
    # The same number written another way on the same phone is a second account; a contact
    # entry names the one account that holds the number (Codex on #169).
    conn.execute(
        "INSERT INTO accounts (id, source_id, locator, device_id, app, identifier)"
        " VALUES ('acct:item1:Phone:2125550122', 'item1', 'x', 'dev:item1', 'Phone',"
        " '2125550122')"
    )
    try:
        (c01,) = build(conn, "C01")[0]
        assert c01.params.account_ids == tuple(MARC_0122)
    finally:
        conn.execute("DELETE FROM accounts WHERE id = 'acct:item1:Phone:2125550122'")


def test_a_contact_entry_written_another_way_still_finds_its_one_account(conn):
    # No account is written "(212) 555-0122"; the one that holds the number is it (Codex on
    # #169). Two that hold it are two candidates, and the exact one is not known.
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    acc = _Account(as_written="(212) 555-0122", app="Phone")
    assert filler._accounts(acc, ["dev:item1"], "", one_number=False) == set(MARC_0122)
    conn.execute(
        "INSERT INTO accounts (id, source_id, locator, device_id, app, identifier)"
        " VALUES ('acct:item1:Phone:12125550122', 'item1', 'x', 'dev:item1', 'Phone',"
        " '12125550122')"
    )
    try:
        filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
        with pytest.raises(Reject):
            filler._accounts(acc, ["dev:item1"], "", one_number=False)
    finally:
        conn.execute("DELETE FROM accounts WHERE id = 'acct:item1:Phone:12125550122'")


def test_parameters_match_the_check_tests(conn):
    (c01,) = build(conn, "C01")[0]
    assert c01.params.device_ids == ("dev:item1",)
    assert c01.params.account_ids == tuple(MARC_0122)
    (c03,) = build(conn, "C03")[0]
    assert c03.params.handles == ("@northstar",) and c03.params.account_ids == ()
    assert c03.params.person_ids == (PETROV,)
    assert c03.params.channels == ("Telegram",)
    assert (c03.params.expected_count, c03.params.count_op) == (13, "eq")
    assert c03.params.window.tz == "America/New_York"
    assert c03.params.window.raw == "From March 10 through March 31, 2026"
    c02 = {a.template_id: a for a in build(conn, "C02")[0]}
    assert c02["same_account"].params.handles == ("@alex92", "@northstar")
    c09 = next(a for a in build(conn, "C09")[0] if a.template_id == "record_time")
    assert c09.params.account_ids == tuple(MARC_0122)
    assert c09.params.person_ids == (PETROV,)  # named in the paragraph, not the claim
    assert c09.params.duration_s == (90, 150)


def test_prompt_shows_only_allowed_templates_and_marks_data(conn):
    _, filler, _ = build(conn, "C14")
    prompt = filler.recorder.calls[0].prompt
    assert "- no_contact:" in prompt and "- same_account:" not in prompt
    assert "[PARAGRAPH START]\nPETROV and REYES had no contact" in prompt
    assert filler.recorder.calls[0].outcome is ModelCallOutcome.OK


def _one(cid: str, **change) -> dict[str, list[dict]]:
    """The good answer for the claim, with the same change made to every proposal."""
    return {cid: [{**p, **change} for p in GOOD[cid]]}


C14_RAW = "between March 20 and March 23, 2026"
BAD = [
    pytest.param("C14", {"people": ["PETROV", "SOKOLOV"]}, "not written", id="name-not-in-text"),
    pytest.param("C14", {"people": ["Petrov"]}, "not written", id="name-not-verbatim"),
    pytest.param("C14", {"channels": ["WhatsApp"]}, "does not name the channel", id="narrowed"),
    pytest.param("C14", {"channels": ["Signal"]}, "not an app", id="unknown-app"),
    pytest.param(
        "C03",
        {"count": {"value": 10}},
        "not written in the claim as a number",
        id="count-is-another-number",
    ),
    pytest.param("C03", {"phones": ["Item 3"]}, "not written", id="phone-not-in-text"),
    pytest.param(
        "C09",
        {"accounts": [{"as_written": "+1 (212) 555-0122", "app": "WhatsApp"}]},
        "matches no account",
        id="wrong-app",
    ),
    pytest.param(
        "C16",
        {"accounts": [{"as_written": "dp_garage", "app": "Telegram"}]},
        "matches no account",
        id="account-on-wrong-app",
    ),
    pytest.param("C14", {"template_id": "same_account"}, "not allowed", id="template-not-allowed"),
    pytest.param("C01", {"handles": ["Marc Garage"]}, "does not take handles", id="handle-refused"),
    pytest.param(
        "C09",
        {"duration": {"as_written": "about 2 minutes"}},
        "not written",
        id="duration-not-verbatim",
    ),
]


# The model's range is refused, so code uses the range the claim plainly states instead
# (stated_windows): the same assumption as the good answer, never a guess at the model's.
BAD_WINDOWS = [
    pytest.param(
        "C14",
        {
            "window": W(
                "between March 20 and March 23, 2026", "2026-03-19T00:00", "2026-03-24T00:00"
            )
        },
        id="window-start-not-stated",
    ),
    pytest.param(
        "C14",
        {
            "window": W(
                "between March 20 and March 23, 2026", "2026-03-20T00:00", "2026-03-26T00:00"
            )
        },
        id="window-end-not-stated",
    ),
    pytest.param(
        "C14",
        {
            "window": W(
                "between March 20 and March 23, 2026",
                "2026-03-20T00:00",
                "2026-03-24T00:00",
                zone="UTC",
            )
        },
        id="utc-not-written",
    ),
    pytest.param(
        "C14",
        {"window": W("between March 20 and 23", "2026-03-20T00:00", "2026-03-24T00:00")},
        id="window-words-invented",
    ),
    pytest.param(
        "C10",
        {"window": W("At 2:31 a.m. on March 5, 2026", "2026-03-05T07:31", "2026-03-05T07:32")},
        id="utc-time-as-local",
    ),
]


@pytest.mark.parametrize(("cid", "change"), BAD_WINDOWS)
def test_a_refused_model_range_is_replaced_by_the_range_the_claim_states(conn, cid, change):
    good = {a.template_id: a for a in build(conn, cid)[0]}
    repaired = {a.template_id: a for a in build(conn, cid, _one(cid, **change))[0]}
    assert repaired.keys() == good.keys()
    for tid, a in repaired.items():
        assert a.params.window == good[tid].params.window, tid
        assert a.params == good[tid].params


def test_a_model_range_on_a_day_the_claim_does_not_state_is_still_dropped(conn):
    # C07 states two dates (March 6 and March 9); a range on neither day matches no stated one.
    answers = {
        "C07": [
            P(
                "record_time",
                people=["PETROV", "REYES"],
                channels=["SMS"],
                window=W("On March 6, 2026", "2026-03-08T00:00", "2026-03-09T00:00"),
            )
        ]
    }
    assumptions, filler, _ = build(conn, "C07", answers)
    assert assumptions == []
    assert any("not one the claim plainly states" in d.reason for d in filler.drops)


def test_a_dated_quote_gets_its_time_assumption_from_code(conn):
    # C05 "On March 12, 2026, PETROV wrote ...": the model gave only the sender.
    good = {a.template_id: a for a in build(conn, "C05")[0]}
    answers = {"C05": GOOD["C05"][:1]}
    got = {a.template_id: a for a in build(conn, "C05", answers)[0]}
    assert got.keys() == {"sender", "record_time"}
    assert got["record_time"].params == good["record_time"].params


def test_a_sender_without_a_party_gets_the_writer_the_claim_names(conn):
    # Mac run ¶6.1: the model left the sender's party out, so nobody was checked as the
    # sender and the claim could never be supported (rule 3e). "PETROV wrote" names him.
    good = {a.template_id: a for a in build(conn, "C05")[0]}
    answers = {"C05": [{**GOOD["C05"][0], "people": []}]}
    got = {a.template_id: a for a in build(conn, "C05", answers)[0]}
    assert got.keys() == {"sender", "record_time"}
    assert got["sender"].params == good["sender"].params
    assert got["record_time"].params == good["record_time"].params


@pytest.mark.parametrize(
    ("text", "quoted", "writer"),
    [
        ("On March 12, 2026, PETROV wrote to @northstar: 'need 2 more by friday'.",
         "need 2 more by friday", "PETROV"),
        ("Daniel Petrov texted REYES 'its done'.", "its done", "PETROV"),
        ("PETROV WROTE 'its done'.", "its done", "PETROV"),  # verbs in capitals too
        ("PETROV wrote 'ok' and REYES replied 'fine'.", "fine", "REYES"),  # nearest verb
        ("PETROV wrote 'ok' and REYES replied 'fine'.", "ok", "PETROV"),
        ("REYES said PETROV wrote 'its done'.", "its done", "PETROV"),  # writer, not speaker
        ("PETROV wrote a report quoting REYES: 'ok'.", "ok", None),  # "quoting" governs
        ("PETROV told agents that REYES said 'ok'.", "ok", None),  # "said" governs
        ("ALEXANDER SOKOLOV wrote 'its done'.", "its done", None),  # no such person
        ("The message 'its done' was sent at 2:31 a.m.", "its done", None),  # no writer
        ("PETROV wrote 'its done'.", "not in the claim", None),
        # The quote is handed on to someone else after the writer's verb (#57 review).
        ("PETROV sent REYES a photo, and REYES answered 'ok see you'.", "ok see you", None),
        ("PETROV texted REYES, who responded 'ok see you'.", "ok see you", None),
        ("PETROV replied to REYES's message 'ok see you'.", "ok see you", None),
        ("PETROV messaged REYES. REYES: 'ok see you'.", "ok see you", None),
        ("PETROV emailed REYES, whose reply was 'ok see you'.", "ok see you", None),
        ("PETROV texted JONES, with JONES' reply being 'ok see you'.", "ok see you", None),
        ("PETROV texted REYES and REYES wrote back 'ok see you'.", "ok see you", "REYES"),
        ("PETROV texted REYES that 'the van is ready'.", "the van is ready", "PETROV"),
        ("A friend of PETROV texted REYES 'its done'.", "its done", None),
        ("Someone posing as PETROV texted 'its done'.", "its done", None),
        ("A FRIEND OF PETROV TEXTED 'its done'.", "its done", None),
        ("Agent Daniel Petrov texted REYES 'its done'.", "its done", "PETROV"),
        ("PETROV texted REYES at 2:31 p.m.: 'ok'.", "ok", "PETROV"),  # Codex on #77
        ("PETROV texted REYES before midnight: 'ok'.", "ok", "PETROV"),
        ("As PETROV texted REYES 'ok', officers watched.", "ok", "PETROV"),
        ("Someone impersonating PETROV texted 'ok'.", "ok", None),
        ("PETROV sent REYES two texts, 'ok' and 'bye'.", "ok", "PETROV"),  # a noun
        ("PETROV texted REYES that it's 'ok see you'.", "ok see you", "PETROV"),  # contraction
        ("PETROV wrote a report with two quotes attributed to REYES: 'ok'.", "ok", None),
        ("PETROV TEXTED REYES, AND REYES SHOT BACK 'OK SEE YOU'.", "OK SEE YOU", None),
        ("PETROV TEXTED REYES AND SMITH: 'OK SEE YOU'.", "OK SEE YOU", None),
        ("PETROV texted REYES, writing 'ok see you'.", "ok see you", "PETROV"),
        ("PETROV texted REYES, with REYES writing 'ok see you'.", "ok see you", None),
        ("PETROV texted REYES from his brother's phone: 'ok see you'.", "ok see you", None),
        ("PETROV texted Dr. Reyes: 'ok see you'.", "ok see you", "PETROV"),
        ("PETROV texted REYES as REYES shot back 'ok see you'.", "ok see you", None),
        ("PETROV texted REYES about Exhibit A. REYES shot back 'ok see you'.", "ok see you", None),
        ("PETROV wrote a report with the quotes from REYES, 'ok see you'.", "ok see you", None),
        ("PETROV texted REYES and read her replies: 'ok'.", "ok", None),
        ("PETROV texted REYES and SMITH: 'ok'.", "ok", "PETROV"),  # Codex round 2
        ("PETROV texted REYES and he replied 'ok'.", "ok", None),
        ("PETROV texted REYES, and REYES shot back 'ok'.", "ok", None),
        ("PETROV texted @writes: 'ok'.", "ok", "PETROV"),
        ("PETROV texted REYES about the quoted statement 'ok'.", "ok", None),
        ("PETROV'S ASSISTANT REYES TEXTED 'ok'.", "ok", "REYES"),
        ("REYES's friend PETROV texted 'ok'.", "ok", "PETROV"),
        # Codex round 6
        ("PETROV wrote a report about REYES and her replies: 'ok'.", "ok", None),
        ("PETROV texted REYES and, replying 'ok', SMITH ended the exchange.", "ok", None),
        ("PETROV texted REYES, replying 'ok', and REYES left.", "ok", None),
        ("PETROV texted REYES, writing 'ok', SMITH watching.", "ok", None),
        # Grok audit of 2ddc302
        ("PETROV texted REYES about the replies: 'ok'.", "ok", None),
        ("PETROV texted REYES about the answers, 'ok'.", "ok", None),
        ("PETROV texted REYES regarding the texts: 'ok'.", "ok", None),
        # Codex round 7
        ("PETROV wrote a report about all the replies: 'ok'.", "ok", None),
        ("PETROV texted REYES about both of the answers: 'ok'.", "ok", None),
        ("PETROV sent REYES the two texts: 'ok'.", "ok", "PETROV"),
        # Codex round 8
        ("PETROV wrote a report listing the replies: 'ok'.", "ok", None),
        ("PETROV texted REYES while SMITH, replying 'ok', left.", "ok", None),
        ("PETROV texted REYES in the group chat, where REYES shot back 'ok'.", "ok", None),
        ("PETROV texted REYES, and her reply was 'ok'.", "ok", None),
        ("PETROV texted REYES, replying 'ok', @northstar ended the exchange.", "ok", None),
        ("PETROV texted REYES from Main St. REYES shot back 'ok'.", "ok", None),
        ("PETROV texted REYES, and @northstar shot back 'ok'.", "ok", None),
        ("PETROV TEXTED REYES, AND @NORTHSTAR SHOT BACK 'OK'.", "OK", None),
        ("PETROV texted REYES and @smith: 'ok'.", "ok", "PETROV"),
        ("PETROV texted REYES, and REYES, annoyed, shot back 'ok'.", "ok", None),
        ("PETROV texted REYES, saying 'ok' was what SMITH had written.", "ok", None),
        ("PETROV WROTE A REPORT WITH THE QUOTES: 'OK'.", "OK", None),
        ("PETROV TEXTED MARCUS REYES: 'OK'.", "OK", "PETROV"),
        ("PETROV texted REYES, and REYES SHOT BACK 'OK'.", "OK", None),
        ("PETROV texted REYES, REYES SHOT BACK 'OK'.", "OK", None),
        ("PETROV texted REYES. @northstar: 'ok'.", "ok", None),
        ("PETROV texted REYES, replying 'ok', you ended the exchange.", "ok", None),
        ("PETROV texted REYES. (REYES: 'ok')", "ok", None),
        ("PETROV texted REYES — @northstar: 'ok'.", "ok", None),
        ("PETROV texted REYES (REYES: 'ok').", "ok", None),
        ("PETROV texted REYES, replying 'ok', an annoyed SMITH ended it.", "ok", None),
        ("PETROV texted REYES\nSMITH: 'ok'", "ok", None),
        ("After PETROV texted REYES, REYES messages back 'ok'.", "ok", None),
        ("PETROV texted REYES, replying 'ok'.", "ok", "PETROV"),
        ("PETROV TEXTED REYES, @northstar SHOT BACK 'OK'.", "OK", None),
        ("PETROV texted REYES, then REYES: 'ok'.", "ok", None),
        ("PETROV texted REYES, and REYES: 'ok'.", "ok", None),
        ("PETROV texted REYES then @northstar: 'ok'.", "ok", None),
        ("PETROV texted REYES and @northstar: 'ok'.", "ok", "PETROV"),
        # The coverage plan's step 3: more ways a claim names the writer.
        ("PETROV asked on Telegram: 'ok?'", "ok?", "PETROV"),
        ("PETROV posted on Instagram: 'ok'.", "ok", "PETROV"),
        ("REYES told PETROV by WhatsApp: 'ok'.", "ok", "REYES"),
        ("REYES told PETROV via Telegram: 'ok'.", "ok", "REYES"),
        ("PETROV told REYES by iMessage: 'ok'.", "ok", "PETROV"),  # an app's word, any case
        ("PETROV told REYES in a WhatsApp chat: 'ok'.", "ok", "PETROV"),
        ("PETROV sent a WhatsApp message to (212) 555-0122 reading 'ok'.", "ok", "PETROV"),
        ("PETROV sent REYES a Telegram message reading 'ok'.", "ok", "PETROV"),
        ("PETROV sent REYES a text that read 'ok'.", "ok", None),  # "read" governs
        ('PETROV wrote to the Instagram user "dp_garage": "ok".', "ok", "PETROV"),
        ('PETROV told "Marc Garage" in a WhatsApp chat: "ok".', "ok", "PETROV"),
        # A quoted word that is no name the case knows still refuses the writer.
        ('PETROV wrote to the user "a friend": "ok".', "ok", None),
        # "reading" that is no message's words.
        ("PETROV texted REYES, reading 'ok'.", "ok", None),
        ("PETROV sent REYES a report reading 'ok'.", "ok", None),
        # A number that is no plain phone number stays a word that refuses.
        ("PETROV sent a message to 555-0122 reading 'ok'.", "ok", None),
        # "said" still names no writer: it may be spoken.
        ("PETROV said to REYES: 'ok'.", "ok", None),
        # Baker Eval on #164: "by" or "via" a person may name another writer, and words
        # handed on may have been sent by someone other than who wrote them.
        ("SMITH sent a message by PETROV: 'ok'.", "ok", None),
        ("PETROV sent a message via REYES: 'ok'.", "ok", None),
        ("REYES forwarded what PETROV posted in the chat: 'ok'.", "ok", None),
        ("REYES shared the post PETROV wrote: 'ok'.", "ok", None),
        ("Quoting a chat, PETROV wrote to REYES: 'ok'.", "ok", None),
        # Codex on #164: a full stop after a number still ends the sentence.
        ("PETROV wrote to (212) 555-0122. REYES: 'ok'.", "ok", None),
    ],
)  # fmt: skip
def test_stated_sender_is_the_writer_of_the_quoted_words(conn, text, quoted, writer):
    filler = LocalAssumptionFiller(FakeModel(by_claim(GOOD)), conn, template=DRAFT)
    c = Claim(id="X", paragraph_id="para:1", text=text, claim_type=ClaimType.COMMUNICATION,
              status=ClaimStatus.ACCEPTED)  # fmt: skip
    got = filler.stated_sender(c, quoted)
    assert got == (filler._person(writer) if writer else None)


def test_a_name_word_counts_only_written_as_a_name(conn):
    # Codex round 13: with a person named Will, the modal "will" must not pass as a name.
    conn.execute("INSERT INTO persons VALUES ('person:will', 'Will Turner', 'expert:test')")
    try:
        filler = LocalAssumptionFiller(FakeModel(by_claim(GOOD)), conn, template=DRAFT)
        c = Claim(id="X", paragraph_id="para:1", text="PETROV texted REYES, REYES will text 'ok'.",
                  claim_type=ClaimType.COMMUNICATION, status=ClaimStatus.ACCEPTED)  # fmt: skip
        assert filler.stated_sender(c, "ok") is None
    finally:
        conn.execute("DELETE FROM persons WHERE id = 'person:will'")


def test_a_phone_scope_does_not_stop_the_writer_from_being_read(conn):
    good = {a.template_id: a for a in build(conn, "C05")[0]}
    answers = {"C05": [{**GOOD["C05"][0], "people": [], "phones": ["Item 1"]}]}
    filler = LocalAssumptionFiller(FakeModel(by_claim(answers)), conn, template=DRAFT)
    para = "Item 1 holds this exchange. " + claim("C05").text  # so "Item 1" is written
    out = filler._resolve(claim("C05"), para, _ProposalOut.model_validate(answers["C05"][0]))
    assert out.params["person_ids"] == list(good["sender"].params.person_ids)
    assert out.params["device_ids"] == ["dev:item1"]


def test_stated_windows_read_the_claims_own_words():
    from core.audit.assumption_filler import stated_windows

    (w,) = stated_windows("At about 7:58 p.m. on March 9, 2026, Item 1 placed a call")
    assert (w.raw, w.start.isoformat(), w.end.isoformat()) == (
        "At about 7:58 p.m. on March 9, 2026",
        "2026-03-09T19:50:00",
        "2026-03-09T20:06:00",
    )
    (w,) = stated_windows("no contact between March 20 and March 23, 2026.")
    assert (w.start.day, w.end.day) == (20, 24)
    (w,) = stated_windows("texted REYES 'its done' at 2:31 a.m. on March 5, 2026")
    assert (w.start.hour, w.start.minute, (w.end - w.start).seconds) == (2, 31, 60)
    assert stated_windows("no contact before March 12, 2026") is None  # open: the model's call
    assert stated_windows("sent on 3/12/2026") is None  # month and day order unknown
    assert stated_windows("sent on March 12") is None  # no year anywhere
    assert stated_windows("sent on March 12", "Events of 2026.")[0].start.year == 2026


@pytest.mark.parametrize(
    ("text", "raw", "start", "end"),
    [
        (
            "Between 9 p.m. and 11 p.m. on May 2, 2026, Item 1 sent texts.",
            "Between 9 p.m. and 11 p.m. on May 2, 2026",
            "21:00",
            "23:01",
        ),
        (
            "From 9 p.m. to 11 p.m. on May 2, 2026, Item 1 sent texts.",
            "From 9 p.m. to 11 p.m. on May 2, 2026",
            "21:00",
            "23:01",
        ),
        (
            "Between 9 and 11 p.m. on May 2, 2026, Item 1 sent texts.",
            "Between 9 and 11 p.m. on May 2, 2026",
            "21:00",
            "23:01",
        ),
        ("between 10:15 a.m. and 11:45 a.m. on May 2, 2026", None, "10:15", "11:46"),
        ("between noon and 2 p.m. on May 2, 2026", None, "12:00", "14:01"),
        (
            "At about noon on May 2, 2026, Item 1 called.",
            "At about noon on May 2, 2026",
            "11:52",
            "12:08",
        ),
        ("At noon on May 2, 2026, Item 1 called.", None, "12:00", "12:01"),
        ("At about 9 p.m. on May 2, 2026, Item 1 called.", None, "20:52", "21:08"),
    ],
)
def test_stated_windows_read_times_of_day(text, raw, start, end):
    from core.audit.assumption_filler import stated_windows

    (w,) = stated_windows(text)
    assert (w.start.strftime("%H:%M"), w.end.strftime("%H:%M")) == (start, end)
    assert w.start.date() == w.end.date() == D(2026, 5, 2).date()
    if raw is not None:
        assert w.raw == raw
    check_window(w.start, w.end, w.raw, text, "", "record_time")


@pytest.mark.parametrize(
    "text",
    [
        "At midnight on May 2, 2026, Item 1 called.",  # start or end of the day
        "between 11 and 1 p.m. on May 2, 2026",  # the bare hour cannot take p.m.
        "between 10 p.m. and midnight on May 2, 2026",
        "between 11 p.m. and 1 a.m. on May 2, 2026",  # crosses midnight
        # "about" a range's end is read (tests/test_fill_windows.py); "roughly" is not
        "between roughly 9 and 11 p.m. on May 2, 2026",
        "between 9 p.m. and roughly 11 p.m. on May 2, 2026",
        "between 9 and 11 on May 2, 2026",  # no a.m. or p.m.
        "at 21:00 on May 2, 2026",
    ],
)
def test_stated_windows_leave_unplain_times_to_the_model(text):
    from core.audit.assumption_filler import stated_windows

    assert stated_windows(text) is None


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (D(2026, 5, 2, 23), D(2026, 5, 2, 23, 1)),  # only the last minute
        (D(2026, 5, 2, 21), D(2026, 5, 2, 21, 1)),  # only the first minute
        (D(2026, 5, 2), D(2026, 5, 3)),  # the whole day
    ],
)
def test_check_window_holds_both_ends_of_a_stated_time_range(start, end):
    for raw in ("Between 9 and 11 p.m. on May 2, 2026", "From 9 p.m. to 11 p.m. on May 2, 2026"):
        with pytest.raises(Reject):
            check_window(start, end, raw, raw, "", "record_time")
    raw = "Between 9 and 11 p.m. on May 2, 2026"
    check_window(D(2026, 5, 2, 21), D(2026, 5, 2, 23, 1), raw, raw, "", "record_time")


def test_check_window_refuses_the_whole_day_for_a_stated_noon():
    raw = "At about noon on May 2, 2026"
    with pytest.raises(Reject):
        check_window(D(2026, 5, 2), D(2026, 5, 3), raw, raw, "", "record_time")


@pytest.mark.parametrize(
    ("text", "gap"),
    [
        ('On March 12, 2026, PETROV wrote "meet me at noon".', None),
        ("On March 12, 2026, PETROV wrote 'meet me at 9 p.m.'.", None),
        ("On March 12, 2026, PETROV wrote “see you at noon”.", None),
        ("On March 12, 2026, PETROV wrote 'I'll meet you at noon'.", None),
        ("On March 12, 2026, PETROV wrote ‘I’ll meet you at noon’.", None),
        ("At noon on March 12, 2026, PETROV wrote 'ok'.", "time of day"),  # outside the quote
        ("On March 12, 2026 at 9 p.m., PETROV's phone sent 'ok'.", "time of day"),
    ],
)
def test_a_time_inside_quoted_words_is_not_the_send_time(text, gap):
    from types import SimpleNamespace

    from core.audit.assumption_filler import coverage_gap
    from core.audit.assumptions import Proposal

    c = Claim(id="X", paragraph_id="para:1", text=text, claim_type=ClaimType.COMMUNICATION,
              status=ClaimStatus.ACCEPTED)  # fmt: skip
    window = SimpleNamespace(raw="On March 12, 2026")
    got = coverage_gap(c, [Proposal("record_time", {"window": window}), Proposal("sender", {})])
    assert (got is None) if gap is None else (gap in got)


def test_stated_windows_skip_a_time_inside_quoted_words():
    from core.audit.assumption_filler import stated_windows

    (w,) = stated_windows("On March 12, 2026, PETROV wrote 'noon'.")
    assert (w.start.hour, (w.end - w.start).days) == (0, 1)
    # a time outside the quoted words is read, never skipped into the whole day
    (w,) = stated_windows("On March 12, 2026 at noon, PETROV wrote 'ok'.")
    assert (w.start.hour, w.start.minute, (w.end - w.start).seconds) == (12, 0, 60)
    # a date in the quoted words is the message's: no range for it
    assert stated_windows('PETROV wrote "meet me at noon on March 12, 2026".') == []
    (w,) = stated_windows("On March 11, 2026, PETROV wrote 'see you at noon on March 12'.")
    assert (w.start.day, w.start.hour) == (11, 0)


@pytest.mark.parametrize(
    ("raw", "ok_day"),
    [
        ("after March 3, 2025", 4),  # March 3 itself is not after March 3
        ("after Mar. 3rd, 2025", 4),
        ("on or after March 3, 2025", 3),
        ("since March 3, 2025", 3),
        ("after Monday, March 3, 2025", 4),  # a weekday between "after" and the date
    ],
)
def test_an_after_window_starts_the_day_after(raw, ok_day):
    c = f"PETROV had no contact with REYES {raw}."
    for day in (3, 4, 5):
        if day == ok_day:
            check_window(D(2025, 3, day), D(2025, 4, 1), raw, c, "", "no_contact")
        else:
            with pytest.raises(Reject):
                check_window(D(2025, 3, day), D(2025, 4, 1), raw, c, "", "no_contact")
    with pytest.raises(Reject):  # no time of day stated: midnight only
        check_window(D(2025, 3, ok_day, 9), D(2025, 4, 1), raw, c, "", "no_contact")


@pytest.mark.parametrize(
    ("text", "start", "end"),
    [
        ("At 9 p.m. on Monday, March 3, 2025, PETROV texted REYES.", "21:00", "21:01"),
        ("Between 9 and 11 p.m. on Monday, March 3, 2025, PETROV texted.", "21:00", "23:01"),
    ],
)
def test_stated_windows_read_a_time_before_a_weekday_and_date(text, start, end):
    from core.audit.assumption_filler import stated_windows

    (w,) = stated_windows(text)
    assert (w.start.strftime("%H:%M"), w.end.strftime("%H:%M")) == (start, end)
    check_window(w.start, w.end, w.raw, text, "", "record_time")


def test_stated_windows_refuse_a_weekday_that_is_not_the_dates():
    from core.audit.assumption_filler import stated_windows

    assert stated_windows("At 9 p.m. on Tuesday, March 3, 2025, PETROV texted REYES.") is None
    assert stated_windows("On Tuesday, March 3, 2025, PETROV texted REYES.") is None
    assert stated_windows("On Monday, March 3, 2025, PETROV texted REYES.")[0].start.day == 3


@pytest.mark.parametrize(
    "raw",
    [
        "after Tuesday, March 3, 2025",  # March 3, 2025 is a Monday
        "On Tuesday, March 3, 2025",
        "at 9 p.m. on Tuesday, March 3, 2025",
    ],
)
def test_check_window_refuses_a_weekday_that_is_not_the_dates(raw):
    for start in (D(2025, 3, 3), D(2025, 3, 3, 21), D(2025, 3, 4)):
        with pytest.raises(Reject):
            check_window(start, D(2025, 3, 5), raw, raw, "", "no_contact")


@pytest.mark.parametrize("raw", ["two days after March 3, 2025", "shortly after March 3, 2025"])
def test_check_window_refuses_a_range_offset_from_a_date(raw):
    for day in (3, 4, 5):
        with pytest.raises(Reject):
            check_window(D(2025, 3, day), D(2025, 4, 1), raw, raw, "", "no_contact")


@pytest.mark.parametrize(("cid", "change", "why"), BAD)
def test_bad_values_drop_the_proposal_and_the_claim_stays_unproven(conn, cid, change, why):
    assumptions, filler, _ = build(conn, cid, _one(cid, **change))
    assert assumptions == []
    reasons = " | ".join(d.reason for d in filler.drops)
    assert why in reasons
    assert "stays unproven" in reasons  # the key template did not survive


# ---------------------------------------------------------------- guards (run 2 replay)
# Run 2's replay found claims "tested" on assumptions that misstate them: the addressee
# checked as the sender, the claim's own words searched as a message, and a sender naming two
# parties that counted for coverage and was then dropped. A sender check on the wrong person
# can fail on a true claim, and a failed check contradicts it without an expert.


def test_the_addressee_is_never_the_sender(conn):
    # C05 "PETROV wrote to @northstar: ...": @northstar is who it went to.
    quote = "need 2 more by friday"
    answers = {"C05": [P("sender", handles=["@northstar"], quoted_text=quote)]}
    assumptions, filler, _ = build(conn, "C05", answers)
    assert "as the one the message went to" in filler.drops[0].reason
    # Code then reads the writer the claim names ("PETROV wrote"), never the addressee.
    senders = [a for a in assumptions if a.template_id == "sender"]
    assert [(a.params.person_ids, a.params.handles) for a in senders] == [((PETROV,), ())]


@pytest.mark.parametrize(
    ("value", "text", "quoted", "addressed"),
    [
        ("@northstar", "PETROV wrote to @northstar: 'ok'.", "ok", True),
        ("PETROV", "PETROV wrote to @northstar: 'ok'.", "ok", False),
        ("REYES", "PETROV texted REYES 'its done'.", "its done", True),
        ("REYES", "PETROV told REYES by Signal: 'its done'.", "its done", True),
        (
            "+1 (212) 555-0122",
            "PETROV's iMessage to +1 (212) 555-0122, 'ok', shows it.",
            "ok",
            True,
        ),
        ("dp", 'PETROV wrote to the Instagram user "dp": "ok"', "ok", True),
        ("dp", 'The Instagram user "dp" wrote to PETROV: "ok"', "ok", False),
        # Written once as the writer: not only the addressee.
        ("PETROV", "REYES wrote to PETROV, and PETROV wrote back 'fine'.", "fine", False),
        # A name inside the quoted message is words, not a place the claim writes the party.
        ("REYES", "PETROV wrote to REYES 'REYES, call me'.", "REYES, call me", True),
        ("SOKOLOV", "PETROV wrote 'ok'.", "ok", False),  # not written: not judged here
        # "from" or "by" after the "to" names the sender; "according to" names a source.
        ("PETROV", "The message to the group from PETROV: 'ok'.", "ok", False),
        ("PETROV", "A message to REYES by PETROV read 'ok'.", "ok", False),
        ("REYES", "According to REYES, PETROV wrote 'ok'.", "ok", False),
        # A new clause ends the recipient's phrase (Codex on #160).
        ("PETROV", "REYES texted back after PETROV wrote 'ok'.", "ok", False),
        ("REYES", "PETROV texted REYES, who replied 'ok'.", "ok", False),
        ("REYES", "PETROV texted REYES, who then wrote 'ok'.", "ok", False),
        # A quote wrapped over two lines is still one quote.
        ("REYES", "PETROV wrote to REYES 'REYES,\ncall me'.", "REYES,\ncall me", True),
    ],
)
def test_only_addressed(value, text, quoted, addressed):
    assert only_addressed(value, text, quoted) is addressed


def test_a_message_is_quoted_words_not_the_claims_own(conn):
    # "call" or "wrote to" in a claim is the claim's wording, not a message anyone wrote.
    answers = {"C05": [P("sender", people=["PETROV"], quoted_text="wrote to")]}
    assumptions, filler, _ = build(conn, "C05", answers)
    assert "not inside quotation marks" in filler.drops[0].reason
    assert {a.params.quoted_text for a in assumptions} == {"need 2 more by friday"}


def test_a_quote_wrapped_over_two_lines_is_still_quoted():
    # Ingest keeps a PDF's line breaks inside claim text (Codex on #160).
    assert _in_quotes("need 2 more", 'PETROV wrote "need 2 more\nby friday".')
    assert not _in_quotes("wrote", 'PETROV wrote "need 2 more\nby friday".')


def test_a_quoted_name_is_not_a_message(conn):
    # C09 "... the number saved as "Marc Garage"": the quoted words name the party.
    garage = {"as_written": "Marc Garage", "app": "Phone"}
    answers = {"C09": [{**GOOD["C09"][0], "accounts": [garage], "quoted_text": "Marc Garage"}]}
    assumptions, filler, _ = build(conn, "C09", answers)
    assert assumptions == []
    assert "a party's name, not a message" in filler.drops[0].reason


def test_a_sender_the_builder_drops_does_not_count_for_coverage(conn):
    # C16: a sender naming PETROV and the dp_garage account is two parties, which the
    # builder drops. It must not count as testing the claim, nor lend its parties to a time
    # range made by code; the claim stays unproven instead of being tested on its time alone.
    quote = "got the money, come get it"
    answers = {"C16": [P("sender", people=["PETROV"], accounts=[DP_GARAGE], quoted_text=quote)]}
    assumptions, filler, _ = build(conn, "C16", answers)
    assert assumptions == []
    reasons = " | ".join(d.reason for d in filler.drops)
    assert "name exactly one party" in reasons
    assert "stays unproven" in reasons


def test_unknown_person_is_dropped(conn):
    answers = {"C18": [P("person_identity", people=["ALEXANDER SOKOLOV"], handles=["@northstar"])]}
    assumptions, filler, _ = build(conn, "C18", answers)
    assert assumptions == []
    assert "matches no person" in filler.drops[0].reason


def test_meaning_claim_without_a_meaning_assumption_gets_it_from_its_quote(conn):
    # C06: the model checks only the easy part (who sent it, when) and skips the meaning.
    # Code adds the meaning of the one quoted message, which only the expert can accept.
    quote = "the package will be at marcs"
    answers = {"C06": [P("sender", handles=["@northstar"], quoted_text=quote)]}
    assumptions, filler, _ = build(conn, "C06", answers)
    assert not filler.drops, filler.drops
    got = {a.template_id: a.params.quoted_text for a in assumptions}
    assert got == {"sender": quote, "record_time": quote, "meaning": quote}


def test_meaning_claim_keeps_meaning(conn):
    quote = "the package will be at marcs"
    sent = P(
        "record_time",
        handles=["@northstar"],
        quoted_text=quote,
        window=W("on March 12, 2026", "2026-03-12T00:00", "2026-03-13T00:00"),
    )
    assumptions, filler, _ = build(conn, "C06", {"C06": [P("meaning", quoted_text=quote), sent]})
    assert not filler.drops, filler.drops
    assert {a.template_id for a in assumptions} == {"meaning", "record_time"}
    # Without the time range, the stated date would go untested.
    assumptions, filler, _ = build(conn, "C06", {"C06": [P("meaning", quoted_text=quote)]})
    assert assumptions == []
    assert "states a date" in filler.drops[-1].reason


def test_claim_is_not_judged_on_its_easy_parts(conn):
    # A quoted message whose writer the claim does not name: its time alone does not test
    # it. (A sender alone gets its date from code, test_a_dated_quote_gets_its_time_...; a
    # named writer gets its sender from code, test_code_adds_the_sender_the_claim_names.)
    text = 'On March 12, 2026, @northstar was sent "need 2 more by friday".'
    keep = [p for p in GOOD["C05"] if p["template_id"] == "record_time"]
    assumptions, filler = build_text(conn, text, ClaimType.COMMUNICATION, keep)
    assert assumptions == []
    assert "who sent it" in filler.drops[-1].reason


def build_text(conn, text: str, claim_type: ClaimType, props: list[dict]):
    """Build a claim of these words (in C05's paragraph) from this model answer."""
    filler = LocalAssumptionFiller(
        FakeModel(json.dumps({"assumptions": props})), conn, template=DRAFT
    )
    c = Claim(
        id="X1",
        paragraph_id=claim("C05").paragraph_id,
        text=text,
        claim_type=claim_type,
        status=ClaimStatus.ACCEPTED,
    )
    return TemplateAssumptionBuilder(filler).build(c), filler


def test_code_adds_the_sender_the_claim_names(conn):
    # C05 with only its time range: "PETROV wrote to @northstar: ..." names the writer.
    keep = [p for p in GOOD["C05"] if p["template_id"] == "record_time"]
    assumptions, filler, _ = build(conn, "C05", {"C05": keep})
    assert not filler.drops, filler.drops
    (sender,) = [a for a in assumptions if a.template_id == "sender"]
    assert sender.params.person_ids == (PETROV,)
    assert sender.params.quoted_text == "need 2 more by friday"


def test_any_claim_that_quotes_a_message_needs_its_sender(conn):
    # A content claim quoting a message is not tested with its writer unchecked.
    quote = "need 2 more by friday"
    text = f'On March 12, 2026, @northstar was sent "{quote}", meaning more drugs.'
    window = W("On March 12, 2026", "2026-03-12T00:00", "2026-03-13T00:00")
    props = [P("meaning", quoted_text=quote), P("record_time", quoted_text=quote, window=window)]
    assumptions, filler = build_text(conn, text, ClaimType.CONTENT_MEANING, props)
    assert assumptions == []
    assert "who sent it" in filler.drops[-1].reason


@pytest.mark.parametrize(
    ("text", "quote"),
    [
        ('PETROV wrote to @northstar: "need 2 more by friday".', "need 2 more by friday"),
        ('A message reading "ok" shows it.', "ok"),
        ('The note: "ok".', "ok"),
        # A quoted name is no message, so the one quote left is.
        ('The Instagram user "dp_garage" wrote: "ok".', "ok"),
        # Two messages: code never picks one.
        ('PETROV wrote "ok" and then "fine".', None),
        # No verb of saying or colon before it: the claim's own words in quotation marks.
        ('PETROV is a "friend".', None),
        # A saved name the verb before it is far from (case01's Mac run, ¶13.3).
        ("PETROV wrote in Russian to the contact saved as ' Mischa ' that he was worried.", None),
        # Only a name in quotation marks.
        ('The Instagram user "dp_garage" sent it.', None),
        # A quote over two lines is refused for a code-made assumption.
        ('PETROV wrote "need 2\nmore".', None),
    ],
)
def test_the_quote(conn, text, quote):
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    c = Claim(
        id="X1",
        paragraph_id="p",
        text=text,
        claim_type=ClaimType.CONTENT_MEANING,
        status=ClaimStatus.ACCEPTED,
    )
    assert filler.the_quote(c, []) == quote


def test_the_quote_is_the_one_a_kept_proposal_uses(conn):
    from core.audit.assumptions import Proposal

    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    c = Claim(
        id="X1",
        paragraph_id="p",
        text='PETROV wrote "ok" and then wrote "fine".',
        claim_type=ClaimType.CONTENT_MEANING,
        status=ClaimStatus.ACCEPTED,
    )
    used = [Proposal("sender", {"quoted_text": "fine", "person_ids": [PETROV]})]
    assert filler.the_quote(c, used) == "fine"
    both = [*used, Proposal("record_time", {"quoted_text": "ok"})]
    assert filler.the_quote(c, both) is None
    # The model's words must lie in a quote that is a message, not a saved name.
    c = c.model_copy(update={"text": 'PETROV wrote to the contact saved as "fine" at noon.'})
    assert filler.the_quote(c, used) is None


def test_dropping_the_time_of_day_is_refused(conn):
    (p,) = GOOD["C10"]
    whole_day = {**p, "window": W("on March 5, 2026", "2026-03-05T00:00", "2026-03-06T00:00")}
    assumptions, filler, _ = build(conn, "C10", {"C10": [whole_day]})
    assert assumptions == []
    assert "time of day" in filler.drops[-1].reason


@pytest.mark.parametrize("raw", ["not json", '{"assumptions": "none"}', "", RuntimeError("x")])
def test_bad_output_gives_no_assumptions_and_is_recorded(conn, raw):
    filler = LocalAssumptionFiller(FakeModel(raw), conn, template=DRAFT)
    assert TemplateAssumptionBuilder(filler).build(claim("C14")) == []
    (call,) = filler.recorder.calls
    assert call.outcome in (ModelCallOutcome.INVALID_OUTPUT, ModelCallOutcome.ERROR)
    assert filler.drops[0].model_call_id == call.id


def test_extra_field_in_a_proposal_is_dropped(conn):
    (p,) = GOOD["C14"]
    answers = {"C14": [{**p, "is_core": False}]}
    assumptions, filler, _ = build(conn, "C14", answers)
    assert assumptions == []
    assert "wrong shape" in filler.drops[0].reason


# ---------------------------------------------------------------- pure helpers


def test_date_mentions():
    ms = date_mentions("From March 10 through March 31, 2026; March 20 to 23; 3/9/2026")
    got = {(m.month, m.day, m.year) for m in ms}
    assert {(3, 10, 2026), (3, 31, 2026), (3, 20, None), (3, 23, None), (3, 9, 2026)} <= got


@pytest.mark.parametrize(
    ("claim_text", "value", "op"),
    [
        ("Item 1 recorded 13 Telegram messages", 13, "eq"),
        ("at least 13 messages", 13, "ge"),
        ("13 messages or more", 13, "ge"),
        ("at most 4 texts", 4, "le"),
        ("From March 10 to March 31, 2026, PETROV and @northstar exchanged 13 messages", 13, "eq"),
        ("13 messages to and from @northstar", 13, "eq"),
        ("13 messages from March 10 to March 31", 13, "eq"),
        ("PETROV and REYES exchanged 13 messages from 9 a.m. to noon", 13, "eq"),
        # Both directions together, as the count check counts (Codex on #160).
        ("PETROV sent and received a total of 13 messages with REYES", 13, "eq"),
        # Calls are counted too (validation fill f); the filler puts 'call' in the channels.
        ("at most 13 calls", 13, "le"),
        ("the TARGET PHONE had four Viber calls with (919) 888-7386", 4, "eq"),
        ("Item 1 holds 13 messages with REYES, incoming and outgoing", 13, "eq"),
    ],
)
def test_count_op(claim_text, value, op):
    assert count_op(claim_text, value) == op


@pytest.mark.parametrize(
    "claim_text",
    [
        "about 13 messages",
        "more than 13 messages",
        "on March 13 they met",
        # The count check counts messages or calls, in both directions between the parties.
        "Item 1 called @northstar 13 times",
        "PETROV sent @northstar 13 messages",
        "On March 12, PETROV sent exactly 13 Telegram messages to @northstar",
        "Item 1 holds 13 messages from @northstar",
        "REYES received 13 texts",
        # One way, written after the count (Baker Eval on #160).
        "13 messages were sent by PETROV to @northstar",
        "13 messages that PETROV sent",
        "On March 12, 13 messages went from PETROV to @northstar",
        "Of the 13 messages, PETROV sent all of them",
        # Refused on purpose: a word of one direction anywhere in the claim refuses its
        # count, even about something else. That costs coverage, never a wrong verdict.
        "After PETROV sent the photo, the two exchanged 13 messages",
        "Item 1 holds 13 incoming messages from REYES",
        # Calls one side placed: the count check counts both directions (Codex on #169).
        "On March 12, 2026, dev:item1 had 13 outgoing Signal calls with (212) 555-0199",
        "On March 12, 2026, dev:item1 made 13 calls to (212) 555-0199",
        "PETROV placed 13 Viber calls with REYES",
        "Item 1 shows 13 missed calls with REYES",
        "dev:item1 had 13 calls with (212) 555-0199, each lasting more than ten minutes",
    ],
)
def test_count_op_refuses(claim_text):
    with pytest.raises(Reject):
        count_op(claim_text, 13)


def test_window_before_and_first():
    c = "PETROV first made contact with @northstar on March 12, 2026."
    raw = "first made contact with @northstar on March 12, 2026"
    check_window(D(2026, 1, 1), D(2026, 3, 12), raw, c, "", "no_contact")
    with pytest.raises(Reject):  # "first" opens the start only for no_contact
        check_window(D(2026, 1, 1), D(2026, 3, 12), raw, c, "", "record_time")
    with pytest.raises(Reject):  # no year anywhere
        check_window(D(2026, 3, 12), D(2026, 3, 13), "On March 12", "On March 12 he left", "")
    with pytest.raises(Reject):  # no time stated: whole days only
        check_window(
            D(2026, 3, 12, 9), D(2026, 3, 13), "On March 12, 2026", "On March 12, 2026", ""
        )


def test_every_template_has_help():
    from core.audit.assumption_filler import TEMPLATE_HELP

    assert set(TEMPLATES) <= set(TEMPLATE_HELP)


@pytest.mark.parametrize(
    ("words", "rng"),
    [
        ("about two minutes", (90, 150)),
        ("two minutes", (120, 179)),
        ("about 30 seconds", (22, 38)),
        ("a minute", (60, 119)),
        ("approximately one hour", (2700, 4500)),
        # halves, to the half the words state
        ("a minute and a half", (90, 119)),
        ("one and a half minutes", (90, 119)),
        ("about one and a half minutes", (68, 112)),
        ("half an hour", (1800, 3599)),
        # two parts, to the second
        ("two minutes and 30 seconds", (150, 150)),
        ("1 minute, 30 seconds", (90, 90)),
        ("forty-five seconds", (45, 45)),
        ("twenty two minutes", (1320, 1379)),
        # a bound is an open range: up to a day, or from 1 second
        ("more than a minute and a half", (91, 86400)),
        ("at least two minutes", (120, 86400)),
        ("under two minutes", (1, 119)),
        ("no more than two minutes", (1, 120)),
    ],
)
def test_duration_range(words, rng):
    from core.audit.assumption_filler import duration_range

    assert duration_range(words) == rng


def test_a_bound_the_claim_writes_before_the_models_words_is_read():
    from core.audit.assumption_filler import duration_range

    assert duration_range("two minutes", "a call lasting more than two minutes") == (121, 86400)
    assert duration_range("two minutes", "a call lasting two minutes") == (120, 179)
    with pytest.raises(Reject, match="more than once"):
        duration_range("two minutes", "one call of about two minutes and one of two minutes")


def test_a_bound_after_the_duration_is_read_after_a_name_whose_lower_case_is_longer():
    from core.audit.assumption_filler import duration_range

    # "İ" lower-cases to two characters: an index found in a lower-cased copy would read the
    # words after the length from the wrong place and miss "or more".
    with pytest.raises(Reject, match="bound after"):
        duration_range("two minutes", "İSMAİL İNCİ called REYES for two minutes or more.")


@pytest.mark.parametrize(
    ("words", "claim"),
    [
        # a bound turned round: read as written, it would mean the opposite
        ("two minutes", "a call lasting not more than two minutes"),
        ("more than two minutes", "a call lasting not more than two minutes"),
        ("two minutes", "a call of not less than two minutes"),
        ("two minutes", "a call that was not under two minutes"),
        ("two minutes", "a call that never lasted over two minutes"),
        ("two minutes", "a call that wasn't more than two minutes"),
        # a bound after the length: read as written, it would be a plain length
        ("two minutes", "a call of two minutes or less"),
        ("two minutes", "a call of two minutes or more"),
        ("two minutes", "a call of two minutes or longer"),
        ("two minutes", "a call of two minutes, or so"),
        ("two minutes", "a call of two minutes plus"),
        ("two minutes or less", ""),
        ("not more than two minutes", ""),
        # typographic apostrophes and "cannot" turn a bound round too (Codex on #153)
        ("under two minutes", "a call that wasn\u2019t under two minutes"),
        ("over two minutes", "a call that didn\u2019t last over two minutes"),
        ("two minutes", "a call that couldn\u02bct have lasted more than two minutes"),
        ("more than two minutes", "the call cannot have lasted more than two minutes"),
    ],
)
def test_a_turned_round_or_trailing_bound_is_refused(words, claim):
    from core.audit.assumption_filler import duration_range

    with pytest.raises(Reject):
        duration_range(words, claim)


@pytest.mark.parametrize(
    ("words", "claim"),
    [
        ("more than a minute", "a call lasting more than a minute and a half"),
        ("a minute", "a call lasting a minute and a half"),
        ("at least two minutes", "a call lasting at least two minutes and 30 seconds"),
        ("two minutes", "a call lasting two minutes, thirty seconds"),
        ("two minutes", "a call lasting two minutes and twenty two seconds"),
        ("30 seconds", "a call lasting two minutes and 30 seconds"),
        ("30 seconds", "a call lasting 1 min., 30 seconds"),
    ],
)
def test_words_that_are_only_part_of_the_claims_length_are_refused(words, claim):
    """Codex on #153: "more than a minute" taken from "more than a minute and a half" was read
    as 61 seconds to a day, so a call shorter than the claim allows could count."""
    from core.audit.assumption_filler import duration_range

    with pytest.raises(Reject, match="goes on past"):
        duration_range(words, claim)


def test_the_whole_length_and_lengths_beside_other_words_still_read():
    from core.audit.assumption_filler import duration_range

    half = "a call lasting more than a minute and a half"
    assert duration_range("more than a minute and a half", half) == (91, 86400)
    assert duration_range("a minute and a half", half) == (91, 86400)
    parts = "a call lasting two minutes and 30 seconds"
    assert duration_range("two minutes and 30 seconds", parts) == (150, 150)
    # a length followed by other words, or by a second call, is still read
    assert duration_range("two minutes", "a call of two minutes and a second call at 9 p.m.") == (
        120,
        179,
    )
    assert duration_range("two minutes", "the second call lasted two minutes") == (120, 179)
    assert duration_range("two minutes", "a call lasting two minutes and then a text") == (
        120,
        179,
    )


def test_no_more_and_no_less_than_stay_bounds():
    from core.audit.assumption_filler import duration_range

    assert duration_range("two minutes", "a call of no more than two minutes") == (1, 120)
    assert duration_range("two minutes", "a call of no less than two minutes") == (120, 86400)
    assert duration_range(
        "two minutes", "PETROV did not answer, and the call lasted two minutes"
    ) == (
        120,
        179,
    )


def test_the_claims_whole_lead_counts_when_the_models_words_carry_part_of_it():
    """Codex on #153: the model's "more than two minutes" taken from the claim's "no more than
    two minutes" was read as more than two minutes, the claim's bound turned round."""
    from core.audit.assumption_filler import duration_range

    no_more, no_less = "a call of no more than two minutes", "a call of no less than two minutes"
    assert duration_range("more than two minutes", no_more) == (1, 120)
    assert duration_range("less than two minutes", no_less) == (120, 86400)
    assert duration_range("over two minutes", "a call of just over two minutes") == (121, 86400)
    assert duration_range("more than two minutes", "a call of more than two minutes") == (
        121,
        86400,
    )


@pytest.mark.parametrize(
    "words",
    ["a while", "2m", "a few minutes", "just two minutes", "under a second", "zero seconds",
     "between one and two minutes", "two minutes and three minutes",
     # half seconds (Codex on #153): "at least ten and a half seconds" read as 10 seconds
     "ten and a half seconds", "at least ten and a half seconds", "10 seconds and a half",
     "half a second"],
)  # fmt: skip
def test_duration_range_refuses(words):
    from core.audit.assumption_filler import duration_range

    with pytest.raises(Reject):
        duration_range(words)


def _outcomes(conn, cid: str) -> list[tuple]:
    """Each assumption the filler builds for the claim, and what its checks found."""
    from core.audit.checks import run_checks

    out = []
    for a in build(conn, cid)[0]:
        found = [(r.check_name, r.outcome, r.record_ids) for r in run_checks(a, conn)]
        out.append((a.template_id, a.params.model_dump_json(), found))
    return out


@pytest.mark.parametrize("cid", ["C03", "C16"])
def test_a_phone_zone_written_the_way_a_ufdr_writes_it_is_read(conn, cid):
    """A Cellebrite Reader 7.48 UFDR writes the phone's zone as '(UTC-05:00)  New_York
    (America)'; the validation run on a public phone had every time range refused on it. The
    same case with the UFDR's wording gets the same assumptions and check outcomes."""
    (was,) = conn.execute("SELECT timezone FROM devices WHERE id = 'dev:item1'").fetchone()
    assert was == "America/New_York"
    iana = _outcomes(conn, cid)
    assert any(found for *_, found in iana)  # the checks ran on a time range
    conn.execute(
        "UPDATE devices SET timezone = '(UTC-05:00)  New_York  (America)' WHERE id = 'dev:item1'"
    )
    try:
        assert _outcomes(conn, cid) == iana
        if cid == "C03":
            assert build(conn, "C03")[0][0].params.window.tz == "America/New_York"
    finally:
        conn.execute("UPDATE devices SET timezone = ? WHERE id = 'dev:item1'", (was,))


def test_a_ufdr_zone_whose_offset_disagrees_is_still_refused(conn):
    (was,) = conn.execute("SELECT timezone FROM devices WHERE id = 'dev:item1'").fetchone()
    conn.execute(
        "UPDATE devices SET timezone = '(UTC+03:00)  New_York  (America)' WHERE id = 'dev:item1'"
    )
    try:
        windows = [a.params.window for a in build(conn, "C03")[0] if a.params.window]
        assert all(w.tz != "America/New_York" for w in windows)
    finally:
        conn.execute("UPDATE devices SET timezone = ? WHERE id = 'dev:item1'", (was,))


def test_the_run_records_the_filler_version(conn):
    from core.audit import assumption_filler

    class Model(FakeModel):
        name, sha256 = "fake", "ab" * 32

    filler = assumption_filler.create(conn, model=Model("{}"))
    (run,) = filler.model_runs
    assert run.params["code_version"] == assumption_filler.FILLER_VERSION


def test_a_phones_own_accounts_stand_for_the_phone_written_as_an_account(conn):
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    text = "Item 1's Telegram account and @alex92 exchanged 3 messages."
    own = filler._own_accounts("Item 1", "Telegram", text)
    assert own == {"acct:item1:Telegram:7001001"}
    assert filler._own_accounts("Item 1", "Instagram", text) == set()  # the claim names no app
    assert filler._own_accounts("Item 3", "Telegram", text) == set()  # no such phone
    assert filler._own_accounts("Item 1", "SMS", "Item 1 texted") == set()  # never a phone app


@pytest.mark.parametrize(
    ("text", "value", "op"),
    [
        ("PETROV and REYES exchanged thirteen messages.", 13, "eq"),
        ("PETROV and REYES exchanged at least twenty-one texts.", 21, "ge"),
        ("PETROV and REYES exchanged 13 messages.", 13, "eq"),
    ],
)
def test_count_op_reads_numbers_in_words(text, value, op):
    assert count_op(text, value) == op


def test_count_op_never_reads_a_as_one():
    with pytest.raises(Reject):
        count_op("PETROV and REYES exchanged a message.", 1)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        # Codex on #164: one part of a longer number is no count.
        ("PETROV and REYES exchanged twenty one messages.", 20),
        ("PETROV and REYES exchanged twenty one messages.", 1),
        ("PETROV and REYES exchanged one hundred messages.", 1),
        ("PETROV and REYES exchanged 1,000 messages.", 1),
        ("PETROV and REYES exchanged 1,000 messages.", 0),
        ("PETROV and REYES exchanged 2.5 thousand messages.", 5),
    ],
)
def test_count_op_reads_only_a_whole_number(text, value):
    with pytest.raises(Reject):
        count_op(text, value)


@pytest.mark.parametrize(
    ("text", "op"),
    [
        # Codex on #164: the words after the whole noun phrase ("text messages") are read.
        ("PETROV and REYES exchanged 13 text messages or more.", "ge"),
        ("PETROV and REYES exchanged 13 text messages or fewer.", "le"),
    ],
)
def test_count_op_reads_past_the_whole_counted_phrase(text, op):
    assert count_op(text, 13) == op


def test_count_op_refuses_one_way_text_messages():
    with pytest.raises(Reject):
        count_op("Item 1 holds 13 text messages from PETROV to REYES.", 13)


@pytest.mark.parametrize(
    "text",
    [
        "On March 12, 2026, on dev:item1, PETROV and REYES had two Telegram video calls.",
        "On March 12, 2026, PETROV and REYES had two audio calls on Telegram.",
    ],
)
def test_count_op_refuses_a_kind_of_call(text):
    # The call log keeps no video or audio kind (Codex on #169).
    with pytest.raises(Reject, match="one kind of call"):
        count_op(text, 2)


def test_one_value_counting_calls_and_messages_is_no_count():
    # The value alone does not say which count a proposal means (Codex on #169).
    from core.audit.assumption_filler import counts_calls

    text = (
        "On March 12, 2026, PETROV and REYES had two Telegram calls and exchanged two Telegram"
        " messages."
    )
    assert not counts_calls(text, 2)
    with pytest.raises(Reject, match="both calls and other records"):
        count_op(text, 2)


@pytest.mark.parametrize(
    "text",
    [
        "On March 12, 2026, on dev:item1, PETROV and REYES had two Telegram calls about narcotics.",
        "On March 12, 2026, PETROV and REYES had two Telegram calls to arrange the meeting.",
        "On March 12, 2026, PETROV and REYES discussed the shipment in two Telegram calls.",
        # a number after "about" is no clock time (Codex on #169)
        "On March 12, 2026, on dev:item1, PETROV and REYES had two Telegram calls about three"
        " kilograms of narcotics.",
    ],
)
def test_count_op_refuses_calls_on_a_subject(text):
    # A call log keeps no subject, so every call would be counted (Codex on #169).
    with pytest.raises(Reject, match="on a subject"):
        count_op(text, 2)
    # a time is not a subject
    assert count_op("At about 9 p.m. on March 12, 2026, PETROV and REYES had two Telegram"
                    " calls.", 2) == "eq"  # fmt: skip


def test_a_call_of_a_kind_the_log_does_not_keep_names_no_app(conn):
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    with pytest.raises(Reject, match="kind of call"):
        filler._call_app("PETROV had a Telegram video call with REYES.", ["call"])


def test_a_count_claim_quoting_only_a_name_needs_no_sender():
    from core.audit.assumption_filler import coverage_gap
    from core.audit.assumptions import Proposal

    # Codex on #164: 'the Telegram user "Marcus R"' is a name, not a message.
    text = 'PETROV sent and received 13 messages with the Telegram user "Marcus R".'
    count = Proposal("message_count", {})
    names = frozenset({"marcus r"})
    c = Claim(id="X", paragraph_id="para:1", text=text, claim_type=ClaimType.COUNT,
              status=ClaimStatus.ACCEPTED)  # fmt: skip
    assert coverage_gap(c, [count], names) is None
    # A quote that is no name still needs its sender, and in a communication claim any does.
    message = c.model_copy(update={"text": text + ' PETROV wrote: "ok".'})
    assert "who sent it" in coverage_gap(message, [count], names)
    talk = c.model_copy(update={"claim_type": ClaimType.COMMUNICATION})
    assert "who sent it" in coverage_gap(talk, [Proposal("record_time", {})], names)


def test_a_code_made_sender_stays_on_the_app_the_claim_names(conn):
    keep = [p for p in GOOD["C05"] if p["template_id"] == "record_time"]
    text = 'On March 12, 2026, PETROV wrote to @northstar on Telegram: "need 2 more by friday".'
    keep = [{**p, "channels": ["Telegram"]} for p in keep]
    assumptions, filler = build_text(conn, text, ClaimType.COMMUNICATION, keep)
    (sender,) = [a for a in assumptions if a.template_id == "sender"]
    assert sender.params.channels == ("Telegram",)


def test_a_code_made_sender_stays_on_the_phone_the_claim_names(conn):
    # Codex on #164: "On Item 1, ..." keeps the sender's search on that phone.
    keep = [
        {**p, "channels": ["Telegram"]} for p in GOOD["C05"] if p["template_id"] == "record_time"
    ]
    text = (
        'On March 12, 2026, on Item 1, PETROV wrote to @northstar on Telegram: "need 2 more by'
        ' friday".'
    )
    assumptions, filler = build_text(conn, text, ClaimType.COMMUNICATION, keep)
    (sender,) = [a for a in assumptions if a.template_id == "sender"]
    assert sender.params.device_ids == ("dev:item1",)


def test_a_code_made_sender_stays_on_the_phones_messages_when_the_claim_names_them(conn):
    # Codex on #164: "texted" or "by iMessage" keeps the search off Telegram and the rest.
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    phone = ["Phone", "SMS"]  # case01's apps that hold a phone's messages
    assert filler._message_apps('PETROV texted REYES: "ok".') == phone
    # "by iMessage" names a kind case01 holds no app for: an iMessage is never read on the
    # SMS app (CodeRabbit on #265), so code makes no sender
    assert filler._message_apps('PETROV told REYES by iMessage: "ok".') is None
    assert filler._message_apps('PETROV texted REYES on Telegram: "ok".') == ["Telegram"]
    assert filler._message_apps('PETROV wrote to REYES: "ok".') == []
    # An app named inside the message is no app it went by.
    assert filler._message_apps('PETROV told REYES by SMS: "use Telegram".') == ["SMS"]
    assert filler._message_apps('PETROV texted REYES: "use Telegram".') == phone


# ---------------------------------------------------------------- PAST-30 fills (validation)


def test_a_dated_quote_with_no_writer_gets_its_time_from_code(conn):
    # Fill a: the claim names no one who sent the words, so code tests when the message was
    # sent, on the app the claim names, with no party; meaning is the model's or code's.
    text = (
        'The Telegram message of March 12, 2026, "the package will be at marcs", shows that the'
        " package held narcotics."
    )
    assumptions, filler = build_text(conn, text, ClaimType.CONTENT_MEANING, [])
    by = {a.template_id: a for a in assumptions}
    assert set(by) == {"meaning", "record_time"}, filler.drops
    t = by["record_time"].params
    assert t.quoted_text == "the package will be at marcs" and t.channels == ("Telegram",)
    assert not (t.person_ids or t.account_ids or t.handles)
    assert t.window is not None and t.window.raw.endswith("March 12, 2026")


@pytest.mark.parametrize(
    "text",
    [
        # a writer the claim names after the quote, or with a verb the cue list reads
        'The Telegram message of March 12, 2026, "the package will be at marcs", which'
        " @northstar sent, held narcotics.",
        'On March 12, 2026, PETROV deleted the Telegram message "the package will be at marcs"'
        " after receiving it from @northstar.",
        'On March 12, 2026, @northstar contacted PETROV by Telegram, writing "the package will be'
        ' at marcs".',
    ],
)
def test_no_time_is_made_without_a_sender_when_the_claim_names_a_writer(conn, text):
    assumptions, filler = build_text(conn, text, ClaimType.CONTENT_MEANING, [])
    assert not any(a.template_id == "record_time" for a in assumptions)


def test_a_time_near_midnight_may_start_on_the_day_before():
    raw = "On May 2, 2023, at approximately 12:01 a.m. EDT"
    check_window(D(2023, 5, 1, 23, 53), D(2023, 5, 2, 0, 10), raw, raw, "", "record_time")
    with pytest.raises(Reject, match="not a date the claim states"):
        check_window(D(2023, 5, 1, 22, 0), D(2023, 5, 2, 0, 10), raw, raw, "", "record_time")
    far = "On May 2, 2023, at approximately 9:00 p.m. EDT"
    with pytest.raises(Reject):
        check_window(D(2023, 5, 1, 20, 52), D(2023, 5, 1, 21, 9), far, far, "", "record_time")
    # "11:59 p.m." on May 2: the evening before is not near it, though its clock time is
    # (Codex on #169)
    late = "On May 2, 2023, at approximately 11:59 p.m. EDT"
    with pytest.raises(Reject, match="not a date the claim states"):
        check_window(D(2023, 5, 1, 23, 53), D(2023, 5, 2, 23, 59), late, late, "", "record_time")


def test_an_identifier_in_brackets_picks_one_of_two_accounts_with_one_name(conn):
    # Fill d: two Telegram accounts carry the display name "Marc Twin"; the claim writes which.
    rows = [
        ("acct:t:twin1", "Telegram", "twin_one_111", "Marc Twin"),
        ("acct:t:twin2", "Telegram", "twin_two_222", "Marc Twin"),
    ]
    src = conn.execute("SELECT source_id FROM accounts LIMIT 1").fetchone()[0]
    for aid, app, ident, name in rows:
        conn.execute(
            "INSERT INTO accounts (id, source_id, locator, device_id, app, identifier,"
            " display_name) VALUES (?, ?, 'x', NULL, ?, ?, ?)",
            (aid, src, app, ident, name),
        )
    try:
        filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
        acc = _Account(as_written="Marc Twin", app="Telegram")
        said = 'PETROV called "Marc Twin" (twin_two_222) on Telegram.'
        assert filler._accounts_named(acc, [], said) == {"acct:t:twin2"}
        with pytest.raises(Reject, match="name of 2 Telegram accounts"):
            filler._accounts_named(acc, [], 'PETROV called "Marc Twin" on Telegram.')
        with pytest.raises(Reject):  # an identifier no account named "Marc Twin" holds
            filler._accounts_named(acc, [], 'PETROV called "Marc Twin" (nobody_9) on Telegram.')
        # The same account on a second phone's extraction is still one account (Codex on #169).
        other = conn.execute(
            "SELECT source_id FROM accounts WHERE source_id != ? LIMIT 1", (src,)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO accounts (id, source_id, locator, device_id, app, identifier,"
            " display_name) VALUES ('acct:t:twin2b', ?, 'x', NULL, 'Telegram', 'twin_two_222',"
            " 'Marc Twin')",
            (other,),
        )
        filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
        assert filler._accounts_named(acc, [], said) == {"acct:t:twin2", "acct:t:twin2b"}
    finally:
        conn.execute(
            "DELETE FROM accounts WHERE id IN ('acct:t:twin1', 'acct:t:twin2', 'acct:t:twin2b')"
        )


def _sender(assumptions):
    return next((a.params for a in assumptions if a.template_id == "sender"), None)


def test_the_one_who_instructed_is_the_writer(conn):
    # Fill b: 'X instructed Y by App to <errand>, writing "..."' names X as the writer.
    text = (
        "On March 12, 2026, PETROV instructed REYES by Telegram to hide the car, writing"
        ' "move it tonight".'
    )
    assumptions, filler = build_text(conn, text, ClaimType.COMMUNICATION, [])
    s = _sender(assumptions)
    assert s is not None, filler.drops
    assert s.person_ids == (PETROV,) and s.channels == ("Telegram",)
    assert s.quoted_text == "move it tonight"


@pytest.mark.parametrize(
    "text",
    [
        # an errand that may bring in another's words or clause
        'PETROV instructed REYES by Telegram to tell his cousin, writing "move it tonight".',
        'PETROV instructed REYES by Telegram to wait and then call, writing "move it tonight".',
        # someone else's instruction
        'A friend of PETROV instructed REYES by Telegram to hide the car, writing "move it'
        ' tonight".',
        # an app the case does not hold
        'PETROV instructed REYES by Wire to hide the car, writing "move it tonight".',
        # a new subject after the quote may be the one writing
        'PETROV instructed REYES by Telegram to hide the car, writing "move it tonight", REYES'
        " said.",
        # the one instructed is the one named first
        'PETROV instructed PETROV by Telegram to hide the car, writing "move it tonight".',
    ],
)
def test_an_instruction_names_no_writer_when_anything_is_in_doubt(conn, text):
    assumptions, _ = build_text(conn, "On March 12, 2026, " + text, ClaimType.COMMUNICATION, [])
    s = _sender(assumptions)
    assert s is None or PETROV not in s.person_ids


def _x1(text: str) -> Claim:
    return Claim(
        id="X1",
        paragraph_id=claim("C05").paragraph_id,
        text=text,
        claim_type=ClaimType.COMMUNICATION,
        status=ClaimStatus.ACCEPTED,
    )


def test_a_deletion_date_dates_no_sending_even_with_a_sender(conn):
    # Fill b names the sender, but March 16 is the deletion's date (Codex on #169).
    text = (
        'On March 16, 2026, REYES deleted the Telegram message "the package will be at marcs"'
        " after receiving it from PETROV."
    )
    assumptions, filler = build_text(conn, text, ClaimType.COMMUNICATION, [])
    assert not any(a.template_id == "record_time" for a in assumptions), filler.drops


def test_a_message_on_an_app_the_case_lacks_gets_no_sender_from_its_receipt(conn):
    # "the Signal message ... after receiving it from REYES" on a case with no Signal: the
    # sender search would run on every app (Codex on #169).
    text = 'PETROV kept the Signal message "move it tonight" after receiving it from REYES.'
    assumptions, filler = build_text(conn, text, ClaimType.COMMUNICATION, [])
    assert not any(c.casefold() == "signal" for c in filler.channels())
    assert not any(a.template_id == "sender" for a in assumptions), filler.drops


def test_the_one_a_message_was_received_from_sent_it(conn):
    # Fill b: '... "words" after receiving it from X.' names X as the sender: a person, or one
    # account on the one app the claim names, by its exact identifier.
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    q = "move it tonight"
    said = 'On March 12, 2026, REYES deleted the Telegram message "move it tonight" after'
    assert filler.received_from(_x1(f"{said} receiving it from PETROV."), q) == {
        "person_ids": [PETROV]
    }
    got = filler.received_from(_x1(f"{said} receiving it from 7001001."), q)
    assert got == {"account_ids": ["acct:item1:Telegram:7001001", "acct:item2:Telegram:7001001"]}
    for text in (
        f"{said} receiving it from 9999999.",  # no such account
        f"{said} receiving it from Dan P.",  # a display name is no identifier
        f"{said} receiving it from PETROV, who wrote it.",  # not the end of the claim
        'On March 12, 2026, REYES forwarded the Telegram message "move it tonight" after'
        " receiving it from PETROV.",  # handed on
        'On March 12, 2026, REYES texted Dre "move it tonight" after receiving it from'
        " PETROV.",  # a writer verb before the quote names another writer
        'On March 12, 2026, REYES deleted the Telegram message "move it tonight" from WhatsApp'
        " after receiving it from 7001001.",  # not right after the quote
        # the words before say whose message it is (Codex on #169)
        'On March 12, 2026, REYES kept PETROV\'s Telegram message "move it tonight" after'
        " receiving it from 7001001.",
        'On March 12, 2026, REYES kept a Telegram message from PETROV, "move it tonight", after'
        " receiving it from 7001001.",
        'On March 12, 2026, REYES kept the Telegram message written by PETROV, "move it'
        ' tonight", after receiving it from 7001001.',
    ):
        assert filler.received_from(_x1(text), q) is None, text


def test_an_open_time_on_one_stated_day_is_the_rest_or_the_start_of_that_day():
    # Fill c.
    w = stated_part_day("On May 7, 2023, there was no Wickr contact after 10:00 a.m. EDT.")
    assert w is not None
    assert (w.start, w.end, w.zone) == (D(2023, 5, 7, 10, 0), D(2023, 5, 8, 0, 0), "EDT")
    assert w.raw == "May 7, 2023, after 10:00 a.m. EDT"
    w = stated_part_day("On May 7, 2023, no call was placed before 9 a.m.")
    assert w is not None and (w.start, w.end) == (D(2023, 5, 7), D(2023, 5, 7, 9, 0))
    for text in (
        "On May 7, 2023, no call was placed after about 9 a.m.",  # "about"
        "On May 7, 2023, no call was placed after 9 a.m. or before 7 a.m.",  # two times
        "On May 7 and May 8, 2023, no call was placed after 9 a.m.",  # two days
        "On May 7, no call was placed after 9 a.m.",  # no year
        "On May 7, 2023, no call was placed after midnight.",  # midnight is not read
        "After May 7, 2023, no call was placed after 9 a.m.",  # an open date
        "On 5/7/2023, no call was placed after 9 a.m.",  # a numeric date
        "On Monday, May 7, 2023, no call was placed after 9 a.m.",  # not that date's weekday
        "On May 7, 2023, at 9 a.m., a call was placed.",  # no open time
        # more days than the one stated (Codex on #169)
        "From May 7, 2023 onward, there was no contact between PETROV and REYES before 9 a.m.",
        "On May 7, 2023 and every day after, no call was placed before 9 a.m.",
        # the day's own zone, which the time's would not carry (Codex on #169)
        "On May 7, 2023 UTC, there was no contact with REYES after 10:00 a.m.",
        "On May 7, 2023 (UTC), there was no contact with REYES after 10:00 a.m.",
        # an offset on the time (Codex on #169)
        "On May 7, 2023, there was no contact with REYES starting two hours after 10:00 a.m.",
        # the stated part is the one left out (Codex on #169)
        "On May 7, 2023, there was no contact between PETROV and REYES except after 10:00 a.m.",
        "On May 7, 2023, there was no contact with REYES other than before 9 a.m.",
    ):
        assert stated_part_day(text) is None, text


def test_the_phone_written_as_an_account_is_its_exact_owner_beside_another_account(conn):
    # "no Telegram contact between dev:item1 and 5551234": the checks read every account id as
    # one party, so the phone's side becomes PETROV, the owner by confirmed stipulation, whose
    # accounts are exactly the phone's own.
    text = "On March 12, 2026, there was no Telegram contact between dev:item1 and 5551234."
    prop = {
        "template_id": "no_contact",
        "accounts": [
            {"as_written": "dev:item1", "app": "Telegram"},
            {"as_written": "5551234", "app": "Telegram"},
        ],
        "channels": ["Telegram"],
        "window": {
            "as_written": "On March 12, 2026",
            "start": "2026-03-12T00:00",
            "end": "2026-03-13T00:00",
            "zone": "phone",
        },
    }
    assumptions, filler = build_text(conn, text, ClaimType.ABSENCE, [prop])
    (a,) = [a for a in assumptions if a.template_id == "no_contact"]
    assert a.params.person_ids == (PETROV,)
    assert a.params.account_ids == ("acct:item1:Telegram:5551234", "acct:item2:Telegram:5551234")
    # An owner with an account elsewhere is wider than the phone: refused, never widened.
    filler.data.links.append(("link:x", "acct:item2:Telegram:7001077", PETROV))
    own = {aid for aid, acc in filler.data.accounts.items() if acc.device_id == "dev:item1"}
    assert filler._exact_owner(own) is None


def test_one_number_written_two_ways_is_one_number():
    # Ruling R6: the same digits, only the formatting differs. A user id stays apart.
    from core.audit.assumption_filler import _same_number
    from core.audit.checks._common import Account

    def acc(app: str, ident: str) -> Account:
        return Account("a", "s", None, app, ident, None)

    n = "19198887386"
    for app, ident in [
        ("unknown", "9198887386"),
        ("unknown", "19198887386"),
        ("unknown", "+19198887386"),
        ("Phone", "9198887386"),
        ("WhatsApp", "(919) 888-7386"),
        ("WhatsApp", "19198887386@s.whatsapp.net"),
        ("Viber", "+1 (919) 888-7386"),
    ]:
        assert _same_number(n, acc(app, ident)), (app, ident)
    for app, ident in [
        ("Telegram", "9198887386"),  # a user id of ten digits
        ("unknown", "29198887386"),
        ("unknown", "919888738"),
        ("Signal", "9198887386"),
    ]:
        assert not _same_number(n, acc(app, ident)), (app, ident)
    # Same ten digits, another country code: two numbers, never one party.
    uk = "449198887386"
    for app, ident in [
        ("unknown", "9198887386"),
        ("unknown", "+19198887386"),
        ("WhatsApp", "(919) 888-7386"),
        ("WhatsApp", "19198887386@s.whatsapp.net"),
        ("Viber", "+1 (919) 888-7386"),
    ]:
        assert not _same_number(uk, acc(app, ident)), (app, ident)
    assert _same_number(uk, acc("WhatsApp", "+44 919 888 7386"))
    assert not _same_number(n, acc("WhatsApp", "+44 919 888 7386"))


@pytest.fixture
def call_log(conn):
    # The phone's call log stores one number two ways, as a UFDR from two databases does.
    src = conn.execute("SELECT source_id FROM accounts WHERE id LIKE 'acct:item1:%'").fetchone()[0]
    rows = [("acct:t:log1", "+12125550199"), ("acct:t:log2", "2125550199")]
    for aid, ident in rows:
        conn.execute(
            "INSERT INTO accounts (id, source_id, locator, device_id, app, identifier,"
            " display_name) VALUES (?, ?, 'x', NULL, 'unknown', ?, 'Mom')",
            (aid, src, ident),
        )
    yield conn
    conn.execute("DELETE FROM accounts WHERE id IN ('acct:t:log1', 'acct:t:log2')")


def test_a_call_on_no_app_to_a_number_is_searched_in_the_call_log(call_log):
    # Ruling R1: no app named, the other party written as a number: the phone's call log.
    text = (
        "On March 12, 2026, at approximately 9:00 p.m., dev:item1 placed an outgoing telephone"
        " call to (212) 555-0199."
    )
    prop = {"template_id": "record_time", "channels": ["call"]}
    assumptions, filler = build_text(call_log, text, ClaimType.COMMUNICATION, [prop])
    (t,) = [a.params for a in assumptions if a.template_id == "record_time"]
    assert t.account_ids == ("acct:t:log1", "acct:t:log2"), filler.drops
    assert t.channels == ("call", "unknown") and t.device_ids == ("dev:item1",)


@pytest.mark.parametrize("app", ["call", "Call", "calls"])
def test_a_number_the_model_puts_on_the_call_channel_is_read_in_the_call_log(call_log, app):
    # A model that writes the channel ("call") as the account's app means the call log, when
    # the claim names no app (R1): seen on the iOS 15 rerun, 2026-11-10.
    text = (
        "On March 12, 2026, at approximately 9:00 p.m., dev:item1 placed an outgoing telephone"
        " call to (212) 555-0199."
    )
    prop = {"template_id": "record_time", "channels": ["call"],
            "accounts": [{"as_written": "(212) 555-0199", "app": app}]}  # fmt: skip
    assumptions, filler = build_text(call_log, text, ClaimType.COMMUNICATION, [prop])
    (t,) = [a.params for a in assumptions if a.template_id == "record_time"]
    assert t.account_ids == ("acct:t:log1", "acct:t:log2"), filler.drops


@pytest.mark.parametrize(
    "text",
    [
        "On March 12, 2026, PETROV had no contact with (212) 555-0199 on dev:item1.",
        "On March 12, 2026, there were no calls between dev:item1 and (212) 555-0199.",
    ],
)
def test_the_call_channel_as_an_app_is_never_the_call_log_for_an_absence(call_log, text):
    # Read on the call log alone, an absence would miss texts with the number (Greptile on #253).
    window = W("On March 12, 2026", "2026-03-12T00:00", "2026-03-13T00:00")
    prop = {"template_id": "no_contact", "phones": ["dev:item1"], "window": window,
            "accounts": [{"as_written": "(212) 555-0199", "app": "call"}]}  # fmt: skip
    assumptions, filler = build_text(call_log, text, ClaimType.ABSENCE, [prop])
    made = [a.params for a in assumptions if a.template_id == "no_contact"]
    assert not any(set(p.account_ids) & {"acct:t:log1", "acct:t:log2"} for p in made), made


def test_the_call_channel_as_an_app_is_not_the_call_log_when_the_claim_names_an_app(call_log):
    text = (
        "On March 12, 2026, at approximately 9:00 p.m., dev:item1 had a Telegram call with"
        " (212) 555-0199."
    )
    prop = {"template_id": "record_time", "channels": ["call"],
            "accounts": [{"as_written": "(212) 555-0199", "app": "call"}]}  # fmt: skip
    assumptions, filler = build_text(call_log, text, ClaimType.COMMUNICATION, [prop])
    made = [a.params for a in assumptions if a.template_id == "record_time"]
    assert not any(set(p.account_ids) & {"acct:t:log1", "acct:t:log2"} for p in made), made


@pytest.mark.parametrize(
    "text",
    [
        "On March 12, 2026, at approximately 9:00 p.m., dev:item1 had a Signal call with"
        " (212) 555-0199.",
        "On March 12, 2026, at approximately 9:00 p.m., dev:item1 had a FaceTime call with"
        " (212) 555-0199.",
        "On March 12, 2026, at approximately 9:00 p.m., dev:item1 had a video call with"
        " (212) 555-0199.",
    ],
)
def test_a_call_on_an_app_the_case_lacks_is_not_the_call_log(call_log, text):
    # The case holds no Signal or FaceTime: the call log does not stand in (Codex on #169).
    prop = {"template_id": "record_time", "channels": ["call"]}
    assumptions, filler = build_text(call_log, text, ClaimType.COMMUNICATION, [prop])
    assert not any(a.template_id == "record_time" for a in assumptions), filler.drops


def test_a_number_written_as_the_call_logs_own_identifier_is_one_number(call_log):
    # "+12125550199" is both a number and the log's identifier; read once, it is one party
    # (Codex on #169).
    text = "On March 12, 2026, at approximately 9:00 p.m., dev:item1 had a call with +12125550199."
    prop = {"template_id": "record_time", "channels": ["call"]}
    assumptions, filler = build_text(call_log, text, ClaimType.COMMUNICATION, [prop])
    (t,) = [a.params for a in assumptions if a.template_id == "record_time"]
    assert t.account_ids == ("acct:t:log1", "acct:t:log2"), filler.drops


@pytest.mark.parametrize(
    "text",
    [
        # a display name with no app
        'On March 12, 2026, at approximately 9:00 p.m., dev:item1 placed a call to "Mom".',
        # a person with no app: the call log is read by number only
        "On March 12, 2026, at approximately 9:00 p.m., PETROV placed a call to (212) 555-0199.",
    ],
)
def test_a_call_on_no_app_is_refused_without_a_number_as_its_party(call_log, text):
    prop = {"template_id": "record_time", "channels": ["call"]}
    assumptions, filler = build_text(call_log, text, ClaimType.COMMUNICATION, [prop])
    assert not any(a.template_id == "record_time" for a in assumptions)
    why = ("only with a phone number", "names 0 apps for the call")
    assert any(w in d.reason for d in filler.drops for w in why), filler.drops


def test_code_made_assumptions_say_so_and_model_ones_do_not(conn):
    # Fill g: an assumption code filled from the claim's wording says so in its text, which the
    # expert reads before accepting it; one the model filled whole does not.
    from core.audit.assumptions import is_code_made

    text = (
        "On March 12, 2026, PETROV instructed REYES by Telegram to hide the car, writing"
        ' "move it tonight".'
    )
    assumptions, _ = build_text(conn, text, ClaimType.COMMUNICATION, [])
    made = {a.template_id: a for a in assumptions}
    assert is_code_made(made["sender"].text) and is_code_made(made["record_time"].text)
    assert made["sender"].text.endswith("Filled from the claim's wording.")
    # C05's and C16's time ranges name the writer alone; code adds the one each went to
    # (@northstar, REYES), so the time check tests both sides (_add_recipient), and the row
    # says code filled it.
    # C10's and C11's time ranges and C16's sender are searched on no app, for claims that
    # say "texted", "the Telegram message" and "on Instagram"; code binds each to the app the
    # claim names, for "texted" the case's one app of a phone's own messages (filler 12,
    # `_bind_named_app`).
    recipient = {"C05": {"record_time"}, "C16": {"record_time", "sender"}}
    recipient |= {"C10": {"record_time"}, "C11": {"record_time"}}
    for cid in sorted(GOOD):
        model_made, *_ = build(conn, cid)
        whole = [
            a
            for a in model_made
            if a.template_id not in {t for t, _ in CODE_ADDS.get(cid, [])}
            and a.template_id not in recipient.get(cid, set())
        ]
        assert not any(is_code_made(a.text) for a in whole if a.template_id != "meaning"), cid
    (timed,) = [a for a in build(conn, "C05")[0] if a.template_id == "record_time"]
    assert is_code_made(timed.text) and timed.params.handles == ("@northstar",)
    (timed,) = [a for a in build(conn, "C16")[0] if a.template_id == "record_time"]
    assert is_code_made(timed.text) and timed.params.person_ids == (REYES,)


def test_a_count_of_calls_is_read_and_made_from_a_calls_time(call_log):
    # Fill f: the claim counts calls on no named app to a number; the model gave one call's
    # time. Code adds the count over the call log, with the phone's side as its exact owner.
    from core.audit.assumption_filler import stated_call_count

    assert stated_call_count("the TARGET PHONE had five calls with (828) 520-5789.") == 5
    assert stated_call_count("PETROV called REYES 13 times") is None
    assert stated_call_count("four calls and then two calls") is None
    assert stated_call_count("about five calls") is None
    assert stated_call_count("dev:item1 had two outgoing calls with (212) 555-0199.") is None
    text = "On March 12, 2026, dev:item1 had two calls with (212) 555-0199."
    prop = {"template_id": "record_time", "channels": ["call"]}
    assumptions, filler = build_text(call_log, text, ClaimType.COUNT, [prop])
    by = {a.template_id: a for a in assumptions}
    assert "message_count" in by, filler.drops
    c = by["message_count"].params
    assert (c.count_op, c.expected_count) == ("eq", 2)
    assert c.channels == ("call", "unknown") and c.person_ids == (PETROV,)
    assert c.account_ids == ("acct:t:log1", "acct:t:log2") and c.device_ids == ("dev:item1",)
    assert by["message_count"].text.endswith("Filled from the claim's wording.")
    assert "calls between" in by["message_count"].text


def test_no_count_is_made_from_the_time_of_one_call_among_them(call_log):
    # A time that dates one of the calls is not the count's span (Codex on #169).
    text = (
        "On March 12, 2026, at approximately 9:00 p.m., dev:item1 had the last of two calls"
        " with (212) 555-0199."
    )
    window = {"as_written": "On March 12, 2026, at approximately 9:00 p.m.",
              "start": "2026-03-12T20:52", "end": "2026-03-12T21:09", "zone": "phone"}  # fmt: skip
    prop = {"template_id": "record_time", "channels": ["call"], "window": window}
    assumptions, filler = build_text(call_log, text, ClaimType.COUNT, [prop])
    assert not any(a.template_id == "message_count" for a in assumptions), filler.drops


def test_a_model_count_of_calls_dated_by_one_call_is_refused(conn):
    # The model's own count window is the one call's time, not the count's (Codex on #169).
    text = (
        "On March 12, 2026, on dev:item1, PETROV and REYES had two Telegram calls, including a"
        " call at approximately 9:00 p.m."
    )
    window = {"as_written": "On March 12, 2026, on dev:item1, PETROV and REYES had two Telegram"
              " calls, including a call at approximately 9:00 p.m.", "start": "2026-03-12T20:52",
              "end": "2026-03-12T21:09", "zone": "phone"}  # fmt: skip
    prop = {"template_id": "message_count", "count": {"value": 2}, "channels": ["Telegram"],
            "people": ["PETROV", "REYES"], "phones": ["dev:item1"], "window": window}  # fmt: skip
    assumptions, filler = build_text(conn, text, ClaimType.COUNT, [prop])
    assert not any(a.template_id == "message_count" for a in assumptions)
    assert any("dates one of the calls" in d.reason for d in filler.drops), filler.drops


def test_a_model_count_of_calls_takes_the_written_phones_zone(call_log):
    # The model gave no phone; code reads it from the claim, and the window takes its zone even
    # when the case's phones are in different zones (Codex on #169).
    call_log.execute("UPDATE devices SET timezone = 'America/Los_Angeles' WHERE id = 'dev:item2'")
    try:
        text = "On March 12, 2026, dev:item1 had two calls with (212) 555-0199."
        window = {"as_written": "On March 12, 2026", "start": "2026-03-12T00:00",
                  "end": "2026-03-13T00:00", "zone": "phone"}  # fmt: skip
        prop = {"template_id": "message_count", "count": {"value": 2}, "channels": ["call"],
                "window": window}  # fmt: skip
        assumptions, filler = build_text(call_log, text, ClaimType.COUNT, [prop])
        (c,) = [a.params for a in assumptions if a.template_id == "message_count"]
        assert c.device_ids == ("dev:item1",), filler.drops
        assert c.window is not None and c.window.tz == "America/New_York"
    finally:
        call_log.execute("UPDATE devices SET timezone = 'America/New_York' WHERE id = 'dev:item2'")


def test_a_model_party_for_calls_must_be_the_claims_one_party(conn):
    # The model named REYES only; the claim names REYES and SMITH, so the phone's owner is no
    # side of these calls (Codex on #169).
    text = "On March 12, 2026, on dev:item1, REYES and SMITH had two Telegram calls."
    window = {"as_written": "On March 12, 2026", "start": "2026-03-12T00:00",
              "end": "2026-03-13T00:00", "zone": "phone"}  # fmt: skip
    prop = {"template_id": "message_count", "count": {"value": 2}, "channels": ["Telegram"],
            "people": ["REYES"], "phones": ["dev:item1"], "window": window}  # fmt: skip
    assumptions, filler = build_text(conn, text, ClaimType.COUNT, [prop])
    assert not any(a.template_id == "message_count" for a in assumptions)
    assert any("not the claim's one party" in d.reason or "one side" in d.reason
               for d in filler.drops), filler.drops  # fmt: skip


@pytest.mark.parametrize(
    "text",
    [
        "On dev:item1, there was no contact between PETROV and REYES except before March 12, 2026.",
        "dev:item1 never communicated with (212) 555-0144 other than after March 12, 2026.",
    ],
)
def test_an_open_range_left_out_by_an_exception_is_not_read(text):
    # The open side is the one the claim exempts (Codex on #169).
    from core.audit.assumption_filler import _open_range_wording

    assert not _open_range_wording(text)


def _no_contact(conn, text: str, **prop):
    return build_text(conn, text, ClaimType.ABSENCE, [{"template_id": "no_contact", **prop}])


def test_never_runs_to_the_extractions_own_edges(conn):
    # Ruling R5: "never" is the whole extraction, read from the phone's dated records; the
    # sides are the phone's exact owner and the one number the claim writes.
    assumptions, filler = _no_contact(
        conn, "dev:item1 never communicated with (212) 555-0144.", phones=["dev:item1"]
    )
    (a,) = [a for a in assumptions if a.template_id == "no_contact"]
    p = a.params
    assert p.person_ids == (PETROV,) and p.device_ids == ("dev:item1",)
    assert p.account_ids == ("acct:item1:Phone:+12125550144", "acct:item1:SMS:+12125550144")
    assert p.window is not None and p.window.raw.startswith(
        "never: from the extraction's first dated record"
    )
    lo, hi = conn.execute(
        "SELECT min(t), max(t) FROM (SELECT ts_utc t FROM messages WHERE source_id = 'item1'"
        " UNION ALL SELECT ts_utc FROM calls WHERE source_id = 'item1') WHERE t IS NOT NULL"
    ).fetchone()
    assert p.window.raw.endswith("so contact outside its records is not seen")
    assert p.window.start_utc.isoformat()[:19] == lo[:19]
    assert p.window.end_utc.isoformat()[:19] == hi[:19]
    assert a.text.endswith("Filled from the claim's wording.")


def test_an_embedded_copy_sets_no_extraction_edge(conn):
    # The absence check's coverage leaves embedded copies out, so the edges must too: an
    # older copy inside a message would stretch the window past what the source spans (Codex
    # on #169).
    tid = conn.execute("SELECT thread_id FROM messages WHERE source_id = 'item1'").fetchone()[0]
    conn.execute(
        "INSERT INTO messages (id, source_id, locator, thread_id, direction, ts_utc, ts_raw,"
        " body) VALUES ('msg:copy', 'item1', 'x/Embedded[0]', ?, 'unknown',"
        " '2020-01-02T00:00:00Z', '2020-01-02', 'old words')",
        (tid,),
    )
    try:
        assumptions, _ = _no_contact(
            conn, "dev:item1 never communicated with (212) 555-0144.", phones=["dev:item1"]
        )
    finally:
        conn.execute("DELETE FROM messages WHERE id = 'msg:copy'")
    (a,) = [a for a in assumptions if a.template_id == "no_contact"]
    assert a.params.window is not None and a.params.window.start_utc.year > 2020


def test_before_a_date_runs_from_the_first_record_whatever_the_model_said(conn):
    # The model's one-day range for "before March 12" would test only March 11; code's range
    # runs from the extraction's first record to the start of March 12.
    window = {"as_written": "before March 12, 2026", "start": "2026-03-11T00:00",
              "end": "2026-03-12T00:00", "zone": "phone"}  # fmt: skip
    assumptions, filler = _no_contact(
        conn,
        "There was no contact between dev:item1 and (212) 555-0144 before March 12, 2026.",
        phones=["dev:item1"],
        window=window,
    )
    (a,) = [a for a in assumptions if a.template_id == "no_contact"]
    w = a.params.window
    assert w is not None and w.raw.startswith("before March 12, 2026: from the extraction's")
    assert w.end_utc.astimezone(ZoneInfo("America/New_York")).isoformat()[:19] == (
        "2026-03-11T23:59:59"
    )
    assert w.start_utc < D(2026, 3, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    ("text", "open_"),
    [
        ("dev:item1 never communicated with X.", True),
        ("no contact before March 12, 2026", True),
        ("no contact since March 12, 2026", True),
        # Both ends stated, a written zone, a time of day: the model's range, read as before
        # (Codex on #169).
        ("no contact from March 10, 2026 until March 12, 2026", False),
        ("no contact between March 10 and 12, 2026, nor after", False),
        ("no contact before March 12, 2026 UTC", False),
        ("no contact before March 12, 2026 (ET)", False),
        ("no contact before 3/12/2026", False),
        ("no contact after 9:00 p.m. on March 12, 2026", False),
        ("they first made contact after March 12, 2026", False),
        ("no contact on March 12, 2026", False),
        ("no contact starting two days after March 12, 2026", False),
        ("no contact in the weeks before March 12, 2026", False),
    ],
)
def test_only_an_open_range_runs_to_the_extractions_edge(text, open_):
    from core.audit.assumption_filler import _open_range_wording

    assert _open_range_wording(text) is open_


def test_an_open_range_takes_its_year_from_the_paragraph(conn):
    # "before March 12" with the year only in the paragraph (Codex on #169).
    assumptions, filler = _no_contact(
        conn,
        "There was no contact between dev:item1 and (212) 555-0144 before March 12.",
        phones=["dev:item1"],
    )
    (a,) = [a for a in assumptions if a.template_id == "no_contact"]
    w = a.params.window
    assert w is not None and w.raw.startswith("before March 12: from"), filler.drops
    assert w.end_utc.astimezone(ZoneInfo("America/New_York")).date().isoformat() == "2026-03-11"


@pytest.mark.parametrize("app", ["Signal", "Viber"])
def test_a_dated_quote_on_an_app_the_case_lacks_gets_no_senderless_time(conn, app):
    # "The Signal message" on a case with no Signal: a time on every app could match the
    # words on Telegram (Codex on #169).
    text = (
        f'The {app} message of March 12, 2026, "the package will be at marcs", shows that the'
        " package held narcotics."
    )
    assumptions, filler = build_text(conn, text, ClaimType.CONTENT_MEANING, [])
    assert not any(c.casefold() == app.casefold() for c in filler.channels())
    assert not any(a.template_id == "record_time" for a in assumptions)


@pytest.mark.parametrize(
    "text",
    [
        # The date may be another act's, not the sending's (Codex on #169).
        'On March 16, 2026, REYES deleted the Telegram message "the package will be at marcs".',
        'On March 16, 2026, the Telegram message "the package will be at marcs" was deleted.',
        'On March 12, 2026, REYES received a Telegram message reading "the package will be at'
        ' marcs".',
        'The Telegram message to REYES of March 12, 2026, "the package will be at marcs", shows'
        " that the package held narcotics.",
    ],
)
def test_a_dated_quote_with_another_party_or_act_gets_no_senderless_time(conn, text):
    # A time on anyone's message would not keep the one it went to (Codex on #169).
    assumptions, _ = build_text(conn, text, ClaimType.CONTENT_MEANING, [])
    for a in assumptions:
        if a.template_id == "record_time":
            assert a.params.person_ids or a.params.account_ids, a.params


def test_a_message_dated_by_its_writers_possessive_gets_no_senderless_time(conn):
    # "PETROV's Telegram message of March 12" names its writer; a time with no party would
    # match anyone's message (Codex on #169).
    text = 'PETROV’s Telegram message of March 12, 2026, "move it tonight".'
    assumptions, _ = build_text(conn, text, ClaimType.COMMUNICATION, [])
    for a in assumptions:
        if a.template_id == "record_time":
            assert a.params.person_ids or a.params.account_ids, a.params


def test_on_or_before_takes_in_the_whole_day(conn):
    # "on or before March 12" includes March 12 (Codex on #169).
    assumptions, filler = _no_contact(
        conn,
        "There was no contact between dev:item1 and (212) 555-0144 on or before March 12, 2026.",
        phones=["dev:item1"],
    )
    (a,) = [a for a in assumptions if a.template_id == "no_contact"]
    w = a.params.window
    assert w is not None and w.raw.startswith("on or before March 12, 2026: from"), filler.drops
    assert w.end_utc.astimezone(ZoneInfo("America/New_York")).isoformat()[:19] == (
        "2026-03-12T23:59:59"
    )


def test_absence_parties_keep_the_app_the_claim_names(conn):
    # "by WhatsApp" is no contact on WhatsApp only, never every app (Codex on #169).
    assumptions, filler = _no_contact(
        conn, "dev:item1 never communicated by WhatsApp with (212) 555-0122.", phones=["dev:item1"]
    )
    (a,) = [a for a in assumptions if a.template_id == "no_contact"]
    assert a.params.channels == ("WhatsApp",), filler.drops
    assert a.params.account_ids == ("acct:item1:WhatsApp:12125550122@s.whatsapp.net",)
    # "texted" may be SMS or iMessage, and a phone app may hold calls: not filled.
    assumptions, filler = _no_contact(
        conn, "dev:item1 never texted (212) 555-0122.", phones=["dev:item1"]
    )
    assert not any(a.template_id == "no_contact" for a in assumptions)
    # A call-only claim is not filled: the absence check would also search messages.
    assumptions, filler = _no_contact(
        conn, "dev:item1 never called (212) 555-0144.", phones=["dev:item1"]
    )
    assert not any(a.template_id == "no_contact" for a in assumptions)
    assert any("call-only" in d.reason for d in filler.drops), filler.drops
    # ... even when the model gave a channel (Codex on #169).
    assumptions, filler = _no_contact(
        conn, "dev:item1 never called (212) 555-0122 on WhatsApp.", phones=["dev:item1"],
        channels=["WhatsApp"],
    )  # fmt: skip
    assert not any(a.template_id == "no_contact" for a in assumptions)


@pytest.mark.parametrize("channels", [None, ["WhatsApp"]])
@pytest.mark.parametrize(
    "text",
    [
        # Messages only: a WhatsApp call would fail it (Codex on #169).
        "dev:item1 never texted (212) 555-0122 on WhatsApp.",
        "dev:item1 never sent a message to (212) 555-0122 on WhatsApp.",
        "dev:item1 never spoke with (212) 555-0122 on WhatsApp.",
    ],
)
def test_absence_parties_refuse_one_kind_of_contact(conn, text, channels):
    extra = {"channels": channels} if channels else {}
    assumptions, filler = _no_contact(conn, text, phones=["dev:item1"], **extra)
    assert not any(a.template_id == "no_contact" for a in assumptions)
    assert any("one-kind" in d.reason for d in filler.drops), filler.drops


@pytest.mark.parametrize("app", ["Signal", "Viber"])
def test_absence_parties_refuse_an_app_the_case_lacks(conn, app):
    # No such app in the case: the scope cannot be kept, so it is never widened (Codex on #169).
    assumptions, filler = _no_contact(
        conn, f"dev:item1 never communicated by {app} with (212) 555-0144.", phones=["dev:item1"]
    )
    assert not any(c.casefold() == app.casefold() for c in filler.channels())
    assert not any(a.template_id == "no_contact" for a in assumptions)
    assert any("does not hold" in d.reason for d in filler.drops), filler.drops


def test_never_on_a_stated_day_keeps_the_days_own_range(conn):
    # "On March 12, 2026, ... never" is that day, not an open range (Codex on #169).
    window = {"as_written": "On March 12, 2026",
              "start": "2026-03-12T00:00", "end": "2026-03-13T00:00", "zone": "phone"}  # fmt: skip
    assumptions, filler = _no_contact(
        conn,
        "On March 12, 2026, dev:item1 never communicated with (212) 555-0144.",
        phones=["dev:item1"],
        window=window,
    )
    (a,) = [a for a in assumptions if a.template_id == "no_contact"]
    assert a.params.window is not None, filler.drops
    assert "extraction" not in a.params.window.raw


@pytest.mark.parametrize(
    "text",
    [
        "During 2025, dev:item1 never communicated with (212) 555-0144.",
        "dev:item1 never communicated with (212) 555-0144 on Mondays.",
        "dev:item1 never communicated with (212) 555-0144 in March.",
        "dev:item1 never communicated with (212) 555-0144 before May 1, 2026 in 2025.",
    ],
)
def test_never_with_another_time_keeps_the_models_range(conn, text):
    # A year, month or weekday the open range would drop (Codex on #169).
    window = {"as_written": "2025", "start": "2025-01-01T00:00", "end": "2026-01-01T00:00",
              "zone": "phone"}  # fmt: skip
    assumptions, _ = _no_contact(conn, text, phones=["dev:item1"], window=window)
    for a in assumptions:
        if a.template_id == "no_contact" and a.params.window is not None:
            assert "extraction" not in a.params.window.raw, text


@pytest.mark.parametrize(
    "text",
    [
        "dev:item1 never sent anything to (212) 555-0144.",
        "dev:item1 never received anything from (212) 555-0144.",
        "dev:item1 never contacted (212) 555-0144.",
    ],
)
def test_absence_parties_refuse_one_direction(conn, text):
    # The absence check reads both ways, so code fills no one-way scope (Codex on #169).
    assumptions, filler = _no_contact(conn, text, phones=["dev:item1"])
    assert not any(a.template_id == "no_contact" for a in assumptions)
    assert any("one-direction" in d.reason for d in filler.drops), filler.drops


@pytest.mark.parametrize(
    "text",
    [
        "dev:item1 never communicated with REYES about narcotics.",
        "dev:item1 never communicated with (212) 555-0144 regarding the package.",
        "dev:item1 never communicated with REYES in person.",
    ],
)
def test_absence_parties_refuse_words_beyond_plain_contact(conn, text):
    # A topic or other scope the absence check cannot keep (Codex on #169).
    assumptions, filler = _no_contact(conn, text, phones=["dev:item1"])
    assert not any(a.template_id == "no_contact" for a in assumptions)
    assert any("more than plain contact" in d.reason for d in filler.drops), filler.drops


def test_an_open_range_reads_the_phone_the_claim_writes(conn):
    # The model gave both people and no phone; the claim writes the phone (Codex on #169).
    assumptions, filler = _no_contact(
        conn,
        "On dev:item1, there was no contact between PETROV and REYES before March 12, 2026.",
        people=["PETROV", "REYES"],
    )
    (a,) = [a for a in assumptions if a.template_id == "no_contact"]
    assert a.params.device_ids == ("dev:item1",), filler.drops
    assert a.params.window is not None and "extraction" in a.params.window.raw


def test_the_extractions_edge_is_kept_as_an_instant_across_a_clock_change(conn):
    # A last record in the repeated hour of a fall-back night (01:30 EST, the second time)
    # ends the range on that instant, not an hour before it (Codex on #169).
    conn.execute(
        "INSERT INTO calls (id, source_id, locator, app, direction, ts_utc, duration_s)"
        " VALUES ('call:dst', 'item1', 'x', 'Phone', 'incoming', '2026-11-01T06:30:00+00:00', 5)"
    )
    try:
        assumptions, filler = _no_contact(
            conn, "dev:item1 never communicated with (212) 555-0144.", phones=["dev:item1"]
        )
        (a,) = [a for a in assumptions if a.template_id == "no_contact"]
        assert a.params.window is not None, filler.drops
        assert a.params.window.end_utc.isoformat()[:19] == "2026-11-01T06:30:00"
    finally:
        conn.execute("DELETE FROM calls WHERE id = 'call:dst'")


def test_a_range_with_both_ends_stated_keeps_its_own_ends(conn):
    window = {"as_written": "from March 10, 2026 until March 12, 2026",
              "start": "2026-03-10T00:00", "end": "2026-03-13T00:00", "zone": "phone"}  # fmt: skip
    assumptions, filler = _no_contact(
        conn,
        "There was no contact between dev:item1 and (212) 555-0144 from March 10, 2026 until"
        " March 12, 2026.",
        phones=["dev:item1"],
        window=window,
    )
    (a,) = [a for a in assumptions if a.template_id == "no_contact"]
    assert a.params.window is not None, filler.drops
    assert "extraction" not in a.params.window.raw
    assert a.params.window.start_utc.astimezone(ZoneInfo("America/New_York")).day == 10


@pytest.mark.parametrize(
    "text",
    [
        "dev:item1 never communicated with (212) 555-0144 or (212) 555-0191.",  # two parties
        "dev:item1 never communicated with @someone.",  # a party code cannot read
        "There was never contact with (212) 555-0144.",  # no phone written
        # Someone else named through the party (Codex on #169).
        "dev:item1 never communicated with REYES's assistant.",
        "dev:item1 never communicated with a friend of REYES.",
        # A name in another clause (Codex on #169).
        "dev:item1 never communicated with SMITH while REYES was abroad.",
        "dev:item1 never communicated with SMITH after REYES left.",
        "dev:item1 never communicated with SMITH; REYES was abroad.",
    ],
)
def test_an_open_range_or_its_sides_are_refused_when_in_doubt(conn, text):
    assumptions, _ = _no_contact(conn, text)
    assert not any(a.template_id == "no_contact" for a in assumptions)


MAR21 = W("On March 21, 2026", "2026-03-21T00:00", "2026-03-22T00:00")


def _count(conn, text: str, value: int | None, **kw):
    kw = {"channels": ["Telegram"], **kw}
    prop = P("message_count", count=None if value is None else {"value": value},
             people=["PETROV", "REYES"], window=MAR21, **kw)  # fmt: skip
    assumptions, filler = build_text(conn, text, ClaimType.COUNT, [prop])
    made = [a for a in assumptions if a.template_id == "message_count"]
    return made, filler


@pytest.mark.parametrize(
    "text, sender",
    [
        (
            "On March 21, 2026, on dev:item1, PETROV sent REYES exactly one Telegram message.",
            PETROV,
        ),
        (
            "On March 21, 2026, on dev:item1, REYES sent exactly one Telegram message to PETROV.",
            REYES,
        ),
        (
            "On March 21, 2026, on dev:item1, Daniel Petrov sent REYES exactly one Telegram"
            " message.",
            PETROV,
        ),
        # the phone written as the sender is its exact owner
        ("On March 21, 2026, dev:item1 sent REYES exactly one Telegram message.", PETROV),
    ],
)
def test_a_count_of_what_one_side_sent_counts_only_that_side(conn, text, sender):
    # Ruling R2: "X sent Y one message" counts X's messages only. That day each sent one, so
    # the two-way count (2) would fail the claim; one side's count passes it.
    made, filler = _count(conn, text, 1, phones=["dev:item1"])
    (a,) = made
    assert a.params.sent_by == (sender,), filler.drops
    assert (a.params.count_op, a.params.expected_count) == ("eq", 1)
    assert "counting only messages" in a.text
    r = CHECKS["count"].run(a, conn)
    assert r.outcome is CheckOutcome.PASS, r.detail
    assert len(r.record_ids) == 1 and "Only messages" in r.searched


@pytest.mark.parametrize(
    "text",
    [
        # passive, two one-way words, a sender the claim does not write before "sent", the
        # sender written on both sides, no other side written after "sent"
        "On March 21, 2026, on dev:item1, exactly one Telegram message was sent by PETROV to"
        " REYES.",
        "On March 21, 2026, on dev:item1, PETROV sent and received exactly one Telegram message.",
        "On March 21, 2026, on dev:item1, the phone sent REYES exactly one Telegram message.",
        "On March 21, 2026, on dev:item1, PETROV sent PETROV and REYES exactly one Telegram"
        " message.",
        "On March 21, 2026, on dev:item1, PETROV sent exactly one Telegram message.",
        # someone's, or someone acted for, is not that side (Baker Eval on #172)
        "On March 21, 2026, on dev:item1, PETROV's lawyer sent REYES exactly one Telegram message.",
        "On March 21, 2026, on dev:item1, PETROV's phone sent REYES exactly one Telegram message.",
        "On March 21, 2026, on dev:item1, a friend of PETROV sent REYES exactly one Telegram"
        " message.",
        "On March 21, 2026, on dev:item1, PETROV sent REYES's lawyer exactly one Telegram message.",
        "On March 21, 2026, on dev:item1, PETROV sent a friend of REYES exactly one Telegram"
        " message.",
        "On March 21, 2026, on dev:item1, PETROV and his lawyer sent REYES exactly one Telegram"
        " message.",
        # a denial is not the plain form (Codex on #172)
        "On March 21, 2026, on dev:item1, PETROV has not sent REYES exactly one Telegram message.",
        "On March 21, 2026, on dev:item1, PETROV never sent REYES exactly one Telegram message.",
        # the other side named in another clause is not the recipient (Codex on #172)
        "On March 21, 2026, on dev:item1, PETROV sent exactly one Telegram message while REYES"
        " was abroad.",
        "On March 21, 2026, on dev:item1, PETROV sent exactly one Telegram message about REYES.",
        # a limit the check does not read: what the messages say (Codex on #172)
        "On March 21, 2026, on dev:item1, PETROV sent REYES exactly one Telegram message about the"
        " delivery.",
        "On March 21, 2026, on dev:item1, PETROV sent REYES exactly one Telegram message"
        " mentioning money.",
    ],
)
def test_a_one_way_count_is_refused_unless_the_words_name_each_side(conn, text):
    made, filler = _count(conn, text, 1, phones=["dev:item1"])
    assert not made, [a.params for a in made]
    assert filler.drops


def test_exchanged_messages_need_one_each_way(conn):
    # Ruling R3: "exchanged" is at least one message each way; with no number, at least two.
    # The phone the claim writes is the one counted, though the model named none.
    text = "On March 21, 2026, PETROV and REYES exchanged Telegram messages on dev:item1."
    made, filler = _count(conn, text, None)
    (a,) = made
    assert a.params.each_way and not a.params.sent_by, filler.drops
    assert (a.params.count_op, a.params.expected_count) == ("ge", 2)
    assert a.params.device_ids == ("dev:item1",)
    assert a.text.endswith("Filled from the claim's wording.")
    assert "with at least one message each way" in a.text
    r = CHECKS["count"].run(a, conn)
    assert r.outcome is CheckOutcome.PASS, r.detail
    assert "sent 1 of them" in r.detail


def test_a_stated_count_of_exchanged_messages_is_still_compared(conn):
    text = (
        "On March 21, 2026, on dev:item1, PETROV and REYES exchanged exactly two Telegram messages."
    )
    made, filler = _count(conn, text, 2, phones=["dev:item1"])
    (a,) = made
    assert a.params.each_way and (a.params.count_op, a.params.expected_count) == ("eq", 2)
    assert CHECKS["count"].run(a, conn).outcome is CheckOutcome.PASS


@pytest.mark.parametrize(
    "text",
    [
        "On March 21, 2026, PETROV and REYES exchanged Telegram messages.",  # no phone written
        "On March 21, 2026, PETROV and REYES exchanged and sent Telegram messages.",  # one-way word
        # a denial is no exchange (Codex on #172)
        "On March 21, 2026, on dev:item1, PETROV and REYES never exchanged Telegram messages.",
        "On March 21, 2026, on dev:item1, PETROV and REYES had not exchanged Telegram messages.",
        "On March 21, 2026, on dev:item1, PETROV and REYES haven't exchanged Telegram messages.",
        # what the messages say is not read (Codex on #172)
        "On March 21, 2026, on dev:item1, PETROV and REYES exchanged Telegram messages about the"
        " delivery.",
        "On March 21, 2026, on dev:item1, PETROV and REYES exchanged Telegram messages that"
        " mention money.",
        # any limit the check does not read, not only topic words (Codex on #172)
        "On March 21, 2026, on dev:item1, PETROV and REYES exchanged Telegram messages in Spanish.",
        "On March 21, 2026, on dev:item1, PETROV and REYES exchanged Telegram messages with photos"
        " attached.",
    ],
)
def test_exchanged_without_one_phone_or_with_a_one_way_word_makes_no_count(conn, text):
    made, filler = _count(conn, text, None)
    assert not any(a.params.each_way for a in made), [a.params for a in made]


@pytest.mark.parametrize(
    "text",
    [
        "On March 21, 2026, on dev:item1, PETROV and REYES exchanged exactly three Telegram"
        " messages.",
        "On March 21, 2026, on dev:item1, PETROV and REYES exchanged dozens of Telegram messages.",
        "On March 21, 2026, on dev:item1, PETROV and REYES exchanged Telegram messages, 3 messages"
        " in all.",
    ],
)
def test_exchanged_with_a_stated_count_the_model_left_out_is_refused(conn, text):
    # Not read as "at least two" (Codex on #172).
    made, filler = _count(conn, text, None)
    assert not made, [a.params for a in made]
    assert any("states how many" in d.reason for d in filler.drops), filler.drops


def test_the_other_side_written_as_its_number_another_way_is_found(conn):
    # The account resolves by number (R6), and the sender reading finds it the same way
    # (Codex on #172).
    text = "On March 21, 2026, on dev:item1, PETROV sent exactly one message to +1 (212) 555-0122."
    marc = {"as_written": "+1 (212) 555-0122", "app": "Phone"}
    prop = P("message_count", count={"value": 1}, people=["PETROV"], phones=["dev:item1"],
             accounts=[marc], window=MAR21)  # fmt: skip
    assumptions, filler = build_text(conn, text, ClaimType.COUNT, [prop])
    (a,) = [a for a in assumptions if a.template_id == "message_count"]
    assert a.params.account_ids == tuple(MARC_0122), filler.drops
    assert a.params.sent_by == (PETROV,)


def test_the_recipient_may_be_written_as_the_app_account_after_to(conn):
    # "sent ... to the Telegram account 7001002": app and "account" words before the
    # identifier still write the recipient (the "another clause" guard, Codex on #172).
    text = (
        "On March 21, 2026, on dev:item1, PETROV sent exactly one Telegram message to the"
        " Telegram account 7001002."
    )
    prop = P("message_count", count={"value": 1}, people=["PETROV"], phones=["dev:item1"],
             channels=["Telegram"], accounts=[{"as_written": "7001002", "app": "Telegram"}],
             window=MAR21)  # fmt: skip
    assumptions, filler = build_text(conn, text, ClaimType.COUNT, [prop])
    (a,) = [a for a in assumptions if a.template_id == "message_count"]
    assert a.params.sent_by == (PETROV,), filler.drops
    assert CHECKS["count"].run(a, conn).outcome is CheckOutcome.PASS


def test_a_recipient_written_by_full_name_is_one_mention(conn):
    # "Marcus Reyes" holds "Reyes"; only the whole name is the mention (Codex on #172).
    text = (
        "On March 21, 2026, on dev:item1, PETROV sent exactly one Telegram message to Marcus Reyes."
    )
    prop = P("message_count", count={"value": 1}, people=["PETROV", "Marcus Reyes"],
             channels=["Telegram"], phones=["dev:item1"], window=MAR21)  # fmt: skip
    assumptions, filler = build_text(conn, text, ClaimType.COUNT, [prop])
    (a,) = [a for a in assumptions if a.template_id == "message_count"]
    assert a.params.sent_by == (PETROV,), filler.drops


@pytest.mark.parametrize(
    "text",
    [
        "On March 21, 2026, on dev:item1, PETROV sent exactly one Telegram message to the"
        " Telegram account 70010023.",
        "On March 21, 2026, PETROV and the Telegram account 70010023 exchanged two Telegram"
        " messages on dev:item1.",
    ],
)
def test_an_identifier_inside_a_longer_one_is_not_the_side(conn, text):
    # The model names account 7001002 for "70010023": its match inside the longer number is
    # not that account, and the "3" left over is not the count (Codex on #172).
    prop = P("message_count", count={"value": 1 if "exactly" in text else 2},
             people=["PETROV"], phones=["dev:item1"], channels=["Telegram"],
             accounts=[{"as_written": "7001002", "app": "Telegram"}], window=MAR21)  # fmt: skip
    assumptions, filler = build_text(conn, text, ClaimType.COUNT, [prop])
    made = [a for a in assumptions if a.template_id == "message_count"]
    assert not any(a.params.each_way or a.params.sent_by for a in made), [a.params for a in made]


@pytest.mark.parametrize(
    "text",
    [
        "On March 21, 2026, PETROV and REYES exchanged two Telegram messages on dev:item1 and"
        " dev:item2.",
        "On March 21, 2026, on dev:item1 and dev:item2, PETROV sent REYES exactly one Telegram"
        " message.",
    ],
)
def test_a_direction_is_not_read_when_the_claim_writes_a_phone_the_count_leaves_out(conn, text):
    # The count searches dev:item1 only; what the claim says of dev:item2 would go untested
    # (Codex on #172).
    made, filler = _count(conn, text, 1 if "exactly" in text else 2, phones=["dev:item1"])
    assert not any(a.params.each_way or a.params.sent_by for a in made), [a.params for a in made]


@pytest.mark.parametrize(
    "text, value",
    [
        # two each is a count per side, not a total (Codex on #172)
        (
            "On March 21, 2026, on dev:item1, PETROV and REYES exchanged exactly two Telegram"
            " messages each.",
            2,
        ),
        # a direct message is not told from a group message by the count (Codex on #172)
        ("On March 21, 2026, PETROV and REYES exchanged Telegram DMs on dev:item1.", None),
        (
            "On March 21, 2026, PETROV and REYES exchanged two Telegram direct messages on"
            " dev:item1.",
            2,
        ),
        ("On March 21, 2026, on dev:item1, PETROV sent REYES exactly one Telegram DM.", 1),
    ],
)
def test_a_direction_is_not_read_with_a_count_per_side_or_direct_messages(conn, text, value):
    made, filler = _count(conn, text, value, phones=["dev:item1"])
    assert not any(a.params.each_way or a.params.sent_by for a in made), [a.params for a in made]


@pytest.mark.parametrize(
    "text, value",
    [
        ("On March 21, 2026, PETROV and REYES exchanged iMessages on dev:item1.", None),
        ("On March 21, 2026, PETROV and REYES exchanged emails on dev:item1.", None),
        ("On March 21, 2026, on dev:item1, PETROV sent REYES exactly one iMessage.", 1),
    ],
)
def test_a_message_noun_that_names_an_app_needs_the_count_kept_to_it(conn, text, value):
    # "iMessages" and "emails" name an app; with no channels the count would search every
    # app (Codex on #172).
    made, filler = _count(conn, text, value, phones=["dev:item1"], channels=[])
    assert not any(a.params.each_way or a.params.sent_by for a in made), [a.params for a in made]


@pytest.mark.parametrize(
    "text",
    [
        "On March 21, 2026, on dev:item1, PETROV sent REYES one to two Telegram messages.",
        "On March 21, 2026, on dev:item1, PETROV and REYES exchanged one to two Telegram messages.",
    ],
)
def test_a_direction_is_not_read_with_a_range_of_counts(conn, text):
    # "one to two" is a range; read as exactly two, one message would fail a true claim
    # (Codex on #172).
    made, filler = _count(conn, text, 2, phones=["dev:item1"])
    assert not any(a.params.each_way or a.params.sent_by for a in made), [a.params for a in made]


@pytest.mark.parametrize(
    "text, value",
    [
        # a count each day is not one count over the days (Codex on #172)
        (
            "Every day from March 21 through March 22, 2026, on dev:item1, PETROV sent REYES"
            " exactly one Telegram message.",
            1,
        ),
        ("Every day, PETROV and REYES exchanged Telegram messages on dev:item1.", None),
        (
            "On March 21, 2026, PETROV and REYES exchanged two Telegram messages per hour on"
            " dev:item1.",
            2,
        ),  # fmt: skip
        # a bound written as a sign is not an exact count (Codex on #172)
        ("On March 21, 2026, on dev:item1, PETROV sent REYES <2 Telegram messages.", 2),
        ("On March 21, 2026, on dev:item1, PETROV sent REYES 2+ Telegram messages.", 2),
        ("On March 21, 2026, PETROV and REYES exchanged ≥2 Telegram messages on dev:item1.", 2),
    ],
)
def test_a_direction_is_not_read_with_a_count_per_period_or_a_bound_sign(conn, text, value):
    made, filler = _count(conn, text, value, phones=["dev:item1"])
    assert not any(a.params.each_way or a.params.sent_by for a in made), [a.params for a in made]


@pytest.mark.parametrize(
    "text",
    [
        "On March 21, 2026, PETROV and REYES exchanged exactly twenty-one Telegram messages on"
        " dev:item1.",
        "On March 21, 2026, on dev:item1, PETROV sent REYES exactly twenty-one Telegram messages.",
    ],
)
def test_a_count_written_as_one_compound_number_is_one_number(conn, text):
    # "twenty-one" is one count, not a range (Codex on #172)
    made, filler = _count(conn, text, 21, phones=["dev:item1"])
    (a,) = made
    assert a.params.each_way or a.params.sent_by, filler.drops
    assert a.params.expected_count == 21


@pytest.mark.parametrize("sender_side", [True, False])
def test_the_accounts_side_is_only_the_accounts_written_there(conn, sender_side):
    # The model may give accounts the paragraph names; the claim's "7001002" is not 7001001,
    # so a count of both would credit the other one (Codex on #172).
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    ids = {a.identifier: a.id for a in filler.data.accounts.values() if a.app == "Telegram"}
    params = {"person_ids": [PETROV], "channels": ["Telegram"],
              "account_ids": [ids["7001002"], ids["7001001"]]}  # fmt: skip
    if sender_side:
        sent = ("the Telegram account 7001002", "PETROV exactly one Telegram message")
    else:
        sent = ("PETROV", "exactly one Telegram message to the Telegram account 7001002")
    with pytest.raises(Reject):
        filler._sent_by(sent, params)
    params["account_ids"] = [ids["7001002"]]
    assert filler._sent_by(sent, params) == ([ids["7001002"]] if sender_side else [PETROV])


def test_an_exchange_holds_only_the_accounts_its_clause_writes(conn):
    # As for "sent": 7001001, given but not written, would have its messages counted for the
    # side the claim writes as 7001002 (Codex on #172).
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    ids = {a.identifier: a.id for a in filler.data.accounts.values() if a.app == "Telegram"}
    text = (
        "On March 21, 2026, PETROV and the Telegram account 7001002 exchanged two Telegram"
        " messages on dev:item1."
    )
    params = {"person_ids": [PETROV], "channels": ["Telegram"],
              "account_ids": [ids["7001002"], ids["7001001"]]}  # fmt: skip
    with pytest.raises(Reject):
        filler._limits_on_exchange(text, params)
    params["account_ids"] = [ids["7001002"]]
    assert filler._limits_on_exchange(text, params) is None


@pytest.mark.parametrize(
    "text, value",
    [
        # a limit before the clause is still a limit (Codex on #172)
        (
            "On March 21, 2026, on dev:item1, in Spanish, PETROV sent REYES exactly one Telegram"
            " message.",
            1,
        ),  # fmt: skip
        (
            "On March 21, 2026, in Spanish, PETROV and REYES exchanged Telegram messages on"
            " dev:item1.",
            None,
        ),  # fmt: skip
    ],
)
def test_a_direction_is_not_read_past_a_limit_before_the_clause(conn, text, value):
    made, filler = _count(conn, text, value, phones=["dev:item1"])
    assert not any(a.params.each_way or a.params.sent_by for a in made), [a.params for a in made]


@pytest.mark.parametrize(
    "text",
    [
        "On March 21, 2026, a Saturday, on dev:item1, PETROV sent REYES exactly one Telegram"
        " message.",
        "On Saturday, March 21, 2026, on dev:item1, PETROV sent REYES exactly one Telegram"
        " message.",
    ],
)
def test_a_date_and_phone_before_the_clause_are_plain(conn, text):
    made, filler = _count(conn, text, 1, phones=["dev:item1"])
    assert any(a.params.sent_by == (PETROV,) for a in made), filler.drops


def test_a_part_of_the_day_is_not_counted_over_the_whole_day(conn):
    # "the morning of" narrows the day; a count over the whole of March 21 would test less.
    text = (
        "On the morning of March 21, 2026, on dev:item1, PETROV sent REYES exactly one Telegram"
        " message."
    )
    made, filler = _count(conn, text, 1, phones=["dev:item1"])
    assert made == [], [a.params for a in made]
    # nor when the model copies only the bare date the claim also writes (Greptile on #253)
    bare = W("March 21, 2026", "2026-03-21T00:00", "2026-03-22T00:00")
    prop = P("message_count", count={"value": 1}, people=["PETROV", "REYES"],
             channels=["Telegram"], phones=["dev:item1"], window=bare)  # fmt: skip
    assumptions, filler = build_text(conn, text, ClaimType.COUNT, [prop])
    made = [a for a in assumptions if a.template_id == "message_count"]
    assert made == [], [a.params for a in made]
    assert any("part code does not read" in d.reason for d in filler.drops), filler.drops


@pytest.mark.parametrize("phrase", ["with each other", "with one another"])
def test_exchanged_with_each_other_is_still_each_way(conn, phrase):
    text = f"On March 21, 2026, PETROV and REYES exchanged Telegram messages {phrase} on dev:item1."
    made, filler = _count(conn, text, None, phones=["dev:item1"])
    (a,) = made
    assert a.params.each_way, filler.drops


@pytest.mark.parametrize(
    "third",
    ["SOKOLOV", "(212) 555-0199"],  # a person the case names, a number
)
def test_an_exchange_with_a_third_party_is_refused(conn, third):
    # The count is between the assumption's two sides; a third written in the clause would be
    # left out of it (Codex on #172).
    conn.execute("INSERT INTO persons VALUES ('person:sokolov', 'Ivan Sokolov', 'expert:test')")
    try:
        text = (
            f"On March 21, 2026, PETROV and REYES exchanged Telegram messages with {third} on"
            " dev:item1."
        )
        made, filler = _count(conn, text, None)
        assert not any(a.params.each_way for a in made), [a.params for a in made]
    finally:
        conn.execute("DELETE FROM persons WHERE id = 'person:sokolov'")


@pytest.mark.parametrize(
    "text, channels",
    [
        # an app the count would not keep to: no channels given (Codex on #172)
        ("On March 21, 2026, PETROV and REYES exchanged Telegram messages on dev:item1.", []),
        ("On March 21, 2026, on dev:item1, PETROV sent REYES exactly one Telegram message.", []),
        # a limit after a comma is still in the clause (Codex on #172)
        (
            "On March 21, 2026, PETROV and REYES exchanged Telegram messages in Spanish, on"
            " dev:item1.",
            ["Telegram"],
        ),
    ],
)
def test_a_direction_is_not_read_past_words_the_count_does_not_keep(conn, text, channels):
    value = 1 if "exactly one" in text else None
    made, filler = _count(conn, text, value, channels=channels)
    assert not any(a.params.each_way or a.params.sent_by for a in made), [a.params for a in made]


def test_the_exchange_clause_is_found_in_the_text_as_written(conn):
    # "ß" case-folds to "ss": an index found in a case-folded copy lands past the clause's
    # true start, and the clause read from it loses the third party written in it.
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    text = (
        "ß" * 60
        + ", PETROV and REYES exchanged Telegram messages with (212) 555-0199, on dev:item1."
    )
    params = {"person_ids": [PETROV, REYES], "channels": ["Telegram"]}
    assert filler._limits_on_exchange(text, params) == "(212) 555-0199"


@pytest.mark.parametrize(
    "text",
    [
        # an earlier "exchanged" that is not about messages: the clause the count reads starts
        # at the later one, and the words before it are a limit (Baker Eval on #190)
        "On March 21, 2026, PETROV exchanged calls with SOKOLOV, and PETROV and REYES exchanged"
        " Telegram messages on dev:item1.",
        "On March 21, 2026, PETROV exchanged photos with SOKOLOV, and PETROV and REYES exchanged"
        " Telegram messages on dev:item1.",
    ],
)
def test_an_earlier_exchange_that_is_not_messages_is_still_a_limit(conn, text):
    conn.execute("INSERT INTO persons VALUES ('person:sokolov', 'Ivan Sokolov', 'expert:test')")
    try:
        made, filler = _count(conn, text, None, phones=["dev:item1"])
        assert not any(a.params.each_way for a in made), [a.params for a in made]
        assert any("before the count" in d.reason for d in filler.drops), filler.drops
    finally:
        conn.execute("DELETE FROM persons WHERE id = 'person:sokolov'")


def test_a_sent_form_code_cannot_place_is_refused(conn, monkeypatch):
    # sent_form and the clause's position read the same words; were they ever to disagree, the
    # claim is refused rather than read from a position code did not find.
    import core.audit.assumption_filler as af

    monkeypatch.setattr(af, "sent_form", lambda claim, value: ("PETROV", "REYES one message"))
    text = "On March 21, 2026, PETROV sent REYES exactly one Telegram message; on dev:item1."
    made, filler = _count(conn, text, 1, phones=["dev:item1"])
    assert not any(a.params.sent_by for a in made), [a.params for a in made]
    assert any("sent form" in d.reason for d in filler.drops), filler.drops


@pytest.fixture
def aliased(conn):
    """PETROV is also called "SUBJECT-1" and "Big Dan" in the document (the expert's entry,
    person_aliases); removed after the test."""
    from core.review import actions

    actions.set_aliases(conn, PETROV, ["SUBJECT-1", "Big Dan"], "expert:test")
    yield conn
    actions.set_aliases(conn, PETROV, [], "expert:test")


def test_an_alias_the_expert_gave_names_that_person(aliased):
    filler = LocalAssumptionFiller(FakeModel(by_claim(GOOD)), aliased, template=DRAFT)
    assert filler._person("SUBJECT-1") == PETROV
    assert filler._person("subject 1") == PETROV  # the alias's letters and digits, any case
    for part in ("SUBJECT", "Dan", "DAN", "Big", "@subject-1", "SUBJECT-12"):  # whole only
        with pytest.raises(Reject):
            filler._person(part)


def test_a_one_way_count_reads_the_sender_by_an_alias(aliased):
    # case04 (#181): the affidavit calls the phone's owner "SUBJECT-1"; the model names him.
    text = "On March 21, 2026, on dev:item1, SUBJECT-1 sent REYES exactly one Telegram message."
    made, filler = _count(aliased, text, 1, phones=["dev:item1"])
    (a,) = made
    assert a.params.sent_by == (PETROV,), filler.drops


def test_exchanged_messages_read_a_side_by_an_alias(aliased):
    text = "On March 21, 2026, SUBJECT-1 and REYES exchanged Telegram messages on dev:item1."
    made, filler = _count(aliased, text, None)
    (a,) = made
    assert a.params.each_way, filler.drops


@pytest.mark.parametrize(
    "text",
    [
        # part of an alias is no name: "Dan" of "Big Dan" is not PETROV
        "On March 21, 2026, on dev:item1, Dan sent REYES exactly one Telegram message.",
        "On March 21, 2026, Dan and REYES exchanged Telegram messages on dev:item1.",
    ],
)
def test_part_of_an_alias_names_no_side(aliased, text):
    made, filler = _count(aliased, text, None if "exchanged" in text else 1, phones=["dev:item1"])
    assert not made, [a.params for a in made]


def test_a_quoted_alias_is_a_name_not_a_message(aliased):
    filler = LocalAssumptionFiller(FakeModel(by_claim(GOOD)), aliased, template=DRAFT)
    assert "subject-1" in filler._names()
    c = Claim(id="X", paragraph_id="para:1", text='REYES wrote to "SUBJECT-1": \'ok\'.',
              claim_type=ClaimType.COMMUNICATION, status=ClaimStatus.ACCEPTED)  # fmt: skip
    assert filler.stated_sender(c, "ok") == REYES


def test_the_writer_is_read_by_an_alias(aliased):
    filler = LocalAssumptionFiller(FakeModel(by_claim(GOOD)), aliased, template=DRAFT)
    c = Claim(id="X", paragraph_id="para:1", text="SUBJECT-1 wrote to REYES: 'ok'.",
              claim_type=ClaimType.COMMUNICATION, status=ClaimStatus.ACCEPTED)  # fmt: skip
    assert filler.stated_sender(c, "ok") == PETROV


def test_an_alias_two_persons_share_names_neither(conn):
    # Entry refuses a shared alias; one stored anyway (an older entry) matches neither person.
    conn.executemany(
        "INSERT INTO person_aliases (person_id, alias, created_by, created_at_utc)"
        " VALUES (?, 'TWIN', 'expert:test', '2026-10-30T00:00:00Z')",
        [(PETROV,), (REYES,)],
    )
    try:
        filler = LocalAssumptionFiller(FakeModel(by_claim(GOOD)), conn, template=DRAFT)
        with pytest.raises(Reject):
            filler._person("TWIN")
        text = "On March 21, 2026, on dev:item1, TWIN sent REYES exactly one Telegram message."
        made, _ = _count(conn, text, 1, phones=["dev:item1"])
        assert not made
    finally:
        conn.execute("DELETE FROM person_aliases WHERE alias = 'TWIN'")


def test_an_alias_is_read_as_every_alias_reader_reads_it(aliased):
    # core/identity/aliases.spans: spacing and punctuation between its words do not count;
    # a longer name or a handle is not the alias.
    filler = LocalAssumptionFiller(FakeModel(by_claim(GOOD)), aliased, template=DRAFT)
    text = "Subject 1 called SUBJECT-12, then @subject-1 and Subject-1A; big  dan's phone"
    spans = filler._person_spans(text)[PETROV]
    assert [text[s:e] for s, e in sorted(spans)] == ["Subject 1", "big  dan"]


@pytest.mark.parametrize(
    "text, writer",
    [
        ("REYES told Big Dan: 'ok'.", REYES),  # the whole alias is one known name
        ("REYES WROTE TO BIG DAN: 'ok'.", REYES),
        ("REYES TOLD SUBJECT-1: 'ok'.", REYES),
        # a word of an alias alone is no name word (Baker Eval on #186)
        ("REYES TOLD BIG: 'ok'.", None),
        ("REYES told SMITH Big: 'ok'.", None),
    ],
)
def test_only_a_whole_alias_is_a_name_between_the_writer_and_the_quote(aliased, text, writer):
    filler = LocalAssumptionFiller(FakeModel(by_claim(GOOD)), aliased, template=DRAFT)
    c = Claim(id="X", paragraph_id="para:1", text=text, claim_type=ClaimType.COMMUNICATION,
              status=ClaimStatus.ACCEPTED)  # fmt: skip
    assert filler.stated_sender(c, "ok") == writer


def test_a_reply_is_not_credited_through_part_of_an_alias(conn):
    # Codex on #186: with the alias "Hot Shot", "REYES SHOT BACK" stays REYES's own clause.
    from core.review import actions

    actions.set_aliases(conn, PETROV, ["Hot Shot"], "expert:test")
    try:
        filler = LocalAssumptionFiller(FakeModel(by_claim(GOOD)), conn, template=DRAFT)
        c = Claim(id="X", paragraph_id="para:1", text="PETROV texted REYES, REYES SHOT BACK 'OK'.",
                  claim_type=ClaimType.COMMUNICATION, status=ClaimStatus.ACCEPTED)  # fmt: skip
        assert filler.stated_sender(c, "OK") is None
    finally:
        actions.set_aliases(conn, PETROV, [], "expert:test")


@pytest.mark.parametrize(
    "text",
    [
        # Codex on #186: an alias written across a new line, a dash or a colon may carry a new
        # label, so it does not stand in as one name between the writer and the quote
        "REYES texted Big\nDan: 'ok'.",
        "REYES texted Big — Dan: 'ok'.",
        "REYES texted Big: Dan: 'ok'.",
    ],
)
def test_an_alias_across_a_label_break_is_no_name_between(aliased, text):
    filler = LocalAssumptionFiller(FakeModel(by_claim(GOOD)), aliased, template=DRAFT)
    c = Claim(id="X", paragraph_id="para:1", text=text, claim_type=ClaimType.COMMUNICATION,
              status=ClaimStatus.ACCEPTED)  # fmt: skip
    assert filler.stated_sender(c, "ok") is None


@pytest.mark.parametrize("written", ["SUBJECT-1", "SUBJECT—1", "SUBJECT_1", "subject 1"])
def test_a_quoted_alias_in_any_spelling_the_matcher_reads_is_a_name(aliased, written):
    # Codex on #186: the quoted name is read as _person reads it, so the one message is found.
    filler = LocalAssumptionFiller(FakeModel(by_claim(GOOD)), aliased, template=DRAFT)
    c = Claim(id="X", paragraph_id="para:1", text=f'REYES wrote to "{written}": "ok".',
              claim_type=ClaimType.COMMUNICATION, status=ClaimStatus.ACCEPTED)  # fmt: skip
    assert filler.the_quote(c, []) == "ok"


def test_a_name_inside_another_persons_alias_is_that_alias(conn):
    # Codex on #186: "Big Reyes" (PETROV's alias) is one designation, not also REYES.
    from core.review import actions

    actions.set_aliases(conn, PETROV, ["Big Reyes"], "expert:test")
    try:
        filler = LocalAssumptionFiller(FakeModel(by_claim(GOOD)), conn, template=DRAFT)
        spans = filler._person_spans("SMITH texted Big Reyes; REYES replied.")
        text = "SMITH texted Big Reyes; REYES replied."
        assert [text[s:e] for s, e in spans[PETROV]] == ["Big Reyes"]
        assert [text[s:e] for s, e in spans[REYES]] == ["REYES"]
    finally:
        actions.set_aliases(conn, PETROV, [], "expert:test")


def test_a_whole_alias_stands_in_whatever_names_the_case_holds(aliased):
    # Codex on #186: a person "B. Smith" must not change how REYES's alias reader works.
    aliased.execute("INSERT INTO persons VALUES ('person:bsmith', 'B. Smith', 'expert:test')")
    try:
        filler = LocalAssumptionFiller(FakeModel(by_claim(GOOD)), aliased, template=DRAFT)
        c = Claim(id="X", paragraph_id="para:1", text="REYES told Big Dan: 'ok'.",
                  claim_type=ClaimType.COMMUNICATION, status=ClaimStatus.ACCEPTED)  # fmt: skip
        assert filler.stated_sender(c, "ok") == REYES
    finally:
        aliased.execute("DELETE FROM persons WHERE id = 'person:bsmith'")


# case05 C04 (a false SUPPORTED, agents bench 2026-11-10): "SUBJECT-1 texted the COURIER from
# the BURNER: ..." kept on one sender row naming only the BURNER's account, so the checks passed
# on who sent the words and never on SUBJECT-1 using the BURNER, or on the day.
ALEX = {"as_written": "@alex92", "app": "Telegram"}
BURNER_TEXT = 'PETROV texted REYES from @alex92 on Telegram: "need 2 more by friday".'


def test_a_named_writer_no_assumption_ties_to_the_account_leaves_the_claim_unproven(conn):
    answer = [P("sender", accounts=[ALEX], quoted_text="need 2 more by friday")]
    assumptions, filler = build_text(conn, BURNER_TEXT, ClaimType.COMMUNICATION, answer)
    assert assumptions == []
    (drop,) = [d.reason for d in filler.drops if "ties them" in d.reason]
    # PETROV wrote it and REYES got it: a sender row tests neither here, and no time row names
    # REYES (Arsh, 2026-11-10: a checked SUPPORTED proves who received the message).
    assert "Daniel Petrov" in drop and "Marcus Reyes" in drop


def test_a_writer_the_assumption_names_is_bound(conn):
    answer = [P("sender", people=["PETROV"], accounts=[ALEX], quoted_text="need 2 more by friday")]
    _, filler = build_text(conn, BURNER_TEXT, ClaimType.COMMUNICATION, answer)
    assert not [d for d in filler.drops if "Daniel Petrov" in d.reason], filler.drops


def test_a_confirmed_link_or_an_owned_phone_binds_the_writer(conn):
    answer = [P("sender", accounts=[ALEX], quoted_text="need 2 more by friday")]
    conn.execute(
        "INSERT INTO identity_links (id, account_id, person_id, status, tier, basis, decided_by,"
        " decided_at_utc) VALUES ('link:test:alex', 'acct:item1:Telegram:5551234', ?,"
        " 'confirmed', 'confirmed', 'test', 'expert:test', '2026-11-10T00:00:00Z')",
        (PETROV,),
    )
    try:
        _, filler = build_text(conn, BURNER_TEXT, ClaimType.COMMUNICATION, answer)
        assert not [d for d in filler.drops if "Daniel Petrov" in d.reason], filler.drops
    finally:
        conn.execute("DELETE FROM identity_links WHERE id = 'link:test:alex'")
    # dp_garage is PETROV's own Instagram account on Item 1, whose owner the expert confirmed.
    text = 'PETROV, using the Instagram account dp_garage, told REYES "got the money, come get it".'
    answer = [P("sender", accounts=[DP_GARAGE], quoted_text="got the money, come get it")]
    _, filler = build_text(conn, text, ClaimType.COMMUNICATION, answer)
    assert not [d for d in filler.drops if "Daniel Petrov" in d.reason], filler.drops


def test_the_one_a_message_went_to_is_tested_on_its_time_row(conn):
    # Arsh, 2026-11-10: a checked SUPPORTED proves who received the message. With a date, code
    # adds REYES to the time row it makes, so the time check asks for both sides.
    text = 'On March 12, 2026, PETROV texted REYES: "need 2 more by friday".'
    answer = [P("sender", people=["PETROV"], quoted_text="need 2 more by friday")]
    assumptions, filler = build_text(conn, text, ClaimType.COMMUNICATION, answer)
    assert not filler.drops, filler.drops
    (timed,) = [a.params for a in assumptions if a.template_id == "record_time"]
    assert timed.person_ids == (PETROV, REYES)
    # Undated, nothing can test REYES: the claim stays unproven.
    undated = 'PETROV texted REYES: "need 2 more by friday".'
    assumptions, filler = build_text(conn, undated, ClaimType.COMMUNICATION, answer)
    assert assumptions == []
    assert any("Marcus Reyes" in d.reason for d in filler.drops), filler.drops
    # A handle written as the one it went to needs a time or count row naming both sides.
    to_handle = 'PETROV wrote to @northstar: "need 2 more by friday".'
    assumptions, filler = build_text(conn, to_handle, ClaimType.COMMUNICATION, answer)
    assert assumptions == []
    assert any("as whom the message went to" in d.reason for d in filler.drops), filler.drops


def test_a_time_row_with_another_recipient_does_not_test_the_one_written(conn):
    # Greptile on #257: a row timing PETROV's words to @northstar does not test "PETROV wrote
    # to @alex92"; only a row naming @alex92 does.
    text = 'On March 12, 2026, PETROV wrote to @alex92: "need 2 more by friday".'
    c = Claim(
        id="X1",
        paragraph_id=claim("C05").paragraph_id,
        text=text,
        claim_type=ClaimType.COMMUNICATION,
        status=ClaimStatus.ACCEPTED,
    )
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    sender = Proposal("sender", {"quoted_text": "need 2 more by friday", "person_ids": [PETROV]})

    def timed(**side) -> Proposal:
        return Proposal(
            "record_time",
            {"quoted_text": "need 2 more by friday", "person_ids": [PETROV], **side},
        )

    other = filler.unbound_person(c, [sender, timed(handles=["@northstar"])])
    assert other is not None and "'@alex92'" in other
    assert filler.unbound_person(c, [sender, timed(handles=["@alex92"])]) is None
    by_account = timed(account_ids=["acct:item1:Telegram:5551234"])  # display name @alex92
    assert filler.unbound_person(c, [sender, by_account]) is None


def test_a_recipient_written_as_a_number_matches_its_whatsapp_account(conn):
    # Greptile on #257: "(212) 555-0122" is the WhatsApp id 12125550122@s.whatsapp.net.
    text = 'On March 12, 2026, PETROV wrote to (212) 555-0122 on WhatsApp: "hello".'
    c = Claim(
        id="X1",
        paragraph_id=claim("C05").paragraph_id,
        text=text,
        claim_type=ClaimType.COMMUNICATION,
        status=ClaimStatus.ACCEPTED,
    )
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    sender = Proposal("sender", {"quoted_text": "hello", "person_ids": [PETROV]})

    def timed(account: str) -> Proposal:
        return Proposal(
            "record_time",
            {"quoted_text": "hello", "person_ids": [PETROV], "account_ids": [account]},
        )

    jid = "acct:item1:WhatsApp:12125550122@s.whatsapp.net"
    assert filler.unbound_person(c, [sender, timed(jid)]) is None
    other = filler.unbound_person(
        c, [sender, timed("acct:item1:WhatsApp:12125550155@s.whatsapp.net")]
    )
    assert other is not None and "(212) 555-0122" in other


QUOTE16 = "got the money, come get it"


def test_an_owner_confirmed_on_another_copy_of_the_account_binds_the_writer(conn):
    # Greptile on #257: scoped to Item 2, the sender row keeps only Item 2's copy of dp_garage;
    # Item 1 holds it as PETROV's own account, and the checks read both by the same key.
    text = 'PETROV wrote from the Instagram account dp_garage: "got the money, come get it".'
    p = Proposal(
        "sender",
        {"quoted_text": QUOTE16, "account_ids": ["acct:item2:Instagram:dp_garage"]},
    )
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    c = Claim(
        id="X1",
        paragraph_id=claim("C05").paragraph_id,
        text=text,
        claim_type=ClaimType.COMMUNICATION,
        status=ClaimStatus.ACCEPTED,
    )
    assert filler.unbound_person(c, [p]) is None
    other = Proposal(
        "sender",
        {"quoted_text": QUOTE16, "account_ids": ["acct:item2:Telegram:7001077"]},
    )
    assert "Daniel Petrov" in (filler.unbound_person(c, [other]) or "")


@pytest.mark.parametrize(
    "lead",
    [
        "Two days before the LOCKER BURGLARY,",
        "The day after the meeting,",
        "The next morning,",
        "Later that night,",
        "3 hours after the call,",
    ],
)
def test_a_day_dated_from_another_needs_a_time_range(lead):
    c = Claim(
        id="X9",
        paragraph_id="p",
        text=f'{lead} PETROV wrote to @northstar: "need 2 more by friday".',
        claim_type=ClaimType.COMMUNICATION,
        status=ClaimStatus.ACCEPTED,
    )
    sender = Proposal("sender", {"quoted_text": "need 2 more by friday"})
    assert coverage_gap(c, [sender]) == (
        "the claim dates itself from another day but no assumption tests a time range"
    )


def test_relative_words_inside_the_quote_date_nothing():
    c = Claim(
        id="X9",
        paragraph_id="p",
        text='PETROV wrote to @northstar: "two days before the drop, call me".',
        claim_type=ClaimType.COMMUNICATION,
        status=ClaimStatus.ACCEPTED,
    )
    sender = Proposal("sender", {"quoted_text": "two days before the drop, call me"})
    assert coverage_gap(c, [sender]) is None


# ---------------------------------------------------------------- filler 12 (v5 failure hunt)

C05_ANSWER = [
    P("sender", people=["PETROV"], quoted_text="need 2 more by friday"),
    P(
        "record_time",
        people=["PETROV"],
        quoted_text="need 2 more by friday",
        window=W("On March 12, 2026", "2026-03-12T00:00", "2026-03-13T00:00"),
    ),
]
C05_TEXT = 'On March 12, 2026, PETROV wrote to @northstar: "need 2 more by friday".'


def test_a_plain_claim_gets_no_event(conn):
    made, _ = build_text(conn, C05_TEXT, ClaimType.COMMUNICATION, C05_ANSWER)
    assert sorted(a.template_id for a in made) == ["record_time", "sender"]


@pytest.mark.parametrize(
    "tail",
    [
        ", and @northstar never replied",
        ", the first message of the day",
        ", and @northstar read it within a minute",
        ", a minute after a Telegram call between them",
        ", while driving",
        " from a second phone",
        ", and sent it twice",
        # Claude review on #265: an act timed from a call with no length, a person reading,
        # and a count or a length no row of this answer reads
        ", after a Telegram call between them",
        ", during a call",
        ", and @northstar was reading it",
        ", one of two messages that day",
        " over two hours",
    ],
)
def test_words_no_check_reads_add_an_event_only_an_expert_carries(conn, tail):
    # Each was a SUPPORTED on its checks alone on Android 13 (v5 failure hunt, 2026-11-16).
    text = C05_TEXT[:-1] + tail + "."
    made, _ = build_text(conn, text, ClaimType.COMMUNICATION, C05_ANSWER)
    (event,) = [a for a in made if a.template_id == "event"]
    assert event.is_core and is_code_made(event.text)
    assert {"sender", "record_time"} <= {a.template_id for a in made}


def test_a_message_reading_its_words_is_no_act(conn):
    text = 'On March 12, 2026, PETROV sent @northstar a message reading: "need 2 more by friday".'
    made, _ = build_text(conn, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert sorted(a.template_id for a in made) == ["record_time", "sender"]


def test_a_spoken_length_is_plain_only_beside_a_row_that_tests_it(conn):
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    text = "At 7:58 p.m. on March 9, 2026, PETROV placed a call of about two minutes to REYES."
    assert filler.unread_words(text, (), {"call", "length"}) == []
    assert filler.unread_words(text, (), {"call"}) == ["two"]
    assert "call" in filler.unread_words(text, (), ())
    both = (
        "At 2:08 p.m. on December 2, 2022, PETROV called REYES, and the two spoke for two minutes."
    )
    assert filler.unread_words(both, (), {"call", "length"}) == []
    assert filler.unread_words(both.replace("the two spoke", "the two calls"), (), {"call"})


def test_a_name_that_folds_longer_does_not_move_later_spans(conn):
    # "ß" casefolds to "ss": spans found in folded text landed one letter late (Claude review
    # on #265), leaving a stray letter of "Telegram" as a word no check reads.
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    text = 'Near the Große Brücke, PETROV wrote to @northstar on Telegram: "need 2 more by friday".'
    assert filler.unread_words(text) == ["near", "grosse", "brücke"]


def _case_with(tmp_path, *sql: str) -> sqlite3.Connection:
    db = tmp_path / "case01.db"
    generate(tmp_path, db)
    c = sqlite3.connect(db)
    stipulate(c, PETROV, "Daniel Petrov", "dev:item1")
    c.execute("PRAGMA foreign_keys = OFF")
    for q in sql:
        c.execute(q)
    return c


def test_a_text_on_a_case_with_two_phone_message_apps_searches_both(tmp_path):
    # "texted" may be SMS or iMessage, as for a code-made sender (Codex on #164): message rows
    # search both, and a count or an absence, which reads one app, is refused (Claude review
    # on #265).
    c = _case_with(
        tmp_path,
        "INSERT INTO threads VALUES ('thr:imsg', 'item1', 'x', 'dev:item1', 'iMessage', NULL)",
    )
    filler = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)
    phone = filler._phone_message_apps()
    assert len(phone) == 2
    text = 'On March 12, 2026, PETROV texted @northstar: "need 2 more by friday".'
    made, _ = build_text(c, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert {a.params.channels for a in made} == {tuple(phone)}
    assert filler.claim_apps(text) == frozenset(a.casefold() for a in phone)
    absence = "PETROV and REYES never texted each other between March 20 and March 23, 2026."
    made, filler = build_text(c, absence, ClaimType.ABSENCE, GOOD["C14"])
    assert made == []


def test_a_count_of_text_messages_on_one_app_the_model_chose_is_refused(tmp_path, conn):
    # The model scoped the count to SMS: on a case with SMS and iMessage, "2 text messages"
    # counted on SMS alone is refused like an unscoped count (CodeRabbit on #265). A count the
    # model put on Telegram was refused already, as the claim does not name it.
    text = "On March 21, 2026, on dev:item1, PETROV sent REYES exactly 2 text messages."
    c = _case_with(
        tmp_path,
        "INSERT INTO threads VALUES ('thr:imsg', 'item1', 'x', 'dev:item1', 'iMessage', NULL)",
    )
    stipulate(c, REYES, "Marcus Reyes", "dev:item2")
    phone = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)._phone_message_apps()
    assert len(phone) == 2
    made, filler = _count(c, text, 2, channels=["SMS"], phones=["dev:item1"])
    assert made == []
    assert any("apps of a phone's own messages" in d.reason for d in filler.drops)
    made, filler = _count(conn, text, 2, phones=["dev:item1"])
    assert made == []


def test_an_absence_on_one_of_the_apps_the_claim_names_is_refused(tmp_path):
    # On a case holding Telegram and Viber, "no contact on Telegram or Viber" read on Telegram
    # alone was kept: Viber went unsearched. It is refused; on both apps it is kept
    # (CodeRabbit on #265). A count so worded is refused already by its own wording checks.
    c = _case_with(
        tmp_path,
        "INSERT INTO threads VALUES ('thr:viber', 'item1', 'x', 'dev:item1', 'Viber', NULL)",
    )
    stipulate(c, REYES, "Marcus Reyes", "dev:item2")
    text = (
        "PETROV and REYES had no contact on Telegram or Viber between March 20 and March 23, 2026."
    )
    (prop,) = GOOD["C14"]
    made, filler = build_text(c, text, ClaimType.ABSENCE, [{**prop, "channels": ["Telegram"]}])
    assert made == []
    assert any("'Viber', which the count or absence" in d.reason for d in filler.drops)
    both = {**prop, "channels": ["Telegram", "Viber"]}
    made, filler = build_text(c, text, ClaimType.ABSENCE, [both])
    assert [a.params.channels for a in made] == [("Telegram", "Viber")], filler.drops


def test_a_phone_named_after_an_app_names_no_app(tmp_path):
    # "the WHATSAPP PHONE" is a phone: a Telegram absence on it is kept on Telegram, not
    # refused for leaving out WhatsApp, and WhatsApp is none of the claim's apps (CodeRabbit on
    # #265; `_absence_parties` reads it so).
    from core.review import actions

    c = _case_with(tmp_path)
    stipulate(c, REYES, "Marcus Reyes", "dev:item2")
    at = D(2026, 10, 26, 12, tzinfo=UTC)
    actions.name_device(c, "dev:item1", ["WHATSAPP PHONE"], "expert:Test Expert", lambda: at)
    text = (
        "On the WHATSAPP PHONE, PETROV and REYES had no contact on Telegram between March 20"
        " and March 23, 2026."
    )
    filler = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)
    assert filler.claim_apps(text) == frozenset({"telegram"})
    (prop,) = GOOD["C14"]
    row = {**prop, "channels": ["Telegram"], "phones": ["the WHATSAPP PHONE"]}
    made, filler = build_text(c, text, ClaimType.ABSENCE, [row])
    assert [a.params.channels for a in made] == [("Telegram",)], filler.drops


def test_by_phone_is_one_kind_of_contact_on_a_case_with_a_phone_named_phone(tmp_path):
    # A phone labelled "Phone" blanked "phone" in "no contact by phone", so the absence, read
    # on messages and calls alike, was kept (CodeRabbit on #265).
    c = _case_with(tmp_path, "UPDATE devices SET label = 'Phone' WHERE id = 'dev:item1'")
    stipulate(c, REYES, "Marcus Reyes", "dev:item2")
    text = "PETROV and REYES had no contact by phone between March 20 and March 23, 2026."
    made, filler = build_text(c, text, ClaimType.ABSENCE, GOOD["C14"])
    assert made == []
    assert any("one kind of contact" in d.reason for d in filler.drops), filler.drops


def test_a_video_is_a_word_no_check_reads(conn):
    # "video" was blanked as a calling app's name, so "sent a video" passed on the sender and
    # time checks alone (CodeRabbit on #265).
    text = 'On March 12, 2026, PETROV sent @northstar a video on Telegram: "need 2 more by friday".'
    made, _ = build_text(conn, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert sorted(a.template_id for a in made) == ["event", "record_time", "sender"]


def test_a_handle_named_like_an_app_picks_no_app(tmp_path):
    # On a case holding Telegram and Viber, "to @viber on Telegram" names Telegram only: the
    # handle never adds Viber to the rows or to the claim's apps (CodeRabbit on #265).
    c = _case_with(
        tmp_path,
        "INSERT INTO threads VALUES ('thr:viber', 'item1', 'x', 'dev:item1', 'Viber', NULL)",
    )
    text = 'On March 12, 2026, PETROV wrote to @viber on Telegram: "need 2 more by friday".'
    filler = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)
    assert "Viber" in filler.channels()
    assert filler._named_apps(text) == ["Telegram"]
    made, _ = build_text(c, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert {a.params.channels for a in made} == {("Telegram",)}


@pytest.mark.parametrize(
    ("tail", "tests"),
    [(", one of 2 messages that day", {"count"}), (", over 2 hours", {"length"})],
)
def test_a_count_or_length_in_digits_is_read_like_one_in_words(conn, tail, tests):
    # "2" passed where "two" was read: digits were never tokens (CodeRabbit on #265).
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    text = f'On March 12, 2026, PETROV wrote to @northstar on Telegram{tail}: "need 2 more".'
    assert filler.unread_words(text) == ["2"]
    assert filler.unread_words(text, (), tests) == []
    # the bare first hour of a range is a time, not a count
    ranged = text.replace("On March 12, 2026", "Between 10 and 11 a.m. on March 12, 2026")
    assert filler.unread_words(ranged, (), tests) == []


def test_an_account_named_like_a_plain_word_hides_no_word(tmp_path):
    # An account shown as "Photo" no longer blanks "sent a photo" (Claude review on #265).
    c = _case_with(
        tmp_path,
        "INSERT INTO accounts (id, source_id, locator, device_id, app, identifier, display_name)"
        " VALUES ('acct:item1:Telegram:photo', 'item1', 'x', NULL, 'Telegram', '555', 'Photo')",
    )
    filler = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)
    text = 'On March 12, 2026, PETROV sent @northstar a photo on Telegram: "need 2 more by friday".'
    assert filler.unread_words(text) == ["photo"]
    assert filler.unread_words(text.replace("a photo", "Photo's message")) == []


def test_a_message_on_no_app_is_bound_to_the_app_the_claim_names(conn):
    text = 'On March 12, 2026, PETROV wrote to @northstar on Telegram: "need 2 more by friday".'
    made, _ = build_text(conn, text, ClaimType.COMMUNICATION, C05_ANSWER)
    rows = {a.template_id: a for a in made}
    assert rows["sender"].params.channels == ("Telegram",)
    assert rows["record_time"].params.channels == ("Telegram",)


@pytest.mark.parametrize("app", ["on Signal", "by email"])
def test_a_message_on_an_app_the_case_does_not_hold_stays_unproven(conn, app):
    # Searched on every app, the words were found on another one: a false SUPPORTED.
    text = f'On March 12, 2026, PETROV wrote to @northstar {app}: "need 2 more by friday".'
    made, filler = build_text(conn, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert made == []
    assert any("names an app no assumption" in d.reason for d in filler.drops)


@pytest.mark.parametrize(
    ("words", "seconds"),
    [
        ("at 9:31:04 p.m.", True),
        ("at 21:14:05Z", True),  # Claude review on #265: a word boundary missed these two
        ("at 2026-03-12T21:14:05", True),
        ("in a call that lasted 0:12:45", False),  # a length, not a time of day
        ("in a call lasting about 0:02:03", False),
        ("at 9:31 p.m.", False),
    ],
)
def test_a_time_of_day_to_the_second_is_told_from_a_length(words, seconds):
    assert _states_seconds(words) is seconds


def test_a_time_to_the_second_is_not_tested_by_a_range_in_minutes(conn):
    text = 'At 9:14:05 p.m. on March 12, 2026, PETROV wrote to @northstar: "need 2 more by friday".'
    answer = [
        C05_ANSWER[0],
        P(
            "record_time",
            people=["PETROV"],
            quoted_text="need 2 more by friday",
            window=W("At 9:14:05 p.m. on March 12, 2026", "2026-03-12T21:14", "2026-03-12T21:15"),
        ),
    ]
    made, filler = build_text(conn, text, ClaimType.COMMUNICATION, answer)
    assert "record_time" not in {a.template_id for a in made}
    assert any("to the second" in d.reason for d in filler.drops)


@pytest.mark.parametrize(
    "words",
    [
        "had no contact on Signal",
        "never emailed each other",
        "never messaged each other",
        "had no contact by telephone",
        # an app outside the calling apps the case does not hold (Claude review on #265)
        "had no contact on TikTok",
        "had no contact on GroupMe",
    ],
)
def test_an_absence_of_one_kind_of_contact_is_never_read_on_every_app(conn, words):
    # The absence check on no app reads every app, messages and calls alike: a Telegram
    # message then "contradicted" a true "no contact on Signal" (v5 failure hunt, 2026-11-16).
    text = f"PETROV and REYES {words} between March 20 and March 23, 2026."
    made, filler = build_text(conn, text, ClaimType.ABSENCE, GOOD["C14"])
    assert made == []
    assert any("could not read the claim's own words" in d.reason for d in filler.drops)


@pytest.mark.parametrize(
    ("words", "kept"),
    [("had no contact on his second line", False), ("had no contact on Line", True)],
)
def test_an_app_named_by_a_plain_word_gets_no_absence_unless_capitalized(
    conn, monkeypatch, words, kept
):
    # "his second line" may name no app at all: code reads no absence on Line for it, while
    # "on Line" names the app (v5 failure hunt, 2026-11-16). The case has no Line, so the
    # app list is patched.
    monkeypatch.setattr(LocalAssumptionFiller, "_named_apps", lambda self, text: ["Line"])
    held = LocalAssumptionFiller.channels
    monkeypatch.setattr(LocalAssumptionFiller, "channels", lambda self: [*held(self), "Line"])
    monkeypatch.setattr(
        LocalAssumptionFiller,
        "_channels",
        lambda self, text, names, template_id="": list(names),
    )
    text = f"PETROV and REYES {words} between March 20 and March 23, 2026."
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    c = Claim(
        id="X1",
        paragraph_id=claim("C05").paragraph_id,
        text=text,
        claim_type=ClaimType.ABSENCE,
        status=ClaimStatus.ACCEPTED,
    )
    out = [Proposal("no_contact", {"person_ids": [PETROV, REYES]}, is_core=True)]
    if kept:
        (row,) = filler._bind_named_app(c, out)
        assert row.params["channels"] == ["Line"]
    else:
        with pytest.raises(Reject, match="plain word"):
            filler._bind_named_app(c, out)


@pytest.mark.parametrize(
    ("words", "kept"), [("had no contact on Recents", True), ("had no contact on recents", False)]
)
def test_a_plain_word_app_written_with_a_capital_is_named_however_the_export_spells_it(
    conn, monkeypatch, words, kept
):
    # An export may store "recents"; "on Recents" still names it (CodeRabbit on #265). Only
    # the case's apps are patched, so the claim's app is read as it would be.
    held = LocalAssumptionFiller.channels
    monkeypatch.setattr(LocalAssumptionFiller, "channels", lambda self: [*held(self), "recents"])
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    c = Claim(
        id="X1",
        paragraph_id=claim("C05").paragraph_id,
        text=f"PETROV and REYES {words} between March 20 and March 23, 2026.",
        claim_type=ClaimType.ABSENCE,
        status=ClaimStatus.ACCEPTED,
    )
    out = [Proposal("no_contact", {"person_ids": [PETROV, REYES]}, is_core=True)]
    if kept:
        (row,) = filler._bind_named_app(c, out)
        assert row.params["channels"] == ["recents"]
    else:
        with pytest.raises(Reject, match="plain word"):
            filler._bind_named_app(c, out)


def test_a_plain_word_app_inside_a_longer_app_name_is_not_written_as_a_name(conn, monkeypatch):
    # "Line" inside "Line Business" is the longer app's name, not a capital on Line, so a row
    # the model put on Line gets no absence (CodeRabbit on #265).
    held = LocalAssumptionFiller.channels
    monkeypatch.setattr(
        LocalAssumptionFiller, "channels", lambda self: [*held(self), "Line", "Line Business"]
    )
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    c = Claim(
        id="X1",
        paragraph_id=claim("C05").paragraph_id,
        text="PETROV and REYES had no contact on Line Business between March 20 and 23, 2026.",
        claim_type=ClaimType.ABSENCE,
        status=ClaimStatus.ACCEPTED,
    )
    assert filler._written_as_name(c.text, "Line Business")
    assert not filler._written_as_name(c.text, "Line")
    out = [
        Proposal("no_contact", {"person_ids": [PETROV, REYES], "channels": ["Line"]}, is_core=True)
    ]
    with pytest.raises(Reject, match="plain word"):
        filler._bind_named_app(c, out)


def test_a_hyphen_joins_the_words_of_a_longer_app_name(conn, monkeypatch):
    # "Line-Business" writes Line Business, not Line; "Line or Line Business" names both
    # (CodeRabbit on #265).
    held = LocalAssumptionFiller.channels
    monkeypatch.setattr(
        LocalAssumptionFiller, "channels", lambda self: [*held(self), "Line", "Line Business"]
    )
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    hyphen = "PETROV wrote on Line-Business on March 20, 2026."
    assert filler._app_mentions(hyphen, "Line Business")
    assert filler._written_as_name(hyphen, "Line Business")
    assert not filler._written_as_name(hyphen, "Line")
    assert filler.claim_apps(hyphen) == {"line business"}
    both = "PETROV wrote on Line or Line Business on March 20, 2026."
    assert filler._written_as_name(both, "Line")
    assert filler.claim_apps(both) == {"line", "line business"}


def test_a_quoted_date_or_year_is_never_the_claims(conn):
    # A date or year inside the quoted message is the message's: a range on the quoted day,
    # or a year taken only from the quote, would test the claim on the wrong day (CodeRabbit
    # on #265).
    import core.audit.assumption_filler as af

    text = 'On March 12, 2026, PETROV wrote to REYES: "see you March 11, 2026".'
    check_window(D(2026, 3, 12), D(2026, 3, 13), "March 12, 2026", text, "")
    with pytest.raises(Reject, match="not a date the claim states"):
        check_window(D(2026, 3, 11), D(2026, 3, 13), "March 12, 2026", text, "")
    # words copied across a quote's edge are part the message's (CodeRabbit on #265)
    from core.audit.assumption_filler import cut_from_longer

    assert cut_from_longer('March 11, 2026".', text)
    assert not cut_from_longer("On March 12, 2026", text)
    # a quoted weekday is the message's, never read with the claim's year; an unquoted wrong
    # weekday is still refused (CodeRabbit on #265)
    monday = 'On March 12, 2026, PETROV wrote "See you Monday, March 11; back in 2024".'
    check_window(D(2026, 3, 12), D(2026, 3, 13), "March 12, 2026", monday, "")
    with pytest.raises(Reject, match="weekday"):
        check_window(
            D(2026, 3, 12), D(2026, 3, 13), "Monday, March 12, 2026", f"On Monday, {monday[3:]}", ""
        )
    # a run of months with a quote inside it is still the claim's run: "May" alone is cut
    # from it (CodeRabbit on #265)
    run = 'In April and May "the busy month" 2026, PETROV wrote: "ok".'
    check_window(D(2026, 4, 1), D(2026, 6, 1), 'April and May "the busy month" 2026', run, "")
    with pytest.raises(Reject, match="cut from a longer run"):
        check_window(D(2026, 5, 1), D(2026, 6, 1), 'May "the busy month" 2026', run, "")
    no_year = 'On March 12, PETROV wrote to REYES: "back in 2025".'
    assert af.stated_windows(no_year, "") is None
    assert af.stated_windows("On March 12", no_year) is None
    (w,) = af.stated_windows("On March 12", f"{no_year} On March 12, 2026, it was.")
    assert w.start == D(2026, 3, 12)
    assert (
        stated_part_day('On March 12, no contact after 9 a.m., per the note "filed 2025".') is None
    )
    # an open range takes the paragraph's year, never a quoted one beside it
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    c = Claim(
        id="X1",
        paragraph_id=claim("C05").paragraph_id,
        text="There was no contact between dev:item1 and (212) 555-0144 before March 12, the"
        ' "2025 plan" aside.',
        claim_type=ClaimType.ABSENCE,
        status=ClaimStatus.ACCEPTED,
    )
    w = filler._open_range(c, ["dev:item1"], "The phones were seized in 2026.")
    assert w.raw.startswith("before March 12: from")
    assert w.end_utc.astimezone(ZoneInfo("America/New_York")).date().isoformat() == "2026-03-11"


def test_words_inside_a_kept_range_are_still_read(conn):
    # The model may keep "On March 12, 2026, while driving" as the day's range; "while
    # driving" is still a word no check reads (Greptile on #265).
    raw = "On March 12, 2026, while driving"
    answer = [
        C05_ANSWER[0],
        P(
            "record_time",
            people=["PETROV"],
            quoted_text="need 2 more by friday",
            window=W(raw, "2026-03-12T00:00", "2026-03-13T00:00"),
        ),
    ]
    text = f'{raw}, PETROV wrote to @northstar: "need 2 more by friday".'
    made, _ = build_text(conn, text, ClaimType.COMMUNICATION, answer)
    assert "event" in {a.template_id for a in made}


@pytest.mark.parametrize("channels", [None, ["Telegram"]])
def test_an_absence_of_one_kind_of_contact_on_a_named_app_is_never_read(conn, channels):
    # The absence check reads messages and calls alike on the app it searches, so a Telegram
    # call would contradict "never messaged each other on Telegram" (Greptile on #265).
    props = [{**p, "channels": channels or []} for p in GOOD["C14"]]
    text = (
        "PETROV and REYES never messaged each other on Telegram between March 20 and"
        " March 23, 2026."
    )
    made, _ = build_text(conn, text, ClaimType.ABSENCE, props)
    assert made == []


def test_a_model_chosen_plain_word_app_gets_no_absence(conn, monkeypatch):
    # A model answer that names Line for "his second line" passes `_channels` (the word is in
    # the claim), and is refused like the one code would bind (Greptile on #265).
    monkeypatch.setattr(LocalAssumptionFiller, "_named_apps", lambda self, text: ["Line"])
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    c = Claim(
        id="X1",
        paragraph_id=claim("C05").paragraph_id,
        text="PETROV and REYES had no contact on his second line between March 20 and 23, 2026.",
        claim_type=ClaimType.ABSENCE,
        status=ClaimStatus.ACCEPTED,
    )
    out = [
        Proposal("no_contact", {"person_ids": [PETROV, REYES], "channels": ["Line"]}, is_core=True)
    ]
    with pytest.raises(Reject, match="plain word"):
        filler._bind_named_app(c, out)


def test_a_person_reading_a_message_is_a_word_no_check_reads(conn):
    # "PETROV read: ..." is an act; only "a message that read: ..." names the words
    # (CodeRabbit on #265).
    text = 'On March 12, 2026, PETROV read: "need 2 more by friday".'
    made, _ = build_text(conn, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert "event" in {a.template_id for a in made}


def test_an_app_the_case_lacks_beside_one_it_holds_stays_unproven(conn):
    # "on Telegram and Signal" on a case with no Signal: binding Telegram alone would test
    # less than the claim says (CodeRabbit on #265).
    text = (
        'On March 12, 2026, PETROV wrote to @northstar on Telegram and Signal: "need 2 more by'
        ' friday".'
    )
    made, filler = build_text(conn, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert made == []
    assert any("also names an app" in d.reason for d in filler.drops)


def test_a_short_name_of_an_app_the_case_holds_is_that_app(tmp_path):
    # "on Wickr" on a case whose app is "Wickr Pro": rows left on no app get Wickr Pro, and
    # "Wickr" is not read as an app the case lacks (CodeRabbit on #265).
    db = tmp_path / "case01.db"
    generate(tmp_path, db)
    c = sqlite3.connect(db)
    stipulate(c, PETROV, "Daniel Petrov", "dev:item1")
    c.execute("PRAGMA foreign_keys = OFF")
    c.execute(
        "INSERT INTO threads VALUES ('thr:wickr', 'item1', 'x', 'dev:item1', 'Wickr Pro', NULL)"
    )
    text = 'On March 12, 2026, PETROV wrote to @northstar on Wickr: "need 2 more by friday".'
    made, filler = build_text(c, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert sorted((a.template_id, a.params.channels) for a in made) == [
        ("record_time", ("Wickr Pro",)),
        ("sender", ("Wickr Pro",)),
    ], filler.drops


def test_a_handle_named_like_an_app_is_no_app(conn):
    # "@viber" is the Telegram account written to, not Viber, which the case lacks (CodeRabbit
    # on #265).
    text = 'On March 12, 2026, PETROV wrote to @viber on Telegram: "need 2 more by friday".'
    scoped = [{**p, "channels": ["Telegram"]} for p in C05_ANSWER]
    _, filler = build_text(conn, text, ClaimType.COMMUNICATION, scoped)
    assert not any("names an app no" in d.reason for d in filler.drops), filler.drops


def test_an_app_the_case_lacks_stays_unproven_on_rows_the_model_scoped(conn):
    # The model already put both rows on Telegram: Signal, which the case lacks, is still read
    # (CodeRabbit on #265). A claim naming Signal alone already drops the model's Telegram, as
    # the claim does not name it.
    text = (
        'On March 12, 2026, PETROV wrote to @northstar on Telegram and Signal: "need 2 more by'
        ' friday".'
    )
    scoped = [{**p, "channels": ["Telegram"]} for p in C05_ANSWER]
    made, filler = build_text(conn, text, ClaimType.COMMUNICATION, scoped)
    assert made == []
    assert any("also names an app" in d.reason for d in filler.drops)


@pytest.mark.parametrize(
    "tail",
    [
        ", over one hour",
        ", for half an hour",
        ", an hour after the call",
        ", for a quarter hour",  # CodeRabbit on #265
        ", for a quarter of an hour",
    ],
)
def test_a_spoken_length_no_row_tests_is_read(conn, tail):
    # "over one hour" passed with no row testing a length: "over", "one" and "hour" are each
    # plain alone (CodeRabbit on #265).
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    text = (
        f'On March 12, 2026, PETROV wrote to @northstar on Telegram{tail}: "need 2 more by friday".'
    )
    assert filler.unread_words(text)
    if "after" not in tail and "quarter" not in tail:
        # "after the call" is read by a row that tests a call; a quarter hour is no length a
        # row tests (`duration_range` reads none), so it stays unread beside one
        assert filler.unread_words(text, (), {"length"}) == []
    made, _ = build_text(conn, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert "event" in {a.template_id for a in made}


def test_a_message_on_two_apps_named_together_waits_for_an_expert(tmp_path):
    # "on Telegram and Viber" was searched on either app, so a Telegram message alone passed
    # the sender and time checks (CodeRabbit on #265). "Telegram or Viber" still reads either.
    c = _case_with(
        tmp_path,
        "INSERT INTO threads VALUES ('thr:viber', 'item1', 'x', 'dev:item1', 'Viber', NULL)",
    )
    text = 'On March 12, 2026, PETROV wrote on Telegram and Viber: "need 2 more by friday".'
    filler = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)
    assert filler._apps_named_together(text) == ["Telegram and Viber"]
    made, _ = build_text(c, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert "event" in {a.template_id for a in made}
    either = text.replace("Telegram and Viber", "Telegram or Viber")
    assert filler._apps_named_together(either) == []
    made, _ = build_text(c, either, ClaimType.COMMUNICATION, C05_ANSWER)
    # both rows are kept and each searches either app; no event (CodeRabbit on #265)
    assert sorted(a.template_id for a in made) == ["record_time", "sender"]
    assert {frozenset(a.params.channels) for a in made} == {frozenset({"Telegram", "Viber"})}
    assert filler._apps_named_together(text.replace(" and Viber", "")) == []


def test_a_hyphenated_app_name_reads_its_join_like_binding(tmp_path):
    # "Telegram or Line-Business" binds both apps; the join scan read only "Line Business", so
    # the app counted as unwritten and the claim got an event (CodeRabbit on #265).
    c = _case_with(
        tmp_path,
        "INSERT INTO threads VALUES ('thr:lb', 'item1', 'x', 'dev:item1', 'Line Business', NULL)",
    )
    text = 'On March 12, 2026, PETROV wrote on Telegram or Line-Business: "need 2 more by friday".'
    filler = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)
    assert filler._apps_named_together(text) == []
    made, _ = build_text(c, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert sorted(a.template_id for a in made) == ["record_time", "sender"]
    assert {frozenset(a.params.channels) for a in made} == {
        frozenset({"Telegram", "Line Business"})
    }
    wrapped = text.replace("Line-Business", "Line\nBusiness")
    assert filler._apps_named_together(wrapped) == []
    made, _ = build_text(c, wrapped, ClaimType.COMMUNICATION, C05_ANSWER)
    assert sorted(a.template_id for a in made) == ["record_time", "sender"]
    assert {frozenset(a.params.channels) for a in made} == {
        frozenset({"Telegram", "Line Business"})
    }
    joined = text.replace(" or ", " and ")
    assert filler._apps_named_together(joined) == ["Telegram and Line-Business"]
    made, _ = build_text(c, joined, ClaimType.COMMUNICATION, C05_ANSWER)
    assert "event" in {a.template_id for a in made}


@pytest.mark.parametrize(
    ("apps", "together"),
    [
        ("Telegram and on either Viber or WhatsApp", True),  # one "and" beside an "or"
        ("Telegram, Viber or WhatsApp", True),  # a list joined by a comma is read as joined
        ("either Telegram or Viber or WhatsApp", False),
        ("Telegram/Viber", False),
    ],
)
def test_each_join_between_named_apps_is_read(tmp_path, apps, together):
    # "on Telegram and on either Viber or WhatsApp" was read as either app because an "or"
    # stood between the first and last app, so a WhatsApp message alone passed (CodeRabbit on
    # #265). Every join between two apps named next to each other is read now.
    c = _case_with(
        tmp_path,
        "INSERT INTO threads VALUES ('thr:viber', 'item1', 'x', 'dev:item1', 'Viber', NULL)",
        "INSERT INTO threads VALUES ('thr:wa', 'item1', 'x', 'dev:item1', 'WhatsApp', NULL)",
    )
    text = f'On March 12, 2026, PETROV wrote on {apps}: "need 2 more by friday".'
    filler = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)
    assert len(filler._named_apps(text)) >= 2
    assert bool(filler._apps_named_together(text)) is together
    made, _ = build_text(c, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert ("event" in {a.template_id for a in made}) is together


def test_a_phone_app_or_a_short_name_is_read_in_the_joins(tmp_path):
    # "on Telegram and SMS": SMS is a phone's own messages app, which `_named_apps` leaves out,
    # so a Telegram message alone passed; "on Telegram or Wickr" on a case holding Wickr Pro
    # was read as joined because "Wickr Pro" is not written whole (CodeRabbit on #265).
    c = _case_with(
        tmp_path,
        "INSERT INTO threads VALUES ('thr:wickr', 'item1', 'x', 'dev:item1', 'Wickr Pro', NULL)",
    )
    filler = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)
    claim = 'On March 12, 2026, PETROV wrote to @northstar on {}: "need 2 more by friday".'
    assert filler._apps_named_together(claim.format("Telegram and SMS"))
    assert filler._apps_named_together(claim.format("Telegram or SMS")) == []
    assert filler._apps_named_together(claim.format("Telegram or Wickr")) == []
    assert filler._apps_named_together(claim.format("Telegram and Wickr"))
    # "texted" names no app of its own
    texted = 'On March 12, 2026, PETROV texted @northstar on Telegram: "need 2 more by friday".'
    assert filler._apps_named_together(texted) == []


@pytest.mark.parametrize("said", ["sent @northstar an SMS", "sent @northstar an iMessage"])
def test_one_phone_app_on_an_app_holding_both_waits_for_an_expert(tmp_path, said):
    # "Native Messages" holds iMessage and SMS together, as LEAPP and a UFDR store them: a row
    # searched there finds an iMessage for "sent an SMS", and no check reads which of the two a
    # row was (CodeRabbit on #265). The claim's word is shown to the expert as an event.
    c = _case_with(
        tmp_path,
        "UPDATE threads SET app = 'Native Messages' WHERE app = 'Telegram'",
    )
    answer = [{**p, "channels": ["Native Messages"]} for p in C05_ANSWER]
    text = f'On March 12, 2026, PETROV {said}: "need 2 more by friday".'
    made, _ = build_text(c, text, ClaimType.COMMUNICATION, answer)
    assert {a.template_id for a in made} == {"record_time", "sender", "event"}
    (event,) = [a for a in made if a.template_id == "event"]
    assert event.is_core and is_code_made(event.text)
    plain = 'On March 12, 2026, PETROV wrote to @northstar: "need 2 more by friday".'
    made, _ = build_text(c, plain, ClaimType.COMMUNICATION, answer)
    assert sorted(a.template_id for a in made) == ["record_time", "sender"]
    # the app named whole names no one kind of message (CodeRabbit on #265)
    named = (
        'On March 12, 2026, PETROV wrote to @northstar on Native Messages: "need 2 more by friday".'
    )
    made, _ = build_text(c, named, ClaimType.COMMUNICATION, answer)
    assert sorted(a.template_id for a in made) == ["record_time", "sender"]


_Q = '"need 2 more by friday"'


@pytest.mark.parametrize(
    ("text", "event"),
    [
        # a second message after the one quoted: no row tests it (CodeRabbit on #265)
        (f"On March 12, 2026, PETROV wrote to @northstar: {_Q}, and @northstar replied.", True),
        (f"On March 12, 2026, PETROV wrote to @northstar: {_Q}, and @northstar wrote back.", True),
        (f"On March 12, 2026, PETROV replied to @northstar, and then wrote: {_Q}.", True),
        # the reply is the quoted message the rows test
        (f"On March 12, 2026, PETROV replied to @northstar: {_Q}.", False),
        (f"On March 12, 2026, PETROV wrote back to @northstar: {_Q}.", False),
    ],
)
def test_a_reply_is_read_only_when_it_is_the_quoted_message(conn, text, event):
    made, _ = build_text(conn, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert ("event" in {a.template_id for a in made}) is event
    assert {"sender", "record_time"} <= {a.template_id for a in made}


def test_a_slash_in_a_date_does_not_make_two_apps_alternatives(tmp_path):
    # "on Telegram (03/12/2026), on Viber": the comma joins the apps; the date's slashes are
    # no "/" between them, which alone keeps "Telegram/Viber" alternatives (CodeRabbit on #265).
    c = _case_with(
        tmp_path,
        "INSERT INTO threads VALUES ('thr:viber', 'item1', 'x', 'dev:item1', 'Viber', NULL)",
    )
    filler = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)
    claim = 'PETROV wrote to @northstar on {}: "need 2 more by friday".'
    assert filler._apps_named_together(claim.format("Telegram (03/12/2026), on Viber"))
    assert filler._apps_named_together(claim.format("Telegram/Viber")) == []
    assert filler._apps_named_together(claim.format("Telegram / Viber")) == []


def test_a_name_inside_a_longer_app_name_is_not_a_second_app(tmp_path):
    # "Facebook Messenger" also holds "Facebook": the two matches sat next to each other with
    # no gap and read as joined, so "Telegram or Facebook Messenger" got an event. The longest
    # name at a mention is the app; "Facebook and Facebook Messenger" keeps both (CodeRabbit
    # on #265).
    c = _case_with(
        tmp_path,
        "INSERT INTO threads VALUES ('thr:fb', 'item1', 'x', 'dev:item1', 'Facebook', NULL)",
        "INSERT INTO threads VALUES ('thr:fbm', 'item1', 'y', 'dev:item1', 'Facebook Messenger',"
        " NULL)",
    )
    filler = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)
    claim = 'PETROV wrote to @northstar on {}: "need 2 more by friday".'
    assert filler._apps_named_together(claim.format("Telegram or Facebook Messenger")) == []
    assert filler._apps_named_together(claim.format("Telegram and Facebook Messenger"))
    assert filler._apps_named_together(claim.format("Facebook or Facebook Messenger")) == []
    assert filler._apps_named_together(claim.format("Facebook and Facebook Messenger"))


def test_an_answered_call_is_plain_only_beside_a_tested_length(conn):
    # "answered" is no reply to a quoted message: beside a row that tests the call's length it
    # is read (a call that lasted was answered), and elsewhere it is a word no check reads.
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    text = "At 7:58 p.m. on March 9, 2026, PETROV placed a call to REYES that was answered."
    assert filler.unread_words(text, (), {"call", "length"}) == []
    assert filler.unread_words(text, (), {"call"}) == ["answered"]


def test_a_tested_length_does_not_hide_a_second_untested_one(conn):
    # "one minute and a quarter hour": the row tests "one minute"; "a quarter hour" is left,
    # and each of its words is plain alone (CodeRabbit on #265). "One minute" alone is read.
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    text = "At 7:58 p.m. on March 9, 2026, PETROV called REYES for one minute{}."
    assert filler.unread_words(text.format(""), (), {"call", "length"}) == []
    assert filler.unread_words(text.format(" and a quarter hour"), (), {"call", "length"}) == [
        "and a quarter hour"
    ]


def test_a_name_inside_a_longer_app_name_binds_no_second_app(tmp_path):
    # "Telegram or Facebook Messenger" bound Facebook too, so a Facebook message could pass
    # it (CodeRabbit on #265). A Facebook written apart is kept.
    c = _case_with(
        tmp_path,
        "INSERT INTO threads VALUES ('thr:fb', 'item1', 'x', 'dev:item1', 'Facebook', NULL)",
        "INSERT INTO threads VALUES ('thr:fbm', 'item1', 'y', 'dev:item1', 'Facebook Messenger',"
        " NULL)",
    )
    filler = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)
    claim = 'PETROV wrote on {}: "need 2 more by friday".'
    assert sorted(filler._named_apps(claim.format("Telegram or Facebook Messenger"))) == [
        "Facebook Messenger",
        "Telegram",
    ]
    assert sorted(filler._named_apps(claim.format("Facebook or Facebook Messenger"))) == [
        "Facebook",
        "Facebook Messenger",
    ]
    text = f"On March 12, 2026, {claim.format('Telegram or Facebook Messenger')}"
    made, _ = build_text(c, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert {a.template_id for a in made} == {"sender", "record_time"}
    assert {frozenset(a.params.channels) for a in made} == {
        frozenset({"Telegram", "Facebook Messenger"})
    }


def test_a_phone_app_named_beside_another_app_is_searched_too(tmp_path):
    # "on Telegram or SMS" bound Telegram alone, as `_named_apps` leaves SMS out, so a count
    # read Telegram only (CodeRabbit on #265). Message rows search SMS too; a count or an
    # absence of the mix is refused; a case with no SMS refuses the claim.
    c = _case_with(tmp_path)
    text = 'On March 12, 2026, PETROV wrote on Telegram or SMS: "need 2 more by friday".'
    made, _ = build_text(c, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert {a.template_id for a in made} == {"sender", "record_time"}
    assert {frozenset(a.params.channels) for a in made} == {frozenset({"Telegram", "SMS"})}
    stipulate(c, REYES, "Marcus Reyes", "dev:item2")
    absence = (
        "PETROV and REYES had no contact on Telegram or SMS between March 20 and March 23, 2026."
    )
    (prop,) = GOOD["C14"]
    made, filler = build_text(c, absence, ClaimType.ABSENCE, [prop])
    assert made == []
    assert any("phone's own messages app beside" in d.reason for d in filler.drops)
    c.execute("UPDATE threads SET app = 'Signal' WHERE app = 'SMS'")
    made, _ = build_text(c, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert made == []


def test_more_findings_on_5da573d(tmp_path, conn):
    # CodeRabbit on #265, on 5da573d.
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=DRAFT)
    # a reply in a sentence of its own is no reply quoted later
    text = f"On March 12, 2026, PETROV wrote to REYES. REYES replied. PETROV wrote: {_Q}."
    assert "replied" in filler.unread_words(text)
    # a count in digits that no phone number holds
    text = f"On March 12, 2026, PETROV wrote to @northstar: {_Q}, one of 10000 that day."
    assert "10000" in filler.unread_words(text)
    # MMS is no SMS: a case with SMS alone holds no MMS app
    c = _case_with(tmp_path)
    claim = 'On March 12, 2026, PETROV wrote on Telegram or {}: "need 2 more by friday".'
    made, _ = build_text(c, claim.format("MMS"), ClaimType.COMMUNICATION, C05_ANSWER)
    assert made == []
    made, _ = build_text(c, claim.format("SMS"), ClaimType.COMMUNICATION, C05_ANSWER)
    assert {a.template_id for a in made} == {"sender", "record_time"}
    assert {frozenset(a.params.channels) for a in made} == {frozenset({"Telegram", "SMS"})}
    # the sheet check reads the phone app the claim names beside another
    sms = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)
    assert sms.claim_apps(claim.format("SMS")) == {"telegram", "sms"}


def test_more_findings_on_37917c7(tmp_path):
    # CodeRabbit on #265, on 37917c7.
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    c = _case_with(tmp_path / "a")
    filler = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)
    # a handle names an account, not a phone's own messages app
    text = 'On March 12, 2026, PETROV wrote to @sms on Telegram: "need 2 more by friday".'
    assert filler.claim_apps(text) == {"telegram"}
    made, _ = build_text(c, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert {frozenset(a.params.channels) for a in made} == {frozenset({"Telegram"})}
    # a message row the model put on Telegram alone for "Telegram or SMS" searches SMS too:
    # a Telegram copy outside the range would fail a true claim sent by SMS
    text = 'On March 12, 2026, PETROV wrote on Telegram or SMS: "need 2 more by friday".'
    on_telegram = [{**p, "channels": ["Telegram"]} for p in C05_ANSWER]
    made, _ = build_text(c, text, ClaimType.COMMUNICATION, on_telegram)
    assert {frozenset(a.params.channels) for a in made} == {frozenset({"Telegram", "SMS"})}
    # ...but a party the model gave as a Telegram account reaches no SMS, so the claim stays
    # unproven rather than read on Telegram alone
    northstar = {"as_written": "5551234", "app": "Telegram"}
    as_account = [on_telegram[0], {**on_telegram[1], "accounts": [northstar]}]
    to_id = text.replace("wrote on", "wrote to Telegram user 5551234 on")
    made, acct = build_text(c, to_id, ClaimType.COMMUNICATION, as_account)
    assert made == [], [a.params for a in made]
    assert any("given as accounts" in d.reason for d in acct.drops), acct.drops
    on_both = [{**p, "channels": ["Telegram", "SMS"]} for p in as_account]
    made, acct = build_text(c, to_id, ClaimType.COMMUNICATION, on_both)
    assert made == [], [a.params for a in made]
    assert any("given as accounts" in d.reason for d in acct.drops), acct.drops
    # SMS and MMS are two kinds, joined by "and" and alternatives by "or"
    text = 'On March 12, 2026, PETROV wrote to @northstar on SMS {} MMS: "need 2 more by friday".'
    assert filler._apps_named_together(text.format("and"))
    assert filler._apps_named_together(text.format("or")) == []
    # an iMessage is never read on the SMS app, whether code or the model scoped the row
    both = _case_with(
        tmp_path / "b",
        "INSERT INTO threads VALUES ('thr:imsg', 'item1', 'x', 'dev:item1', 'iMessage', NULL)",
    )
    text = 'On March 12, 2026, PETROV sent @northstar an iMessage: "need 2 more by friday".'
    made, _ = build_text(both, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert {a.params.channels for a in made} == {("iMessage",)}
    on_sms = [{**p, "channels": ["SMS"]} for p in C05_ANSWER]
    texted = text.replace("sent @northstar an iMessage", "texted @northstar an iMessage")
    made, sms = build_text(both, texted, ClaimType.COMMUNICATION, on_sms)
    assert made == []
    assert any("kind of text message" in d.reason for d in sms.drops)
    assert LocalAssumptionFiller(FakeModel("{}"), both, template=DRAFT).claim_apps(text) == {
        "imessage"
    }
    # a time to the second inside a quote a line break wraps is the quote's, not the claim's
    text = (
        'On March 12, 2026, PETROV wrote to @northstar: "need 2 more by friday", adding'
        ' "back at\n9:31:04".'
    )
    made, wrapped = build_text(c, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert not any("to the second" in d.reason for d in wrapped.drops)


def test_more_findings_on_e3062bf(tmp_path):
    # CodeRabbit on #265, on e3062bf.
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    c = _case_with(tmp_path / "a")  # SMS, no MMS
    # "on SMS or MMS" on a case with no MMS app: SMS alone is not every alternative, whether
    # code or the model scoped the row
    text = 'On March 12, 2026, PETROV wrote on SMS or MMS: "need 2 more by friday".'
    made, filler = build_text(c, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert made == [], [a.params for a in made]
    on_sms = [{**p, "channels": ["SMS"]} for p in C05_ANSWER]
    made, filler = build_text(c, text, ClaimType.COMMUNICATION, on_sms)
    assert made == [], [a.params for a in made]
    assert any("(mms)" in d.reason for d in filler.drops), filler.drops
    # ...and both kinds held keep the alternative searchable
    both = _case_with(
        tmp_path / "b",
        "INSERT INTO threads VALUES ('thr:mms', 'item1', 'x', 'dev:item1', 'MMS', NULL)",
    )
    made, _ = build_text(both, text, ClaimType.COMMUNICATION, on_sms)
    assert {frozenset(a.params.channels) for a in made} == {frozenset({"SMS", "MMS"})}
    # a handle on several apps the claim names resolves to one account, so reaches one app
    to_handle = text.replace("wrote on SMS or MMS", "wrote to @northstar on Telegram or SMS")
    made, handle = build_text(c, to_handle, ClaimType.COMMUNICATION, C05_ANSWER)
    assert made == [], [a.params for a in made]
    assert any("or a handle" in d.reason for d in handle.drops), handle.drops
    # an app the claim names in lower case widens the row the model scoped
    lower = 'On March 12, 2026, PETROV wrote on Telegram or whatsapp: "need 2 more by friday".'
    on_telegram = [{**p, "channels": ["Telegram"]} for p in C05_ANSWER]
    made, _ = build_text(c, lower, ClaimType.COMMUNICATION, on_telegram)
    assert {frozenset(a.params.channels) for a in made} == {frozenset({"Telegram", "WhatsApp"})}
    # an app's name inside a quote a line break wraps is the quote's, not the claim's
    wrapped = (
        'On March 12, 2026, PETROV wrote to @northstar on Telegram: "need 2 more by friday",'
        ' adding "try\nSignal tomorrow".'
    )
    tg = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)
    assert tg.claim_apps(wrapped) == {"telegram"}
    # in one quote, a wrapped app name is the message's, and the claim is read on Telegram
    one = wrapped.replace('friday",\n adding "try', "friday, try").replace(
        'friday", adding "try', "friday, try"
    )
    assert one.count('"') == 2, one
    made, _ = build_text(c, one, ClaimType.COMMUNICATION, C05_ANSWER)
    assert {a.template_id for a in made} >= {"sender", "record_time"}
    # its second quote, which no row tests, needs an expert (CodeRabbit on #265)
    made, _ = build_text(c, wrapped, ClaimType.COMMUNICATION, C05_ANSWER)
    assert {a.template_id for a in made} >= {"sender", "record_time", "event"}


def test_a_plain_word_app_written_lowercase_binds_no_row(tmp_path):
    # "his second line" names no Line (CodeRabbit on #265): a row on no app, the model's or
    # code's own, is never bound to Line, where a true message on another app would go
    # unfound, and the sheet check does not excuse a Line the model chose, since `claim_apps`
    # reads the same.
    c = _case_with(
        tmp_path,
        "INSERT INTO threads VALUES ('thr:ln', 'item1', 'x', 'dev:item1', 'Line', NULL)",
    )
    filler = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)
    phone = tuple(filler._phone_message_apps())

    def rows(text: str, answer: list[dict]) -> dict[str, tuple[str, ...]]:
        made, _ = build_text(c, text, ClaimType.COMMUNICATION, answer)
        got = {a.template_id: tuple(a.params.channels) for a in made}
        assert {"sender", "record_time"} <= set(got), got
        return got

    texted = 'On March 12, 2026, PETROV texted REYES on his second line: "need 2 more by friday".'
    wrote = 'On March 12, 2026, PETROV wrote to REYES on his second line: "need 2 more by friday".'
    named = 'On March 12, 2026, PETROV wrote to REYES on Line: "need 2 more by friday".'
    beside = (
        'On March 12, 2026, PETROV wrote to REYES on Telegram or his second line: "need 2 more'
        ' by friday".'
    )
    # the model's rows on no app
    got = rows(texted, C05_ANSWER)
    assert got["sender"] == got["record_time"] == phone
    got = rows(wrote, C05_ANSWER)
    assert got["sender"] == got["record_time"] == ()
    got = rows(named, C05_ANSWER)
    assert got["sender"] == got["record_time"] == ("Line",)
    # beside an app written as a name, a lowercase plain word is left out
    got = rows(beside, C05_ANSWER)
    assert got["sender"] == got["record_time"] == ("Telegram",)
    # code's own sender searches the same apps
    assert set(phone) <= set(filler._message_apps(texted) or ()) and "Line" not in (
        filler._message_apps(texted) or ()
    )
    assert filler._message_apps(wrote) == []
    assert filler._message_apps(named) == ["Line"]
    assert filler._message_apps(beside) == ["Telegram"]
    # and the sheet check excuses only those
    assert filler.claim_apps(texted) == frozenset(a.casefold() for a in phone)
    assert filler.claim_apps(wrote) == frozenset()
    assert filler.claim_apps(named) == frozenset({"line"})
    assert filler.claim_apps(beside) == frozenset({"telegram"})


def test_coderabbit_round_on_4a9bc77(tmp_path):
    # Five findings from CodeRabbit's review of 4a9bc77 on #265.
    c = _case_with(
        tmp_path,
        "INSERT INTO threads VALUES ('thr:imsg', 'item1', 'x', 'dev:item1', 'iMessage', NULL)",
        "INSERT INTO threads VALUES ('thr:sig', 'item1', 'y', 'dev:item1', 'Signal', NULL)",
        "INSERT INTO threads VALUES ('thr:fbm', 'item1', 'z', 'dev:item1', 'Facebook Messenger',"
        " NULL)",
    )
    filler = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)
    # 1. "sent an SMS": code's own sender searches the SMS app, never the iMessage store
    # beside it, which the binding would refuse, leaving the claim unread
    sms = 'On March 12, 2026, PETROV sent an SMS to @northstar: "need 2 more by friday".'
    assert filler._message_apps(sms) == ["SMS"]
    made, _ = build_text(c, sms, ClaimType.COMMUNICATION, [C05_ANSWER[1]])
    got = {a.template_id: tuple(a.params.channels) for a in made}
    assert got.get("sender") == ("SMS",), got
    # 2. an app named only inside the quote is no app the model may put a row on
    quoted = (
        'On March 12, 2026, PETROV wrote to @northstar on Telegram: "need 2 more by friday on'
        ' Signal".'
    )
    said = "need 2 more by friday on Signal"
    on_signal = [{**p, "channels": ["Signal"], "quoted_text": said} for p in C05_ANSWER]
    made, f = build_text(c, quoted, ClaimType.COMMUNICATION, on_signal)
    assert [d.reason for d in f.drops] == ["the claim does not name the channel 'Signal'"] * 2
    assert {a.template_id: a.params.channels for a in made} == {
        "sender": ("Telegram",),
        "record_time": ("Telegram",),
    }
    # the model's own rows on the app the claim names are kept, on that app
    on_telegram = [{**p, "channels": ["Telegram"], "quoted_text": said} for p in C05_ANSWER]
    made, f = build_text(c, quoted, ClaimType.COMMUNICATION, on_telegram)
    assert not f.drops, f.drops
    assert {(a.template_id, a.params.channels, a.params.quoted_text) for a in made} == {
        ("sender", ("Telegram",), said),
        ("record_time", ("Telegram",), said),
    }
    # 3. "Facebook" alone beside a held "Facebook Messenger" is an app the case lacks
    assert filler._names_an_app_the_case_lacks("on Facebook and Facebook Messenger")
    assert not filler._names_an_app_the_case_lacks("on Facebook Messenger")

    # 4. read on the kept rows (`coverage_gap`)
    def gap(text: str, *rows: Proposal) -> str | None:
        cl = Claim(
            id="X1",
            paragraph_id="p",
            text=text,
            claim_type=ClaimType.COMMUNICATION,
            status=ClaimStatus.ACCEPTED,
        )
        return coverage_gap(cl, list(rows))

    class _W:
        raw = "On March 12, 2026, at 9:31"

    def row(tid: str, quote: str) -> Proposal:
        return Proposal(tid, {"quoted_text": quote, "window": _W()})

    # a time to the second is tested by no check, whatever path its range took
    secs = 'On March 12, 2026, at 9:31:04, PETROV wrote to @northstar: "ok".'
    assert "to the second" in (gap(secs, row("sender", "ok"), row("record_time", "ok")) or "")
    assert (
        gap(secs.replace("9:31:04", "9:31"), row("sender", "ok"), row("record_time", "ok")) is None
    )
    # 5. each quoted message needs a row that tests it, or an expert
    two = (
        'On March 12, 2026, PETROV wrote to @northstar: "need 2 more by friday" and then "on my'
        ' way".'
    )
    made, _ = build_text(c, two, ClaimType.COMMUNICATION, C05_ANSWER)
    assert {a.template_id for a in made} == {"sender", "record_time", "event"}
    one = 'On March 12, 2026, PETROV wrote to @northstar: "need 2 more by friday".'
    made, _ = build_text(c, one, ClaimType.COMMUNICATION, C05_ANSWER)
    assert {a.template_id for a in made} == {"sender", "record_time"}
    # a quote that only names a party is no message, read without spaces or punctuation
    named = one.replace("@northstar:", '@northstar ("Daniel  Petrov,"):')
    made, _ = build_text(c, named, ClaimType.COMMUNICATION, C05_ANSWER)
    assert {a.template_id for a in made} == {"sender", "record_time"}


def test_coderabbit_round_on_4ecf6d3(tmp_path):
    # Findings from CodeRabbit's review of 4ecf6d3 on #265.
    c = _case_with(
        tmp_path,
        "INSERT INTO threads VALUES ('thr:imsg', 'item1', 'x', 'dev:item1', 'iMessage', NULL)",
        "INSERT INTO threads VALUES ('thr:line', 'item1', 'w', 'dev:item1', 'Line', NULL)",
    )
    filler = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)
    # 1. "an SMS on his second line", on a case with Line: code's own sender searches SMS,
    # never every phone app with the iMessage store
    line = (
        'On March 12, 2026, PETROV sent an SMS on his second line to @northstar: "need 2 more'
        ' by friday".'
    )
    assert filler._message_apps(line) == ["SMS"]
    # 2. a handle ("@sms") names an account, never the SMS app
    handle = 'On March 12, 2026, PETROV wrote to @sms on Telegram: "need 2 more by friday".'
    on_sms = [{**p, "channels": ["SMS"]} for p in C05_ANSWER]
    made, f = build_text(c, handle, ClaimType.COMMUNICATION, on_sms)
    assert [d.reason for d in f.drops] == ["the claim does not name the channel 'SMS'"] * 2
    assert {a.template_id: a.params.channels for a in made} == {
        "sender": ("Telegram",),
        "record_time": ("Telegram",),
    }
    # 3. a zoned clock time to the second is a time of day, whatever word stands before it
    assert _states_seconds("logged for 09:31:04 UTC")
    assert _states_seconds("for 9:31:04 p.m.")
    assert _states_seconds("for 09:31:04-04:00")
    assert _states_seconds("for 09:31:04 (UTC)")
    assert _states_seconds("for 09:31:04 Eastern Time")
    assert not _states_seconds("lasted 0:12:45")
    assert not _states_seconds("for 0:12:45 at most")
    # 4. two quoted messages always need an expert: a check finds a quote's words inside a
    # longer message, so one record may pass the rows for both, whatever the rows quote
    two = (
        'On March 12, 2026, PETROV wrote to @northstar: "need 2 more by friday" and then'
        ' "I\'m on my way now".'
    )

    def rows(sent: str, timed: str) -> list[dict]:
        return [{**C05_ANSWER[0], "quoted_text": sent}, {**C05_ANSWER[1], "quoted_text": timed}]

    def kinds(text: str, answer: list[dict]) -> set[str]:
        made, _ = build_text(c, text, ClaimType.COMMUNICATION, answer)
        return {a.template_id for a in made}

    full = "need 2 more by friday"
    assert "event" in kinds(two, rows(full, "I'm on my way now"))
    assert "event" in kinds(two, rows(full, "on my way"))  # a part of the second quote
    assert "event" in kinds(two, rows(full, full))  # one quote's rows never stand for both
    twice = 'On March 12, 2026, PETROV wrote to @northstar: "ok" and then "ok".'
    assert "event" in kinds(twice, rows("ok", "ok"))
    thanks = 'On March 12, 2026, PETROV wrote to @northstar: "ok" and then "ok, thanks".'
    assert "event" in kinds(thanks, rows("ok", "ok, thanks"))
    # distinct quotes too: one record "ok, thanks" passes a row for "ok" and one for "thanks"
    apart = 'On March 12, 2026, PETROV wrote to @northstar: "ok" and then "thanks".'
    assert "event" in kinds(apart, rows("ok", "thanks"))
    # one quoted message stays code's to test
    assert kinds('On March 12, 2026, PETROV wrote to @northstar: "ok".', rows("ok", "ok")) == {
        "sender",
        "record_time",
    }
    # a name after a semicolon is a message, not a party
    semi = 'On March 12, 2026, PETROV wrote to @northstar: "need 2 more by friday"; "Petrov".'
    assert "event" in kinds(semi, C05_ANSWER)
    # 5. a quote is a party's name only where the claim writes it as a party
    said = (
        'On March 12, 2026, PETROV wrote to @northstar: "Petrov" and then "need 2 more by friday".'
    )
    assert "event" in kinds(said, C05_ANSWER)
    bracketed = 'On March 12, 2026, PETROV wrote to @northstar ("Petrov"): "need 2 more by friday".'
    assert kinds(bracketed, C05_ANSWER) == {"sender", "record_time"}
    # a name after a comma is a party only as the clause's subject, with its verb after it
    comma = (
        'On March 12, 2026, PETROV wrote to @northstar: "need 2 more by friday" and then, "Petrov".'
    )
    assert "event" in kinds(comma, C05_ANSWER)
    # nor is a trailing phrase a subject's verb: "Petrov" on Telegram is a message
    trailing = comma.replace('"Petrov".', '"Petrov" on Telegram.')
    assert "event" in kinds(trailing, C05_ANSWER)
    from core.audit.assumption_filler import _quote_is_a_party

    subject = 'On November 6, 2022, "ThisIs DfirTwo" asked SUBJECT-1, "Can you delete it?"'
    at = subject.index('"ThisIs')
    assert _quote_is_a_party(subject, at, subject.index(" asked"))
    then = 'On November 6, 2022, "ThisIs DfirTwo" then asked SUBJECT-1, "Can you delete it?"'
    assert _quote_is_a_party(then, then.index('"ThisIs'), then.index(" then"))
    end = comma.rindex('"') + 1
    assert not _quote_is_a_party(comma, comma.rindex('"', 0, end - 1), end)
    # a comma before the verb makes it an attribution: the quote is the message PETROV wrote
    attributed = comma.replace('"Petrov".', '"Petrov", wrote PETROV.')
    end = attributed.index('", wrote') + 1
    assert not _quote_is_a_party(attributed, attributed.rindex('"', 0, end - 1), end)
    assert "event" in kinds(attributed, C05_ANSWER)


def test_a_phone_named_after_an_app_puts_no_message_row_on_that_app(tmp_path):
    # "on the WHATSAPP PHONE" names a phone, not WhatsApp: code's own sender searches the
    # app the claim names, and the model's WhatsApp channel is left out of its rows, which are
    # then scoped to the app the claim names (CodeRabbit on #265).
    from core.review import actions

    c = _case_with(tmp_path)
    at = D(2026, 10, 26, 12, tzinfo=UTC)
    actions.name_device(c, "dev:item1", ["WHATSAPP PHONE"], "expert:Test Expert", lambda: at)
    filler = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)
    text = (
        'On March 12, 2026, on the WHATSAPP PHONE, PETROV wrote to @northstar on Telegram: "need'
        ' 2 more by friday".'
    )
    assert filler._message_apps(text) == ["Telegram"]
    on_whatsapp = [{**p, "channels": ["WhatsApp"]} for p in C05_ANSWER]
    made, f = build_text(c, text, ClaimType.COMMUNICATION, on_whatsapp)
    assert not f.drops, f.drops
    assert {a.template_id: a.params.channels for a in made} == {
        "sender": ("Telegram",),
        "record_time": ("Telegram",),
    }


def test_a_phone_named_after_a_message_kind_gives_code_s_sender_no_kind(tmp_path):
    # "On the SMS PHONE" names a phone, not SMS: on a case with SMS and iMessage stores, code's
    # own sender searches every app, as for any claim that names none, and is kept by the
    # binding (CodeRabbit on #265).
    from core.review import actions

    c = _case_with(
        tmp_path,
        "INSERT INTO threads VALUES ('thr:imsg', 'item1', 'x', 'dev:item1', 'iMessage', NULL)",
    )
    at = D(2026, 10, 26, 12, tzinfo=UTC)
    actions.name_device(c, "dev:item1", ["SMS PHONE"], "expert:Test Expert", lambda: at)
    filler = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)
    text = (
        'On March 12, 2026, on the SMS PHONE, PETROV wrote to @northstar: "need 2 more by friday".'
    )
    assert filler._message_apps(text) == []
    made, f = build_text(c, text, ClaimType.COMMUNICATION, [C05_ANSWER[1]])
    assert {a.template_id for a in made} == {"sender", "record_time"}, f.drops
    (sender,) = [a for a in made if a.template_id == "sender"]
    assert sender.params.channels == ()
    # an iMessage written apart from the phone's name is that kind alone
    imsg = text.replace("PETROV wrote to", "PETROV wrote an iMessage to")
    assert filler._message_apps(imsg) == ["iMessage"]
    made, f = build_text(c, imsg, ClaimType.COMMUNICATION, [C05_ANSWER[1]])
    assert {a.template_id: a.params.channels for a in made}.get("sender") == ("iMessage",), f.drops


def test_a_phone_named_after_an_app_off_the_case_keeps_code_s_sender(tmp_path):
    # "the SMS TELEGRAM PHONE" names a phone, not Telegram: on a case with no Telegram, the
    # check for an app the case lacks reads the claim without the phone's name, so code's own
    # sender stands (CodeRabbit on #265)
    from core.review import actions

    c = _case_with(
        tmp_path,
        "INSERT INTO threads VALUES ('thr:imsg', 'item1', 'x', 'dev:item1', 'iMessage', NULL)",
    )
    at = D(2026, 10, 26, 12, tzinfo=UTC)
    actions.name_device(c, "dev:item1", ["SMS SIGNAL PHONE"], "expert:Test Expert", lambda: at)
    text = (
        'On March 12, 2026, on the SMS SIGNAL PHONE, PETROV wrote to @northstar: "need 2 more'
        ' by friday".'
    )
    made, f = build_text(c, text, ClaimType.COMMUNICATION, [C05_ANSWER[1]])
    assert {a.template_id for a in made} == {"sender", "record_time"}, f.drops
    # Signal written apart from the phone's name still stops code's sender
    signal = text.replace("PETROV wrote to", "PETROV wrote on Signal to")
    made, f = build_text(c, signal, ClaimType.COMMUNICATION, [C05_ANSWER[1]])
    assert "sender" not in {a.template_id for a in made}


def test_a_phone_named_only_by_a_message_kind_gives_code_no_sender(tmp_path):
    # a phone the expert named "the SMS": "sent an SMS on the SMS" cannot tell the phone from
    # the kind, so code's own sender searches no app and the claim stays the expert's
    # (CodeRabbit on #265)
    from core.review import actions

    c = _case_with(
        tmp_path,
        "INSERT INTO threads VALUES ('thr:imsg', 'item1', 'x', 'dev:item1', 'iMessage', NULL)",
    )
    at = D(2026, 10, 26, 12, tzinfo=UTC)
    actions.name_device(c, "dev:item1", ["the SMS"], "expert:Test Expert", lambda: at)
    filler = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)
    text = (
        'On March 12, 2026, PETROV sent an SMS on the SMS to @northstar: "need 2 more by friday".'
    )
    assert filler._message_apps(text) is None
    made, _ = build_text(c, text, ClaimType.COMMUNICATION, [C05_ANSWER[1]])
    assert "sender" not in {a.template_id for a in made}
    # nor does a model's row stand: no message row can tell the phone from the kind
    made, f = build_text(c, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert not {a.template_id for a in made} & {"sender", "record_time"}
    assert any("only an app's or a kind's" in d.reason for d in f.drops), f.drops
    # an absence too: "no contact on the SMS" may be the phone or the kind
    absent = "PETROV had no contact with @northstar on the SMS between March 20 and March 23, 2026."
    none = P(
        "no_contact",
        people=["PETROV"],
        handles=["@northstar"],
        window=W("between March 20 and March 23, 2026", "2026-03-20T00:00", "2026-03-24T00:00"),
    )
    made, f = build_text(c, absent, ClaimType.ABSENCE, [none])
    assert "no_contact" not in {a.template_id for a in made}
    assert any("only an app's or a kind's" in d.reason for d in f.drops), f.drops
    # a handle ("to @SMS") is an account, never the phone
    handle = 'On March 12, 2026, PETROV wrote to @SMS on Telegram: "need 2 more by friday".'
    assert filler._message_apps(handle) == ["Telegram"]
    # nor does it hold code's sender to that phone: the message may be on another one
    assert filler._written_phones(handle) == set()
    made, f = build_text(c, handle, ClaimType.COMMUNICATION, [C05_ANSWER[1]])
    (sender,) = [a for a in made if a.template_id == "sender"]
    assert sender.params.channels == ("Telegram",), sender.params
    assert not sender.params.device_ids, sender.params
    # nor a web address, whatever its suffix, while a phone named by a whole address is read
    pixel = 'On March 12, 2026, PETROV wrote to @northstar from https://SMS.dev/notes: "ok".'
    assert filler._written_phones(pixel) == set()
    # an address ends at an angle bracket: the phone written after it is still the claim's
    bracketed = "PETROV wrote on <https://example.dev/notes>,SMS,"
    assert filler._phone_spans(bracketed) == [("dev:item1", 44, 47)]
    # nor does a host start before the mark that ends a phone's name
    before = 'On March 12, 2026, on SMS,https://example.com PETROV wrote to @northstar: "ok".'
    assert filler._written_phones(before) == {"dev:item1"}
    # and the phone named as a kind there still stops code's sender
    assert filler._message_apps(before) is None
    made, _ = build_text(c, before, ClaimType.COMMUNICATION, [C05_ANSWER[1]])
    assert "sender" not in {a.template_id for a in made}
    actions.name_device(c, "dev:item1", ["the SMS", "SMS.COM"], "expert:Test Expert", lambda: at)
    assert filler._phone_spans("PETROV wrote on SMS.COM") == [("dev:item1", 16, 23)]
    # the phone's name inside a quote is the message's words, not the phone
    quoted = 'On March 12, 2026, PETROV wrote to @northstar on Telegram: "see you on the SMS".'
    assert filler._message_apps(quoted) == ["Telegram"]
    made, f = build_text(c, quoted, ClaimType.COMMUNICATION, [C05_ANSWER[1]])
    assert {a.template_id for a in made} >= {"sender", "record_time"}, f.drops


def test_a_phone_named_only_by_an_app_the_case_lacks_gives_code_no_sender(tmp_path):
    # "the SIGNAL" for a phone on a case with no Signal: "on the SIGNAL" may be the phone or
    # the app, so no message row is kept (CodeRabbit on #265)
    from core.review import actions

    c = _case_with(tmp_path)
    at = D(2026, 10, 26, 12, tzinfo=UTC)
    actions.name_device(c, "dev:item1", ["the SIGNAL"], "expert:Test Expert", lambda: at)
    filler = LocalAssumptionFiller(FakeModel("{}"), c, template=DRAFT)
    text = 'On March 12, 2026, on the SIGNAL, PETROV wrote to @northstar: "need 2 more by friday".'
    assert filler._message_apps(text) is None
    made, f = build_text(c, text, ClaimType.COMMUNICATION, C05_ANSWER)
    assert not {a.template_id for a in made} & {"sender", "record_time"}
    assert any("only an app's or a kind's" in d.reason for d in f.drops), f.drops
