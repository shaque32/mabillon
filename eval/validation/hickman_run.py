"""The validation-v1 run on a public Hickman phone (eval/validation/PREREGISTERED.md).

    python -m eval.validation.hickman_run --ufdr PHONE.ufdr --claims CLAIMS.jsonl --out DIR

It builds one case the way an expert would, then runs `mabillon audit` with its defaults:
1. checks the claims file and the package's report.xml against the hashes it is given;
2. renders the claims as a numbered affidavit PDF (paragraph n is claim n's text, verbatim);
3. creates DIR/case.db in local mode, imports the UFDR, imports the affidavit, adds each claim
   to its paragraph, and sets the case up as the affidavit defines it: the phone is the TARGET
   PHONE, SUBJECT-1 used it (a stipulation), and each other SUBJECT-<n> the claims name is a
   person. A person the affidavit's header defines by a telephone number ("SUBJECT-2 is the user
   of telephone number (919) 888-7386") is linked to each account whose identifier is that
   number, written any way (a WhatsApp id 19198887386@s.whatsapp.net too), never to an account
   by its display name;
4. runs the audit with the product's local components (no AI reviewer, no cloud), or with
   --cloud, with Claude (core/llm/cloud.py) for the two model jobs an audit of given claims
   runs: assumption filling and stance labeling. Stance goes through the product's cloud path
   (the signed cloud prompt, every request in the audit log, a sticky failure pauses the run);
   the filler gets the same logging and pausing here, until the product routes it to the cloud
   (CLAUDE.md, signed 2026-11-09). --max-usd stops the run once its estimated spend passes the
   figure, as a sticky failure would; out of API credit stops it the same way. Resume with the
   same DIR: finished claims reuse their stored answers and cost nothing;
5. writes DIR/report.html, DIR/run.json (versions, machine, times) and DIR/results.zip. If the
   report's own checks refuse it, run.json says why and the results go out without it.

The claims file holds claims only, never their answers: the run machine never sees the key.
Run it again with the same DIR to resume: a built case is kept, and the audit reuses the model
outputs of the claims it finished. A case built by an earlier SETUP is refused, never resumed.
--fake swaps in the eval's stand-in components (tests only).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from core.audit.assumption_filler import NATIVE_CALL_APP
from core.audit.checks._common import namespace
from core.contracts import ClaimType, DocKind
from core.db import apply_schema, connect

ACTOR = "expert:validation"
SOURCE_ID = "ios15"
OWNER = "SUBJECT-1"
PHONE_NAME = "TARGET PHONE"  # the affidavit's name for the phone
# The people the affidavit defines, found in the claims text by this rule alone (never from the
# answers): every SUBJECT-<n> written in a claim.
SUBJECT = re.compile(r"\bSUBJECT-\d+\b")
# The affidavit's header defines these people by a telephone number (PREREGISTERED_v3.md, R4). The
# number is the definition, as the phone is SUBJECT-1's: a premise of the affidavit, not a claim.
DEFINED_NUMBERS = {"SUBJECT-2": "(919) 888-7386"}
# An identifier that is a telephone number: digits with + ( ) - . and spaces, or a WhatsApp id.
_NUMBER_ID = re.compile(r"\+?[\d\s().-]+(?:@s\.whatsapp\.net)?")
TITLE = "AFFIDAVIT (VALIDATION V1, HICKMAN PUBLIC IMAGE, NOT A REAL CASE)"
# The batch 3 writer typed "content" for content_meaning; ClaimType has no "content". The claim
# type only picks which checks run; the signed answers do not depend on it.
TYPE_ALIASES = {"content": "content_meaning"}
RESULT_FILES = ("case.db", "run.json", "report.html", "progress.log")
# How build() sets the case up. A case built by an earlier setup is not resumed: run 1's case
# (setup 1) had no phone name and no SUBJECT-2; run 2's (setup 2) had no account for SUBJECT-2.
SETUP = 3


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def report_xml_sha256(ufdr: Path) -> str:
    """The SHA-256 of the package's report.xml, streamed out of the zip."""
    from core.ingest.ufdr import find_report

    h = hashlib.sha256()
    with zipfile.ZipFile(ufdr) as z, z.open(find_report(z)) as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def load_claims(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if [r["para_no"] for r in rows] != list(range(1, len(rows) + 1)):
        raise SystemExit(f"{path}: paragraphs must run 1..n in order")
    if any("label" in r or "key_evidence" in r for r in rows):
        raise SystemExit(f"{path}: holds answers; the run machine gets claims only")
    for r in rows:
        r["claim_type"] = ClaimType(TYPE_ALIASES.get(r["claim_type"], r["claim_type"])).value
    return rows


def render_affidavit(claims: list[dict], path: Path) -> Path:
    """Claim n as printed paragraph n, laid out like the synthetic govdoc fixtures."""
    from eval.synthetic import govdocs as g

    paras = (g.Para(TITLE, heading=True),) + tuple(g.Para(c["text"], c["para_no"]) for c in claims)
    g._write(g._layout(paras, indent_style=False), path, TITLE)
    return path


def build(  # noqa: ANN001
    ufdr: Path, claims: list[dict], out: Path, log, phone_zone: str | None = None
) -> None:
    from core.ingest.govdoc import PdfGovDocIngester
    from core.ingest.ufdr import UfdrImporter
    from core.review import actions

    db = out / "case.db"
    db.unlink(missing_ok=True)
    conn = connect(db)
    apply_schema(conn)
    t = time.monotonic()
    src = UfdrImporter(source_id=SOURCE_ID).import_source(ufdr, conn)
    log(f"imported {src.file_name} ({src.fidelity.value}) in {time.monotonic() - t:.0f} s")
    _, paragraphs = PdfGovDocIngester(DocKind.AFFIDAVIT).ingest(
        render_affidavit(claims, out / "affidavit.pdf"), conn
    )
    by_label = {p.label: p for p in paragraphs if p.label}
    for c in claims:
        para = by_label.get(str(c["para_no"]))
        if para is None:
            raise SystemExit(f"{c['claim_id']}: the ingester found no paragraph {c['para_no']}")
        kind = ClaimType(c["claim_type"])
        actions.add_claim(conn, c["claim_id"], para.id, c["text"], kind, ACTOR)
    actions.name_device(conn, f"dev:{SOURCE_ID}", [PHONE_NAME], ACTOR)
    if phone_zone:
        # The examiner's statement of the zone, for a package that records none; the action
        # refuses it when the package does (core/review/actions.set_device_zone).
        try:
            actions.set_device_zone(conn, f"dev:{SOURCE_ID}", phone_zone, ACTOR)
        except actions.ReviewError as e:
            raise SystemExit(f"--phone-zone: {e}") from None
        log(f"the phone's zone, as the examiner gives it: {phone_zone}")
    actions.stipulate_device_owner(conn, f"dev:{SOURCE_ID}", OWNER, ACTOR)
    others = sorted(set(SUBJECT.findall(" ".join(c["text"] for c in claims))) - {OWNER})
    linked = {}
    for name in others:
        pid = actions.add_person(conn, name, ACTOR)
        if name in DEFINED_NUMBERS:
            linked[name] = link_defined_number(conn, pid, DEFINED_NUMBERS[name])
    conn.close()
    log(
        f"case built: {len(claims)} claims on {len(paragraphs)} paragraphs; the phone is"
        f" {PHONE_NAME}, used by {OWNER}; other people: {', '.join(others) or 'none'}"
        + "".join(f"; {n} linked to {len(ids)} accounts by number" for n, ids in linked.items())
    )


def number_digits(identifier: str, app: str | None = None) -> str | None:
    """The national digits of an identifier that is a telephone number, else None: '+1 (919)
    888-7386', '19198887386' and '19198887386@s.whatsapp.net' all give '9198887386'. Bare
    digits are a number only on a phone app or the call log (`app` None, or its namespace
    "tel"): on another app they are a user id (Codex on #169)."""
    ident = identifier.strip()
    if not _NUMBER_ID.fullmatch(ident):
        return None
    if (
        app is not None
        and not ident.startswith("+")
        and not ident.endswith("@s.whatsapp.net")
        and namespace(app) != "tel"
        and app != NATIVE_CALL_APP
    ):
        return None
    digits = re.sub(r"\D", "", identifier.split("@", 1)[0])
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits if len(digits) == 10 else None


def link_defined_number(conn, person_id: str, number: str) -> list[str]:  # noqa: ANN001
    """Link the person to every account whose identifier is the defined number (R4). A display
    name never links; nor does a number inside a longer identifier. Returns the account ids."""
    from core.review import actions

    want = number_digits(number)
    ids = [
        aid
        for aid, app, ident in conn.execute("SELECT id, app, identifier FROM accounts ORDER BY id")
        if ident and number_digits(ident, app or "") == want
    ]
    note = f"The affidavit defines {person_id} as the user of telephone number {number}."
    for aid in ids:
        actions.link_account(conn, aid, person_id, ACTOR, note)
    return ids


def machine() -> dict:
    info: dict = {"python": sys.version.split()[0], "platform": platform.platform()}
    smi = shutil.which("nvidia-smi")
    try:
        if smi is None:
            raise OSError("no nvidia-smi")
        info["gpu"] = subprocess.run(  # noqa: S603 - fixed arguments
            [smi, "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        info["gpu"] = None
    try:
        import llama_cpp

        info["llama_cpp_python"] = llama_cpp.__version__
        info["gpu_offload"] = bool(llama_cpp.llama_supports_gpu_offload())
    except ImportError:
        info["llama_cpp_python"] = None
    return info


# Dollars per million (input, output) tokens. A copy of eval/bench/claude_bench.py's table, which
# the installer does not ship; tests/test_validation_run.py checks the two agree.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


class Budgeted:
    """A cloud model that counts its spend and stops once it passes a cap. The cap and the
    out-of-credit stop both raise a sticky CloudError, which pauses the audit (CloudPaused):
    the answers stored so far are kept, and a resume picks up where it stopped."""

    def __init__(self, model, max_usd: float | None, spent_usd: float = 0.0) -> None:  # noqa: ANN001
        self._m = model
        self.name, self.sha256 = model.name, model.sha256
        self.params, self.where = model.params, getattr(model, "where", "cloud")
        self.max_usd = max_usd
        self.spent_usd = spent_usd
        self.calls = self.input_tokens = self.output_tokens = 0
        self._price = PRICES_PER_MTOK.get(model.name)

    def request(self, prompt: str, schema):  # noqa: ANN001, ANN201
        return self._m.request(prompt, schema)

    def prepare(self) -> None:
        prepare = getattr(self._m, "prepare", None)
        if prepare is not None:
            prepare()

    def _count(self, out) -> None:  # noqa: ANN001
        if out is None:
            return
        inp, outp = int(out.prompt_tokens or 0), int(out.completion_tokens or 0)
        self.input_tokens += inp
        self.output_tokens += outp
        if self._price is not None:
            self.spent_usd += (inp * self._price[0] + outp * self._price[1]) / 1_000_000

    def generate_json(self, prompt: str, schema, params=None):  # noqa: ANN001, ANN201
        from core.llm.cloud import CloudError

        if self.max_usd is not None and self.spent_usd >= self.max_usd:
            raise CloudError(
                f"the run's spend cap of ${self.max_usd:.2f} is reached"
                f" (${self.spent_usd:.2f} spent)",
                sticky=True,
            )
        self.calls += 1
        try:
            out = self._m.generate_json(prompt, schema, params)
        except CloudError as e:
            self._count(getattr(e, "response", None))
            raise
        self._count(out)
        return out

    def usage(self) -> dict:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "spent_usd": round(self.spent_usd, 2),
        }


class _Pausing:
    """The filler's model port: a sticky cloud failure pauses the audit (CloudPaused), as the
    stance labeler's CloudPort does; any other failure is that one answer dropped."""

    def __init__(self, model) -> None:  # noqa: ANN001
        self._m = model
        self.name, self.sha256 = model.name, model.sha256
        self.params, self.where = model.params, getattr(model, "where", "cloud")

    def generate_json(self, prompt: str, schema, params=None):  # noqa: ANN001, ANN201
        from core.audit._llm_json import CloudPaused
        from core.llm.cloud import CloudError

        try:
            return self._m.generate_json(prompt, schema, params)
        except CloudError as e:
            if e.sticky:
                raise CloudPaused(f"the cloud model stopped answering ({e.reason})") from e
            raise


def cloud_components(conn, model):  # noqa: ANN001, ANN201
    """The product's components with Claude filling assumptions and labeling stance."""
    from core import pipeline
    from core.audit import assumption_filler, stance
    from core.audit._local_model import SentLog

    filler = assumption_filler.create(conn, model=_Pausing(SentLog(model, conn)))
    labeler = stance.create(conn, cloud_model=model)
    return pipeline.real_components(conn, replace={"labeler": labeler}, filler=filler)


def audit(out: Path, fake: bool, log, cloud_model=None) -> dict:  # noqa: ANN001
    from core import pipeline

    conn = connect(out / "case.db")
    if fake:
        from eval.pipeline_fakes import fake_components

        comps = fake_components()
    elif cloud_model is not None:
        comps = cloud_components(conn, cloud_model)
    else:
        comps = pipeline.real_components(conn)  # local model, no AI reviewer, no cloud
    # The run 3 plan keeps the challenge step off (on by default since #162), so run 3 changes
    # only the filler and stays comparable to run 2. The audit's configuration records it.
    comps.challenge = False

    def progress(done: int, total: int, d) -> None:  # noqa: ANN001
        spent = f" (${cloud_model.spent_usd:.2f} spent)" if cloud_model is not None else ""
        log(f"[{done}/{total}] {d.claim_id}: {d.verdict.value}{spent}")

    t = time.monotonic()
    result = pipeline.run_audit(conn, comps, progress=progress)
    tally: dict[str, int] = {}
    for d in result.decisions:
        tally[d.verdict.value] = tally.get(d.verdict.value, 0) + 1
    calls = {
        purpose: {"calls": n, "first_utc": first, "last_utc": last}
        for purpose, n, first, last in conn.execute(
            "SELECT r.purpose, COUNT(*), MIN(c.at_utc), MAX(c.at_utc) FROM model_calls c"
            " JOIN model_runs r ON r.id = c.model_run_id GROUP BY r.purpose"
        )
    }
    conn.close()
    return {
        "run_id": result.run_id,
        "fake": result.fake,
        "challenge": comps.challenge,
        "verdicts": tally,
        "audit_seconds": round(time.monotonic() - t),
        "model_calls": calls,
        "model_outputs_reused": result.model_outputs_reused,
        "dropped_labels": result.dropped_labels,
        "unlabeled": result.unlabeled,
    }


def report(out: Path, log) -> dict:  # noqa: ANN001
    """Write report.html. A report the invariants refuse is left out and said so: the audit's
    results are in case.db either way, and the score is read from there."""
    from core.audit.invariants import InvariantViolation
    from core.report.html import write_report

    path = out / "report.html"
    path.unlink(missing_ok=True)  # never ship a report from an earlier attempt
    conn = connect(out / "case.db")
    try:
        write_report(conn, path)
    except InvariantViolation as e:
        log(f"report not written: {e}")
        return {"written": False, "error": str(e)}
    finally:
        conn.close()
    return {"written": True}


def model_config() -> dict | None:
    from core.audit._local_model import ModelConfigError, load_config

    try:
        cfg = load_config()
    except ModelConfigError:
        return None
    return {"name": cfg.name, "sha256": cfg.sha256, "n_ctx": cfg.n_ctx}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ufdr", type=Path, required=True)
    ap.add_argument("--claims", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--claims-sha256", help="refuse a claims file with another hash")
    ap.add_argument("--report-sha256", help="refuse a package whose report.xml has another hash")
    ap.add_argument("--fake", action="store_true", help="stand-in components (tests only)")
    ap.add_argument(
        "--cloud",
        metavar="MODEL",
        help="Claude for assumption filling and stance (e.g. claude-opus-5-5); the key comes"
        " from $MABILLON_ANTHROPIC_API_KEY",
    )
    ap.add_argument("--effort", default=None, help="the cloud model's effort (default: medium)")
    ap.add_argument(
        "--phone-zone",
        help="the phone's zone, as the examiner gives it, for a package that records none",
    )
    ap.add_argument(
        "--max-usd", type=float, help="with --cloud: stop once the run's spend passes this"
    )
    a = ap.parse_args(argv)
    if a.cloud and a.max_usd is not None and a.cloud not in PRICES_PER_MTOK:
        # Without a price the spend counter never moves, so the cap would never stop a call.
        raise SystemExit(f"--max-usd: no price for {a.cloud}; add it to PRICES_PER_MTOK")
    a.out.mkdir(parents=True, exist_ok=True)
    plog = (a.out / "progress.log").open("a", encoding="utf-8")

    def log(msg: str) -> None:
        line = f"{datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ} {msg}"
        print(line, flush=True)
        plog.write(line + "\n")
        plog.flush()

    from core import build as build_mod
    from core.audit.rules import RULE_VERSION

    run_path = a.out / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8")) if run_path.exists() else {}
    claims_sha = sha256_file(a.claims)
    if a.claims_sha256 and claims_sha != a.claims_sha256:
        raise SystemExit(f"{a.claims}: SHA-256 {claims_sha}, expected {a.claims_sha256}")
    claims = load_claims(a.claims)
    built = a.out / "built.ok"  # the inputs the case in DIR was built from
    if built.exists():
        was = json.loads(built.read_text(encoding="utf-8"))
        if was.get("setup", 1) != SETUP:
            raise SystemExit(
                f"{a.out} was set up by an earlier version of this run (setup"
                f" {was.get('setup', 1)}, now {SETUP}); use a new --out"
            )
        if was["claims_sha256"] != claims_sha:
            raise SystemExit(
                f"{a.out} was built from claims {was['claims_sha256']}; use a new --out"
            )
        if a.report_sha256 and was["report_xml_sha256"] != a.report_sha256:
            raise SystemExit(
                f"{a.out} was built from report.xml {was['report_xml_sha256']}; use a new --out"
            )
    run.setdefault("started_utc", f"{datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ}")
    run.update(
        build=build_mod.build_info(),
        rule_version=RULE_VERSION,
        model=None if a.fake else model_config(),
        machine=machine(),
        claims={"file": a.claims.name, "sha256": claims_sha, "n": len(claims)},
    )
    if not built.exists():
        log("checking the phone package's report.xml")
        report_sha = report_xml_sha256(a.ufdr)
        if a.report_sha256 and report_sha != a.report_sha256:
            raise SystemExit(f"report.xml SHA-256 {report_sha}, expected {a.report_sha256}")
        run["report_xml_sha256"] = report_sha
        build(a.ufdr, claims, a.out, log, a.phone_zone)
        run["phone_zone_given"] = a.phone_zone
        inputs = {"claims_sha256": claims_sha, "report_xml_sha256": report_sha, "setup": SETUP}
        built.write_text(json.dumps(inputs), encoding="utf-8")
    run_path.write_text(json.dumps(run, indent=2), encoding="utf-8")
    from core.audit._llm_json import CloudPaused
    from core.pipeline import ComponentsMissing

    cloud_model = None
    if a.cloud and not a.fake:
        from core.llm import cloud

        cfg = cloud.load_config()
        cfg = cloud.CloudConfig(
            api_key=cfg.api_key, model=a.cloud, effort=a.effort or cloud.DEFAULT_EFFORT
        )
        spent_before = float(run.get("cloud", {}).get("spent_usd", 0.0))
        cloud_model = Budgeted(cloud.ClaudeModel(cfg), a.max_usd, spent_before)
        run["model"] = {"cloud": cfg.model, "effort": cfg.effort, "jobs": ["assumptions", "stance"]}
    try:
        try:
            run["audit"] = audit(a.out, a.fake, log, cloud_model)
        finally:
            if cloud_model is not None:
                total = run.setdefault("cloud", {"sessions": []})
                total["sessions"].append(cloud_model.usage())
                total["spent_usd"] = round(cloud_model.spent_usd, 2)
                run_path.write_text(json.dumps(run, indent=2), encoding="utf-8")
                log(f"cloud spend so far: ${cloud_model.spent_usd:.2f}")
    except CloudPaused as e:
        log(f"paused: {e}")
        plog.close()
        print(f"paused: {e}. Run the same command again to resume.")
        return 3
    except ComponentsMissing as e:
        raise SystemExit(f"audit: {e}") from e
    run["finished_utc"] = f"{datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ}"
    run["report"] = report(a.out, log)
    run_path.write_text(json.dumps(run, indent=2), encoding="utf-8")
    plog.close()
    with zipfile.ZipFile(a.out / "results.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for name in RESULT_FILES:
            if (a.out / name).exists():
                z.write(a.out / name, name)
    print(f"done: {run['audit']['verdicts']}; results in {a.out / 'results.zip'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
