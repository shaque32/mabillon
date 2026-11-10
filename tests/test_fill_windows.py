"""Time ranges the filler reads from a claim's own words: approximate ranges ("between
approximately 2:06 and 2:22 p.m."), open ranges, whole months, and the model's words cut from a
longer range. All wording is made up, on synthetic case01 (phones in America/New_York).

Each new reading is the words' own range: never wider than them, where an event claim would
pass on a record the words leave out, and never narrower, where a count or an absence would
miss one they take in.
"""

import sqlite3
from datetime import UTC, time, timedelta
from datetime import datetime as D

import pytest

from core.audit.assumption_filler import (
    LocalAssumptionFiller,
    Reject,
    _ProposalOut,
    _Window,
    check_window,
    coverage_gap,
    cut_from_longer,
    months_stated,
    stated_windows,
    time_mentions,
)
from core.audit.assumptions import Proposal
from core.contracts import Claim, ClaimStatus, ClaimType
from core.review import actions
from eval.synthetic.generate import generate
from tests.checks.helpers import stipulate
from tests.fake_model import FakeModel

PETROV, REYES = "person:petrov", "person:reyes"
QUOTE = "need 2 more by friday"
US = timedelta(microseconds=1)
NY = "America/New_York"


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


def filler(conn) -> LocalAssumptionFiller:
    return LocalAssumptionFiller(
        FakeModel("{}"), conn, template="{claim} {paragraph} {templates} {channels}"
    )


def claim(text: str, kind: ClaimType = ClaimType.COMMUNICATION) -> Claim:
    return Claim(id="X", paragraph_id="para:none", text=text, claim_type=kind,
                 status=ClaimStatus.ACCEPTED)  # fmt: skip


def W(as_written: str, start: str, end: str, zone: str = "phone") -> dict:  # noqa: N802
    return {"as_written": as_written, "start": start, "end": end, "zone": zone}


def proposal(**kw) -> _ProposalOut:
    base = dict(template_id="record_time", people=["PETROV"], accounts=[], handles=[],
                phones=[], channels=[], quoted_text=QUOTE, count=None, duration=None,
                window=None)  # fmt: skip
    return _ProposalOut.model_validate({**base, **kw})


def resolved(conn, text: str, w: dict | None):
    return filler(conn)._resolve(claim(text), "", proposal(window=w)).params["window"]


def model_window(conn, text: str, w: dict, template: str, devices=("dev:item1",)):
    return filler(conn)._window(text, "", _Window.model_validate(w), list(devices), template)


def code_window(conn, text: str, template: str, devices=("dev:item1",)):
    return filler(conn)._stated(claim(text), "", list(devices), template, None)


def local(w):
    """The window's ends in New York, wall clock, the end as its exclusive minute."""
    from zoneinfo import ZoneInfo

    z = ZoneInfo(w.tz)
    return w.start_utc.astimezone(z).replace(tzinfo=None), (w.end_utc + US).astimezone(z).replace(
        tzinfo=None
    )


# ---------------------------------------------------------------- approximate ranges


@pytest.mark.parametrize(
    ("text", "start", "end"),
    [
        # "approximately" after "between" makes both ends approximate: 8 minutes wider each,
        # as "about 2:06 p.m." alone is 1:58 to 2:14 p.m.
        ("On April 27, 2023, between approximately 2:06 and 2:22 p.m. EDT, X called.",
         "13:58", "14:30"),
        ("Between approximately 1:55 p.m. and 2:01 p.m. EDT on May 8, 2023, X called.",
         "13:47", "14:09"),
        ("On April 26, 2023, between approximately 11:42 a.m. and 12:18 p.m., X called.",
         "11:34", "12:26"),
        ("On May 2, 2023, from about 11:33 to 11:48 a.m., X called.", "11:25", "11:56"),
        ("On May 2, 2023, between around 9 and 10 p.m., X called.", "20:52", "22:08"),
        ("approximately between 9 and 11 p.m. on May 2, 2023, X called.", "20:52", "23:08"),
        ("On May 2, 2023, approximately between 9 and 11 p.m., X called.", "20:52", "23:08"),
        # only the end is approximate
        ("On May 2, 2023, between 9 p.m. and about 11 p.m., X called.", "21:00", "23:08"),
        # neither: through the end minute, as before
        ("On May 2, 2023, between 9 and 11 p.m., X called.", "21:00", "23:01"),
    ],
)  # fmt: skip
def test_an_approximate_range_is_eight_minutes_wider_at_each_approximate_end(text, start, end):
    (w,) = stated_windows(text)
    assert (w.start.strftime("%H:%M"), w.end.strftime("%H:%M")) == (start, end)
    assert w.raw in text
    for tpl in ("record_time", "no_contact", "message_count"):
        check_window(w.start, w.end, w.raw, text, "", tpl)


