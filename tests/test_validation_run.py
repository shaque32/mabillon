"""The validation-v1 run driver (eval/validation/hickman_run.py), on synthetic case01 as a UFDR
with stand-in components. The real run is on the public Hickman phone with the local model."""

from __future__ import annotations

import json
import shutil
import sqlite3
import zipfile
from pathlib import Path

import pytest

from core.db import connect
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


def test_a_phone_zone_must_be_the_one_the_package_records(ufdr, tmp_path, monkeypatch):
    # case01's package records America/New_York: the source's zone is kept, never replaced.
    claims, out = _claims(tmp_path), tmp_path / "out"
    args = ["--ufdr", str(ufdr), "--claims", str(claims), "--out", str(out), "--fake"]
    opened = []

    def tracked(path):  # noqa: ANN001, ANN202
        conn = connect(path)
        opened.append(conn)
        return conn

    with monkeypatch.context() as m:
        m.setattr(hickman_run, "connect", tracked)
        with pytest.raises(SystemExit, match="--phone-zone: the extraction records .* not Ameri"):
            hickman_run.main([*args, "--phone-zone", "America/Chicago"])
    # the refused build closed its case.db, which on Windows the next build must replace (CI)
    for conn in opened:
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")
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
    # ...but one zone written two ways is the same zone (Claude review on #267)
    same = _defs(tmp_path, {"phone_time_zone": "(UTC-05:00) Eastern Time (US & Canada)"})
    assert hickman_run.main([*args[:-1], str(same), "--phone-zone", "America/New_York"]) == 0


def test_a_resume_whose_package_is_gone_says_so(ufdr, tmp_path):
    copy = tmp_path / ufdr.name
    shutil.copyfile(ufdr, copy)
    args = ["--ufdr", str(copy), "--claims", str(_claims(tmp_path)), "--out",
            str(tmp_path / "out"), "--fake"]  # fmt: skip
    assert hickman_run.main(args) == 0
    copy.unlink()
    with pytest.raises(SystemExit, match="cannot read .* to resume"):
        hickman_run.main(args)


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
    with pytest.raises(SystemExit, match="--phone-sha256: .*item1.ufdr has SHA-256"):
        hickman_run.main([*plain, "--phone-sha256", "item1=" + "0" * 64])
    # a package changed since the build is refused even with its original digest given, since
    # a resume hashes the bytes (CodeRabbit on #267)
    original = pair[0].read_bytes()
    try:
        pair[0].write_bytes(original + b"\0")
        with pytest.raises(SystemExit, match="was built from item1.ufdr"):
            hickman_run.main(args)
    finally:
        pair[0].write_bytes(original)


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


def test_one_zone_written_two_ways_is_not_a_conflict(pair, tmp_path):
    phones = {
        **PHONES,
        "item2": {**PHONES["item2"], "zone": "(UTC-05:00) Eastern Time (US & Canada)"},
    }
    defs = {"phones": phones, "phone_time_zone": "America/New_York"}
    assert hickman_run.main(_two(pair, tmp_path, defs)) == 0


@pytest.mark.parametrize("given", [["--phone-zone", "America/New_York"], []])
def test_a_recorded_zone_no_tool_can_read_is_refused_even_when_the_same_is_given(
    ufdr, tmp_path, monkeypatch, given
):
    import core.timeline.records as records

    # the package's zone text reads as none; with no zone given the run stops too, before any
    # model call, rather than score a phone whose every window is refused (Claude review)
    monkeypatch.setattr(records, "zone", lambda name: None)
    args = ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path)), "--out",
            str(tmp_path / "out"), "--fake", *given]  # fmt: skip
    with pytest.raises(SystemExit, match="names no time zone this tool can read"):
        hickman_run.main(args)


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
                "Phone Account Address": "+19195550100",
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


@pytest.mark.parametrize(
    ("rows", "stops"),
    [
        ([("com.samsung.android.dialer", "1"), ("com.samsung.android.dialer", "2")], True),
        ([("com.android.phone", "99"), ("com.android.phone", "98")], True),
        ([("com.samsung.android.dialer", "1"), ("com.android.phone", "2")], False),
        ([(None, "1")], False),
    ],
)
def test_a_call_log_no_check_can_read_stops_the_build_before_any_model_call(
    tmp_path, monkeypatch, rows, stops
):
    # Gate G5b: a call log whose every row was placed by another app (a Samsung phone names
    # its own dialer package) or has no direction stores no call with a side, so every call
    # claim on the phone would go untested: the build stops before the audit.
    from eval.synthetic.leapp import Lava

    lv = Lava(leapp="ALEAPP")
    for i, (package, kind) in enumerate(rows):
        values = {"Call Date": f"2024-03-01T15:0{i}:00Z", "Partner": "+19195550111",
                  "Phone Account Address": "+19195550100",
                  "Raw Call Type (as stored)": kind, "Duration in Secs": "5"}  # fmt: skip
        if package:
            values["Phone Account Package"] = package
        lv.add("get_calllog", **values)
    zipped = lv.write_zip(tmp_path / "item1.zip")
    args = ["--phone", f"item1={zipped}", "--claims", str(_claims(tmp_path)), "--out",
            str(tmp_path / "out"), "--fake", "--phone-zone", "America/New_York"]  # fmt: skip
    why = rf"item1: its call log \(get_calllog\) has {len(rows)} rows"
    if not stops:
        assert hickman_run.main(args) == 0
        assert hickman_run.main(args) == 0  # and a resume passes it too, and logs the count
        logged = (tmp_path / "out" / "progress.log").read_text(encoding="utf-8")
        assert logged.count("rows are phone calls a check can read") == 2
        return
    with pytest.raises(SystemExit, match=why):
        hickman_run.main(args)
    assert not (tmp_path / "out" / "built.ok").exists()
    # A case built before the guard is not resumed either (CodeRabbit on #269).
    with monkeypatch.context() as m:
        m.setattr(hickman_run, "call_log_check", lambda conn, sid, importer, **_k: (None, None))
        assert hickman_run.main(args) == 0
    assert (tmp_path / "out" / "built.ok").exists()
    with pytest.raises(SystemExit, match=why):
        hickman_run.main(args)


