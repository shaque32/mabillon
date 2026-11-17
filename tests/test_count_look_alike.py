"""Count check 1.3.0: rows one message may be stored as twice (v5 failure hunt, 2026-11-16).

On Android 13 a TikTok chat of 12 messages is 17 rows: five live messages also stored as a
recovered copy, with the same sender, words and time and no copy number. "Exactly 12" then
failed, a false contradiction. Rows that repeat another's words within TWIN_S seconds, on any
app and from any sender, keep the count from passing or failing."""

from datetime import UTC, datetime, timedelta

import pytest

from core.audit.checks._common import Row
from core.audit.checks.count import (
    TWIN_S,
    each_way_rests_on_look_alikes,
    look_alike,
    look_alikes_matter,
)

T0 = datetime(2021, 12, 13, 0, 14, 17, tzinfo=UTC)


def row(i: int, text: str | None, at: datetime | None, sender: str = "acct:a", **kw) -> Row:
    return Row(f"m{i}", "message", "src", kw.get("app", "TikTok"), sender, ("acct:b",), at, None,
               text, direction=kw.get("direction", "incoming"))  # fmt: skip


def test_a_recovered_copy_of_a_message_is_a_look_alike() -> None:
    rows = [row(1, "Do I even know you?", T0), row(2, "Do I even know you?", T0)]
    assert look_alike(rows) == 1


def test_the_sms_store_and_google_messages_a_millisecond_apart_are_look_alikes() -> None:
    rows = [row(1, "I know. Lol. ", T0), row(2, "i know.  lol.", T0 + timedelta(milliseconds=1))]
    assert look_alike(rows) == 1


def test_the_same_words_sent_again_later_are_two_messages() -> None:
    later = T0 + timedelta(seconds=TWIN_S + 1)
    assert look_alike([row(1, "ok", T0), row(2, "ok", later)]) == 0


def test_copies_with_other_labels_are_still_look_alikes() -> None:
    # Android 13: one text is "+19198887386" in one store and "9198887386" in the other, or
    # has no sender at all; another export may name the app another way (CodeRabbit on #265).
    # A look-alike only holds a count open, so a rare true pair costs a pass, never a verdict.
    near = T0 + timedelta(milliseconds=12)
    assert look_alike([row(1, "ok", T0), row(2, "ok", near, sender="acct:9198887386")]) == 1
    assert look_alike([row(1, "ok", T0), row(2, "ok", near, sender=None)]) == 1
    assert look_alike([row(1, "ok", T0), row(2, "ok", near, app="SMS")]) == 1
    assert look_alike([row(1, "ok", T0), row(2, "ok", near, direction="unknown")]) == 1


def test_three_copies_count_twice_and_far_apart_ones_never() -> None:
    rows = [row(i, "ok", T0 + timedelta(milliseconds=i)) for i in range(3)]
    assert look_alike(rows) == 2
    spread = [row(i, "ok", T0 + timedelta(seconds=i * (TWIN_S + 1))) for i in range(4)]
    assert look_alike(spread) == 0


def test_rows_with_no_words_or_no_time_are_never_look_alikes() -> None:
    assert look_alike([row(1, "", T0), row(2, "", T0)]) == 0
    assert look_alike([row(1, "ok", None), row(2, "ok", None)]) == 0


@pytest.mark.parametrize(
    ("n", "twins", "want", "op", "matters"),
    [
        (17, 5, 12, "eq", True),  # Android 13: 12 messages stored as 17 rows
        (17, 5, 11, "eq", False),  # more than 11 however the rows are merged: a FAIL stands
        (10, 2, 5, "ge", False),  # at least 5 however merged (Claude review on #265)
        (10, 2, 9, "ge", True),
        (17, 5, 20, "le", False),  # merging only lowers the count
        (17, 5, 14, "le", True),
        (17, 5, 10, "le", False),  # more than 10 however merged
        (12, 0, 12, "eq", False),
    ],
)
def test_look_alikes_hold_a_count_open_only_when_merging_them_could_change_it(
    n: int, twins: int, want: int, op: str, matters: bool
) -> None:
    assert look_alikes_matter(n, twins, want, op) is matters


def test_a_message_each_way_on_a_look_alike_pair_alone_is_held_open() -> None:
    # "A to B 'ok'" and "B to A 'ok'" a second apart may be one message from A with the other
    # label: B's only message is one of the pair (CodeRabbit on #265).
    a, b = {"acct:a"}, {"acct:b"}
    later = T0 + timedelta(seconds=10)
    pair = [row(1, "ok", T0), row(2, "ok", T0 + timedelta(seconds=1), sender="acct:b")]
    assert each_way_rests_on_look_alikes([*pair, row(3, "other", later)], a, b)
    # B also sent a message of its own: a message each way stands
    own = row(4, "sure", later, sender="acct:b")
    assert not each_way_rests_on_look_alikes([*pair, row(3, "other", later), own], a, b)
    # no look-alikes at all
    assert not each_way_rests_on_look_alikes([row(1, "ok", T0), own], a, b)
