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
    _without_claims_comma,
)
from core.audit.assumptions import TemplateAssumptionBuilder, is_code_made
from core.audit.checks import run_checks
from core.audit.checks._common import sentence_aligned
from core.audit.rules import decide_verdict
from core.contracts import (
    AssumptionKind,
    CheckOutcome,
    Claim,
    ClaimStatus,
    ClaimType,
    Verdict,
)
from core.db import apply_schema, connect
from eval.synthetic.generate import generate
from tests.checks.helpers import NY, check, stipulate
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


def test_a_curly_quote_with_the_claims_comma_inside_is_the_message(conn):
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=PROMPT)
    c = _claim(
        conn,
        "At 2:31 a.m. on March 5, 2026, PETROV texted REYES “its done,” which shows the job"
        " was finished.",
        ClaimType.CONTENT_MEANING,
    )
    assert filler.the_quote(c, []) == "its done"


def test_a_quote_nested_in_the_message_stays_part_of_it(conn):
    filler = LocalAssumptionFiller(FakeModel("{}"), conn, template=PROMPT)
    c = _claim(conn, "PETROV texted REYES \"he said 'its done'\".", ClaimType.CONTENT_MEANING)
    assert filler.the_quote(c, []) == "he said 'its done'"


# --- the claim's comma is not the message's


@pytest.mark.parametrize(
    ("words", "text", "want"),
    [
        # American usage: the claim's comma sits inside its closing mark.
        ("ready when needed,", 'His text "ready when needed," shows it.', "ready when needed"),
        ("ready when needed,", "His text “ready when needed,” shows it.", "ready when needed"),
        # A comma inside the message is the message's.
        ("got the money,", 'He wrote "got the money, come get it".', "got the money,"),
        # Only a comma, and only one: other marks stay as written.
        ("ready.", 'He wrote "ready."', "ready."),
        ("wait,,", 'He wrote "wait,,"', "wait,,"),
    ],
)
def test_without_claims_comma(words, text, want):
    assert _without_claims_comma(words, text) == want


def test_a_model_quote_with_the_claims_comma_finds_the_message(conn):
    # The record reads "its done"; the claim writes "its done," and the model copied the
    # comma. Without it the checks find the message; with it they found nothing.
    text = (
        'At 2:31 a.m. on March 5, 2026, PETROV texted REYES "its done," which shows the job'
        " was finished."
    )
    window = W("At 2:31 a.m. on March 5, 2026", "2026-03-04T21:00", "2026-03-04T22:00")
    props = [P("sender", people=["PETROV"], quoted_text="its done,"),
             P("record_time", people=["PETROV"], quoted_text="its done,", window=window),
             P("meaning", quoted_text="its done,")]  # fmt: skip
    c, made, filler = build(conn, text, ClaimType.CONTENT_MEANING, props)
    assert {a.params.quoted_text for a in made} == {"its done"}, reasons(filler)
    (sender,) = [a for a in made if a.template_id == "sender"]
    (r,) = run_checks(sender, conn)
    assert r.outcome is CheckOutcome.PASS and "msg:item1:Chats!1011" in r.record_ids


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
    # says the opposite. The words sit inside a longer sentence, so who sent it and when are
    # not settled (sender 1.2.0, time 1.1.0), and what they mean is the expert's to judge: the
    # meaning stays uncovered.
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
    (sender,) = [a for a in made if a.template_id == "sender"]
    (r,) = run_checks(sender, conn)
    assert r.outcome is CheckOutcome.INCONCLUSIVE and "different or unknown senders" in r.detail
    # (Every "ok" of PETROV's on the phone is dated another day, so the time check fails.)
    decision, _ = verdict(conn, c, made)
    assert decision.verdict is not Verdict.SUPPORTED


# --- the sender check: someone else's only on a record or a confirmed fact (sender 1.1.0)

OWNER, Q, R, S = "person:owner", "person:q", "person:r", "person:s"


