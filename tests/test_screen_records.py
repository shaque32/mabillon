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


def test_the_note_names_the_phones_zone_in_full(conn) -> None:
    # a time in view ends in the zone's short name; the full name settles which zone it is
    sources = records.Sources(conn)
    assert records.zone_names(sources) == "America/New_York"
    assert records.time_note([ZONED], "America/New_York") == (
        "Times are the phone's local time (America/New_York), derived from UTC and the phone's "
        "time zone."
    )
    assert "(America/New_York)" in records.note(records.record_rows(conn, [M948]), sources)


def test_the_note_names_only_the_zones_of_the_phones_the_rows_are_from(conn) -> None:
    conn.execute("UPDATE devices SET timezone = 'America/Chicago' WHERE id = 'dev:item2'")
    try:
        sources = records.Sources(conn)
        both = records.zone_names(sources)
        assert "America/New_York" in both and "America/Chicago" in both
        assert records.zone_names(sources, {"dev:item1"}) == "America/New_York"
        assert records.zone_names(sources, ()) == ""
        note = records.note(records.record_rows(conn, [M948], sources=sources), sources)
        assert "(America/New_York)" in note and "Chicago" not in note
    finally:
        conn.rollback()


def test_the_note_is_left_out_when_no_row_has_a_time_or_an_excel_row(conn) -> None:
    sources = records.Sources(conn)
    (row,) = records.record_rows(conn, [M948], sources=sources)
    assert records.note([replace(row, local="", source_id="")], sources) == ""
    # a row in an Excel report says, in view, what its row number is
    assert records.note([replace(row, local="")], sources) == records.EXCEL_ROW_NOTE
    assert records.note([row], sources).endswith(records.EXCEL_ROW_NOTE)


def test_a_row_with_no_time_does_not_read_as_the_day_above(conn) -> None:
    rows = records.record_rows(conn, [M948, "msg:item1:Chats!949"])
    untimed = [
        rows[0],
        replace(rows[1], local="time unknown (source shows '3/12')"),
        replace(rows[1], local=""),
    ]
    out = records.table(untimed, records.Sources(conn))
    # a time that was not read is not "no date": only a record with no time at all is
    assert "<td class='d'>date not read</td><td class='t'>time unknown" in out
    assert "<td class='d'>no date</td><td class='t'></td>" in out


def test_an_attachment_takes_its_messages_time(conn) -> None:
    att, msg = conn.execute("SELECT id, message_id FROM attachments LIMIT 1").fetchone()
    (a, m) = records.record_rows(conn, [att, msg])
    assert a.local == m.local and records.reading(a.local) is not None
    assert a.device == m.device == "dev:item1"
    assert "no date" not in records.table([a], records.Sources(conn))


def test_a_message_whose_stored_time_is_not_a_time_keeps_its_row(conn) -> None:
    conn.execute("UPDATE messages SET ts_utc = 'not a time' WHERE id = ?", (M948,))
    try:
        sources = records.Sources(conn)
        bad, good = records.record_rows(conn, [M948, "msg:item1:Chats!949"], sources=sources)
        assert bad.local.startswith("time unknown") and bad.thread and bad.title
        assert records.reading(good.local) is not None and good.who
        assert "date not read" in records.table([bad, good], sources)
        assert "thread" in records.line(conn, M948, sources)
    finally:
        conn.rollback()


def test_a_call_whose_stored_time_cannot_be_read_says_so(conn) -> None:
    call = conn.execute("SELECT id FROM calls LIMIT 1").fetchone()[0]
    conn.execute("UPDATE calls SET ts_utc = 'not a time' WHERE id = ?", (call,))
    try:
        (row,) = records.record_rows(conn, [call])
        assert row.local.startswith("time unknown")
    finally:
        conn.rollback()


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
    sources = records.Sources(conn)
    assert records.local_day(sources, late, "dev:item1") == "Mar 10, 2026"
    assert records.local_day(sources, late, None) == "Mar 11, 2026 (UTC)"
    assert records.local_day(sources, None, "dev:item1") == ""