def _ios_calls(tmp_path: Path, rows: list[tuple[str, str]]) -> list[str]:
    from eval.synthetic.leapp import Lava

    lv = Lava(leapp="iLEAPP")
    for i, (provider, direction) in enumerate(rows):
        lv.add("callHistory", **{"Starting Timestamp": f"2024-03-01T15:0{i}:00Z",
                                 "Service Provider": provider, "Call Direction": direction,
                                 "Phone Number": "+19195550111", "Answered": "Yes"})  # fmt: skip
    zipped = lv.write_zip(tmp_path / "item1.zip")
    return ["--phone", f"item1={zipped}", "--claims", str(_claims(tmp_path)), "--out",
            str(tmp_path / "out"), "--fake", "--phone-zone", "America/New_York"]  # fmt: skip


def test_facetime_calls_do_not_hide_a_phone_call_log_no_check_can_read(tmp_path):
    # FaceTime rows in callHistory are stored with sides under their own app: they are not
    # phone calls, so phone calls with no direction still stop the run (Claude review on #269).
    rows = [
        ("com.apple.Telephony", ""),
        ("com.apple.Telephony", ""),
        ("com.apple.FaceTime", "Outgoing"),
    ]
    with pytest.raises(SystemExit, match=r"callhistory\) has 3 rows.*direction_not_stated 2"):
        hickman_run.main(_ios_calls(tmp_path, rows))


def test_a_call_history_of_facetime_calls_only_is_not_stopped(tmp_path, capsys):
    assert hickman_run.main(_ios_calls(tmp_path, [("com.apple.FaceTime", "Outgoing")])) == 0
    assert "callhistory: 0 of 1 rows are phone calls a check can read" in capsys.readouterr().out


def test_a_call_log_the_import_could_not_read_stops_the_build(tmp_path, monkeypatch):
    # A call log table the importer could not read is listed only under not_imported: the run
    # stops on it too (Claude review on #269).
    import eval.synthetic.leapp as synth

    monkeypatch.setitem(synth.HEADERS, "get_calllog", ("Partner", "Duration in Secs"))
    lv = synth.Lava(leapp="ALEAPP")
    lv.add("get_calllog", **{"Partner": "+19195550111", "Duration in Secs": "5"})
    zipped = lv.write_zip(tmp_path / "item1.zip")
    args = ["--phone", f"item1={zipped}", "--claims", str(_claims(tmp_path)), "--out",
            str(tmp_path / "out"), "--fake", "--phone-zone", "America/New_York"]  # fmt: skip
    with pytest.raises(SystemExit, match=r"its call log \(get_calllog, 1 records\) was not read"):
        hickman_run.main(args)
    # the importer keeps the entry's key and whether it may hold rows (CodeRabbit on #269)
    conn = sqlite3.connect(tmp_path / "out" / "case.db")
    (raw,) = conn.execute("SELECT payload_json FROM source_coverage").fetchone()
    conn.close()
    (entry,) = [t for t in json.loads(raw)["not_imported"] if t["table"] == "get_calllog"]
    assert (entry["key"], entry["may_hold_records"]) == ("get_calllog", True)


def test_a_refused_call_log_with_rows_stops_the_build_when_the_manifest_counts_none(
    tmp_path, monkeypatch
):
    # A manifest count of 0 is not taken on trust when the table is there: a refused call log
    # with a row may hold records, and one with none is empty (CodeRabbit on #269).
    import zipfile

    import eval.synthetic.leapp as synth

    monkeypatch.setitem(synth.HEADERS, "get_calllog", ("Partner", "Duration in Secs"))

    def built(rows: int, out: str) -> list[str]:
        lv = synth.Lava(leapp="ALEAPP")
        lv.tables["get_calllog"] = [{"Partner": "+19195550111", "Duration in Secs": "5"}] * rows
        manifest, data = lv.build()
        for entries in manifest["artifacts"].values():
            for e in entries:
                if e["artifact_key"] == "get_calllog":
                    e["record_count"] = 0
        zipped = tmp_path / f"{out}.zip"
        with zipfile.ZipFile(zipped, "w") as z:
            z.writestr("LEAPP_Reports_x/_lava_data.lava", json.dumps(manifest))
            z.writestr("LEAPP_Reports_x/_lava_artifacts.db", data)
            z.writestr("LEAPP_Reports_x/_HTML/index.html", "<html></html>")
        return ["--phone", f"item1={zipped}", "--claims", str(_claims(tmp_path)), "--out",
                str(tmp_path / out), "--fake", "--phone-zone", "America/New_York"]  # fmt: skip

    with pytest.raises(SystemExit, match=r"its call log \(get_calllog, 0 records\) was not read"):
        hickman_run.main(built(1, "one"))
    assert hickman_run.main(built(0, "none")) == 0  # a refused table with no row is empty


def test_a_call_log_of_untimed_calls_stops_the_build(tmp_path):
    # A sided phone call whose time cannot be read is no call a check can read (CodeRabbit on
    # #269): the same import with a readable time passes.
    from eval.synthetic.leapp import Lava

    def args(when: object, out: str, own: str | None = "+19195550100") -> list[str]:
        lv = Lava(leapp="ALEAPP")
        lv.add("get_calllog", **{"Call Date": when, "Partner": "+19195550111",
                                 "Phone Account Address": own,
                                 "Raw Call Type (as stored)": "2", "Duration in Secs": "5",
                                 "Phone Account Package": "com.android.phone"})  # fmt: skip
        zipped = lv.write_zip(tmp_path / f"{out}.zip")
        return ["--phone", f"item1={zipped}", "--claims", str(_claims(tmp_path)), "--out",
                str(tmp_path / out), "--fake", "--phone-zone", "America/New_York"]  # fmt: skip

    with pytest.raises(SystemExit, match=r"no phone call a check can read"):
        hickman_run.main(args(10**18, "untimed"))  # past any date Python can hold
    # a timed call on a phone with no line of its own: no check can put its owner on it
    with pytest.raises(SystemExit, match=r"no account of its own"):
        hickman_run.main(args("2024-03-01T15:00:00Z", "unowned", own=None))
    assert hickman_run.main(args("2024-03-01T15:00:00Z", "timed")) == 0


