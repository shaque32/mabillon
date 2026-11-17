"""The validation-v1 run driver (eval/validation/hickman_run.py), on synthetic case01 as a UFDR
with stand-in components. The real run is on the public Hickman phone with the local model."""

from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from core.review.device_names import logged_names
from eval.synthetic.generate import generate
from eval.synthetic.ufdr import write_case01
from eval.validation import hickman_run

CLAIMS = [
    {"claim_id": "C01", "page": 1, "para_no": 1, "claim_type": "communication",
     "text": "On April 28, 2023, the TARGET PHONE exchanged Signal messages with (919) 888-7386."},
    {"claim_id": "C02", "page": 1, "para_no": 2, "claim_type": "content",
     "text": 'SUBJECT-1 wrote "I\'m here!" to SUBJECT-2 on April 28, 2023.'},
    {"claim_id": "D01", "page": 2, "para_no": 3, "claim_type": "timing",
     "text": "On Tuesday, April 24, 2023, the TARGET PHONE's Discord account exchanged messages."},
]  # fmt: skip


@pytest.fixture(scope="module")
def ufdr(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("case01")
    generate(out)
    return write_case01(out)[0]


def _claims(tmp_path: Path, rows: list[dict] = CLAIMS) -> Path:
    path = tmp_path / "claims.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def test_the_run_builds_the_case_audits_it_and_zips_the_results(ufdr, tmp_path):
    claims, out = _claims(tmp_path), tmp_path / "out"
    sha = hickman_run.sha256_file(claims)
    report = hickman_run.report_xml_sha256(ufdr)
    args = ["--ufdr", str(ufdr), "--claims", str(claims), "--out", str(out), "--fake"]
    assert hickman_run.main([*args, "--claims-sha256", sha, "--report-sha256", report]) == 0

    conn = sqlite3.connect(out / "case.db")
    rows = conn.execute(
        "SELECT c.id, c.claim_type, c.text, p.label FROM claims c"
        " JOIN govdoc_paragraphs p ON p.id = c.paragraph_id ORDER BY c.id"
    ).fetchall()
    # Each claim sits on its own printed paragraph, verbatim; "content" reads as content_meaning.
    assert rows == [
        ("C01", "communication", CLAIMS[0]["text"], "1"),
        ("C02", "content_meaning", CLAIMS[1]["text"], "2"),
        ("D01", "timing", CLAIMS[2]["text"], "3"),
    ]
    owner = conn.execute(
        "SELECT s.subject_id, p.name FROM stipulations s JOIN persons p ON p.id = s.person_id"
    ).fetchall()
    assert owner == [("dev:ios15", "SUBJECT-1")]
    # Set up as the affidavit defines it: the phone's name, and SUBJECT-2 as a person only.
    assert logged_names(conn) == {"dev:ios15": ["TARGET PHONE"]}
    assert [r[0] for r in conn.execute("SELECT name FROM persons ORDER BY name")] == [
        "SUBJECT-1",
        "SUBJECT-2",
    ]
    assert conn.execute("SELECT COUNT(*) FROM identity_links").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM verdicts").fetchone()[0] == 3
    sources = conn.execute("SELECT id FROM sources ORDER BY id").fetchall()
    conn.close()

    run = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert run["claims"] == {"file": "claims.jsonl", "sha256": sha, "n": 3}
    assert run["report_xml_sha256"] == report
    assert run["audit"]["fake"] is True and sum(run["audit"]["verdicts"].values()) == 3
    assert run["audit"]["challenge"] is False  # the run 3 plan keeps it off
    with zipfile.ZipFile(out / "results.zip") as z:
        assert sorted(z.namelist()) == ["case.db", "progress.log", "report.html", "run.json"]

    # A second run resumes: the case is not rebuilt, and the audit runs again on it.
    assert hickman_run.main(args) == 0
    conn = sqlite3.connect(out / "case.db")
    assert conn.execute("SELECT id FROM sources ORDER BY id").fetchall() == sources
    assert conn.execute("SELECT COUNT(DISTINCT pipeline_run_id) FROM verdicts").fetchone()[0] == 2
    conn.close()
    # A run that stopped after the build but before run.json still records what it was built
    # from when it resumes (CodeRabbit on #267).
    (out / "run.json").unlink()
    assert hickman_run.main(args) == 0
    again = json.loads((out / "run.json").read_text(encoding="utf-8"))
    for key in ("phones", "phone_zone_given", "source_id", "definitions", "report_xml_sha256"):
        assert again[key] == run[key], key


def test_a_claims_file_with_answers_is_refused(ufdr, tmp_path):
    rows = [{**CLAIMS[0], "label": "supported"}]
    with pytest.raises(SystemExit, match="claims only"):
        hickman_run.main(
            ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path, rows)), "--out",
             str(tmp_path / "out"), "--fake"]
        )  # fmt: skip


