"""The assumption filler's reading of numbers a model writes on no app or as bare digits.

Synthetic data only (eval/synthetic case01): the SMS app holds the phones' text messages, and
WhatsApp ids are numbers ("12125550122@s.whatsapp.net").
"""

from __future__ import annotations

import pytest

from core.audit.checks import run_checks
from core.contracts import CheckOutcome, ClaimType
from tests.test_assumption_filler import PETROV, W, build_text, call_log, conn  # noqa: F401

QUOTE = "running late, cover standup?"
ALEX = ("acct:item1:SMS:+12125550182",)
TEXTED = f'(212) 555-0182 sent dev:item1 a text message reading "{QUOTE}".'


def _sender(number: str = "(212) 555-0182", app: str = "unknown", **kw) -> dict:
    return {"template_id": "sender", "quoted_text": QUOTE,
            "accounts": [{"as_written": number, "app": app}], **kw}  # fmt: skip


def _made(assumptions, template_id: str):
    return [a for a in assumptions if a.template_id == template_id]


@pytest.fixture
def two_phone_apps(conn):  # noqa: F811
    # A case whose phone messages sit on two apps: "text message" could be either.
    src = conn.execute("SELECT source_id FROM threads WHERE app = 'SMS'").fetchone()[0]
    conn.execute(
        "INSERT INTO threads (id, source_id, locator, device_id, app, title)"
        " VALUES ('thr:t:imsg', ?, 'x', 'dev:item1', 'iMessage', NULL)",
        (src,),
    )
    yield conn
    conn.execute("DELETE FROM threads WHERE id = 'thr:t:imsg'")


# ------------------------------------------------- a text message's number on no app


@pytest.mark.parametrize("app", ["unknown", "text", "text message", "Unknown"])
def test_a_text_messages_number_on_no_app_is_read_on_the_phones_messaging_app(conn, app):  # noqa: F811
    # Seen on a practice run: the model wrote a texting number with app "unknown".
    assumptions, filler = build_text(conn, TEXTED, ClaimType.COMMUNICATION, [_sender(app=app)])
    (s,) = _made(assumptions, "sender")
    assert s.params.account_ids == ALEX, filler.drops
    assert s.params.channels == ("SMS",)  # the search stays on that app
    (r,) = run_checks(s, conn)
    assert r.outcome is CheckOutcome.PASS, r.detail


def test_a_text_messages_number_is_never_read_in_the_call_log(call_log):  # noqa: F811
    # The call log ("unknown") holds the number; the text sits on the SMS app, whose sender a
    # call-log party would read as someone else: a wrong "contradicted".
    text = f'(212) 555-0199 sent dev:item1 a text message reading "{QUOTE}".'
    prop = _sender("(212) 555-0199")
    assumptions, filler = build_text(call_log, text, ClaimType.COMMUNICATION, [prop])
    made = [a.params for a in assumptions if a.params.account_ids]
    assert not any(set(p.account_ids) & {"acct:t:log1", "acct:t:log2"} for p in made), made
    assert any("matches no account" in d.reason and "SMS" in d.reason for d in filler.drops)


@pytest.mark.parametrize(
    ("text", "template_id", "extra"),
    [
        (
            "On March 12, 2026, PETROV never texted (212) 555-0199.",
            "no_contact",
            {"window": W("On March 12, 2026", "2026-03-12T00:00", "2026-03-13T00:00")},
        ),
        (
            "On March 6, 2026, PETROV exchanged three text messages with (212) 555-0199 on"
            " dev:item1.",
            "message_count",
            {"count": {"value": 3}, "phones": ["dev:item1"],
             "window": W("On March 6, 2026", "2026-03-06T00:00", "2026-03-07T00:00")},
        ),
    ],
)  # fmt: skip
def test_a_count_or_an_absence_never_reads_a_text_messages_number_on_one_app(
    call_log,  # noqa: F811
    text,
    template_id,
    extra,
):
    # The number is in the call log ("unknown"). Read there, or on any one app, "never texted"
    # would pass on texts it never searched (Greptile on #253), and a count would miss them.
    prop = {"template_id": template_id, "people": ["PETROV"],
            "accounts": [{"as_written": "(212) 555-0199", "app": "unknown"}], **extra}  # fmt: skip
    kind = ClaimType.ABSENCE if template_id == "no_contact" else ClaimType.COUNT
    assumptions, filler = build_text(call_log, text, kind, [prop])
    made = [a.params for a in _made(assumptions, template_id)]
    assert not any(set(p.account_ids) & {"acct:t:log1", "acct:t:log2"} for p in made), made
    assert any("would miss the messages" in d.reason for d in filler.drops), filler.drops


def test_a_text_message_on_a_named_app_is_not_read_on_the_phones_messaging_app(conn):  # noqa: F811
    text = f'(212) 555-0182 sent dev:item1 a Telegram text message reading "{QUOTE}".'
    assumptions, filler = build_text(conn, text, ClaimType.COMMUNICATION, [_sender()])
    assert not any(set(a.params.account_ids) & set(ALEX) for a in assumptions), assumptions
    assert any("names another app" in d.reason for d in filler.drops), filler.drops


def test_a_text_message_on_an_app_off_the_case_is_refused(conn):  # noqa: F811
    text = f'(212) 555-0182 sent dev:item1 a Signal text message reading "{QUOTE}".'
    assumptions, filler = build_text(conn, text, ClaimType.COMMUNICATION, [_sender()])
    assert not any(set(a.params.account_ids) & set(ALEX) for a in assumptions), assumptions


def test_the_app_is_never_picked_among_two_phone_message_apps(two_phone_apps):
    assumptions, filler = build_text(two_phone_apps, TEXTED, ClaimType.COMMUNICATION, [_sender()])
    assert not any(set(a.params.account_ids) & set(ALEX) for a in assumptions), assumptions
    assert any("2 apps of a phone's own messages" in d.reason for d in filler.drops)