@pytest.mark.parametrize("unread", [False, True])
def test_the_call_log_is_found_by_its_key_when_its_table_is_named_otherwise(
    tmp_path, monkeypatch, unread
):
    # The importer reads a call log by its artifact key; a manifest whose table for that key
    # has another name is still checked (CodeRabbit on #269).
    import eval.synthetic.leapp as synth

    name = synth.sanitize
    monkeypatch.setattr(synth, "sanitize", lambda n: "calls_t" if n == "get_calllog" else name(n))
    if unread:
        monkeypatch.setitem(synth.HEADERS, "get_calllog", ("Partner", "Duration in Secs"))
    lv = synth.Lava(leapp="ALEAPP")
    lv.add("get_calllog", **{"Call Date": "2024-03-01T15:00:00Z", "Partner": "+19195550111",
                             "Raw Call Type (as stored)": "1", "Duration in Secs": "5",
                             "Phone Account Package": "com.samsung.android.dialer"})  # fmt: skip
    zipped = lv.write_zip(tmp_path / "item1.zip")
    args = ["--phone", f"item1={zipped}", "--claims", str(_claims(tmp_path)), "--out",
            str(tmp_path / "out"), "--fake", "--phone-zone", "America/New_York"]  # fmt: skip
    why = r"\(calls_t, 1 records\) was not read" if unread else r"\(calls_t\) has 1 rows"
    with pytest.raises(SystemExit, match=why):
        hickman_run.main(args)


def test_the_call_log_check_reads_only_what_the_stored_case_says(tmp_path):
    # CodeRabbit on #269: unread entries with no count, entries with no key, another table
    # whose name starts with the call log's, and a table name with a line break.
    from eval.synthetic.leapp import Lava

    lv = Lava(leapp="ALEAPP")
    lv.add("get_calllog", **{"Call Date": "2024-03-01T15:00:00Z", "Partner": "+19195550111",
                             "Phone Account Address": "+19195550100",
                             "Raw Call Type (as stored)": "2", "Duration in Secs": "5",
                             "Phone Account Package": "com.android.phone"})  # fmt: skip
    zipped = lv.write_zip(tmp_path / "item1.zip")
    args = ["--phone", f"item1={zipped}", "--claims", str(_claims(tmp_path)), "--out",
            str(tmp_path / "out"), "--fake", "--phone-zone", "America/New_York"]  # fmt: skip
    assert hickman_run.main(args) == 0
    built = (tmp_path / "out" / "case.db").read_bytes()

    def check(edit_payload=None, sql=(), source="item1", importer="leapp", owner=False):  # noqa: ANN001, ANN202
        db = tmp_path / "check.db"
        db.write_bytes(built)
        conn = sqlite3.connect(db)
        conn.execute("PRAGMA foreign_keys = ON")  # as core.db.connect opens it
        (raw,) = conn.execute(
            "SELECT payload_json FROM source_coverage WHERE source_id = 'item1'"
        ).fetchone()
        p = json.loads(raw)
        if edit_payload:
            edit_payload(p)
        conn.execute(
            "UPDATE source_coverage SET payload_json = ? WHERE source_id = 'item1'",
            (json.dumps(p),),
        )
        for q in sql:
            conn.execute(q)
        conn.commit()
        try:
            return hickman_run.call_log_check(conn, source, importer, owner_confirmed=owner)
        finally:
            conn.close()

    assert check() == (None, "get_calllog: 1 of 1 rows are phone calls a check can read")
    db = sqlite3.connect(tmp_path / "out" / "case.db")
    sides = db.execute("SELECT from_account_id, to_account_id FROM calls").fetchall()
    db.close()
    assert len(sides) == 1 and all(sides[0])  # the phone's own line and the other party

    def unread(holds):  # noqa: ANN001, ANN202
        def edit(p):  # noqa: ANN001, ANN202
            entry = {"table": "calls_x", "key": "get_calllog", "records": None}
            p["not_imported"].append({**entry, "reason": "bad", "may_hold_records": holds})

        return edit

    assert "was not read" in (check(unread(True))[0] or "")
    assert check(unread(False))[0] is None  # known to be empty
    assert "was not read" in (check(unread(None))[0] or "")  # nothing known: fails closed

    def unread_upper(p):  # noqa: ANN001, ANN202
        # a call log key in other ASCII case is still the call log (CodeRabbit on #269)
        entry = {"table": "calls_x", "key": "GET_CALLLOG", "records": 4}
        p["not_imported"].append({**entry, "reason": "bad", "may_hold_records": True})

    assert "was not read" in (check(unread_upper)[0] or "")

    def counted_empty(p):  # noqa: ANN001, ANN202
        # the manifest counts calls in the call log, but its table gave no row (CodeRabbit)
        for a in p["leapp"]["artifacts_read"]:
            a["records"] = 3 if a["key"] == "get_calllog" else a["records"]
        for t in p["tables"]:
            t["rows_read"] = 0 if t.get("header_locator") == "get_calllog" else t["rows_read"]

    assert "counts 3 records in its manifest but none was read" in (check(counted_empty)[0] or "")

    def counted_read(p):  # noqa: ANN001, ANN202
        for a in p["leapp"]["artifacts_read"]:
            a["records"] = 3 if a["key"] == "get_calllog" else a["records"]

    assert check(counted_read)[0] is None  # a count its table gave rows for passes

    def keyless(p):  # noqa: ANN001, ANN202
        p["not_imported"].append({"table": "calls_x", "records": 3, "reason": "missing columns"})

    assert "build it again" in (check(keyless)[0] or "")
    # the call log's own row loses its sides; a sided call stored under "get_calllog/second"
    # (a copy of that row, with its real accounts) is another table's and must not make it
    # readable
    other = ("INSERT INTO calls (id, source_id, locator, device_id, app, from_account_id,"
             " to_account_id, direction, ts_utc) SELECT id || 'b', source_id,"
             " 'get_calllog/second/rowid=9', device_id, app, from_account_id, to_account_id,"
             " direction, ts_utc FROM calls")  # fmt: skip
    no_sides = ("UPDATE calls SET from_account_id = NULL, to_account_id = NULL"
                " WHERE locator NOT LIKE 'get_calllog/second/%'")  # fmt: skip
    assert "no phone call a check can read" in (check(sql=(no_sides,))[0] or "")
    assert "no phone call a check can read" in (check(sql=(other, no_sides))[0] or "")
    # calls of an app not known as a provider, and no phone call: an iOS phone provider
    # written another way would read so, so the check stops; FaceTime calls only pass
    # (Claude review on #269)
    voip = "UPDATE calls SET app = 'com.example.voip'"
    assert "1 calls of an app not known as a call provider" in (check(sql=(voip,))[0] or "")
    assert check(sql=("UPDATE calls SET app = 'FaceTime'",)) == (
        None, "get_calllog: 0 of 1 rows are phone calls a check can read"
    )  # fmt: skip
    # a call with a side but no time is no call a check can read (CodeRabbit on #269)
    no_time = "UPDATE calls SET ts_utc = NULL"
    assert "no phone call a check can read" in (check(sql=(no_time,))[0] or "")
    # nor one whose other party is not where its direction puts it: an outgoing call with only
    # the phone's own line, or the same row read as incoming (CodeRabbit on #269)
    no_callee = "UPDATE calls SET to_account_id = NULL"
    assert "no phone call a check can read" in (check(sql=(no_callee,))[0] or "")
    turned = "UPDATE calls SET direction = 'incoming'"
    assert "no phone call a check can read" in (check(sql=(turned,))[0] or "")
    # an outgoing call with the callee and no line of the phone is read (as the caller check),
    # while the phone has an account of its own elsewhere in the case...
    no_line = "UPDATE calls SET from_account_id = NULL"
    assert check(sql=(no_line,))[0] is None
    # ...and with no account of its own, no check can put its owner on a call (CodeRabbit)
    unowned = "UPDATE accounts SET device_id = NULL"
    assert "no account of its own" in (check(sql=(no_line, unowned))[0] or "")
    # on resume the build's owner stipulation must still be one confirmed owner: withdrawn,
    # the accounts stay but no check can read the owner's side (CodeRabbit on #269)
    assert check(owner=True)[0] is None
    withdrawn = (
        "UPDATE stipulations SET status = 'rejected', decided_by = 'expert:x',"
        " decided_at_utc = '2026-11-18T00:00:00Z'"
    )
    assert check(sql=(withdrawn,))[0] is None  # at build, before the owner is stipulated
    assert "no one confirmed device owner" in (check(sql=(withdrawn,), owner=True)[0] or "")
    # a LEAPP phone whose coverage is not in the case, or whose importer the build did not
    # record, fails closed; another importer's phone is not checked (CodeRabbit on #269)
    assert "left no coverage record" in (check(source="item9")[0] or "")
    assert "did not record which importer" in (check(source="item9", importer=None)[0] or "")
    assert check(source="item9", importer="ufdr") == (None, None)

    def newline(p):  # noqa: ANN001, ANN202
        for t in [*p["tables"], *p["leapp"]["artifacts_read"]]:
            if (t.get("header_locator") or t.get("table")) == "get_calllog":
                t["header_locator" if "header_locator" in t else "table"] = "get_calllog\nX: ok"

    stop, _ = check(newline)
    assert stop and "\n" not in stop and "get_calllog\\nX: ok" in stop