def test_the_bare_first_hour_of_an_approximate_range_takes_the_ends_p_m():
    # Before, "2:06" after "between approximately" was read as 2:06 a.m. (a 24-hour time), so
    # a model's window twelve hours off passed the check.
    text = "On April 27, 2023, between approximately 2:06 and 2:22 p.m. EDT, X called."
    assert time_mentions(text) == [time(14, 6), time(14, 22)]
    with pytest.raises(Reject, match="not near the start of the stated time range"):
        check_window(D(2023, 4, 27, 2, 0), D(2023, 4, 27, 2, 10),
                     "On April 27, 2023, between approximately 2:06 and 2:22 p.m.", text, "",
                     "message_count")  # fmt: skip


@pytest.mark.parametrize(
    "text",
    [
        # only "about", "approximately" and "around" are read
        "On May 2, 2023, between roughly 9 and 11 p.m., X called.",
        "On May 2, 2023, between approximately 11:50 and 12:10 p.m., X called.",  # 11:50 p.m.?
        "On May 2, 2023, between approximately 11 p.m. and 1 a.m., X called.",  # crosses midnight
        "On May 2, 2023, between approximately 9 and 11, X called.",  # no a.m. or p.m.
        "On May 2 and 3, 2023, between approximately 9 and 10 p.m., X called.",  # two days
        # a weekday that is not the date's (May 2, 2023 was a Tuesday)
        "On Wednesday, May 2, 2023, between approximately 9 and 10 p.m., X called.",
    ],
)
def test_an_approximate_range_code_cannot_read_plainly_is_not_read(text):
    assert stated_windows(text) is None


def test_the_model_window_is_code_reading_of_an_approximate_range(conn):
    # The model's 2:06 to 2:22 p.m. is narrower than the words; its 2:00 to 2:30 p.m. is near
    # enough to pass the 15-minute check. Either way the range is code's 1:58 to 2:29:59 p.m.
    text = (
        f'On April 27, 2023, between approximately 2:06 and 2:22 p.m. EDT, PETROV wrote "{QUOTE}".'
    )
    words = "On April 27, 2023, between approximately 2:06 and 2:22 p.m. EDT"
    for s, e in (("14:06", "14:23"), ("14:00", "14:30"), ("14:14", "14:20")):
        w = resolved(conn, text, W(words, f"2023-04-27T{s}", f"2023-04-27T{e}"))
        assert w.start_utc == D(2023, 4, 27, 17, 58, tzinfo=UTC)  # 1:58 p.m. EDT
        assert w.end_utc == D(2023, 4, 27, 18, 30, tzinfo=UTC) - US  # last instant of 2:29
        assert w.tz == NY


@pytest.mark.parametrize("template", ["record_time", "no_contact", "message_count"])
def test_an_approximate_range_has_the_same_boundary_instants_for_every_template(conn, template):
    words = "On January 9, 2026, between approximately 9:10 and 9:40 p.m. EST"
    text = f"{words}, PETROV called REYES."
    w = model_window(conn, text, W(words, "2026-01-09T21:05", "2026-01-09T21:45"), template)
    # 9:02 p.m. EST is in; 9:01:59.999999 is not; 9:47:59.999999 is in; 9:48 is not.
    assert w.start_utc == D(2026, 1, 10, 2, 2, tzinfo=UTC)
    assert w.end_utc == D(2026, 1, 10, 2, 48, tzinfo=UTC) - US