def test_the_wrong_claims_file_or_phone_is_refused_before_anything_is_built(ufdr, tmp_path):
    claims, out = _claims(tmp_path), tmp_path / "out"
    base = ["--ufdr", str(ufdr), "--claims", str(claims), "--out", str(out), "--fake"]
    with pytest.raises(SystemExit, match="expected"):
        hickman_run.main([*base, "--claims-sha256", "0" * 64])
    with pytest.raises(SystemExit, match="report.xml SHA-256"):
        hickman_run.main([*base, "--report-sha256", "0" * 64])
    assert not (out / "case.db").exists()


def test_paragraphs_must_run_in_order(tmp_path):
    rows = [CLAIMS[0], {**CLAIMS[1], "para_no": 5}]
    with pytest.raises(SystemExit, match="1..n"):
        hickman_run.load_claims(_claims(tmp_path, rows))


def test_a_resume_with_other_inputs_is_refused(ufdr, tmp_path):
    claims, out = _claims(tmp_path), tmp_path / "out"
    assert (
        hickman_run.main(
            ["--ufdr", str(ufdr), "--claims", str(claims), "--out", str(out), "--fake"]
        )
        == 0
    )
    run = (out / "run.json").read_text(encoding="utf-8")
    other = tmp_path / "other"
    other.mkdir()
    other_claims = _claims(other, CLAIMS[:2])
    with pytest.raises(SystemExit, match="was built from claims"):
        hickman_run.main(
            ["--ufdr", str(ufdr), "--claims", str(other_claims), "--out", str(out), "--fake"]
        )
    with pytest.raises(SystemExit, match="was built from report.xml"):
        hickman_run.main(
            ["--ufdr", str(ufdr), "--claims", str(claims), "--out", str(out), "--fake",
             "--report-sha256", "0" * 64]
        )  # fmt: skip
    # the zone is given only at build, so a resume that names one is refused, not ignored
    with pytest.raises(SystemExit, match="--phone-zone: .* was built with no zone given"):
        hickman_run.main(
            ["--ufdr", str(ufdr), "--claims", str(claims), "--out", str(out), "--fake",
             "--phone-zone", "America/New_York"]
        )  # fmt: skip
    assert (out / "run.json").read_text(
        encoding="utf-8"
    ) == run  # the record still names the case's inputs
    # A case run 1's setup built (no phone name, no SUBJECT-2) is never resumed.
    built = json.loads((out / "built.ok").read_text(encoding="utf-8"))
    del built["setup"]
    (out / "built.ok").write_text(json.dumps(built), encoding="utf-8")
    with pytest.raises(SystemExit, match="earlier version of this run"):
        hickman_run.main(
            ["--ufdr", str(ufdr), "--claims", str(claims), "--out", str(out), "--fake"]
        )


