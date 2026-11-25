"""Context Restore pages of the review screen: paste an exhibit, see each quoted message found in
the extraction and opened in its own conversation, and the draft request for the full extraction.

Pure functions of the case database, like ui/pages.py, and rendered with the same HTML fragments
as the report (core/report/restore.py), so the screen and the report never disagree. Adding and
removing an exhibit go through core/restore/store.py, which writes the audit log.

Each page's body sits in its own wrapper (pg-exhibits, pg-exhibit, pg-match, pg-letter) so its
look lives in ui/css/exhibits.py, scoped to that page, without restyling the report's fragments
anywhere else.
"""

from __future__ import annotations

import html
import sqlite3

from core.report.letter import needs_request, request_letter
from core.report.restore import context_table, exhibit_section, match_notes
from core.restore.store import (
    MAX_EXHIBIT_CHARS,
    load_excerpt,
    load_excerpts,
    load_exhibit,
    load_exhibits,
    load_match,
    stale_reason,
)
from core.restore.view import ContextView, Line, match_view
from ui import records as screen_records
from ui.pages import Page, e, link, q


def _table(conn: sqlite3.Connection, lines: tuple[Line, ...], app: str) -> tuple[str, str]:
    """Messages as the screen's table (date, the phone's local time, sender, message, row in
    the file), with the report's own table (core/report/restore.py context_table: UTC, the
    time as printed, direction, tier and source id for every row) folded under it. Returns
    (what to say once above the rows: their tier and how to read the time, the table)."""
    sources = screen_records.Sources(conn)
    rows = screen_records.message_rows(conn, lines, app)
    same = screen_records.shared(rows, sources)
    n = len(lines)
    note = (
        (f"Tier: {e(same.tier.value)}, for every message" if same.tier else "Tier in each row")
        + (f"; all in {same.words}" if same.sheet else "")
        + f". Times are the phone's local time, {screen_records.LOCAL_TIME_NOTE}."
    )
    excel = (
        f"<p class='muted'>{e(screen_records.EXCEL_ROW_NOTE)}</p>"
        if sources.excel(ln.source_id for ln in lines)
        else ""
    )
    return (
        f"<p class='muted conv-note'>{note}</p>",
        screen_records.table(rows, sources)
        + f"<details class='exported'><summary>Exported values for {'this' if n == 1 else 'these'}"
        f" {n:,} message{'' if n == 1 else 's'} (UTC, as printed, direction, tier, source)"
        f"</summary>{excel}{context_table(lines)}</details>",
    )


def _span(first_utc: str | None, last_utc: str | None) -> str:
    """A thread's first and last day, in words, by the UTC date."""
    first, last = screen_records.day(first_utc), screen_records.day(last_utc)
    if not first or not last:
        return ""
    return f", {first} (UTC)" if first == last else f", {first} to {last} (UTC)"


def conversation(conn: sqlite3.Connection, view: ContextView) -> str:
    """A message in its conversation, for the screen: what core/report/restore.py view_block
    prints in the report, with each row in reading words and the exported values of every row
    one fold away. The related threads fold under one disclosure so the conversation itself
    leads. Every row stays on the page."""
    t = view.thread
    note, table = _table(conn, view.lines, t.app)
    out = [
        f"<p class='conv-head'>{q(t.app)} thread {q(t.title or '(untitled)')} on {q(t.device)} "
        f"in {q(t.file_name)}. {t.messages:,} message{'' if t.messages == 1 else 's'}"
        + _span(t.first_utc, t.last_utc)
        + f". Showing {len(view.lines)}"
        + (
            f"; {view.before:,} earlier and {view.after:,} later not shown"
            if view.before or view.after
            else ""
        )
        + f".</p>{note}{table}"
    ]
    if not view.related:
        out.append("<p class='muted'>No other thread shares these participants' identifiers.</p>")
        return "".join(out)
    out.append(
        f"<details class='related'><summary>Related threads between the same participants "
        f"({len(view.related):,})</summary><p class='muted'>Matched by identifier as the "
        "sources show it (phone numbers by their digits), plus identity links an expert "
        "confirmed. Messages from the same period as the conversation above.</p>"
    )
    for r in view.related:
        rt = r.thread
        out.append(
            f"<p><strong>{q(rt.app)} thread {q(rt.title or '(untitled)')}</strong> on "
            f"{q(rt.device)} in {q(rt.file_name)} ({rt.messages:,} messages). Shares "
            + ", ".join(q(s.split(":", 1)[1]) for s in r.shared)
            + ".</p>"
        )
        if r.nearest:
            out.append(
                "<p class='muted'>No message in this thread falls in the same period. "
                + ("The nearest before and after:" if r.lines else "")
                + "</p>"
            )
        if r.lines:
            out.append("".join(_table(conn, r.lines, rt.app)))
        if r.more:
            out.append(f"<p class='muted'>{r.more:,} more messages in the period.</p>")
    out.append("</details>")
    return "".join(out)