def test_a_resume_stops_when_case_db_holds_another_import(tmp_path):
    # A case.db restored from another run under the same phone name would pass the call-log
    # check with its own calls: the resume first checks it holds the import built.ok records
    # (CodeRabbit on #269).
    from eval.synthetic.leapp import Lava

    lv = Lava(leapp="ALEAPP")
    lv.add("get_calllog", **{"Call Date": "2024-03-01T15:00:00Z", "Partner": "+19195550111",
                             "Phone Account Address": "+19195550100",
                             "Raw Call Type (as stored)": "2", "Duration in Secs": "5",
                             "Phone Account Package": "com.android.phone"})  # fmt: skip
    zipped = lv.write_zip(tmp_path / "item1.zip")
    args = ["--phone", f"item1={zipped}", "--claims", str(_claims(tmp_path)), "--out",
            str(tmp_path / "out"), "--fake", "--phone-zone", "America/New_York"]  # fmt: skip
    assert hickman_run.main(args) == 0
    conn = sqlite3.connect(tmp_path / "out" / "case.db")
    conn.execute("UPDATE sources SET sha256 = ? WHERE id = 'item1'", ("0" * 64,))
    conn.commit()
    conn.close()
    with pytest.raises(SystemExit, match=r"item1: .*case.db does not hold the import built.ok"):
        hickman_run.main(args)


@pytest.mark.parametrize("change", ["text", "claim_id", "zone"])
def test_a_resume_refuses_another_builds_case_db_of_the_same_package(tmp_path, change):
    # Two builds of one package under one phone name that differ in a claim's text, only in
    # a claim id, or only in the zone given: the second build's case.db restored into the
    # first's output passes the phone check, but is not the case built.ok records, so the
    # resume stops (CodeRabbit on #269).
    import shutil

    from eval.synthetic.leapp import Lava

    lv = Lava(leapp="ALEAPP")
    lv.add("get_calllog", **{"Call Date": "2024-03-01T15:00:00Z", "Partner": "+19195550111",
                             "Phone Account Address": "+19195550100",
                             "Raw Call Type (as stored)": "2", "Duration in Secs": "5",
                             "Phone Account Package": "com.android.phone"})  # fmt: skip
    zipped = lv.write_zip(tmp_path / "item1.zip")
    other = tmp_path / "other"
    other.mkdir()
    row = {**CLAIMS[0]}
    if change == "text":
        row["text"] = row["text"].replace("Signal", "WhatsApp")
    elif change == "claim_id":
        row["claim_id"] = "C99"
    other_claims = _claims(other, [row, *CLAIMS[1:]]) if change != "zone" else _claims(other)

    def args(claims: Path, out: str, zone: str) -> list[str]:
        return ["--phone", f"item1={zipped}", "--claims", str(claims), "--out",
                str(tmp_path / out), "--fake", "--phone-zone", zone]  # fmt: skip

    first = args(_claims(tmp_path), "a", "America/New_York")
    zone_b = "America/Chicago" if change == "zone" else "America/New_York"
    assert hickman_run.main(first) == 0
    assert hickman_run.main(args(other_claims, "b", zone_b)) == 0
    assert hickman_run.main(first) == 0  # its own case.db resumes
    shutil.copy(tmp_path / "b" / "case.db", tmp_path / "a" / "case.db")
    with pytest.raises(SystemExit, match=r"case.db is not the case built.ok records"):
        hickman_run.main(first)