def test_a_refused_report_leaves_the_audit_results_and_says_why(ufdr, tmp_path, monkeypatch):
    from core.audit.invariants import InvariantViolation
    from core.report import html

    def refuse(conn, path, timeline=None):  # noqa: ANN001, ARG001
        raise InvariantViolation("report says 'x': ...")

    monkeypatch.setattr(html, "write_report", refuse)
    out = tmp_path / "out"
    args = ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path)), "--out", str(out), "--fake"]
    assert hickman_run.main(args) == 0
    run = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert run["report"] == {"written": False, "error": "report says 'x': ..."}
    assert sum(run["audit"]["verdicts"].values()) == 3
    with zipfile.ZipFile(out / "results.zip") as z:
        assert sorted(z.namelist()) == ["case.db", "progress.log", "run.json"]
        assert "report not written" in z.read("progress.log").decode()


def test_a_number_reads_the_same_whatever_its_formatting():
    for written in ("(919) 888-7386", "+1 (919) 888-7386", "+1 919-888-7386", "19198887386",
                    "9198887386", "19198887386@s.whatsapp.net"):  # fmt: skip
        assert hickman_run.number_digits(written) == "9198887386", written
    for other in ("This Is DFIR Two", "thisisdfirtwo@gmail.com", "919888738",
                  "+19198887386x", "29198887386", "19198887386@talk.kik.com"):  # fmt: skip
        assert hickman_run.number_digits(other) is None, other
    # A ten-digit user id reads as digits, but never as the defined number.
    assert hickman_run.number_digits("1364243771") != "9198887386"


def test_a_person_defined_by_a_number_is_linked_to_that_numbers_accounts_only(tmp_path):
    from core.db import apply_schema, connect
    from core.review import actions

    conn = connect(tmp_path / "case.db")
    apply_schema(conn)
    conn.execute(
        "INSERT INTO sources VALUES ('p', 'synthetic', 'unknown', 'file_system', 'f', '0', NULL,"
        " NULL, NULL, '2026-05-01T00:00:00Z')"
    )
    accounts = [
        ("a:sig", "Signal", "+19198887386", "This Is DFIR Two"),
        ("a:wa", "WhatsApp", "19198887386@s.whatsapp.net", "This Is DFIR Two"),
        ("a:tg", "Telegram", "1364243771", "This Is DFIR Two"),  # a user id: not the number
        ("a:line", "Line", "u2353528e3ca406ce7a308f29772ee2c9", "(919) 888-7386"),  # a name
        ("a:other", "Signal", "+19195794674", "This Is DFIR"),
        # bare digits: a number on the phone's own app, a user id on another (Codex on #169)
        ("a:ph", "Phone", "9198887386", None),
        ("a:tg2", "Telegram", "9198887386", None),
    ]
    conn.executemany(
        "INSERT INTO accounts (id, source_id, locator, device_id, app, identifier, display_name)"
        " VALUES (?, 'p', 'x', NULL, ?, ?, ?)",
        accounts,
    )
    pid = actions.add_person(conn, "SUBJECT-2", hickman_run.ACTOR)
    ids = hickman_run.link_defined_number(conn, pid, "(919) 888-7386")
    assert ids == ["a:ph", "a:sig", "a:wa"]
    links = conn.execute("SELECT account_id, status, decided_by FROM identity_links").fetchall()
    assert sorted(links) == [("a:ph", "confirmed", hickman_run.ACTOR),
                             ("a:sig", "confirmed", hickman_run.ACTOR),
                             ("a:wa", "confirmed", hickman_run.ACTOR)]  # fmt: skip


class _NoCredit:
    """An Anthropic client whose every call fails the way an account out of credit does."""

    class messages:  # noqa: N801 - the SDK's attribute name
        @staticmethod
        def create(**kw):  # noqa: ANN003, ANN205
            raise RuntimeError("Error code: 400 - credit balance is too low")