def test_an_approximate_end_may_widen_past_midnight(conn):
    text = (
        f'On May 2, 2023, between approximately 11:40 and 11:55 p.m. EDT, PETROV wrote "{QUOTE}".'
    )
    w = code_window(conn, text, "record_time")
    assert local(w) == (D(2023, 5, 2, 23, 32), D(2023, 5, 3, 0, 3))
    text = (
        f'On May 2, 2023, between approximately 12:02 and 12:30 a.m. EDT, PETROV wrote "{QUOTE}".'
    )
    w = code_window(conn, text, "record_time")
    assert local(w) == (D(2023, 5, 1, 23, 54), D(2023, 5, 2, 0, 38))


# ---------------------------------------------------------------- clock changes and zones

SPRING = "On March 8, 2026"  # New York's clocks skip 2:00 to 3:00 a.m.
FALL = "On November 1, 2026"  # New York's clocks repeat 1:00 to 2:00 a.m.


def test_an_approximate_range_on_the_night_the_clocks_skip_an_hour(conn):
    w = code_window(conn, f'{SPRING}, between approximately 1:10 and 1:40 a.m., PETROV called.',
                    "record_time")  # fmt: skip
    assert (w.start_utc, w.end_utc + US) == (D(2026, 3, 8, 6, 2, tzinfo=UTC),
                                             D(2026, 3, 8, 6, 48, tzinfo=UTC))  # fmt: skip
    # Across the skipped hour: 1:42 a.m. EST to 3:18 a.m. EDT, 36 minutes of real time.
    w = code_window(conn, f'{SPRING}, between approximately 1:50 and 3:10 a.m., PETROV called.',
                    "record_time")  # fmt: skip
    assert (w.end_utc + US) - w.start_utc == timedelta(minutes=36)
    # A stated time the clocks skip is refused, even when the widened ends exist.
    for text in (
        f"{SPRING}, between approximately 2:05 and 2:55 a.m., PETROV called.",
        f"{SPRING}, between approximately 2:05 and 3:30 a.m., PETROV called.",
        f"{SPRING}, between approximately 3:05 and 3:30 a.m., PETROV called.",  # 2:57 a.m.
    ):
        with pytest.raises(Reject, match="clocks change"):
            code_window(conn, text, "no_contact")


def test_an_approximate_range_on_the_night_the_clocks_go_back(conn):
    # With no zone written, 1:02 a.m. is two instants: refused.
    with pytest.raises(Reject, match="two times"):
        code_window(conn, f"{FALL}, between approximately 1:10 and 1:40 a.m., PETROV called.",
                    "record_time")  # fmt: skip
    edt = code_window(conn, f"{FALL}, between approximately 1:10 and 1:40 a.m. EDT, PETROV called.",
                      "record_time")  # fmt: skip
    est = code_window(conn, f"{FALL}, between approximately 1:10 and 1:40 a.m. EST, PETROV called.",
                      "record_time")  # fmt: skip
    assert edt.start_utc == D(2026, 11, 1, 5, 2, tzinfo=UTC)
    assert est.start_utc == D(2026, 11, 1, 6, 2, tzinfo=UTC)
    assert (edt.end_utc + US) - edt.start_utc == timedelta(minutes=46)
    # An approximate end that widens into the other offset is refused: 1:58 a.m. EDT + 8
    # minutes is 2:06 a.m., which is EST that night.
    with pytest.raises(Reject, match="UTC-04:00"):
        code_window(conn, f"{FALL}, between approximately 1:10 and 1:58 a.m. EDT, PETROV called.",
                    "record_time")  # fmt: skip
    # Across the repeated hour, with each end one instant: 12:50 a.m. EDT to 2:13 a.m. EST.
    w = code_window(conn, f"{FALL}, between approximately 12:58 and 2:05 a.m., PETROV called.",
                    "no_contact")  # fmt: skip
    assert (w.start_utc, w.end_utc + US) == (D(2026, 11, 1, 4, 50, tzinfo=UTC),
                                             D(2026, 11, 1, 7, 13, tzinfo=UTC))  # fmt: skip