def test_a_resume_refuses_a_case_whose_build_recorded_no_build_id(ufdr, tmp_path):
    # A build that wrote no build id to built.ok (as #269's setup 5 could) has nothing to tie
    # its case.db to, so a resume stops (CodeRabbit on #269). The audit of such a build stops
    # too, since it runs only on the case built.ok records.
    out = tmp_path / "out"
    args = ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path)), "--out", str(out),
            "--fake"]  # fmt: skip
    assert hickman_run.main(args) == 0
    built = json.loads((out / "built.ok").read_text(encoding="utf-8"))
    built["build_id"] = None
    (out / "built.ok").write_text(json.dumps(built), encoding="utf-8")
    with pytest.raises(SystemExit, match="built.ok records no build id"):
        hickman_run.main(args)
    with pytest.raises(SystemExit, match="is not the case built.ok records"):
        hickman_run.audit(out, True, lambda _m: None, built=built)


@pytest.mark.parametrize(
    ("sql", "says"),
    [
        (
            "UPDATE persons SET name = 'SUBJECT-3' WHERE id LIKE '%:owner'",
            "is SUBJECT-3, not SUBJECT-1",
        ),
        ("UPDATE stipulations SET status = 'rejected'", "is no one, not SUBJECT-1"),
        # a second confirmed owner of the same name, as a restored case could hold
        (
            "INSERT INTO persons (id, name, created_by) VALUES ('p2', 'SUBJECT-1', 'expert:x');"
            "INSERT INTO stipulations (id, kind, subject_id, person_id, statement, status,"
            " decided_by, decided_at_utc) SELECT id || '2', kind, subject_id, 'p2', statement,"
            " status, decided_by, decided_at_utc FROM stipulations WHERE kind = 'device_owner'",
            "is SUBJECT-1, SUBJECT-1, not SUBJECT-1",
        ),
        # the one confirmed owner moved to another person of the same name
        (
            "INSERT INTO persons (id, name, created_by) VALUES ('p2', 'SUBJECT-1', 'expert:x');"
            "UPDATE stipulations SET person_id = 'p2' WHERE kind = 'device_owner'",
            "is SUBJECT-1 under p2, not the person the build stipulated",
        ),
    ],
)
def test_a_resume_stops_when_the_device_owner_changed_since_the_build(tmp_path, sql, says):
    # An owner stipulated again as another person since the build keeps one confirmed owner,
    # but the claims name the defined owner: the resume stops (CodeRabbit on #269).
    from eval.synthetic.leapp import Lava

    lv = Lava(leapp="ALEAPP")
    lv.add("get_calllog", **{"Call Date": "2024-03-01T15:00:00Z", "Partner": "+19195550111",
                             "Phone Account Address": "+19195550100",
                             "Raw Call Type (as stored)": "2", "Duration in Secs": "5",
                             "Phone Account Package": "com.android.phone"})  # fmt: skip
    zipped = lv.write_zip(tmp_path / "item1.zip")
    args = ["--phone", f"item1={zipped}", "--claims", str(_claims(tmp_path)), "--out",
            str(tmp_path / "out"), "--fake", "--phone-zone", "America/New_York"]  # fmt: skip
    assert hickman_run.main(args) == 0
    assert hickman_run.main(args) == 0  # unchanged, it resumes
    conn = sqlite3.connect(tmp_path / "out" / "case.db")
    conn.executescript(sql)
    conn.commit()
    conn.close()
    with pytest.raises(SystemExit, match=rf"item1: its confirmed device owner {says}"):
        hickman_run.main(args)


def test_a_call_log_the_manifest_counts_but_whose_table_is_empty_stops_the_build(tmp_path):
    # A real get_calllog table with no row and a manifest count of 3: the calls it counts were
    # never read, so the build stops before any model call (CodeRabbit on #269).
    import zipfile

    from eval.synthetic.leapp import Lava

    lv = Lava(leapp="ALEAPP")
    lv.add("get_calllog", **{"Call Date": "2024-03-01T15:00:00Z", "Partner": "+19195550111",
                             "Phone Account Address": "+19195550100",
                             "Raw Call Type (as stored)": "2", "Duration in Secs": "5",
                             "Phone Account Package": "com.android.phone"})  # fmt: skip
    manifest, data = lv.build()
    entry = next(e for es in manifest["artifacts"].values() for e in es
                 if e["artifact_key"] == "get_calllog")  # fmt: skip
    entry["record_count"] = 3
    db = sqlite3.connect(":memory:")
    db.deserialize(data)
    db.execute(f'DELETE FROM "{entry["tablename"]}"')
    db.commit()
    data = db.serialize()
    db.close()
    zipped = tmp_path / "item1.zip"
    with zipfile.ZipFile(zipped, "w") as z:
        z.writestr("LEAPP_Reports_x/_lava_data.lava", json.dumps(manifest))
        z.writestr("LEAPP_Reports_x/_lava_artifacts.db", data)
    args = ["--phone", f"item1={zipped}", "--claims", str(_claims(tmp_path)), "--out",
            str(tmp_path / "out"), "--fake", "--phone-zone", "America/New_York"]  # fmt: skip
    with pytest.raises(SystemExit, match=r"item1: .*counts 3 records in its manifest but none"):
        hickman_run.main(args)