def sender_case() -> sqlite3.Connection:
    """One phone, its owner by confirmed stipulation, and accounts the case ties to people in
    different ways. Every value is invented."""
    conn = connect(":memory:")
    apply_schema(conn)
    conn.execute(
        "INSERT INTO sources VALUES ('p1', 'synthetic', 'full_extraction', 'file_system', 'f',"
        " '0', NULL, NULL, NULL, '2026-05-01T00:00:00Z')"
    )
    conn.execute("INSERT INTO devices VALUES ('dev:p1', 'p1', 'x', 'phone', NULL, NULL, ?)", (NY,))
    accounts = [
        # id, device (own accounts only), app, identifier
        ("a:own:sms", "dev:p1", "SMS", "+15550000001"),
        ("a:own:wa", "dev:p1", "WhatsApp", "15550000001@s.whatsapp.net"),
        ("a:q:sms", None, "SMS", "+15550000002"),  # Q's only account, by confirmed link
        ("a:x:wa", None, "WhatsApp", "x@s.whatsapp.net"),  # linked to no one
        ("a:y:wa", None, "WhatsApp", "y@s.whatsapp.net"),  # linked to no one
        ("a:unflagged:wa", None, "WhatsApp", "own2@s.whatsapp.net"),  # an own handle, unflagged
        ("a:r:wa", None, "WhatsApp", "r@s.whatsapp.net"),  # R's, by confirmed link
        ("a:r:sms", None, "SMS", "+15550000003"),  # R's too, by confirmed link
        ("a:s:wa", None, "WhatsApp", "s@s.whatsapp.net"),  # S's by a proposed link only
    ]
    conn.executemany("INSERT INTO accounts VALUES (?, 'p1', 'x', ?, ?, ?, NULL)", accounts)
    conn.executemany(
        "INSERT INTO threads VALUES (?, 'p1', 'x', NULL, ?, NULL)",
        [("t:sms", "SMS"), ("t:wa", "WhatsApp")],
    )
    for pid, name in ((Q, "Q"), (R, "R"), (S, "S")):
        conn.execute("INSERT INTO persons VALUES (?, ?, 'expert:test')", (pid, name))
    for acc, pid, status in (
        ("a:q:sms", Q, "confirmed"),
        ("a:r:wa", R, "confirmed"),
        ("a:r:sms", R, "confirmed"),
        ("a:s:wa", S, "proposed"),
    ):
        conn.execute(
            "INSERT INTO identity_links VALUES (?, ?, ?, ?, 'confirmed', 'test', 'expert:test',"
            " '2026-05-01T00:00:00Z')",
            (f"link:{acc}", acc, pid, status),
        )
    msgs = [
        # id, sender, direction, body
        ("m:alpha", "a:x:wa", "incoming", "alpha"),
        ("m:bravo", "a:unflagged:wa", "outgoing", "bravo"),
        ("m:charlie", "a:own:wa", "outgoing", "charlie"),
        ("m:delta", "a:r:wa", "incoming", "delta"),
        ("m:echo", "a:s:wa", "incoming", "echo"),
        ("m:foxtrot", "a:y:wa", "incoming", "foxtrot"),
        ("m:golf", "a:x:wa", "unknown", "golf"),
        ("m:hotel1", "a:q:sms", "incoming", "hotel"),
        ("m:hotel2", "a:r:wa", "incoming", "hotel"),
        ("m:india1", "a:q:sms", "incoming", "india"),
        ("m:india2", "a:x:wa", "incoming", "india"),
        ("m:juliet", "a:r:sms", "incoming", "juliet"),
    ]
    for mid, sender, direction, body in msgs:
        tid = "t:sms" if ":sms" in sender else "t:wa"
        conn.execute(
            "INSERT INTO messages (id, source_id, locator, thread_id, sender_account_id,"
            " direction, ts_utc, body) VALUES (?, 'p1', 'x', ?, ?, ?, '2026-03-10T15:00:00Z', ?)",
            (mid, tid, sender, direction, body),
        )
    stipulate(conn, OWNER, "Owner", "dev:p1")
    return conn


@pytest.mark.parametrize(
    ("words", "party", "want"),
    [
        # A person defined by one linked account; the words came from an account
        # on another app that no confirmed link ties to anyone. Unknown, never a fail.
        ("alpha", {"person_ids": [Q]}, CheckOutcome.INCONCLUSIVE),
        # The owner expected, and the phone recorded the message as received: someone else's.
        ("alpha", {"person_ids": [OWNER]}, CheckOutcome.FAIL),
        # The owner expected, an outgoing row from an own handle the export did not flag.
        ("bravo", {"person_ids": [OWNER]}, CheckOutcome.INCONCLUSIVE),
        # The owner expected, and the direction is unknown.
        ("golf", {"person_ids": [OWNER]}, CheckOutcome.INCONCLUSIVE),
        # A third party expected, and the phone's own account sent it.
        ("charlie", {"person_ids": [Q]}, CheckOutcome.FAIL),
        # The sender is another person's by a confirmed link.
        ("delta", {"person_ids": [Q]}, CheckOutcome.FAIL),
        # The same with only a proposed link: proposed links never count.
        ("echo", {"person_ids": [Q]}, CheckOutcome.INCONCLUSIVE),
        # A bare account expected, another unlinked account on the same app sent it: one user
        # can hold two handles.
        ("foxtrot", {"account_ids": ["a:x:wa"]}, CheckOutcome.INCONCLUSIVE),
        # The sender is R's, and so is the account expected: not someone else.
        ("juliet", {"account_ids": ["a:r:wa"]}, CheckOutcome.INCONCLUSIVE),
        # Mixed copies: one from Q, one from R (someone else) or from no one known.
        ("hotel", {"person_ids": [Q]}, CheckOutcome.INCONCLUSIVE),
        ("india", {"person_ids": [Q]}, CheckOutcome.INCONCLUSIVE),
        # Every copy from someone else, and every copy from the party, are unchanged.
        ("delta", {"person_ids": [OWNER]}, CheckOutcome.FAIL),
        ("delta", {"person_ids": [R]}, CheckOutcome.PASS),
        ("charlie", {"person_ids": [OWNER]}, CheckOutcome.PASS),
    ],
)
def test_the_sender_check_fails_only_on_a_record_or_a_confirmed_fact(words, party, want):
    r = check(sender_case(), "sender", quoted_text=words, **party)
    assert r.outcome is want, r.detail
    if words in {"alpha", "foxtrot", "golf"} and want is CheckOutcome.INCONCLUSIVE:
        assert "no confirmed link ties" in r.detail