def test_a_written_zone_the_phone_is_not_in_then_is_refused(conn):
    with pytest.raises(Reject, match=r"EDT \(UTC-04:00\), but the phone's zone America/New_York"):
        code_window(conn, "On January 9, 2026, between approximately 9:10 and 9:40 p.m. EDT,"
                    " PETROV called.", "record_time")  # fmt: skip


def test_an_approximate_range_is_read_in_the_zone_the_examiner_gives(tmp_path):
    db = tmp_path / "case01.db"
    generate(tmp_path, db)
    c = sqlite3.connect(db)
    c.execute("UPDATE devices SET timezone = NULL WHERE id = 'dev:item1'")
    c.commit()
    text = "On July 9, 2026, between approximately 9:10 and 9:40 p.m. CDT, PETROV called."
    with pytest.raises(Reject, match="time zone"):
        code_window(c, text, "record_time")
    actions.set_device_zone(c, "dev:item1", "America/Chicago", "expert:Test Expert")
    w = code_window(c, text, "record_time")
    assert (w.tz, w.start_utc) == ("America/Chicago", D(2026, 7, 10, 2, 2, tzinfo=UTC))
    with pytest.raises(Reject, match="EDT"):
        code_window(c, text.replace("CDT", "EDT"), "record_time")
    c.close()


# ---------------------------------------------------------------- the model's words


@pytest.mark.parametrize(
    ("words", "text"),
    [
        # "approximately" left out: the minute would be narrower than the words
        ("7:58 p.m. on January 9, 2026",
         "At approximately 7:58 p.m. on January 9, 2026, X called."),
        # one end of a range
        ("On January 9, 2026, between approximately 9:10",
         "On January 9, 2026, between approximately 9:10 and 9:40 p.m., X called."),
        ("9:40 p.m. on January 9, 2026",
         "Between 9:10 and 9:40 p.m. on January 9, 2026, X called."),
        # an open word left out
        ("10:00 a.m. on January 9, 2026", "No contact after 10:00 a.m. on January 9, 2026."),
        ("On January 9, 2026, at 9 p.m.", "On January 9, 2026, at 9 p.m. or later, X called."),
        ("May 9, 2026", "On May 9, 2026 and May 10, 2026, X called."),
        # words only inside the quoted message
        ("9 p.m. on May 9, 2026", 'PETROV wrote "meet at 9 p.m. on May 9, 2026" to REYES.'),
    ],
)  # fmt: skip
def test_words_cut_from_a_longer_range_are_not_the_claims_range(words, text):
    assert cut_from_longer(words, text)


@pytest.mark.parametrize(
    ("words", "text"),
    [
        ("On January 9, 2026, at approximately 7:58 p.m. EST",
         "On January 9, 2026, at approximately 7:58 p.m. EST, X called."),
        ("approximately 7:58 p.m. on January 9, 2026",
         "At approximately 7:58 p.m. on January 9, 2026, X called."),
        ("On January 9, 2026", 'On January 9, 2026, PETROV wrote "at 9 p.m.".'),
        ("May 9, 2026", "SUBJECT-2's iMessage of May 9, 2026, \"see you\", shows intent."),
    ],
)  # fmt: skip
def test_the_whole_range_the_claim_writes_is_not_cut(words, text):
    assert not cut_from_longer(words, text)


def test_a_model_window_cut_from_the_claims_range_gives_way_to_code(conn):
    # The model dropped "approximately": its minute window is refused and code reads the
    # claim's 7:50 to 8:05 p.m.
    text = f'At approximately 7:58 p.m. EST on January 9, 2026, PETROV wrote "{QUOTE}".'
    w = resolved(conn, text, W("7:58 p.m. EST on January 9, 2026", "2026-01-09T19:58",
                               "2026-01-09T19:59"))  # fmt: skip
    assert local(w) == (D(2026, 1, 9, 19, 50), D(2026, 1, 9, 20, 6))


def test_a_model_window_whose_words_give_no_date_gives_way_to_code(conn):
    text = (
        f'On April 27, 2023, between approximately 2:06 and 2:22 p.m. EDT, PETROV wrote "{QUOTE}".'
    )
    w = resolved(conn, text, W("between approximately 2:06 and 2:22 p.m. EDT", "2023-04-27T14:06",
                               "2023-04-27T14:23"))  # fmt: skip
    assert local(w) == (D(2023, 4, 27, 13, 58), D(2023, 4, 27, 14, 30))