def test_out_of_credit_pauses_the_cloud_run_and_a_resume_is_offered(ufdr, tmp_path, monkeypatch):
    from core.llm import cloud

    monkeypatch.setenv(cloud.KEY_ENV, "sk-test")
    monkeypatch.setattr(cloud.ClaudeModel, "_get_client", lambda self: _NoCredit())
    out = tmp_path / "out"
    rc = hickman_run.main(
        ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path)), "--out", str(out),
         "--cloud", "claude-opus-5-5"]
    )  # fmt: skip
    assert rc == 3
    log = (out / "progress.log").read_text(encoding="utf-8")
    assert "paused: the cloud model stopped answering" in log
    run = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert run["model"] == {"cloud": "claude-opus-5-5", "effort": "medium",
                            "jobs": ["assumptions", "stance"]}  # fmt: skip
    assert run["cloud"]["spent_usd"] == 0
    assert "finished_utc" not in run
    # every request went into the case's audit log before it was sent
    conn = sqlite3.connect(out / "case.db")
    sent = conn.execute("SELECT COUNT(*) FROM audit_log WHERE action = 'cloud.sent'").fetchone()[0]
    conn.close()
    assert sent >= 1


class _Out:
    def __init__(self, inp: int, outp: int) -> None:
        self.prompt_tokens, self.completion_tokens = inp, outp


class _Stub:
    name, sha256, params, where = "claude-opus-5-5", "api:claude-opus-5-5", None, "cloud"

    def generate_json(self, prompt, schema, params=None):  # noqa: ANN001, ANN201
        return _Out(1_000_000, 100_000)  # $4 in + $2 out at the Opus price


def test_the_spend_cap_stops_further_calls_as_a_sticky_failure():
    from core.llm.cloud import CloudError

    m = hickman_run.Budgeted(_Stub(), max_usd=10.0, spent_usd=3.0)
    m.generate_json("p", {})
    assert round(m.spent_usd, 2) == 9.0
    m.generate_json("p", {})  # under the cap when sent; it may end past it
    assert round(m.spent_usd, 2) == 15.0
    with pytest.raises(CloudError) as e:
        m.generate_json("p", {})
    assert e.value.sticky
    assert m.usage()["calls"] == 2


def test_the_driver_prices_match_the_bench_prices():
    from eval.bench.claude_bench import PRICES_PER_MTOK

    assert hickman_run.PRICES_PER_MTOK == PRICES_PER_MTOK


def test_a_capped_run_on_a_model_without_a_price_is_refused(ufdr, tmp_path):
    claims, out = _claims(tmp_path), tmp_path / "out"
    args = ["--ufdr", str(ufdr), "--claims", str(claims), "--out", str(out)]
    with pytest.raises(SystemExit, match="no price for"):
        hickman_run.main([*args, "--cloud", "claude-unpriced", "--max-usd", "5"])
    assert not out.exists()


def test_a_phone_zone_must_be_the_one_the_package_records(ufdr, tmp_path):
    # case01's package records America/New_York: the source's zone is kept, never replaced.
    claims, out = _claims(tmp_path), tmp_path / "out"
    args = ["--ufdr", str(ufdr), "--claims", str(claims), "--out", str(out), "--fake"]
    with pytest.raises(SystemExit, match="--phone-zone: the extraction records .* not America/C"):
        hickman_run.main([*args, "--phone-zone", "America/Chicago"])
    assert hickman_run.main([*args, "--phone-zone", "America/New_York"]) == 0
    from core.zones import given_zones

    conn = sqlite3.connect(out / "case.db")
    assert given_zones(conn) == {}, "the same zone is not given again over the package's own"
    conn.close()
    run = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert run["phones"][0]["zone_recorded"] == "America/New_York"


def _defs(tmp_path: Path, defs: dict) -> Path:
    path = tmp_path / "definitions.json"
    path.write_text(json.dumps(defs), encoding="utf-8")
    return path


