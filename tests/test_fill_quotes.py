"""Claims that quote a message: which quote is the message, its words, and its meaning.

Synthetic case01 only (eval/synthetic), with a scripted fake model. The meaning of quoted
words is interpretation: code reads which words a claim quotes and finds them in the records,
and a meaning assumption stays for the expert to accept, whatever the checks find.
"""

import json
import sqlite3

import pytest

from core.audit.assumption_filler import (
    _MESSAGE_CUE_RE,
    LocalAssumptionFiller,
)
from core.audit.assumptions import TemplateAssumptionBuilder, is_code_made
from core.audit.checks import run_checks
from core.audit.rules import decide_verdict
from core.contracts import (
    AssumptionKind,
    CheckOutcome,
    Claim,
    ClaimStatus,
    ClaimType,
    Verdict,
)
from eval.synthetic.generate import generate
from tests.checks.helpers import stipulate
from tests.fake_model import FakeModel

PETROV, REYES = "person:petrov", "person:reyes"
PARA = "para:quotes"
PROMPT = "{claim}{paragraph}{templates}{channels}"


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    out = tmp_path_factory.mktemp("case01")
    db = out / "case01.db"
    generate(out, db)
    c = sqlite3.connect(db)
    stipulate(c, PETROV, "Daniel Petrov", "dev:item1")
    stipulate(c, REYES, "Marcus Reyes", "dev:item2")
    yield c
    c.close()


def P(template_id: str, **kw) -> dict:  # noqa: N802
    base = dict(people=[], accounts=[], handles=[], phones=[], channels=[], quoted_text="",
                count=None, duration=None, window=None)  # fmt: skip
    return {"template_id": template_id, **base, **kw}


def W(as_written: str, start: str, end: str) -> dict:  # noqa: N802
    return {"as_written": as_written, "start": start, "end": end, "zone": "phone"}


def _claim(conn, text: str, claim_type: ClaimType) -> Claim:
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        "INSERT OR REPLACE INTO govdoc_paragraphs (id, govdoc_id, page, para_no, label,"
        " char_start, char_end, text) VALUES (?, 'gd', 1, 1, '1', 0, ?, ?)",
        (PARA, len(text), text),
    )
    return Claim(id="X1", paragraph_id=PARA, text=text, claim_type=claim_type,
                 status=ClaimStatus.ACCEPTED)  # fmt: skip


def build(conn, text: str, claim_type: ClaimType, props: list[dict]):
    filler = LocalAssumptionFiller(
        FakeModel(json.dumps({"assumptions": props})), conn, template=PROMPT
    )
    c = _claim(conn, text, claim_type)
    return c, TemplateAssumptionBuilder(filler).build(c), filler


def verdict(conn, c: Claim, made):
    checks = [r for a in made for r in run_checks(a, conn)]
    return decide_verdict(c, made, [], checks, [], "run:test"), checks


def reasons(filler) -> str:
    return " | ".join(d.reason for d in filler.drops)


# --- which quote is the message


@pytest.mark.parametrize(
    "before",
    [
        "PETROV wrote to @northstar on Telegram ",
        "PETROV wrote to REYES on Telegram ",
        "PETROV wrote on Telegram to REYES ",
        "PETROV texted REYES by iMessage, ",
        "PETROV texted +1 (212) 555-0111 via SMS ",
        "PETROV told REYES via Telegram direct message ",
        "PETROV wrote to the TARGET PHONE ",
    ],
)
def test_a_verb_with_its_recipient_and_app_leads_a_message(before):
    assert _MESSAGE_CUE_RE.search(before)


@pytest.mark.parametrize(
    "before",
    [
        "the contact saved as ",  # a saved name
        "the Telegram user ",  # a party's name
        "PETROV wrote about ",  # the words are a topic, not the message
        "PETROV saved REYES on Telegram as ",
        "PETROV wrote in Russian to the contact saved as ",
    ],
)
def test_other_lead_ins_lead_no_message(before):
    assert not _MESSAGE_CUE_RE.search(before)


def test_a_quote_after_the_recipient_and_app_gets_its_meaning(conn):
    # The claim quotes one message after "wrote to X on App"; the model tested who sent it and
    # when. Code adds the meaning of that one message, which only the expert can accept.
    quote = "need 2 more by friday"
    text = f'On March 12, 2026, PETROV wrote to @northstar on Telegram "{quote}".'
    window = W("On March 12, 2026", "2026-03-12T00:00", "2026-03-13T00:00")
    props = [P("sender", people=["PETROV"], channels=["Telegram"], quoted_text=quote),
             P("record_time", people=["PETROV"], channels=["Telegram"], quoted_text=quote,
               window=window)]  # fmt: skip
    c, made, filler = build(conn, text, ClaimType.CONTENT_MEANING, props)
    assert {a.template_id for a in made} == {"sender", "record_time", "meaning"}, reasons(filler)
    (meaning,) = [a for a in made if a.template_id == "meaning"]
    assert meaning.params.quoted_text == quote and meaning.is_core and is_code_made(meaning.text)
    # Sender and time pass on the records; the meaning has no check and nobody accepted it.
    decision, checks = verdict(conn, c, made)
    assert {r.outcome for r in checks} == {CheckOutcome.PASS}
    assert decision.verdict is Verdict.UNPROVEN
    assert any("mean what the claim says" in r for r in decision.reasons)