def test_a_model_window_a_little_off_about_a_time_is_code_reading(conn):
    # Before, a model's end 16 minutes off code's was kept: 8:06 to 8:13 p.m. for "about 7:58
    # p.m.", which leaves 7:58 itself out.
    text = f'At approximately 7:58 p.m. EST on January 9, 2026, PETROV wrote "{QUOTE}".'
    w = resolved(conn, text, W("At approximately 7:58 p.m. EST on January 9, 2026",
                               "2026-01-09T20:06", "2026-01-09T20:13"))  # fmt: skip
    assert local(w) == (D(2026, 1, 9, 19, 50), D(2026, 1, 9, 20, 6))


# ---------------------------------------------------------------- open ranges


def test_an_absence_after_a_time_is_the_rest_of_the_day_never_the_models_edge(conn):
    # The model ends at noon: narrower than the words, so a contact at 3 p.m. would be missed.
    text = "After 10:00 a.m. EDT on May 7, 2023, there was no contact between PETROV and REYES."
    with pytest.raises(Reject, match="read by code"):
        words = "After 10:00 a.m. EDT on May 7, 2023"
        model_window(conn, text, W(words, "2023-05-07T10:00", "2023-05-07T12:00"), "no_contact")
    w = code_window(conn, text, "no_contact")  # validation fill c
    assert local(w) == (D(2023, 5, 7, 10, 0), D(2023, 5, 8, 0, 0))


@pytest.mark.parametrize(
    ("words", "start", "end"),
    [
        ("before May 1, 2023", "2023-04-20T00:00", "2023-05-01T00:00"),
        ("since May 1, 2023", "2023-05-01T00:00", "2023-05-09T00:00"),
        ("beginning at approximately 8:00 p.m. on May 9, 2023",
         "2023-05-09T19:52", "2023-05-09T21:00"),
        ("from May 1, 2023", "2023-05-01T00:00", "2023-05-02T00:00"),
        ("by 9 p.m. on May 9, 2023", "2023-05-09T00:00", "2023-05-09T21:00"),
    ],
)  # fmt: skip
def test_a_count_or_absence_never_takes_the_models_open_edge(conn, words, start, end):
    text = f"PETROV and REYES had four calls {words}."
    for template in ("message_count", "no_contact"):
        with pytest.raises(Reject, match="read by code"):
            model_window(conn, text, W(words, start, end), template)


def test_an_event_after_a_time_stays_on_that_day(conn):
    text = f'After 10:00 a.m. on May 7, 2023, PETROV wrote "{QUOTE}".'
    words = "After 10:00 a.m. on May 7, 2023"
    w = model_window(conn, text, W(words, "2023-05-07T10:00", "2023-05-08T00:00"), "record_time")
    assert local(w) == (D(2023, 5, 7, 10, 0), D(2023, 5, 8, 0, 0))
    # A narrower end is no wider than the words: kept for an event.
    w = model_window(conn, text, W(words, "2023-05-07T10:00", "2023-05-07T10:10"), "record_time")
    assert local(w) == (D(2023, 5, 7, 10, 0), D(2023, 5, 7, 10, 10))
    # Past that day's midnight, a record on May 15 would pass: refused.
    for end in ("2023-05-20T00:00", "2023-05-08T00:01", "2023-05-07T23:00"):
        with pytest.raises(Reject, match="one stated day|midnight or a stated time"):
            model_window(conn, text, W(words, "2023-05-07T10:00", end), "record_time")