def test_another_phone_takes_its_own_source_id_and_header_definitions(ufdr, tmp_path):
    # Validation v4: a second phone's claims writer hands over the affidavit's header.
    claims = _claims(tmp_path)
    first = tmp_path / "first"
    base = ["--ufdr", str(ufdr), "--claims", str(claims), "--fake"]
    assert hickman_run.main([*base, "--out", str(first)]) == 0
    conn = sqlite3.connect(first / "case.db")
    numbers = [
        ident
        for ident, app in conn.execute("SELECT identifier, app FROM accounts ORDER BY id")
        if ident and hickman_run.number_digits(ident, app or "")
    ]
    conn.close()
    assert numbers, "case01 has an account whose identifier is a telephone number"
    out = tmp_path / "out"
    defs = _defs(tmp_path, {"SUBJECT-2": numbers[0]})
    args = [*base, "--out", str(out), "--source-id", "a13", "--definitions", str(defs)]
    assert hickman_run.main(args) == 0
    conn = sqlite3.connect(out / "case.db")
    owner = conn.execute("SELECT subject_id FROM stipulations").fetchall()
    assert owner == [("dev:a13",)]
    assert logged_names(conn) == {"dev:a13": ["TARGET PHONE"]}
    assert conn.execute("SELECT COUNT(*) FROM identity_links").fetchone()[0] >= 1
    conn.close()
    run = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert run["source_id"] == "a13"
    assert run["definitions"] == {"SUBJECT-2": numbers[0]}
    # A resume must name the same phone and header; anything else is a new case.
    with pytest.raises(SystemExit, match="another source id or definitions"):
        hickman_run.main([*base, "--out", str(out), "--definitions", str(defs)])
    other = _defs(tmp_path / "first", {"SUBJECT-2": "(212) 555-0144"})
    with pytest.raises(SystemExit, match="another source id or definitions"):
        hickman_run.main(
            [*base, "--out", str(out), "--source-id", "a13", "--definitions", str(other)]
        )
    with pytest.raises(SystemExit, match="another source id or definitions"):
        hickman_run.main([*base, "--out", str(out), "--source-id", "a13"])
    assert hickman_run.main(args) == 0


@pytest.mark.parametrize(
    ("defs", "why"),
    [
        ({"SUBJECT-1": "(212) 555-0144"}, "not a SUBJECT-<n> other than SUBJECT-1"),
        ({"BOSS": "(212) 555-0144"}, "not a SUBJECT-<n>"),
        ({"SUBJECT-2": "Marcus"}, "not a number"),
        ({"SUBJECT-2": 2125550144}, "names to strings"),
        (["SUBJECT-2"], "names to strings"),
    ],
)
def test_a_header_that_defines_anything_else_is_refused(ufdr, tmp_path, defs, why):
    defs_path = _defs(tmp_path, defs)
    args = ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path)), "--out",
            str(tmp_path / "out"), "--fake", "--definitions", str(defs_path)]  # fmt: skip
    with pytest.raises(SystemExit, match=why):
        hickman_run.main(args)
    assert not (tmp_path / "out" / "case.db").exists()


def test_the_headers_zone_is_the_examiners_and_a_different_one_is_refused(ufdr, tmp_path):
    defs = _defs(tmp_path, {"phone_time_zone": "America/New_York"})
    args = ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path)), "--out",
            str(tmp_path / "out"), "--fake", "--definitions", str(defs)]  # fmt: skip
    with pytest.raises(SystemExit, match="differs from the definitions"):
        hickman_run.main([*args, "--phone-zone", "America/Chicago"])
    # case01's package records another zone, so the header's is refused as --phone-zone is.
    other = _defs(tmp_path, {"phone_time_zone": "America/Chicago"})
    with pytest.raises(SystemExit, match="--phone-zone: the extraction records"):
        hickman_run.main([*args[:-1], str(other)])


# ---------------------------------------------------------------- two phones (validation v5)