# --- a quote that sits inside a longer sentence (sender 1.2.0, time 1.1.0)


@pytest.mark.parametrize(
    ("quote", "body", "aligned"),
    [
        ("dont text me about it, use telegram", "dont text me about it, use telegram", True),
        ("text me about it", "dont text me about it, use telegram", False),  # reverses it
        ("I did not say", "I did not say go", False),
        ("not say go", "I did not say go", False),
        ("van is back at gus", "home. van is back at gus", True),
        ("back at gus", "home. van is back at gus", False),  # inside its clause
        # No punctuation at all: the whole message aligns; a quote that stops before more
        # words with no mark between does not.
        ("ok see you at 5", "ok see you at 5", True),
        ("ok see you at 5", "ok see you at 5 bring the stuff", False),
        # A clause cut at a comma, a semicolon, a colon or a dash.
        ("use telegram", "dont text me about it, use telegram", True),
        ("got the money", "got the money, come get it", True),
        ("got the money", "got the money - come get it", True),
        ("got the money", "got the money; come get it", True),
        ("send", "pls re-send", False),  # a hyphen inside a word is no dash
        # A sentence of a longer message, between sentence ends, curly or straight.
        ("Lets go now", "Yes. Lets go now. Bring it.", True),
        ("Let's go now", "Yes. Let’s go now. Bring it.", True),
        ("Yes.", "Yes. Lets go now.", True),
        # An emoji or a line break ends a sentence.
        ("come get it", "got the money 😀 come get it", True),
        ("got the money", "got the money 😀 come get it", True),
        ("come get it", "got the money\ncome get it", True),
        ("got the money", "got the money\n\ncome get it", True),
        # An ellipsis ends one; the message's own quotation marks do not hide its start.
        ("bring it", "I'll be there... bring it", True),
        ("ok", '"ok"', True),
        ("ok", "  ok  ", True),
    ],
)
def test_sentence_aligned(quote, body, aligned):
    assert sentence_aligned(quote, body) is aligned


def test_a_communication_claim_quoting_a_reversing_fragment_is_not_supported(conn):
    # Code-checked support (rule 3c') must not rest on words cut out of a sentence that says
    # the opposite: "text me about it" from "dont text me about it, use telegram".
    quote = "text me about it"
    text = f'On March 19, 2026, PETROV texted REYES "{quote}".'
    window = W("On March 19, 2026", "2026-03-19T00:00", "2026-03-20T00:00")
    props = [P("sender", people=["PETROV"], quoted_text=quote),
             P("record_time", people=["PETROV"], quoted_text=quote, window=window)]  # fmt: skip
    c, made, filler = build(conn, text, ClaimType.COMMUNICATION, props)
    decision, checks = verdict(conn, c, made)
    assert {r.outcome for r in checks} == {CheckOutcome.INCONCLUSIVE}, reasons(filler)
    assert all("dont text me about it, use telegram" in r.detail for r in checks)
    assert decision.verdict is Verdict.UNPROVEN


def test_the_whole_message_still_passes(conn):
    quote = "dont text me about it, use telegram"
    text = f'On March 19, 2026, PETROV texted REYES "{quote}".'
    window = W("On March 19, 2026", "2026-03-19T00:00", "2026-03-20T00:00")
    props = [P("sender", people=["PETROV"], quoted_text=quote),
             P("record_time", people=["PETROV"], quoted_text=quote, window=window)]  # fmt: skip
    c, made, _ = build(conn, text, ClaimType.COMMUNICATION, props)
    decision, checks = verdict(conn, c, made)
    assert {r.outcome for r in checks} == {CheckOutcome.PASS}
    assert decision.verdict is Verdict.SUPPORTED


def test_a_fragment_never_fails_the_time_check(conn):
    # The fragment's message is dated outside the window: it may be another message, so the
    # time check does not fail on it.
    window = W("On March 1, 2026", "2026-03-01T00:00", "2026-03-02T00:00")
    props = [P("record_time", people=["PETROV"], quoted_text="text me about it", window=window)]
    text = 'On March 1, 2026, PETROV texted REYES "text me about it".'
    _, made, _ = build(conn, text, ClaimType.TIMING, props + [P("sender", people=["PETROV"],
                       quoted_text="text me about it")])  # fmt: skip
    (rt,) = [a for a in made if a.template_id == "record_time"]
    (r,) = run_checks(rt, conn)
    assert r.outcome is CheckOutcome.INCONCLUSIVE
    assert "inside a longer sentence" in r.detail