def _found_counts(conn: sqlite3.Connection, ex_id: str) -> tuple[int, int]:
    excerpts = load_excerpts(conn, ex_id)
    found = sum(
        1
        for x in excerpts
        if conn.execute(
            "SELECT 1 FROM exhibit_matches WHERE excerpt_id = ? LIMIT 1", (x.id,)
        ).fetchone()
    )
    return found, len(excerpts)


def _option_text(text: str, label: str, limit: int = 80) -> str:
    """A paragraph's opening words for a select option: without its own leading number, which
    the option already shows, and cut at a word with an ellipsis."""
    text = " ".join(text.split())
    for lead in (f"{label}.", f"{label})", f"¶{label}"):
        if text.startswith(lead):
            text = text[len(lead) :].lstrip()
            break
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:") + "…"


def exhibits_page(conn: sqlite3.Connection, page: Page) -> str:
    exhibits = load_exhibits(conn)
    out = [
        "<div class='pg-exhibits'><h1>Exhibits</h1>"
        "<p class='lede'>Paste the messages a government exhibit quotes. Mabillon finds each "
        "one in the phone records and shows it in its conversation.</p>"
    ]
    if needs_request(conn):
        out.append(
            "<p class='warn'>Only curated reports (or sources of unknown coverage) are imported, "
            "so an exhibit's message may be missing from them. "
            "<a href='/request-letter'>Draft request for the full extraction</a></p>"
        )
    if exhibits:
        out.append(
            "<table class='exhibits'><thead><tr><th>Exhibit</th><th>Quoted messages found</th>"
            "<th>Added</th><th>Status</th></tr></thead>"
        )
        stale_any = False
        for ex in exhibits:
            found, total = _found_counts(conn, ex.id)
            stale = stale_reason(conn, ex.id)
            stale_any = stale_any or stale is not None
            out.append(
                f"<tr><td><a href='{e(link('/exhibit', id=ex.id))}'>{q(ex.label)}</a></td>"
                f"<td class='n'>{found} of {total}</td><td class='meta'>{e(ex.added_by)}, "
                f"{e(ex.added_at_utc.strftime('%Y-%m-%d %H:%M UTC'))}</td>"
                f"<td class='meta'>{e(stale or 'Current')}</td></tr>"
            )
        out.append("</table>")
        if stale_any:
            out.append(
                page.form(
                    "/exhibit/rematch",
                    "Some exhibits were searched before the latest import or matcher change. "
                    "<button type='submit'>Search all exhibits again</button>",
                    back="/exhibits",
                )
            )
    else:
        out.append("<p class='muted'>No exhibits yet.</p>")

    paragraphs = list(
        conn.execute(
            "SELECT p.id, p.page, coalesce(p.label, p.para_no), p.text"
            " FROM govdoc_paragraphs p ORDER BY p.govdoc_id, p.para_no"
        )
    )
    options = "<option value=''>(none)</option>" + "".join(
        f"<option value='{e(pid)}'>Page {pg}, paragraph {e(lbl)}: "
        f"{e(_option_text(txt, str(lbl)))}</option>"
        for pid, pg, lbl, txt in paragraphs
    )
    out.append(
        "<h2 id='add'>Add an exhibit</h2>"
        + page.form(
            "/exhibit/add",
            "<div class='fields'><p><label>Exhibit name <input type='text' name='label' "
            "required maxlength='120' class='wide' placeholder='Government Exhibit 4'></label>"
            f"</p><p><label>Cited in (optional) <select name='paragraph'>{options}</select>"
            "</label></p></div><p><label>Quoted messages, as the exhibit prints them"
            f"<textarea name='text' rows='8' required maxlength='{MAX_EXHIBIT_CHARS}'>"
            "</textarea></label></p><fieldset class='msgsplit'><legend>One message per</legend>"
            "<label><input type='radio' name='split' value='line' checked> line</label>"
            "<label><input type='radio' name='split' value='block'> paragraph</label></fieldset>"
            "<button type='submit' class='primary'>Add and search</button>",
            back="/exhibits",
        )
        + "</div>"
    )
    return page.wrap("Exhibits", "".join(out))