TWO = [
    {"claim_id": "T01", "page": 1, "para_no": 1, "claim_type": "communication",
     "text": "On April 28, 2023, SUBJECT-1 exchanged Signal messages with SUBJECT-2."},
    {"claim_id": "T02", "page": 1, "para_no": 2, "claim_type": "communication",
     "text": "The SECOND PHONE exchanged messages with SUBJECT-3."},
]  # fmt: skip
PHONES = {
    "item1": {"name": "TARGET PHONE", "owner": "SUBJECT-1"},
    "item2": {"name": "SECOND PHONE", "owner": "SUBJECT-2"},
}


@pytest.fixture(scope="module")
def pair(tmp_path_factory) -> list[Path]:
    out = tmp_path_factory.mktemp("case01pair")
    generate(out)
    return write_case01(out)


def _two(pair: list[Path], tmp_path: Path, defs: dict, *extra: str) -> list[str]:
    return [
        "--phone", f"item1={pair[0]}", "--phone", f"item2={pair[1]}",
        "--claims", str(_claims(tmp_path, TWO)), "--out", str(tmp_path / "out"), "--fake",
        "--definitions", str(_defs(tmp_path, defs)), *extra,
    ]  # fmt: skip


def test_two_phones_each_take_their_name_and_user(pair, tmp_path):
    defs = {"phones": PHONES, "SUBJECT-3": "(919) 888-7386"}
    sha = {p.stem: hickman_run.sha256_file(p) for p in pair}
    args = _two(pair, tmp_path, defs, *(f"--phone-sha256={k}={v}" for k, v in sha.items()))
    assert hickman_run.main(args) == 0
    out = tmp_path / "out"
    conn = sqlite3.connect(out / "case.db")
    assert logged_names(conn) == {"dev:item1": ["TARGET PHONE"], "dev:item2": ["SECOND PHONE"]}
    owners = conn.execute(
        "SELECT s.subject_id, p.name FROM stipulations s JOIN persons p ON p.id = s.person_id"
        " ORDER BY s.subject_id"
    ).fetchall()
    assert owners == [("dev:item1", "SUBJECT-1"), ("dev:item2", "SUBJECT-2")]
    # each phone's user is its stipulated owner, never a second person of the same name
    people = [n for (n,) in conn.execute("SELECT name FROM persons ORDER BY name")]
    assert people == ["SUBJECT-1", "SUBJECT-2", "SUBJECT-3"]
    conn.close()
    run = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert [(p["source_id"], p["importer"], p["sha256"]) for p in run["phones"]] == [
        ("item1", "ufdr", sha["item1"]),
        ("item2", "ufdr", sha["item2"]),
    ]
    assert "report_xml_sha256" not in run
    # a resume names the same phones, in any order and with hashes in either case; swapping
    # the packages is a new case
    assert hickman_run.main(args) == 0
    upper = [f"--phone-sha256={k}={v.upper()}" for k, v in sha.items()]
    assert hickman_run.main([*_two(pair, tmp_path, defs)[2:4], *_two(pair, tmp_path, defs)[:2],
                             *_two(pair, tmp_path, defs)[4:], *upper]) == 0  # fmt: skip
    swapped = [a.replace("item1=", "itemX=").replace("item2=", "item1=") for a in args]
    swapped = [a.replace("itemX=", "item2=") for a in swapped]
    with pytest.raises(SystemExit, match="other phones"):
        hickman_run.main(swapped)
    plain = [a for a in args if not a.startswith("--phone-sha256")]
    with pytest.raises(SystemExit, match="was built from item1.ufdr"):
        hickman_run.main([*plain, "--phone-sha256", "item1=" + "0" * 64])


