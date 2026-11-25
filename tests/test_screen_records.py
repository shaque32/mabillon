"""The screen's record rows (ui/records.py): a record reads as one calm row, and every value the
longer line showed (the UTC time, the time as printed, the record id, the spreadsheet row and
what that row number means, the tier, the direction) is still on the same page, one fold away.
Synthetic demo case only."""

from __future__ import annotations

import html
import re
from dataclasses import replace

import pytest

from core.casework import cases
from core.contracts import ProvenanceTier
from core.db import connect
from core.report.html import record_line
from core.report.restore import context_table
from core.restore.view import Line, context_view
from core.review.status import claim_state
from eval import demo
from ui import records
from ui.app import App, Request

PORT = 8766
HOST = {"host": f"127.0.0.1:{PORT}"}
M948 = "msg:item1:Chats!948"


@pytest.fixture(scope="module")
def app(tmp_path_factory) -> App:
    root = tmp_path_factory.mktemp("demo")
    demo.reset(root)
    (case,) = cases.list_cases(demo.cases_dir(root))
    a = App(home=demo.cases_dir(root), port=PORT, model_check=None)
    a.open_case(case)
    a.case_db = case.db  # type: ignore[attr-defined]
    return a


@pytest.fixture()
def conn(app):  # noqa: ANN201
    c = connect(app.case_db)
    yield c
    c.close()


def _get(app: App, path: str, **query: str) -> str:
    return app.handle(Request("GET", path, query, dict(HOST))).body.decode()


def _folds(body: str, cls: str) -> list[str]:
    """The inside of every <details class=cls> on a page (none of them nests another)."""
    return re.findall(rf"<details class='{cls}'>(.*?)</details>", body, re.S)


def _line(sender: str, direction: str, **kw: object) -> Line:
    base = {
        "record_id": "msg:x:Chats!2",
        "source_id": "x",
        "locator": "Chats!2",
        "shown_as": None,
        "utc": "2026-03-10 15:16:44 UTC",
        "local": "2026-03-10 11:16:44 EDT (UTC-04:00)",
        "raw": "3/10/2026 3:16:44 PM(UTC+0)",
        "body": "ok",
        "tier": ProvenanceTier.OBSERVED,
    }
    return Line(sender=sender, direction=direction, **{**base, **kw})  # type: ignore[arg-type]


# ---------------------------------------------------------------- one time format


@pytest.mark.parametrize(
    ("local", "date", "clock", "caveat"),
    [
        ("2026-03-10 11:16:44 EDT (UTC-04:00)", "Mar 10, 2026", "11:16:44 AM EDT", ""),
        ("2026-02-20 19:02:11 EST (UTC-05:00)", "Feb 20, 2026", "7:02:11 PM EST", ""),
        ("2026-03-13 00:03:27 EDT (UTC-04:00)", "Mar 13, 2026", "12:03:27 AM EDT", ""),
        ("2026-12-01 12:00:00 +03 (UTC+03:00)", "Dec 1, 2026", "12:00:00 PM +03", ""),
        (
            "2026-03-10 15:16:44 UTC (device zone unknown)",
            "Mar 10, 2026",
            "3:16:44 PM UTC",
            "device zone unknown",
        ),
    ],
)
def test_a_local_time_reads_in_words(local, date, clock, caveat) -> None:
    r = records.reading(local)
    assert r is not None and (r.date, r.clock, r.caveat) == (date, clock, caveat)


def test_the_full_time_with_its_offset_stays_in_the_hover_title() -> None:
    full = "2026-03-10 11:16:44 EDT (UTC-04:00)"
    assert records.when(full) == (
        f"<span class='lt' title='{full}'>Mar 10, 2026, 11:16:44 AM EDT</span>"
    )
    assert records.when(full, date=False).endswith(">11:16:44 AM EDT</span>")


def test_a_time_shown_in_utc_says_the_zone_is_unknown_in_view() -> None:
    assert records.when("2026-03-10 15:16:44 UTC (device zone unknown)").endswith(
        "3:16:44 PM UTC</span> (device zone unknown)"
    )


@pytest.mark.parametrize(
    "text", ["time unknown", "time unknown (source shows '3/10')", "", "2026-13-01 10:00:00 X (y)"]
)
def test_a_time_that_cannot_be_read_prints_as_stored(text) -> None:
    assert records.reading(text) is None
    assert records.when(text) == text.replace("'", "&#x27;")


ZONED = "2026-03-10 11:16:44 EDT (UTC-04:00)"
UTC_ONLY = "2026-03-10 15:16:44 UTC (device zone unknown)"


def test_the_note_on_times_says_utc_where_the_phones_zone_is_unknown() -> None:
    assert records.time_note([ZONED, ZONED]) == (
        "Times are the phone's local time, derived from UTC and the phone's time zone."
    )
    assert records.time_note([UTC_ONLY, ""]) == "Times are UTC: the phone's time zone is unknown."
    assert "except those marked device zone unknown, which are UTC" in records.time_note(
        [ZONED, UTC_ONLY]
    )
    assert records.time_note(["", "time unknown"]) == ""