def test_a_claim_that_names_a_call_and_a_text_is_not_rewritten(conn):  # noqa: F811
    text = f'(212) 555-0182 called dev:item1 and sent a text message reading "{QUOTE}".'
    assumptions, filler = build_text(conn, text, ClaimType.COMMUNICATION, [_sender()])
    assert not any(set(a.params.account_ids) & set(ALEX) for a in assumptions), assumptions


def test_the_word_text_alone_is_no_text_message(conn):  # noqa: F811
    # "the text" of a message on any app is not a phone's text message.
    text = f'(212) 555-0182 sent dev:item1 a message with the text "{QUOTE}".'
    assumptions, filler = build_text(conn, text, ClaimType.COMMUNICATION, [_sender()])
    assert not any(set(a.params.account_ids) & set(ALEX) for a in assumptions), assumptions


def test_a_text_messages_number_keeps_the_models_other_channel_refused(conn):  # noqa: F811
    prop = _sender(channels=["Telegram"])
    text = f'(212) 555-0182 sent dev:item1 a text message on Telegram reading "{QUOTE}".'
    assumptions, filler = build_text(conn, text, ClaimType.COMMUNICATION, [prop])
    assert not any(set(a.params.account_ids) & set(ALEX) for a in assumptions), assumptions


def test_an_app_the_case_holds_by_that_name_is_the_models_own(conn):  # noqa: F811
    # "SMS" is an app in this case: the model named it, and nothing is rewritten.
    assumptions, filler = build_text(conn, TEXTED, ClaimType.COMMUNICATION, [_sender(app="SMS")])
    (s,) = _made(assumptions, "sender")
    assert s.params.account_ids == ALEX, filler.drops


# ------------------------------------------------- bare digits and a WhatsApp id


@pytest.fixture
def whatsapp_extra(conn):  # noqa: F811
    """Accounts a test adds to WhatsApp on item1, removed after."""
    src = conn.execute("SELECT source_id FROM accounts WHERE id LIKE 'acct:item1:%'").fetchone()[0]
    added: list[str] = []

    def add(aid: str, ident: str) -> None:
        conn.execute(
            "INSERT INTO accounts (id, source_id, locator, device_id, app, identifier,"
            " display_name) VALUES (?, ?, 'x', NULL, 'WhatsApp', ?, NULL)",
            (aid, src, ident),
        )
        added.append(aid)

    yield add
    conn.executemany("DELETE FROM accounts WHERE id = ?", [(a,) for a in added])


MARC_WA = (
    "acct:item1:WhatsApp:12125550122@s.whatsapp.net",
    "acct:item2:WhatsApp:12125550122@s.whatsapp.net",
)


def _uses(conn, digits: str, text: str, app: str = "WhatsApp"):  # noqa: F811
    prop = {"template_id": "person_identity", "people": ["PETROV"],
            "accounts": [{"as_written": digits, "app": app}]}  # fmt: skip
    assumptions, filler = build_text(conn, text, ClaimType.IDENTITY, [prop])
    return [a.params for a in _made(assumptions, "person_identity")], filler


def test_bare_digits_are_the_whatsapp_account_whose_id_is_that_number(conn):  # noqa: F811
    # Seen on a practice run: "the WhatsApp account <digits>", the id being
    # "<digits>@s.whatsapp.net". The same number on both phones is one party (R6).
    made, filler = _uses(conn, "12125550122", "PETROV used the WhatsApp account 12125550122.")
    (p,) = made
    assert p.account_ids == MARC_WA and p.person_ids == (PETROV,), filler.drops


@pytest.mark.parametrize("digits", ["2125550122", "112125550122", "1212555012", "212555"])
def test_only_the_whole_digits_of_a_whatsapp_id_match(conn, digits):  # noqa: F811
    # A suffix ("2125550122", the number without its country code) or a longer run is
    # another number: never a partial match.
    made, filler = _uses(conn, digits, f"PETROV used the WhatsApp account {digits}.")
    assert not made, made


def test_bare_digits_find_no_whatsapp_id_on_an_app_the_claim_does_not_name(conn):  # noqa: F811
    made, _ = _uses(conn, "12125550122", "PETROV used the account 12125550122.")
    assert not made, made
    # Telegram is named: its accounts are searched, never WhatsApp's.
    made, _ = _uses(
        conn, "12125550122", "PETROV used the Telegram account 12125550122.", "Telegram"
    )
    assert not made, made


def test_a_group_or_linked_id_with_the_same_digits_is_no_number(conn, whatsapp_extra):  # noqa: F811
    whatsapp_extra("acct:t:wa-group", "12125550122@g.us")
    whatsapp_extra("acct:t:wa-lid", "12125550122@lid")
    whatsapp_extra("acct:t:wa-plus", "+1 212-555-0122")  # the same number: one party (R6)
    made, filler = _uses(conn, "12125550122", "PETROV used the WhatsApp account 12125550122.")
    (p,) = made
    assert set(p.account_ids) == {*MARC_WA, "acct:t:wa-plus"}, filler.drops


def test_digits_that_are_one_accounts_id_and_anothers_number_are_refused(conn, whatsapp_extra):  # noqa: F811
    # The same digits on two different accounts of the app: a user id written exactly so, and a
    # WhatsApp id holding the number. Which one the claim means is not known.
    whatsapp_extra("acct:t:wa-bare", "12125550122")
    made, filler = _uses(conn, "12125550122", "PETROV used the WhatsApp account 12125550122.")
    assert not made, made
    assert any("one account's id and another's number" in d.reason for d in filler.drops)