def exhibit_page(conn: sqlite3.Connection, page: Page, ex_id: str) -> str | None:
    ex = load_exhibit(conn, ex_id)
    if ex is None:
        return None
    back = link("/exhibit", id=ex.id)
    body = [
        "<div class='pg-exhibit'><p class='back'><a href='/exhibits'>All exhibits</a></p>",
        f"<h1>{q(ex.label)}</h1>",
        exhibit_section(conn, ex, match_link=lambda m: link("/exhibit/match", id=m.id)),
        "<details class='pasted'><summary>Exhibit text as pasted</summary>"
        f"<pre class='exhibit-text'>{q(ex.text)}</pre></details>",
        "<div class='actions'>",
        page.form(
            "/exhibit/rematch",
            f"<input type='hidden' name='id' value='{e(ex.id)}'>"
            "<button type='submit'>Search again</button> <span>against the messages imported "
            "now.</span>",
            cls="act",
            back=back,
        ),
        page.form(
            "/exhibit/remove",
            f"<input type='hidden' name='id' value='{e(ex.id)}'>"
            "<button type='submit'>Remove this exhibit</button> <span>The removal is recorded "
            "in the audit log with your name.</span>",
            cls="act remove",
            back="/exhibits",
        ),
        "</div></div>",
    ]
    return page.wrap(ex.label, "".join(body))


def match_page(conn: sqlite3.Connection, page: Page, match_id: str) -> str | None:
    m = load_match(conn, match_id)
    if m is None:
        return None
    excerpt = load_excerpt(conn, m.excerpt_id)
    if excerpt is None:
        return None
    ex = load_exhibit(conn, excerpt.exhibit_id)
    body_row = conn.execute("SELECT body FROM messages WHERE id = ?", (m.record_id,)).fetchone()
    if ex is None or body_row is None:
        return None
    out = [
        f"<div class='pg-match'><p class='back'><a href='{e(link('/exhibit', id=ex.id))}'>"
        f"Back to {e(ex.label)}</a></p>",
        f"<h1>Quoted message {excerpt.seq} in context</h1>",
        f"<p class='prints'>The exhibit prints:</p><blockquote>{q(excerpt.text)}</blockquote>",
        "<ul class='notes'>"
        + "".join(f"<li>{n}</li>" for n in match_notes(excerpt, m, body_row[0]))
        + "</ul>",
        f"<p class='muted tiers'>Match tier derived: found and verified by code (matcher "
        f"{e(m.matcher_version)}). Messages are observed; the phone's local time is derived "
        "from UTC and the phone's time zone.</p>",
        conversation(conn, match_view(conn, m)),
        "</div>",
    ]
    return page.wrap(f"{ex.label}, message {excerpt.seq}", "".join(out), wide=True)


def letter_page(conn: sqlite3.Connection, page: Page) -> str:
    text = request_letter(conn)
    if text is None:
        body = (
            "<div class='pg-letter'><h1>Request for the full extraction</h1><p>Every evidence "
            "source in this case is recorded as a full extraction, so no request is drafted.</p>"
            "</div>"
        )
    else:
        body = (
            "<div class='pg-letter'><div class='letter-head'><div><h1>Request for the full "
            "extraction (draft)</h1><p>Built from the imported sources for counsel to review "
            "and complete. Not legal advice. Mabillon does not send it anywhere.</p></div>"
            "<a class='button' href='/request-letter.txt'>Download as text</a></div>"
            f"<pre class='letter'>{html.escape(text)}</pre></div>"
        )
    return page.wrap("Request letter", body)