# ---------------------------------------------------------------- sender and direction


def test_a_direction_that_does_not_follow_from_the_sender_is_said_in_words() -> None:
    assert "outgoing" not in records.who(_line("Telegram 7001001 (this phone)", "outgoing"))
    assert "incoming" not in records.who(_line("Telegram 5551234", "incoming"))
    assert records.who(_line("Telegram 7001001 (this phone)", "incoming")).endswith(" · incoming")
    assert records.who(_line("Telegram 5551234", "unknown")).endswith(" · unknown")


def test_a_direction_said_in_a_one_line_record_is_bracketed(conn) -> None:
    # " · " parts the line, so "· incoming in Telegram thread" would read as one part
    (row,) = records.record_rows(conn, [M948])
    assert row.way == ""
    line = records.line(conn, M948, records.Sources(conn))
    assert " · incoming" not in line and " · outgoing" not in line
    conn.execute("UPDATE messages SET direction = 'incoming' WHERE id = ?", (M948,))
    try:
        (row,) = records.record_rows(conn, [M948])
        assert row.way == "incoming" and row.who.endswith(" · incoming")
        line = records.line(conn, M948, records.Sources(conn))
        assert "this phone) (incoming) in " in line
    finally:
        conn.rollback()


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
    assert 'Observed <span class="q">Telegram</span> messages in thread ' in note
    assert "@northstar" in note  # one thread: said once, so no row repeats it
    assert "in thread" not in table
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
    # and it does not hide the app the found messages share (CodeRabbit on #277)
    assert records.shared(rows, records.Sources(conn)).app == "Telegram"
    # a caller that holds its own reference to the record still places it
    line = records.line(conn, gone, records.Sources(conn), place=("item1", "Chats!999999"))
    assert line.startswith("record not found · ") and "Excel row 999999" in line


# ---------------------------------------------------------------- the claim page


def test_cited_messages_from_several_threads_each_say_their_thread(app, conn) -> None:
    # an outgoing row's counterparty is its thread: C14 cites two phones' SMS and Telegram
    block = _get(app, "/claim", id="C14").split("Records the failed check cites", 1)[1]
    note, table = block.split("<table class='recs'>", 1)
    table = table.split("</table>", 1)[0]
    cited = [rid for ch in claim_state(conn, "C14").checks for rid in ch.record_ids]
    messages = [rid for rid in cited if rid.startswith("msg:")]
    assert len(messages) > 1 and "in thread" not in note
    assert table.count("<span class='muted'>in thread ") == len(messages)


def test_one_cited_record_is_said_in_the_singular(app) -> None:
    block = _get(app, "/claim", id="C11").split("Records the failed check cites (1)", 1)[1]
    assert 'Observed <span class="q">Telegram</span> message in thread' in block
    assert "<summary>Exported values for this record (UTC" in block
    assert "these 1 record" not in block


def test_an_undecided_card_keeps_the_senders_name_from_the_source(app, conn) -> None:
    # the messages drawn above the line give the account, not its display name
    body = _get(app, "/claim", id="C05")
    item = next(x for x in claim_state(conn, "C05").evidence if x.record_id == M948)
    card = body.split(f"<div class='item' id='{item.id}'>", 1)[1]
    rec = card.split("<p class='ev-rec'>", 1)[1].split("</p>", 1)[0]
    assert rec.startswith(
        '<span class="q">7001001</span> (<span class="q">Dan P</span>, this phone)'
    )
    assert "class='lt'" not in rec  # the bubble above gives the time