def test_a_quote_nested_in_the_message_stays_part_of_it(conn):
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=PROMPT)
    c = _claim(conn, "PETROV texted REYES \"he said 'its done'\".", ClaimType.CONTENT_MEANING)
    assert filler.the_quote(c, []) == "he said 'its done'"


# --- a claim that characterizes a message keeps an uncovered meaning


@pytest.mark.parametrize(
    "verb",
    ["complained to REYES by text", "threatened REYES by text", "admitted to REYES by text"],
)
def test_a_characterized_quote_stays_for_the_expert(conn, verb):
    quote = "dont text me about it, use telegram"
    text = f'On March 19, 2026, PETROV {verb}: "{quote}", referring to the search.'
    window = W("On March 19, 2026", "2026-03-19T00:00", "2026-03-20T00:00")
    props = [P("sender", people=["PETROV"], quoted_text=quote),
             P("record_time", people=["PETROV"], quoted_text=quote, window=window)]  # fmt: skip
    c, made, filler = build(conn, text, ClaimType.CONTENT_MEANING, props)
    meaning = [a for a in made if a.template_id == "meaning"]
    assert len(meaning) == 1 and meaning[0].kind is AssumptionKind.MEANING, reasons(filler)
    assert meaning[0].is_core and not run_checks(meaning[0], conn)  # no check covers meaning
    decision, checks = verdict(conn, c, made)
    assert all(r.outcome is CheckOutcome.PASS for r in checks)
    assert decision.verdict is Verdict.UNPROVEN


def test_a_fragment_that_reverses_the_message_stays_unproven(conn):
    # The record reads "dont text me about it, use telegram"; the claim quotes a fragment that
    # says the opposite. The words are in the record, so who sent it and when pass, but what
    # they mean is the expert's to judge: the meaning stays uncovered.
    quote = "text me about it"
    text = f'On March 19, 2026, PETROV texted REYES "{quote}", inviting more messages.'
    window = W("On March 19, 2026", "2026-03-19T00:00", "2026-03-20T00:00")
    props = [P("sender", people=["PETROV"], quoted_text=quote),
             P("record_time", people=["PETROV"], quoted_text=quote, window=window)]  # fmt: skip
    c, made, filler = build(conn, text, ClaimType.CONTENT_MEANING, props)
    assert "meaning" in {a.template_id for a in made}, reasons(filler)
    decision, _ = verdict(conn, c, made)
    assert decision.verdict is Verdict.UNPROVEN
    assert any("mean what the claim says" in r for r in decision.reasons)


def test_a_paraphrase_without_quotation_marks_is_refused(conn):
    text = "On March 19, 2026, PETROV told REYES by text to stop writing about the package."
    props = [P("event", people=["PETROV", "REYES"],
               window=W("On March 19, 2026", "2026-03-19T00:00", "2026-03-20T00:00"))]  # fmt: skip
    _, made, filler = build(conn, text, ClaimType.CONTENT_MEANING, props)
    assert made == []
    assert "the claim quotes no words" in reasons(filler)


def test_a_quoted_name_is_no_message_for_meaning(conn):
    text = 'PETROV and the Instagram user "dp_garage" discussed the money.'
    _, made, filler = build(conn, text, ClaimType.CONTENT_MEANING, [P("event", people=["PETROV"])])
    assert made == []
    assert "only quoted words are a name" in reasons(filler)


def test_two_quoted_messages_get_no_meaning_from_code(conn):
    # The model tested one of two quoted messages. Code does not give the claim's meaning to
    # one of them: the other's writer and words would go untested.
    text = (
        'On March 5, 2026, PETROV texted REYES "its done" and REYES replied "ok", showing'
        " they agreed."
    )
    props = [P("sender", people=["PETROV"], quoted_text="its done")]
    _, made, filler = build(conn, text, ClaimType.CONTENT_MEANING, props)
    assert made == []
    assert "quotes 2 messages" in reasons(filler)


def test_words_in_messages_from_different_senders_are_not_settled(conn):
    # "ok" is in messages from several accounts: the sender check does not pass or fail on it.
    text = 'On March 12, 2026, PETROV wrote to @northstar on Telegram "ok", agreeing.'
    window = W("On March 12, 2026", "2026-03-12T00:00", "2026-03-13T00:00")
    props = [P("sender", people=["PETROV"], channels=["Telegram"], quoted_text="ok"),
             P("record_time", people=["PETROV"], channels=["Telegram"], quoted_text="ok",
               window=window)]  # fmt: skip
    c, made, filler = build(conn, text, ClaimType.CONTENT_MEANING, props)
    assert "meaning" in {a.template_id for a in made}, reasons(filler)
    decision, _ = verdict(conn, c, made)
    assert decision.verdict is not Verdict.SUPPORTED