@pytest.mark.parametrize(
    ("entry", "stop"),
    [({"artifact_key": "get_calllog", "record_count": 2},
      r"item1: its call log \(no table named, 2 records\)"),
     ({"record_count": 2}, r"item1: the LEAPP manifest lists an entry with neither an artifact"
                           r" key nor a table \(Call logs, 2 records\)"),
     ({"record_count": 0}, None),
     ({"artifact_key": " ", "record_count": 2},
      r"item1: the LEAPP manifest lists an entry with neither an artifact key nor a table")],
)  # fmt: skip
def test_a_call_log_listed_with_no_table_stops_the_build(tmp_path, entry, stop):
    # The importer lists an entry with no table as not imported; the build's check stops on a
    # call log so listed before any model call (Claude review on #269). An entry with no key
    # either is named as a manifest problem, since a rebuild would list it again, and one
    # counted empty passes (CodeRabbit on #269).
    import zipfile

    from eval.synthetic.leapp import Lava

    lv = Lava(leapp="ALEAPP")
    lv.add("get_calllog", **{"Call Date": "2024-03-01T15:00:00Z", "Partner": "+19195550111",
                             "Phone Account Address": "+19195550100",
                             "Raw Call Type (as stored)": "2", "Duration in Secs": "5",
                             "Phone Account Package": "com.android.phone"})  # fmt: skip
    manifest, data = lv.build()
    next(v for v in manifest["artifacts"].values() if v).append({"name": "Call logs", **entry})
    zipped = tmp_path / "item1.zip"
    with zipfile.ZipFile(zipped, "w") as z:
        z.writestr("LEAPP_Reports_x/_lava_data.lava", json.dumps(manifest))
        z.writestr("LEAPP_Reports_x/_lava_artifacts.db", data)
    args = ["--phone", f"item1={zipped}", "--claims", str(_claims(tmp_path)), "--out",
            str(tmp_path / "out"), "--fake", "--phone-zone", "America/New_York"]  # fmt: skip
    if stop is None:
        assert hickman_run.main(args) == 0
        return
    with pytest.raises(SystemExit, match=stop):
        hickman_run.main(args)


def test_the_audit_runs_only_on_the_case_built_ok_records(ufdr, tmp_path):
    # CodeRabbit on #269: a case.db swapped after the resume's checks, before the audit opens
    # it, is refused by the audit itself, against the record the run checked, so swapping
    # built.ok along with it is refused too.
    out, other = tmp_path / "out", tmp_path / "other"
    args = ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path)), "--out", str(out),
            "--fake"]  # fmt: skip
    assert hickman_run.main(args) == 0
    assert hickman_run.main([*args[:-2], str(other), "--fake"]) == 0
    built = json.loads((out / "built.ok").read_text(encoding="utf-8"))
    assert [p.get("owner") for p in built["phones"]] == ["SUBJECT-1"]  # the owners it rechecks
    for name in ("case.db", "built.ok"):  # another build's files, both swapped in
        shutil.copy(other / name, out / name)
    with pytest.raises(SystemExit, match="is not the case built.ok records"):
        hickman_run.audit(out, True, lambda _m: None, built=built)
    # the very build, but its owner stipulation withdrawn after the resume's checks
    built = json.loads((other / "built.ok").read_text(encoding="utf-8"))
    conn = sqlite3.connect(out / "case.db")
    conn.execute("UPDATE stipulations SET status = 'rejected' WHERE kind = 'device_owner'")
    conn.commit()
    conn.close()
    with pytest.raises(SystemExit, match="its confirmed device owner is no one, not SUBJECT-1"):
        hickman_run.audit(out, True, lambda _m: None, built=built)


def test_a_resume_audits_with_the_record_it_checked_not_built_ok_read_again(
    ufdr, tmp_path, monkeypatch
):
    # CodeRabbit on #269: main() hands the audit the record its resume checked, so a case.db
    # swapped together with its built.ok after those checks is refused through main() too.
    out, other = tmp_path / "out", tmp_path / "other"
    args = ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path)), "--out", str(out),
            "--fake"]  # fmt: skip
    assert hickman_run.main(args) == 0
    assert hickman_run.main([*args[:-2], str(other), "--fake"]) == 0
    real = hickman_run.machine

    def swapped_first():  # noqa: ANN202  # called after the resume's checks, before the audit
        for name in ("case.db", "built.ok"):
            shutil.copy(other / name, out / name)
        return real()

    monkeypatch.setattr(hickman_run, "machine", swapped_first)
    with pytest.raises(SystemExit, match="is not the case built.ok records"):
        hickman_run.main(args)
    conn = sqlite3.connect(out / "case.db")  # refused by the audit, not after it: no new run
    assert conn.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0] == 1
    conn.close()


def test_the_audit_checks_the_call_log_again_before_any_model_call(tmp_path, monkeypatch):
    # CodeRabbit on #269: call rows made unreadable after the resume's checks are refused by
    # the audit itself, on the connection it audits with, before the pipeline runs.
    from eval.synthetic.leapp import Lava

    lv = Lava(leapp="ALEAPP")
    lv.add("get_calllog", **{"Call Date": "2024-03-01T15:00:00Z", "Partner": "+19195550111",
                             "Phone Account Address": "+19195550100",
                             "Raw Call Type (as stored)": "2", "Duration in Secs": "5",
                             "Phone Account Package": "com.android.phone"})  # fmt: skip
    zipped = lv.write_zip(tmp_path / "item1.zip")
    out = tmp_path / "out"
    args = ["--phone", f"item1={zipped}", "--claims", str(_claims(tmp_path)), "--out",
            str(out), "--fake", "--phone-zone", "America/New_York"]  # fmt: skip
    assert hickman_run.main(args) == 0
    real = hickman_run.machine

    def untimed_first():  # noqa: ANN202  # called after the resume's checks, before the audit
        conn = sqlite3.connect(out / "case.db")
        with conn:
            conn.execute("UPDATE calls SET ts_utc = NULL")
        conn.close()
        return real()

    monkeypatch.setattr(hickman_run, "machine", untimed_first)
    with pytest.raises(SystemExit, match=r"item1: .*no phone call a check can read"):
        hickman_run.main(args)
    conn = sqlite3.connect(out / "case.db")  # refused by the audit, not after it: no new run
    assert conn.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0] == 1
    conn.close()


def test_the_audit_never_creates_a_case_db_moved_away(ufdr, tmp_path):
    out = tmp_path / "out"
    args = ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path)), "--out", str(out),
            "--fake"]  # fmt: skip
    assert hickman_run.main(args) == 0
    built = json.loads((out / "built.ok").read_text(encoding="utf-8"))
    (out / "case.db").rename(tmp_path / "moved.db")
    with pytest.raises(SystemExit, match="is gone since the run checked it"):
        hickman_run.audit(out, True, lambda _m: None, built=built)
    assert not (out / "case.db").exists()