def test_the_cited_records_are_a_table_and_their_exported_values_fold_under_it(app, conn) -> None:
    body = _get(app, "/claim", id="C04")
    st = claim_state(conn, "C04")
    cited = [rid for ch in st.checks for rid in ch.record_ids]
    assert cited and "Records the failed check cites" in body
    block = body.split("Records the failed check cites", 1)[1]
    table = block.split("</table>", 1)[0]
    assert "<table class='recs'>" in table and "UTC 20" not in table
    assert "messages in" in block.split("<table", 1)[0]
    above = html.unescape(block.split("<table", 1)[0])
    assert "derived from UTC and the phone's time zone" in above
    assert records.EXCEL_ROW_NOTE in above  # in view, not only in the fold
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
    sources = records.Sources(conn)
    how = records.note(records.record_rows(conn, [x.record_id for x in items]), sources)
    assert "(America/New_York)" in how and how.endswith(records.EXCEL_ROW_NOTE)
    assert how in html.unescape(evidence)
    # every tier badge is still on its card
    assert body.count("<div class='ev-tags'>") >= len(items)


def test_an_irrelevant_row_is_short_and_opens_the_item_with_its_exported_values(app, conn) -> None:
    body = _get(app, "/claim", id="C16")
    rows = body.split("<details id='irrelevant'", 1)[1].split("</details>", 1)[0]
    assert "labeled irrelevant</summary>" in rows and "Open, or flag this label" in rows
    assert "as printed" not in rows and "Excel row" in rows
    hidden = [x for x in claim_state(conn, "C16").evidence if x.stance.value == "irrelevant"]
    sources = records.Sources(conn)
    how = records.note(records.record_rows(conn, [x.record_id for x in hidden]), sources)
    assert how.endswith(records.EXCEL_ROW_NOTE) and how in html.unescape(rows)
    item = hidden[0]
    page = _get(app, "/evidence", id=item.id)
    assert record_line(conn, item.record_id) in page
    # the item's own page says how to read its time and the times of the messages around it
    card = html.unescape(page.split("<h2>Context</h2>", 1)[0])
    assert records.note(records.record_rows(conn, [item.record_id]), sources) in card


def test_a_page_with_no_time_in_view_prints_no_note_on_times(app, conn) -> None:
    item = next(x for x in claim_state(conn, "C16").evidence if x.stance.value == "irrelevant")
    # the screen reads the case through its own connection, so the change is committed and
    # then put back
    kept = conn.execute("SELECT ts_utc, ts_raw, id FROM messages").fetchall()
    conn.execute("UPDATE messages SET ts_utc = NULL, ts_raw = NULL")
    conn.commit()
    try:
        page = html.unescape(_get(app, "/evidence", id=item.id))
        assert "Times are" not in page and records.EXCEL_ROW_NOTE in page
        rows = _get(app, "/claim", id="C16").split("<details id='irrelevant'", 1)[1]
        assert "Times are" not in rows.split("</details>", 1)[0]
    finally:
        conn.executemany("UPDATE messages SET ts_utc = ?, ts_raw = ? WHERE id = ?", kept)
        conn.commit()


def test_a_long_cited_list_is_described_over_every_record_it_counts(app, conn, monkeypatch) -> None:
    from ui import pages

    # C14's failed check cites twelve records from three threads on two phones; its first
    # three are from one thread in one file. Drawing only three must not say "in thread ..."
    # or name one file for all twelve.
    monkeypatch.setattr(pages, "FAILED_CITED_SHOWN", 3)
    block = _get(app, "/claim", id="C14").split("Records the failed check cites (12)", 1)[1]
    above, table = block.split("<table class='recs'>", 1)
    table = table.split("</table>", 1)[0]
    assert table.count("<tr") == 4 and "and 9 more" in block
    assert "in thread" not in above and "item1.xlsx" not in above
    assert table.count('in thread <span class="q">Marc Garage</span>') == 3
    assert table.count("item1.xlsx") == 3  # each row names its own file


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
    assert "derived from UTC and the phone's time zone" in html.unescape(note)
    assert records.EXCEL_ROW_NOTE in html.unescape(note)  # in view, and still in the fold
    fold = _folds(body, "exported")[0]
    assert context_table(view.lines) in fold  # the report's own table, every column
    t = view.thread  # and the thread's first and last message in UTC, as the report's header
    assert f"{t.first_utc} to {t.last_utc} UTC" in fold
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
