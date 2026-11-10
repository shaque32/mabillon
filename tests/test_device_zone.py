"""A phone's time zone the expert gives when its extraction records none
(core/review/actions.set_device_zone, core/zones.device_zones), on synthetic case01."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from core.audit.assumption_filler import LocalAssumptionFiller, Reject
from core.audit.checks._common import CaseData
from core.audit.invariants import check_report_text
from core.enrich.local_time import device_zone
from core.report.html import _limitations, sources
from core.review import actions, audit_log
from core.review.actions import ReviewError
from core.zones import GIVEN_ACTION, device_zones, given_zones
from eval.synthetic.generate import generate

EXPERT = "expert:Test Expert"
AT = datetime(2026, 11, 10, 12, tzinfo=UTC)
TEMPLATE = "{claim} {paragraph} {templates} {channels}"


@pytest.fixture
def conn(tmp_path):
    """case01 with item1's extraction recording no zone, as some Android exports do."""
    db = tmp_path / "case01.db"
    generate(tmp_path, db)
    c = sqlite3.connect(db)
    c.execute("UPDATE devices SET timezone = NULL WHERE id = 'dev:item1'")
    c.commit()
    yield c
    c.close()


def _zone(conn: sqlite3.Connection) -> str:
    filler = LocalAssumptionFiller(None, conn, template=TEMPLATE)  # type: ignore[arg-type]
    return filler._phone_zone(["dev:item1"])


def test_no_time_range_is_read_on_a_phone_with_no_zone_until_the_expert_gives_one(conn):
    with pytest.raises(Reject, match="time zone"):
        _zone(conn)
    assert actions.set_device_zone(conn, "dev:item1", " America/New_York ", EXPERT) == (
        "America/New_York"
    )
    assert _zone(conn) == "America/New_York"
    # every reader of the phone's zone reads the same one
    assert device_zones(conn)["dev:item1"] == "America/New_York"
    src = conn.execute("SELECT source_id FROM devices WHERE id = 'dev:item1'").fetchone()[0]
    assert CaseData(conn).sources[src].tz == "America/New_York"
    assert str(device_zone(conn, "dev:item1")) == "America/New_York"


def test_the_newest_entry_is_the_zone_and_an_empty_one_clears_it(conn):
    actions.set_device_zone(conn, "dev:item1", "America/Chicago", EXPERT)
    actions.set_device_zone(conn, "dev:item1", "America/New_York", EXPERT, lambda: AT)
    assert given_zones(conn) == {"dev:item1": ("America/New_York", EXPERT, "2026-11-10T12:00:00Z")}
    assert actions.set_device_zone(conn, "dev:item1", "", EXPERT) is None
    assert given_zones(conn) == {}
    with pytest.raises(Reject):
        _zone(conn)
    acts = [r[0] for r in conn.execute("SELECT action FROM audit_log ORDER BY seq")]
    assert acts.count(GIVEN_ACTION) == 3
    assert audit_log.verify_chain(conn)


@pytest.mark.parametrize("zone", ["EST", "UTC-5", "Eastern", "America/Nowhere", "-05:00"])
def test_a_zone_that_does_not_say_when_the_clocks_change_is_refused(conn, zone):
    with pytest.raises(ReviewError, match="place name"):
        actions.set_device_zone(conn, "dev:item1", zone, EXPERT)
    assert given_zones(conn) == {}


def test_a_zone_the_extraction_records_is_never_replaced(conn):
    recorded = conn.execute("SELECT timezone FROM devices WHERE id = 'dev:item2'").fetchone()[0]
    assert recorded
    with pytest.raises(ReviewError, match="records this phone's zone"):
        actions.set_device_zone(conn, "dev:item2", "Asia/Tokyo", EXPERT)
    assert device_zones(conn)["dev:item2"] == recorded


def test_only_an_expert_gives_a_known_device_a_zone(conn):
    with pytest.raises(ReviewError, match="expert"):
        actions.set_device_zone(conn, "dev:item1", "America/New_York", "system")
    with pytest.raises(ReviewError, match="no device"):
        actions.set_device_zone(conn, "dev:nope", "America/New_York", EXPERT)


def test_the_report_lists_the_zone_as_the_experts_statement(conn):
    actions.set_device_zone(conn, "dev:item1", "America/New_York", EXPERT, lambda: AT)
    text = _limitations(conn, sources(conn))
    assert "The phone's time zone is an expert statement" in text
    assert "America/New_York" in text and "dev:item1" in text and EXPERT in text
    check_report_text(text)