@pytest.mark.parametrize("when", ["report", "zip"])
def test_the_report_and_zip_ship_only_the_audited_build(ufdr, tmp_path, monkeypatch, when):
    # CodeRabbit on #269: the report and results.zip are made from the copy the audit took on
    # its checked connection, so another build's case.db put at out/case.db while the report
    # reads (then put back) or before the zip is written never reaches them.
    out, other = tmp_path / "out", tmp_path / "other"
    args = ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path)), "--out", str(out),
            "--fake"]  # fmt: skip
    (tmp_path / "o").mkdir()
    marked = [{**CLAIMS[0], "text": CLAIMS[0]["text"] + " OTHER BUILD"}, *CLAIMS[1:]]
    other_args = ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path / "o", marked)),
                  "--out", str(other), "--fake"]  # fmt: skip
    assert hickman_run.main(other_args) == 0
    real_report = hickman_run.report
    kept = tmp_path / "kept.db"

    def report_then(o, log, *a):  # noqa: ANN001, ANN002, ANN202
        shutil.copy(o / "case.db", kept)
        shutil.copy(other / "case.db", o / "case.db")
        r = real_report(o, log, *a)
        if when == "report":  # only while the report read, then put back
            shutil.copy(kept, o / "case.db")
        return r

    monkeypatch.setattr(hickman_run, "report", report_then)
    assert hickman_run.main(args) == 0
    built = json.loads((out / "built.ok").read_text(encoding="utf-8"))
    shipped = tmp_path / "shipped.db"
    with zipfile.ZipFile(out / "results.zip") as z, z.open("case.db") as src:
        shipped.write_bytes(src.read())
    conn = sqlite3.connect(shipped)
    try:
        assert hickman_run.stamped_build(conn) == built["build_id"]
        assert conn.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0] == 1
    finally:
        conn.close()
    other_built = json.loads((other / "built.ok").read_text(encoding="utf-8"))
    assert other_built["build_id"] != built["build_id"]
    html = (out / "report.html").read_text(encoding="utf-8")
    assert "OTHER BUILD" not in html  # the other build's claim text never reaches the report
    assert "OTHER BUILD" in (other / "report.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("journal", ["delete", "wal"])
def test_the_copy_holds_the_owners_the_final_check_passed(ufdr, tmp_path, monkeypatch, journal):
    # CodeRabbit on #269: the final owner check and the copy read in one transaction, so an
    # owner withdrawn by another connection between the two never reaches audited.db. Under
    # the default rollback journal the withdrawal waits on that read; under WAL it commits,
    # and the copy still holds the snapshot the check passed.
    from core import pipeline

    out = tmp_path / "out"
    args = ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path)), "--out", str(out),
            "--fake"]  # fmt: skip
    if journal == "wal":  # build first, then resume on a WAL case.db
        assert hickman_run.main(args) == 0
        conn = sqlite3.connect(out / "case.db")
        assert conn.execute("PRAGMA journal_mode = WAL").fetchone()[0] == "wal"
        conn.close()
    real_check, real_audit, audited = hickman_run.owner_stop, pipeline.run_audit, []

    def audit_then(*a, **k):  # noqa: ANN002, ANN003, ANN202
        r = real_audit(*a, **k)
        audited.append(True)
        return r

    def then_withdraw(conn, phones):  # noqa: ANN001, ANN202
        r = real_check(conn, phones)
        if audited and len(audited) == 1:  # the check after the audit, before the copy
            audited.append(True)
            other = sqlite3.connect(out / "case.db", timeout=0.2)
            try:
                with other:
                    other.execute(
                        "UPDATE stipulations SET status = 'rejected' WHERE kind = 'device_owner'"
                    )
            except sqlite3.OperationalError as e:
                assert journal == "delete" and "locked" in str(e)  # held off by the read
            finally:
                other.close()
        return r

    monkeypatch.setattr(pipeline, "run_audit", audit_then)
    monkeypatch.setattr(hickman_run, "owner_stop", then_withdraw)
    assert hickman_run.main(args) == 0
    assert len(audited) == 2  # the withdrawal was tried

    def owner(db: Path) -> str:
        conn = sqlite3.connect(db)
        try:
            return conn.execute(
                "SELECT status FROM stipulations WHERE kind = 'device_owner'"
            ).fetchone()[0]
        finally:
            conn.close()

    shipped = tmp_path / "shipped.db"
    with zipfile.ZipFile(out / "results.zip") as z, z.open("case.db") as src:
        shipped.write_bytes(src.read())
    assert owner(shipped) == "confirmed"
    assert owner(out / "case.db") == ("rejected" if journal == "wal" else "confirmed")


def test_one_run_at_a_time_uses_an_out_dir(ufdr, tmp_path):
    out = tmp_path / "out"
    args = ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path)), "--out", str(out),
            "--fake"]  # fmt: skip
    assert hickman_run.main(args) == 0
    assert not (out / hickman_run.LOCK).exists()  # released when the run ends
    before = (out / "results.zip").read_bytes()
    (out / hickman_run.LOCK).write_text("12345\n", encoding="utf-8")  # another run holds it
    with pytest.raises(SystemExit, match="another run is using"):
        hickman_run.main(args)
    assert (out / hickman_run.LOCK).exists()  # never taken from its holder
    assert (out / "results.zip").read_bytes() == before  # nor its files touched


def test_a_lock_whose_pid_write_fails_is_released(ufdr, tmp_path, monkeypatch):
    out = tmp_path / "out"
    args = ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path)), "--out", str(out),
            "--fake"]  # fmt: skip

    def full(fd, data):  # noqa: ANN001, ANN202
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(hickman_run.os, "write", full)
    with pytest.raises(OSError, match="No space left"):
        hickman_run.main(args)
    assert not (out / hickman_run.LOCK).exists()