def test_an_event_before_a_time_starts_no_earlier_than_that_days_midnight(conn):
    text = f'Before 9 p.m. on May 7, 2023, PETROV wrote "{QUOTE}".'
    words = "Before 9 p.m. on May 7, 2023"
    w = model_window(conn, text, W(words, "2023-05-07T00:00", "2023-05-07T21:00"), "record_time")
    assert local(w) == (D(2023, 5, 7, 0, 0), D(2023, 5, 7, 21, 0))
    for start in ("2023-05-01T21:00", "2023-05-06T23:59", "2023-05-07T03:00"):
        with pytest.raises(Reject, match="one stated day|midnight or a stated time"):
            model_window(conn, text, W(words, start, "2023-05-07T21:00"), "record_time")
    # "after 9 a.m. and before 5 p.m.": both ends at stated times, not left open
    text = f'After 9 a.m. and before 5 p.m. on May 7, 2023, PETROV wrote "{QUOTE}".'
    words = "After 9 a.m. and before 5 p.m. on May 7, 2023"
    with pytest.raises(Reject):
        model_window(conn, text, W(words, "2023-05-01T09:00", "2023-05-30T17:00"), "record_time")
    w = model_window(conn, text, W(words, "2023-05-07T09:00", "2023-05-07T17:00"), "record_time")
    assert local(w) == (D(2023, 5, 7, 9, 0), D(2023, 5, 7, 17, 0))


# ---------------------------------------------------------------- whole months


@pytest.mark.parametrize(
    ("words", "start", "end"),
    [
        ("In April and May 2023", D(2023, 4, 1), D(2023, 6, 1)),
        ("in May 2023", D(2023, 5, 1), D(2023, 6, 1)),
        ("during April through June 2023", D(2023, 4, 1), D(2023, 7, 1)),
        ("In April, May and June 2023", D(2023, 4, 1), D(2023, 7, 1)),
        ("in December 2023", D(2023, 12, 1), D(2024, 1, 1)),
        ("during 2023", D(2023, 1, 1), D(2024, 1, 1)),
    ],
)
def test_whole_months_are_the_months_the_words_state(words, start, end):
    assert months_stated(words) == (start, end)


@pytest.mark.parametrize(
    "words",
    [
        "In April and June 2023",  # May is not stated
        "In April or May 2023",
        "In early May 2023",
        "In late April and May 2023",
        "Before May 2023",
        "Since April 2023",
        "Between April and June 2023",  # is June in it?
        "From April 2023",
        "On 1 May 2023",  # a day first, not the month
        "In May 2023, at 9 p.m.",
        "In May 2023 and on June 3, 2023",
        "In December 2022 and January 2023",  # a year beside each month: not read
    ],
)
def test_months_code_does_not_read_plainly(words):
    assert months_stated(words) is None


def test_a_whole_month_window_is_exactly_the_stated_months(conn):
    text = "In April and May 2023, PETROV and REYES had no contact."
    words = "In April and May 2023"
    for template in ("record_time", "no_contact"):
        w = model_window(conn, text, W(words, "2023-04-01T00:00", "2023-06-01T00:00"), template)
        assert local(w) == (D(2023, 4, 1), D(2023, 6, 1))
    # One of the two months (narrower) or a month more (wider) is refused.
    for s, e in (("2023-04-01T00:00", "2023-05-01T00:00"), ("2023-04-01T00:00", "2023-07-01T00:00"),
                 ("2023-03-31T00:00", "2023-06-01T00:00")):  # fmt: skip
        with pytest.raises(Reject, match="months the words state"):
            model_window(conn, text, W(words, s, e), "no_contact")


def test_one_month_copied_from_a_longer_run_of_months_is_refused(conn):
    # The model copied only "May 2023" from "In April and May 2023": May alone would leave
    # April's contact unsearched, so an absence could pass on half the claim's range.
    text = "In April and May 2023, PETROV and REYES had no contact."
    for words in ("May 2023", "April and May 2023"):
        for template in ("record_time", "no_contact"):
            if words == "April and May 2023":
                w = model_window(
                    conn, text, W(words, "2023-04-01T00:00", "2023-06-01T00:00"), template
                )
                assert local(w) == (D(2023, 4, 1), D(2023, 6, 1))
                continue
            with pytest.raises(Reject, match="cut from a longer run of months"):
                model_window(conn, text, W(words, "2023-05-01T00:00", "2023-06-01T00:00"), template)


MEET = (
    "On October 28, 2025, PETROV and REYES arranged by text to meet at 7 p.m. on Thursday,"
    " October 30, 2025, at the lot by the grain elevator."
)