def test_a_table_of_utc_times_is_not_headed_local_time(conn) -> None:
    rows = records.record_rows(conn, [M948, "msg:item1:Chats!949"])
    utc = [replace(r, local=UTC_ONLY) for r in rows]
    out = records.table(utc, records.Sources(conn))
    assert "<th>Time (UTC)</th>" in out and "Phone's local time" not in out
    assert "(device zone unknown)" in out
    assert "<th>Phone's local time</th>" in records.table(rows, records.Sources(conn))


def test_a_day_is_on_the_phones_calendar_or_says_it_is_utc(conn) -> None:
    # the demo phone is on New York time: 02:30 UTC on Mar 11 is still Mar 10 there
    late = "2026-03-11T02:30:00Z"
    assert records.local_day(conn, late, "dev:item1") == "Mar 10, 2026"
    assert records.local_day(conn, late, None) == "Mar 11, 2026 (UTC)"
    assert records.local_day(conn, None, "dev:item1") == ""


# ---------------------------------------------------------------- sender and direction


def test_a_direction_that_does_not_follow_from_the_sender_is_said_in_words() -> None:
    assert "outgoing" not in records.who(_line("Telegram 7001001 (this phone)", "outgoing"))
    assert "incoming" not in records.who(_line("Telegram 5551234", "incoming"))
    assert records.who(_line("Telegram 7001001 (this phone)", "incoming")).endswith(" · incoming")
    assert records.who(_line("Telegram 5551234", "unknown")).endswith(" · unknown")


def test_a_message_with_no_sender_account_always_says_its_direction() -> None:
    # CodeRabbit on #277: "unknown" is no account, so it cannot stand in for the direction
    assert records.who(_line("unknown", "incoming")).endswith(" · incoming")
    assert records.who(_line("unknown", "outgoing")).endswith(" · outgoing")
    assert records.who(_line("unknown sender", "incoming")).endswith(" · incoming")


def test_a_cited_table_names_the_app_its_senders_leave_off(app, conn) -> None:
    # CodeRabbit on #277: senders drop "Telegram" when every cited message is from it, so the
    # line above the table has to say it
    body = _get(app, "/claim", id="C04")
    block = body.split("Records the failed check cites", 1)[1]
    note, table = block.split("<table class='recs'>", 1)
    table = table.split("</table>", 1)[0]
    assert "Telegram" not in table
    assert 'Observed <span class="q">Telegram</span> messages in' in note
    # and when the cited messages are from more than one app, each sender keeps its own
    mixed = records.record_rows(conn, [M948, "msg:item1:Chats!857"])
    assert records.shared(mixed, records.Sources(conn)).app is None
    assert all(
        r.who.startswith(('<span class="q">Telegram ', '<span class="q">SMS ')) for r in mixed
    )


def test_a_sender_keeps_the_account_and_gains_the_name_the_source_gives() -> None:
    own = _line("Telegram 7001001 (this phone)", "outgoing")
    assert records.who(own, "Telegram", "Dan P") == (
        '<span class="q">7001001</span> (<span class="q">Dan P</span>, this phone)'
    )
    # a name printed on the message's own row leads, as on the rest of the screen
    printed = _line("Telegram 5551234", "incoming", shown_as="Sasha")
    assert records.who(printed, "Telegram", "@alex92") == (
        '<span class="q">Sasha</span> (<span class="q">5551234</span>)'
    )


def test_rows_that_differ_in_tier_or_file_say_so_in_each_row(conn) -> None:
    sources = records.Sources(conn)
    rows = records.record_rows(conn, [M948, "msg:item1:Chats!949"])
    same = records.table(rows, sources)
    assert "<th>Tier</th>" not in same and "<th>Excel row</th>" in same
    assert "<td class='src'>948</td>" in same
    mixed = [rows[0], replace(rows[1], tier=ProvenanceTier.DERIVED)]
    out = records.table(mixed, sources)
    assert "<th>Tier</th>" in out and "<td class='tier'>derived</td>" in out
    two_files = records.record_rows(conn, [M948, "msg:item2:Chats!918"])
    out = records.table(two_files, sources)
    assert "<th>Row in the file</th>" in out
    assert 'item2.xlsx</span>, <span class="q">Chats</span> sheet, Excel row 918' in out


def test_a_record_that_is_gone_keeps_its_row(conn) -> None:
    gone = "msg:item1:Chats!999999"
    (row,) = records.record_rows(conn, [gone])
    assert row.what == "record not found"
    assert "record not found" in records.table([row], records.Sources(conn))
    # nothing was observed, so it carries no tier and does not count toward the shared one
    assert row.tier is None
    rows = records.record_rows(conn, [M948, gone])
    assert records.shared(rows, records.Sources(conn)).tier is ProvenanceTier.OBSERVED
    # a caller that holds its own reference to the record still places it
    line = records.line(conn, gone, records.Sources(conn), place=("item1", "Chats!999999"))
    assert line.startswith("record not found · ") and "Excel row 999999" in line


# ---------------------------------------------------------------- the claim page