@pytest.mark.parametrize(
    ("defs", "why"),
    [
        ({}, "two phones need phones"),
        ({"phones": {"item1": PHONES["item1"]}}, r"phones names \['item1'\]"),
        ({"phones": {**PHONES, "item3": PHONES["item1"]}}, "the packages are"),
        ({"phones": PHONES, "SUBJECT-2": "(919) 888-7386"}, "other than SUBJECT-1, SUBJECT-2"),
        (
            {"phones": {**PHONES, "item2": {"name": "TARGET PHONE", "owner": "SUBJECT-2"}}},
            "same name",
        ),
        ({"phones": {**PHONES, "item2": {"name": "SECOND PHONE"}}}, "needs a name and an owner"),
        (
            {"phones": {**PHONES, "item2": {"name": "SECOND PHONE", "owner": "SUBJECT-1"}}},
            "same user",
        ),
        (
            {"phones": {**PHONES, "item2": {"name": "SECOND PHONE", "owner": "Jo"}}},
            "owner is not a SUBJECT",
        ),
        ({"phones": {**PHONES, "item2": {**PHONES["item2"], "imei": "1"}}}, "needs a name"),
        (
            {
                "phones": {**PHONES, "item2": {**PHONES["item2"], "zone": "America/Chicago"}},
                "phone_time_zone": "America/New_York",
            },
            "item2.zone is America/Chicago, but the zone given for every phone",
        ),
    ],
)
def test_two_phones_with_a_header_that_does_not_define_both_are_refused(pair, tmp_path, defs, why):
    with pytest.raises(SystemExit, match=why):
        hickman_run.main(_two(pair, tmp_path, defs))
    assert not (tmp_path / "out" / "case.db").exists()


def test_a_phone_package_with_other_bytes_is_refused(pair, tmp_path):
    args = _two(pair, tmp_path, {"phones": PHONES}, "--phone-sha256", "item2=" + "0" * 64)
    with pytest.raises(SystemExit, match="--phone-sha256: .*item2.ufdr"):
        hickman_run.main(args)
    assert not (tmp_path / "out" / "built.ok").exists()


def test_phone_flags_do_not_mix(pair, tmp_path):
    claims = str(_claims(tmp_path, TWO))
    base = ["--claims", claims, "--out", str(tmp_path / "out"), "--fake"]
    for extra, why in (
        (["--ufdr", str(pair[0]), "--phone", f"item2={pair[1]}"], "use --phone for each"),
        ([], "name the phone"),
        (["--phone", f"item1={pair[0]}", "--source-id", "a13"], "--source-id goes with --ufdr"),
        (["--phone", f"item1={pair[0]}", "--report-sha256", "0" * 64], "use --phone-sha256"),
        (["--phone", str(pair[0])], "SOURCE_ID=VALUE"),
        (["--phone", f"item1={pair[0]}", "--phone", f"item1={pair[1]}"], "given twice"),
        (["--phone", f"item1={pair[0]}", "--phone-sha256", "item9=00"], "no phone item9"),
    ):
        with pytest.raises(SystemExit, match=why):
            hickman_run.main([*base, *extra])