@pytest.mark.parametrize("template", ["record_time", "message_count", "no_contact"])
def test_the_time_of_a_planned_meeting_is_not_when_the_messages_were_sent(conn, template):
    # The model's words are the meeting's time; the texts that set it were sent on October 28.
    words = "7 p.m. on Thursday, October 30, 2025"
    with pytest.raises(Reject, match="time of another act"):
        model_window(conn, MEET, W(words, "2025-10-30T18:52", "2025-10-30T19:09"), template)
    # Code's own reading never takes the meeting's day: it reads October 28 or refuses.
    try:
        w = code_window(conn, MEET, template)
    except Reject:
        return
    assert local(w)[0].date() == D(2025, 10, 28).date(), local(w)


def test_a_planned_meeting_is_no_event_window_but_a_meeting_that_happened_is(conn):
    words = "7 p.m. on Thursday, October 30, 2025"
    with pytest.raises(Reject, match="time of another act"):
        model_window(conn, MEET, W(words, "2025-10-30T18:52", "2025-10-30T19:09"), "event")
    held = "PETROV and REYES attended a meeting on Thursday, October 30, 2025."
    model_window(
        conn, held, W("Thursday, October 30, 2025", "2025-10-30T00:00", "2025-10-31T00:00"), "event"
    )


ONLY_MEET = (
    "PETROV and REYES arranged by text to meet at 7 p.m. on Thursday, October 30, 2025, at the"
    " lot by the grain elevator."
)


@pytest.mark.parametrize("template", ["record_time", "message_count", "no_contact", "event"])
def test_code_never_falls_back_to_the_time_of_a_planned_act(conn, template):
    # The model's words are refused, and the claim states no other range: code's own reading
    # must refuse too, never bring the meeting's time back (agents thread on #255, C43).
    with pytest.raises(Reject, match="time of another act"):
        code_window(conn, ONLY_MEET, template)
    w = W("7 p.m. on Thursday, October 30, 2025", "2025-10-30T19:00", "2025-10-30T19:01")
    with pytest.raises(Reject, match="time of another act it names"):
        filler(conn)._resolve(claim(ONLY_MEET), "", proposal(window=w, quoted_text=""))


def test_the_fallback_on_the_meetings_day_never_takes_the_meeting(conn):
    # MEET states October 28 (the texts) and October 30 (the meeting). The model's day is the
    # 30th, and that day's only stated range is the meeting's, so the fallback refuses; it never
    # swaps in the 28th, a day the model did not give.
    w = W("7 p.m. on Thursday, October 30, 2025", "2025-10-30T19:00", "2025-10-30T19:01")
    with pytest.raises(Reject, match="time of another act it names"):
        filler(conn)._resolve(claim(MEET), "", proposal(window=w, quoted_text=""))


@pytest.mark.parametrize(
    ("text", "words"),
    [
        ("On October 30, 2025, at 7 p.m., PETROV texted REYES.", "On October 30, 2025, at 7 p.m."),
        # "agreed" across a comma is no cue for the time that follows
        (
            "At 7 p.m. on Thursday, October 30, 2025, PETROV texted REYES, who agreed, on"
            " WhatsApp.",
            "7 p.m. on Thursday, October 30, 2025",
        ),
    ],
)
def test_a_time_no_other_act_names_is_still_read(conn, text, words):
    model_window(conn, text, W(words, "2025-10-30T18:52", "2025-10-30T19:09"), "record_time")


def test_a_claim_dated_by_a_month_is_never_judged_without_a_time_range():
    sender = Proposal("sender", {"quoted_text": QUOTE, "person_ids": [PETROV]}, is_core=True)
    for text in (
        f'In April 2023, PETROV wrote "{QUOTE}".',
        f'During 2023, PETROV wrote "{QUOTE}".',
        f'On 3 April 2023, PETROV wrote "{QUOTE}".',  # a day first is not read as a date
    ):
        gap = coverage_gap(claim(text), [sender])
        assert gap is not None and "month or a year" in gap
    # A month or year inside the quoted message dates nothing.
    assert coverage_gap(claim('PETROV wrote "see you in May 2023".'), [sender]) is None