def test_the_cited_records_are_a_table_and_their_exported_values_fold_under_it(app, conn) -> None:
    body = _get(app, "/claim", id="C04")
    st = claim_state(conn, "C04")
    cited = [rid for ch in st.checks for rid in ch.record_ids]
    assert cited and "Records the failed check cites" in body
    block = body.split("Records the failed check cites", 1)[1]
    table = block.split("</table>", 1)[0]
    assert "<table class='recs'>" in table and "UTC 20" not in table
    assert "messages in" in block.split("<table", 1)[0]
    assert "derived from UTC and the phone's time zone" in block.split("<table", 1)[0]
    assert table.count("<tr") == len(cited) + 1
    assert "/selection/context?id=msg%3Aitem1%3AChats%21938" in table
    (fold,) = _folds(block.split("Rules' working", 1)[0], "exported")
    assert "not the report's # column" in html.unescape(fold)
    for rid in cited:
        assert record_line(conn, rid) in fold, rid  # the line the report prints, whole
        assert f"<span class='mono'>{rid}</span>" in fold


def test_an_evidence_card_says_the_record_once_and_keeps_the_report_line_in_its_fold(
    app, conn
) -> None:
    body = _get(app, "/claim", id="C03")
    items = [x for x in claim_state(conn, "C03").evidence if x.stance.value != "irrelevant"]
    assert items
    for item in items:
        card = body.split(f"<div class='item' id='{item.id}'>", 1)[1].split("<div class='item'", 1)[
            0
        ]
        visible, fold = card.split("<details class='more'>", 1)
        assert "<p class='ev-rec'>" in visible and "Excel row" in visible
        assert "UTC 20" not in visible and "as printed" not in visible
        assert "<summary>Exported values and model note</summary>" in fold
        assert record_line(conn, item.record_id) in fold
        assert "spreadsheet row" in fold and "not the report's # column" in fold
        assert item.record_id in fold
    evidence = body.split("<h2 id='evidence'>Evidence</h2>", 1)[1].split("<div class='item'", 1)[0]
    assert records.TIMES_NOTE in evidence.replace("&#x27;", "'")
    # every tier badge is still on its card
    assert body.count("<div class='ev-tags'>") >= len(items)


def test_an_irrelevant_row_is_short_and_opens_the_item_with_its_exported_values(app, conn) -> None:
    body = _get(app, "/claim", id="C16")
    rows = body.split("<details id='irrelevant'", 1)[1].split("</details>", 1)[0]
    assert "labeled irrelevant</summary>" in rows and "Open, or flag this label" in rows
    assert "as printed" not in rows and "Excel row" in rows
    assert records.TIMES_NOTE in rows.replace("&#x27;", "'")
    item = next(x for x in claim_state(conn, "C16").evidence if x.stance.value == "irrelevant")
    page = _get(app, "/evidence", id=item.id)
    assert record_line(conn, item.record_id) in page


def test_bubble_times_use_the_same_reading_format(app) -> None:
    body = _get(app, "/claim", id="C16")
    times = re.findall(
        r"<div class='t'>(?:<span class='cited'>This record</span>)?(.*?)</div>", body
    )
    assert times
    for t in times:
        assert re.fullmatch(
            r"<span class='lt' title='\d{4}-\d\d-\d\d \d\d:\d\d:\d\d \S+ \(UTC[+-]\d\d:\d\d\)'>"
            r"[A-Z][a-z]{2} \d{1,2}, \d{4}, \d{1,2}:\d\d:\d\d [AP]M \S+</span>",
            t,
        ), t


# ---------------------------------------------------------------- the conversation table


def test_the_conversation_is_five_columns_and_the_reports_table_folds_under_it(app, conn) -> None:
    body = _get(app, "/selection/context", id=M948)
    view = context_view(conn, M948)
    table = body.split("<table class='recs'>", 1)[1].split("</table>", 1)[0]
    head = re.findall(r"<th>(.*?)</th>", table)
    assert head == ["Date", "Phone's local time", "From", "Message", "Excel row"]
    assert table.count("<tr") == len(view.lines) + 1
    assert "<tr class='target'>" in table and "need 2 more by friday" in table
    note = body.split("<table class='recs'>", 1)[0]
    assert "Tier: observed, for every message" in note
    head = note.split("<p class='conv-head'>", 1)[1].split("</p>", 1)[0]
    assert "(UTC)" not in head  # the span is on the phone's calendar, as the date cells are
    assert "derived from UTC and the phone's time zone" in note
    fold = _folds(body, "exported")[0]
    assert context_table(view.lines) in fold  # the report's own table, every column
    assert "not the report's # column" in html.unescape(fold)
    for ln in view.lines:
        assert ln.utc in fold and ln.direction in fold


def test_related_threads_get_the_same_table_and_fold(app, conn) -> None:
    rid = "msg:item1:Chats!1011"
    view = context_view(conn, rid)
    assert view.related
    body = _get(app, "/selection/context", id=rid)
    related = body.split("<details class='related'>", 1)[1]
    with_lines = [r for r in view.related if r.lines]
    assert related.count("<table class='recs'>") == len(with_lines)
    for r in with_lines:
        assert context_table(r.lines) in related