def test_a_leapp_phone_takes_the_given_zone_only_when_it_records_none(tmp_path):
    from core.zones import device_zones
    from eval.synthetic.leapp import Lava

    def phone(name: str, zones: tuple[str, ...]) -> Path:
        lv = Lava(leapp="ALEAPP")
        lv.add(
            "get_calllog",
            **{
                "Call Date": "2024-03-01T15:00:00Z",
                "Partner": "+19195550111",
                "Raw Call Type (as stored)": "1",
                "Duration in Secs": "5",
            },
        )
        for i, z in enumerate(zones):
            lv.add(
                "get_battery_usage_v4",
                **{"Timestamp": f"2024-03-0{i + 1}T00:00:00Z", "Timezone": z},
            )
        return lv.write_zip(tmp_path / f"{name}.zip")  # fmt: skip

    claims = str(_claims(tmp_path, TWO))
    kept, given = phone("kept", ("America/New_York",)), phone("given", ())
    defs = {"phones": {"kept": PHONES["item1"], "given": PHONES["item2"]},
            "phone_time_zone": "America/New_York"}  # fmt: skip
    args = ["--phone", f"kept={kept}", "--phone", f"given={given}", "--claims", claims,
            "--out", str(tmp_path / "out"), "--fake",
            "--definitions", str(_defs(tmp_path, defs))]  # fmt: skip
    assert hickman_run.main(args) == 0
    conn = sqlite3.connect(tmp_path / "out" / "case.db")
    assert device_zones(conn) == {"dev:given": "America/New_York", "dev:kept": "America/New_York"}
    conn.close()
    run = json.loads((tmp_path / "out" / "run.json").read_text(encoding="utf-8"))
    assert [
        (p["importer"], p["zone_recorded"], p["zone_set_by_examiner"]) for p in run["phones"]
    ] == [("leapp", "America/New_York", False), ("leapp", None, True)]
    # a phone that kept two zones records none, and one given zone would misread part of it
    moved = phone("moved", ("America/New_York", "America/Chicago"))
    defs["phones"] = {"kept": PHONES["item1"], "moved": PHONES["item2"]}
    args = ["--phone", f"kept={kept}", "--phone", f"moved={moved}", "--claims", claims,
            "--out", str(tmp_path / "out2"), "--fake",
            "--definitions", str(_defs(tmp_path, defs))]  # fmt: skip
    with pytest.raises(SystemExit, match="moved recorded 2 zones"):
        hickman_run.main(args)
    # ...and with no zone given the run stops too: none of its stated windows could be read
    del defs["phone_time_zone"]
    args[-1] = str(_defs(tmp_path, defs))
    args[args.index("--out") + 1] = str(tmp_path / "out3")
    with pytest.raises(SystemExit, match="moved recorded 2 zones"):
        hickman_run.main(args)


def test_a_leapp_phone_whose_one_zone_was_not_recorded_still_refuses_another(tmp_path):
    # One zone in the phone's tables plus a zone value the importer could not read: the
    # package records no zone, but a given zone must still match the one its tables name.
    from eval.synthetic.leapp import Lava

    lv = Lava(leapp="ALEAPP")
    lv.add(
        "get_calllog",
        **{
            "Call Date": "2024-03-01T15:00:00Z",
            "Partner": "+19195550111",
            "Raw Call Type (as stored)": "1",
            "Duration in Secs": "5",
        },
    )
    lv.add(
        "get_battery_usage_v4",
        **{"Timestamp": "2024-03-01T00:00:00Z", "Timezone": "America/Chicago"},
    )
    lv.add(
        "get_battery_usage_v4", **{"Timestamp": "2024-03-02T00:00:00Z", "Timezone": "Mars/Olympus"}
    )
    pkg = lv.write_zip(tmp_path / "half.zip")
    claims = str(_claims(tmp_path, TWO[:1]))

    def run(zone: str, out: str) -> int:
        defs = {"phones": {"half": PHONES["item1"]}, "phone_time_zone": zone}
        return hickman_run.main(
            ["--phone", f"half={pkg}", "--claims", claims, "--out", str(tmp_path / out),
             "--fake", "--definitions", str(_defs(tmp_path, defs))]
        )  # fmt: skip

    with pytest.raises(SystemExit, match="half's own tables name the zone America/Chicago"):
        run("America/New_York", "out")
    assert run("America/Chicago", "out2") == 0


def test_two_packages_of_one_name_swapped_between_phones_are_refused(pair, tmp_path):
    # Report.zip in two folders: the file names match, so only the bytes tell them apart, and
    # a resume without --phone-sha256 still checks them (CodeRabbit on #267).
    one, two = tmp_path / "one", tmp_path / "two"
    for d, src in ((one, pair[0]), (two, pair[1])):
        d.mkdir()
        (d / "Report.ufdr").write_bytes(src.read_bytes())
    args = _two([one / "Report.ufdr", two / "Report.ufdr"], tmp_path, {"phones": PHONES})
    assert hickman_run.main(args) == 0
    assert hickman_run.main(args) == 0  # the same packages resume
    swapped = _two([two / "Report.ufdr", one / "Report.ufdr"], tmp_path, {"phones": PHONES})
    with pytest.raises(SystemExit, match="was built from Report.ufdr"):
        hickman_run.main(swapped)