def test_a_refused_resume_leaves_no_earlier_results_zip(ufdr, tmp_path):
    out = tmp_path / "out"
    args = ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path)), "--out", str(out),
            "--fake"]  # fmt: skip
    assert hickman_run.main(args) == 0 and (out / "results.zip").exists()
    conn = sqlite3.connect(out / "case.db")
    with conn:
        conn.execute("UPDATE stipulations SET status = 'rejected' WHERE kind = 'device_owner'")
    conn.close()
    with pytest.raises(SystemExit, match="confirmed device owner"):
        hickman_run.main(args)
    assert not (out / "results.zip").exists()


def test_a_failed_attempt_leaves_no_earlier_results_zip(ufdr, tmp_path, monkeypatch):
    out = tmp_path / "out"
    args = ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path)), "--out", str(out),
            "--fake"]  # fmt: skip
    assert hickman_run.main(args) == 0 and (out / "results.zip").exists()

    def broken(*a, **k):  # noqa: ANN002, ANN003, ANN202
        raise SystemExit("audit broke")

    monkeypatch.setattr(hickman_run, "audit", broken)
    with pytest.raises(SystemExit, match="audit broke"):
        hickman_run.main(args)
    assert not (out / "results.zip").exists()


def test_a_zip_without_the_audited_case_is_never_published(ufdr, tmp_path, monkeypatch):
    out = tmp_path / "out"
    args = ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path)), "--out", str(out),
            "--fake"]  # fmt: skip
    real = hickman_run.report

    def report_then(o, *a):  # noqa: ANN001, ANN002, ANN202
        r = real(o, *a)
        (o / hickman_run.AUDITED).unlink()
        return r

    monkeypatch.setattr(hickman_run, "report", report_then)
    with pytest.raises(SystemExit, match="audited.db is missing; results.zip not published"):
        hickman_run.main(args)
    assert not (out / "results.zip").exists() and not (out / "results.zip.part").exists()


def test_a_zip_that_fails_to_write_is_never_published(ufdr, tmp_path, monkeypatch):
    out = tmp_path / "out"
    args = ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path)), "--out", str(out),
            "--fake"]  # fmt: skip
    real = zipfile.ZipFile.write

    def failing(self, filename, arcname=None, *a, **k):  # noqa: ANN001, ANN002, ANN003, ANN202
        if arcname == "report.html":
            raise OSError("disk full")
        return real(self, filename, arcname, *a, **k)

    monkeypatch.setattr(zipfile.ZipFile, "write", failing)
    with pytest.raises(OSError, match="disk full"):
        hickman_run.main(args)
    assert not (out / "results.zip").exists() and not (out / "results.zip.part").exists()


def test_a_built_ok_gone_mid_run_never_turns_a_resume_into_a_build(ufdr, tmp_path, monkeypatch):
    # CodeRabbit on #269: the build-or-resume choice is made once, so a built.ok removed
    # after the resume's checks never starts a build that deletes the checked case.db.
    out = tmp_path / "out"
    args = ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path)), "--out", str(out),
            "--fake"]  # fmt: skip
    assert hickman_run.main(args) == 0
    real = hickman_run.owner_stop

    def gone(conn, phones):  # noqa: ANN001, ANN202
        (out / "built.ok").unlink(missing_ok=True)
        return real(conn, phones)

    monkeypatch.setattr(hickman_run, "owner_stop", gone)
    monkeypatch.setattr(
        hickman_run, "build", lambda *a, **k: pytest.fail("a resume started a build")
    )
    assert hickman_run.main(args) == 0


def test_an_owner_changed_during_the_audit_stops_the_run_unscored(ufdr, tmp_path, monkeypatch):
    # CodeRabbit on #269: the audit reads its stipulations after the driver's owner check, so
    # an owner withdrawn in between (here, as the audit starts) is caught when it returns.
    from core import pipeline

    out = tmp_path / "out"
    args = ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path)), "--out", str(out),
            "--fake"]  # fmt: skip
    assert hickman_run.main(args) == 0
    built = json.loads((out / "built.ok").read_text(encoding="utf-8"))
    real = pipeline.run_audit

    def withdrawn_first(conn, *a, **k):  # noqa: ANN001, ANN002, ANN003, ANN202
        with conn:
            conn.execute("UPDATE stipulations SET status = 'rejected' WHERE kind = 'device_owner'")
        return real(conn, *a, **k)

    monkeypatch.setattr(pipeline, "run_audit", withdrawn_first)
    with pytest.raises(SystemExit, match="owners changed during the audit, so it is not scored"):
        hickman_run.audit(out, True, lambda _m: None, built=built)
    # the refused run is stored as stopped, never the case's completed audit, and no copy of
    # it is left for a report or zip
    conn = sqlite3.connect(out / "case.db")
    try:
        ((status, note),) = conn.execute(
            "SELECT status, note FROM pipeline_runs ORDER BY started_at_utc DESC, id DESC LIMIT 1"
        )
        assert status == "stopped" and note.startswith(hickman_run.REFUSED)
        completed = [r[0] for r in conn.execute(
            "SELECT id FROM pipeline_runs WHERE status = 'completed'")]  # fmt: skip
        assert len(completed) == 1  # only the first, unrefused audit
        assert pipeline.last_run(conn)["run_id"] == completed[0]
        halted = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE action = ?", (pipeline.HALT_ACTION,)
        ).fetchone()[0]
        assert halted == 1
    finally:
        conn.close()
    assert not (out / hickman_run.AUDITED).exists()


def test_a_resume_with_no_case_db_says_so(ufdr, tmp_path):
    args = ["--ufdr", str(ufdr), "--claims", str(_claims(tmp_path)), "--out",
            str(tmp_path / "out"), "--fake"]  # fmt: skip
    assert hickman_run.main(args) == 0
    (tmp_path / "out" / "case.db").unlink()
    with pytest.raises(SystemExit, match="built.ok is there but case.db is not"):
        hickman_run.main(args)
    assert not (tmp_path / "out" / "case.db").exists()


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
            "Phone Account Address": "+19195550100",
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
    # with no zone given the run stops and names the zone to give, as with two zones
    with pytest.raises(SystemExit, match="half's tables name the zone America/Chicago but"):
        hickman_run.main(
            ["--phone", f"half={pkg}", "--claims", claims, "--out", str(tmp_path / "out3"),
             "--fake", "--definitions", str(_defs(tmp_path, {"phones": {"half": PHONES["item1"]}}))]
        )  # fmt: skip


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
