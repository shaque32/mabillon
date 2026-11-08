# Mabillon product status

The technical source of truth for what Mabillon (formerly Baker) does today. Every statement is
checked against code, tests or recorded runs. Where something exists only on an unmerged branch,
or is only reported in a changelog entry or project record, it says so.

- **As of:** 2026-11-08 (status refresh after #225)
- **main:** `9c4e8b3` (merge of #225, 2026-11-08). Everything merged through #225 and #235 is
  covered.
- **Verified on:** main `9c4e8b3`: every version below was read from the code at that commit.
  This refresh applied the 40 pending `docs/changelog/` edits of the PRs merged from #145 to #235
  and took each PR's merge date from GitHub; it did not re-verify every line number below.
- **Source labels:** **main** (merged, checked in code), **open PR #N** (not merged),
  **reported** (a run recorded in a changelog entry or project record, not re-run here),
  **unverified** (built or claimed, not measured).
- **Rule version:** 0.5.0 on main (`core/audit/rules.py`; 0.3.0 #98, 0.4.0 #166, 0.5.0 #228).
  **Contracts and schema:** 0.8.0 on main (`core/contracts.py`, `core/schema.sql`; 0.4.0
  forwarded columns #89, 0.5.0 `sent_by` and `each_way` #172, 0.6.0 person aliases #181, 0.7.0
  case events #201, 0.8.0 counsel reviews and the checked and counsel_reviewed bases #228).
- **Quote check:** 1.2.0 on main (#76), recorded on every run and printed in the report
  (`core/audit/quotes.py`, `VERSION`). Since #91 it also appears, with the Mabillon build and
  rule versions, in the report's top line, on the case overview screen and in the eval's
  `run.json`, and each model run's seed is in the report's versions table.
- **Report version:** 0.17.0 on main (`core/report/html.py`, `REPORT_VERSION`). Since 0.10.0
  (#108): 0.11.0 a scoped bundle's report says what it left out (#104); 0.12.0 Examiner activity
  section (#111); 0.13.0 the product named Mabillon (#127); 0.14.0 each verdict traced and "What
  can be checked again" (#131); 0.15.0 states the local repeat-check result for the tested model
  file and prompt (#136); 0.16.0 a stance rationale with a forbidden word is withheld per item,
  with an expert acknowledgment logged before sign-off (`core/review/withheld.py`, #138);
  0.17.0 lists the expert's names for each device (#139). Now **0.39.0 on main**: 0.18.0 each
  source's tested or "Not tested" notice (#145); 0.19.0 Native Messages holds iMessages and SMS
  together (#155); 0.20.0 to 0.30.0 the new look, the challenge and testability marks, rules
  0.4.0, one-side counts and aliases (#149, #159, #162, #163, #166, #167, #172, #174, #178,
  #181); 0.31.0 case events (#201); 0.32.0 number names (#209); 0.33.0 and 0.34.0 quoted words
  (#217, #218); 0.35.0 first-run fixes (#223); 0.37.0 plain verdict reasons (#216); 0.38.0
  rules 0.5.0 labels (#228); 0.39.0 a refusal quoting the claim's words is cited (#235). Each
  entry in `docs/changelog/` names its own bump.
- **Importers (main):** Cellebrite UFDR `ufdr` 0.3.2 (`core/ingest/ufdr.py`; 0.3.0 #117,
  0.3.1 #130, 0.3.2 #145); Cellebrite Excel and PDF 0.3.2 (`core/ingest/cellebrite_common.py`;
  0.3.0 #129, 0.3.1 #139, 0.3.2 #145); Magnet AXIOM 0.2.1 (`core/ingest/axiom.py`; 0.2.0 #116,
  0.2.1 #145). Since #145 each records `format_check` and an `import.format` audit entry
  (format notice version 1.1.0, `core/ingest/tested.py`). UFDR and AXIOM record
  `FORMAT_SUPPORT = "unverified"`. `mabillon ufdr-check` 0.3.0 (`core/ingest/ufdr_check.py`, #130).
- **Other versions (main):** identity proposer 1.1.0 (`core/identity/links.py`, #139: name
  words keep a designation's number, so SUBJECT-1 and SUBJECT-2 are two people); check versions
  same_account and absence 1.0.1, sender and weekday 1.0.2, time 1.0.3 (#165: curly quotes and
  runs of spaces fold in the text match; time 1.0.2 was #164), count 1.2.0 (1.1.0 calls #169,
  1.2.0 one side's messages #172), contact 1.0.0; assumption filler 5 (`FILLER_VERSION`,
  `core/audit/assumption_filler.py`, #209); challenge step 1.0.0 (`core/audit/challenge.py`);
  testability step 0.2.0 (`core/audit/testability.py`); reproducibility bundle format 1.2.0
  (`core/bundle/export.py`); validation scorer 1.3.0 (`eval/validation/score_hickman.py`,
  #165); key-evidence loss report 1.0.0 (`eval/loss_report.py`, #148).
- **Build stamp:** before #91, the version a report printed was `PIPELINE_VERSION`
  ("0.1.0", `core/pipeline.py`), a constant that cannot tell two builds apart. #91 (merged
  2026-10-18) also records each run's release (`pyproject.toml`, 0.0.1 today) and git commit, with a flag when
  tracked files had uncommitted changes, in the run's config as `build` (`core/build.py`), and
  prints them in the report, on the overview screen and in `run.json`. An installed copy has no
  `.git`: it reads the commit from the installer's `BUILD_INFO.json` (Windows already writes
  one; #91 makes the Mac installer write one, with whether the copied files differed from the
  commit). A folder made by `git archive` (the zip the Mac guide starts from) names its commit
  in `core/BUILD_COMMIT`. Where changed files are unknown (Windows, an unzipped archive), the
  stamp says "uncommitted changes not checked", as does an installed copy recorded clean (its
  files cannot be rechecked). A rules-only re-run also names the build its evidence came from.
  GitHub's own "Download ZIP" should fill `core/BUILD_COMMIT` in the same way; not checked.
- **Signed prompts on main:** stance v1.1 (local model) and v1.2 for a cloud model only (`stance_cloud.md`: v1.1 plus the told-frame sentences, signed 2026-10-15, #93), reviewer v1.1, claims v1.0, assumptions v1.0,
  testability agent v1.2 (`agent_testability.md`, signed 2026-11-04; v1.0 #159, v1.2 #211)
  (`core/audit/prompts/`). Stance v1.4 (`eval/probe/stance_v1_4_draft.md`, #182) is v1.1
  reordered for speed; it is not signed, and its Mac test led to no prompt change (#187).
- **Name:** the product is Mabillon. The command is `mabillon`, with `baker` kept as an alias for
  a release (`pyproject.toml`, #128). File format ids and the `baker_version` field keep the
  development name.

**Newer changes:** merged entries in `docs/changelog/` marked `Status doc: pending` are not yet
applied here and win where they differ (`python tools/changelog.py pending` lists them). One
status refresh PR applies them after merges; feature PRs do not edit this file.

## 1. What Mabillon is

Mabillon (formerly Baker) is a local app for defense forensic experts. It reads a government document (affidavit or
report) and the phone extraction reports. It splits the document into claims and marks each
claim supported, contradicted or unproven, with cited evidence. The expert runs it in a browser
on their own computer (`mabillon serve`, http://127.0.0.1:8765). Mabillon also opens in its own
window (`mabillon serve --window`; the Mac apps in ~/Applications and the Windows Start-menu
shortcuts), WebKit on a Mac and Edge WebView2 on Windows; seen working on a Mac 2026-11-06,
unverified on a Windows PC (#219). Cases live in ~/Mabillon/cases
and settings in ~/.mabillon; ~/Baker and ~/.baker are read when only they exist, and `BAKER_*`
variables are still read beside `MABILLON_*` (#128). Correctness matters more than
coverage: one wrong "supported" is the failure that counts most.

## 2. Pipeline (main)

| Step | What happens | Code | Model? |
|---|---|---|---|
| 1. Import | Opens each input read-only and SHA-256 hashes it. The browser case workflow also copies it into the case folder, and the importer refuses to store a copy whose bytes no longer match the upload's hash (nothing is stored; `tests/test_import_changed.py`, #88); `mabillon import` on the CLI reads the original path and keeps no copy. In an encrypted case each copy is renamed input-<random> once its import is stored; the real name is in the encrypted database (#230). Every evidence source shows a format notice (#145, section 8 item 1) | `core/ingest/`, `core/casework/cases.py`, `cli/main.py` | No |
| 2. Normalize | Writes canonical rows; every row has a `source_ref`; times stored UTC with the original offset and raw value | `core/ingest/`, `core/schema.sql` | No |
| 3. Enrich | Full-text search, local time, derived record text | `core/enrich/` | No |
| 4. Claims | Splits the document into paragraphs; the local model proposes atomic claims; the expert edits the list | `core/claims/` | Local 14B |
| 5. Assumptions | Fills fixed templates per claim type; values must be tied to the document or case data, or the proposal is refused. A message's quoted words must sit inside quotation marks; a party the claim writes only as the one written to is never the sender; coverage is judged only on proposals that fit their template (#160). A count of "times" is refused; counts of calls (#169) and of one side's messages ("X sent Y three messages") or "exchanged" messages (at least one each way, never failed on one side's silence; #172) are filled, though #160 first refused them. Code adds a meaning assumption on the claim's one quoted message and a sender for the writer the claim names; every quoted message needs a sender; runs record the filler version. Code reads a call's parties from the claim on the one app it names; the time check reads a call with an app as that app's calls only. stated_sender reads more wordings of a message's writer; a phone written as an account is its own accounts on the named app; counts may be written in words (#164). It also reads native calls by number, one number written several ways as one party, writers from "instructed ..., writing" and "after receiving it from", part-day ranges on a stated day, and open no-contact ranges ("never", "before", "since") to the extraction's first or last dated record; code-made assumptions say "Filled from the claim's wording." (#169). A person is read by their name or by an alias the expert entered (whole only; an alias two persons share matches neither) (#186). It reads a whole day tied to an event the expert entered (the day of, the day before or after, N days before or after; one-day events only; schema 0.7.0, #201) | `core/audit/assumption_filler.py` | Local 14B |
| 6. Checks | Deterministic checks: sender, identity, timing, weekday, count, absence | `core/audit/checks/` | No |
| 7. Retrieval | Structured filters plus keyword ranking, with surrounding messages and the other phone's copy | `core/audit/retrieval.py` | No |
| 8. Stance | Labels one record against one assumption: supports, contradicts, complicates or irrelevant. Code stores a label on a record that is not the quoted message of a one-message assumption as complicates (a near miss) or irrelevant, never supports or contradicts (#220) | `core/audit/stance.py` | Local 14B by default; Opus 5.5, opt-in per case (#68); `PROBE_PASSED` lists Opus 5.5 at medium effort with the cloud prompt, stance v1.2 (signed 2026-10-20, #101) |
| 9. Quote check | The label's quote must appear verbatim in the record, or the label is dropped. With #76 (version 1.2.0) the quote must also take in a letter or digit of the record's own fields: Mabillon's words in a rendered line ("call from") or a placeholder ("(no name)", "unknown") cannot verify it alone | `core/audit/quotes.py` | No |
| 10. AI review | Optional second pass on supporting items; off by default | `core/audit/review.py` | Local 14B |
| 11. Verdict | `decide_verdict` applies rules 0.5.0 (0.4.0 #166, 0.5.0 #228) | `core/audit/rules.py` | No |
| 12. Invariants | Re-checks each decision against stored records; a violation rolls back the claim and fails the run | `core/audit/invariants.py` | No |
| 13. Review | Expert accepts, dismisses or reopens evidence and confirms verdicts; hash-chained audit log. Each page the examiner opens is logged as a page view; Activity tab, CSV and `mabillon activity` (`core/review/activity.py`, #111). The expert acknowledges each withheld model rationale before confirming or overriding the claim's verdict (`rationale.acknowledge` in the audit log, #138) | `core/review/` | No |
| 14. Report | HTML report with findings, limitations, source hashes, model runs and rule version. Each decided claim traces its verdict per core assumption: what the rules relied on, who proposed it (model, code or expert) and the expert's step; a "What can be checked again" section says verdicts re-derive from recorded labels and decisions, and that a hosted model's labels cannot be regenerated exactly (#131). A stance rationale that uses a forbidden word is withheld from its row and listed under Withheld model rationales; Mabillon's own text is still checked whole (#138). Same inputs, versions and expert decisions give the same report hash, time fields masked; it agrees with the review screen on each claim's status, verdict and evidence ids (`tests/test_report_consistency.py`, synthetic case01) | `core/report/` | No |

Each claim is committed when it finishes, so the expert can review early claims while the audit
runs, and a stopped run resumes from stored model outputs (`core/pipeline.py`,
`core/audit/_local_model.py`). Claims whose core check already failed are not sent to the stance
model, because their verdict cannot change.

Correction to older docs: `docs/ARCHITECTURE.md` lists embeddings and translation under Enrich.
On main, retrieval uses no embeddings, and the translator (`core/audit/translation.py`) is not
called by the pipeline, the CLI or the UI. Non-Latin quotes are flagged for a human reader
instead. ARCHITECTURE.md also says a Tauri UI comes later; the shipped UI is the local browser
screen in `ui/`.

## 3. Models and their exact jobs

| Model | Where it runs | Jobs | Status |
|---|---|---|---|
| Qwen3-14B Q4_K_M (GGUF, Apache-2.0, sha256 `500a8806…81f0`, n_ctx 8192) | Expert's computer, llama-cpp-python, `flash` runtime | Claim proposal, assumption filling, stance labels (every case not opted in to cloud), optional AI review | main |
| Claude Opus 5.5, medium effort | Anthropic API, expert's own key | Stance labels only, for cases the expert opted in, with the cloud prompt, stance v1.2 (`PROBE_PASSED`, signed 2026-10-20) | main (#68; entry #101) |
| mDeBERTa-v3-base classifier | Training on cloud CPU | Candidate small stance model | branch #50 (draft); runs 5 to 7 (2026-10-15 and 16) trained on data from #79's generators and #87's (both merged), and none is a candidate on dev; run 8's data, a fresh draw of run 7's generator, is delivered; runs 1 to 4 did not pass the go bar |
| Claude Sonnet 5.5, Haiku 5.5, Opus 5.5 | Anthropic API | Benchmarks only, in `eval/bench/` | main (eval only) |
| DeepSeek V4.1 Flash, Kimi K3.1 Pro and nine other open-weight models | OpenRouter (hosted) | Benchmarks only, in `eval/bench/open_bench.py`; stance on the signed probe set, and case01 for the two that passed (section 7) | main (eval only, #225). Plan C would host DeepSeek V4.1 Flash for every job (section 5); not built |

The local model file is pinned by SHA-256 and checked before loading (`core/audit/_local_model.py`,
`packaging/windows/pins.json`). Every model call is stored with model hash, prompt hash,
parameters and seed, and identical calls reuse stored output. Each claim's audit-log entry
binds its stored model calls by SHA-256 (#104). A repeat check (2026-10-24, MacBook Air M4,
macOS 15.6.1, llama-cpp-python 0.3.36; reported) found the 14B's stance answers with prompt v1.1
byte-identical on the GPU when asked again, after a fresh load and across two case01 audits
(105/105, 105/105, 85/85); CPU only kept every stance and quote but reworded 7 of 20 rationales.
Other machines and runtime versions are not measured (#136).

## 4. The "judge": how Opus is used

There is no model judge of verdicts in Mabillon. The word "judge" does not name any component.

- **Verdicts come from code or the expert.** `core/audit/rules.py` (`decide_verdict`, rules
  0.5.0) is the only automated verdict path. The expert can also override a verdict (screen or
  `mabillon verdict --set`), which `core/review/actions.py` `override_verdict` writes directly,
  without the rules, under the expert's name in the audit log. An override to Supported needs at
  least one supporting item the expert accepted on an observed record of a core assumption, and
  cites those items; the bundle verifier replays them (#205). One exception: when the rules
  had supported the claim by code checks alone (rule 3c'), an override back to Supported keeps
  the checked basis and its cited checks, with no evidence (#228). No model, local or cloud, writes a
  verdict, an identity link or a confirmation.
- **What Opus does (#68, on main; opted-in cases since #101).** It is the stance labeler: for one (assumption, record)
  pair it returns a label, a quote and a rationale. It is a remote HTTPS call to
  `api.anthropic.com` (`core/llm/cloud.py`), pinned so a stray `ANTHROPIC_BASE_URL` cannot
  redirect it, using the expert's own key from `$MABILLON_ANTHROPIC_API_KEY` (`$BAKER_ANTHROPIC_API_KEY` still read); in an encrypted
  case, the key saved in the case, encrypted under the case key (`case.cloud-key`); else
  `~/.mabillon/cloud.json` (owner-only file). Only the filled-in stance prompt is sent: assumption,
  record, nearby messages, claim text and a group chat's member list. That is up to 20
  messages either side of the record with device-local times, senders' handles, numbers, saved
  names and confirmed people, and the record's full text (an attachment's file name, never the
  file); never a locator, file hash or the case name (`docs/SECURITY_PRIVACY.md` section 5,
  #133). Input files and the case database are never sent.
- **When Opus is used (#68).** Opt-in per case, local by default (Arsh chose "Opt-in cloud",
  2026-10-15 07:10Z). Only when all hold: the expert attested for this case that
  the protective order allows cloud AI; the case is not marked as possibly containing CSAM; a key
  is set up; and the model passed the signed stance test at its configured effort with the cloud stance prompt (`core/audit/prompts/stance_cloud.md`, v1.2,
  which only a cloud model reads)
  (`PROBE_PASSED` in `core/llm/cloud.py`). That list holds one entry: Opus 5.5 at medium effort with the cloud prompt (signed by Arsh 2026-10-20, #101). With v1.2, Opus 5.5 met the
  bars on the signed set and on new held-out items (section 7); another model or effort labels locally. The choice is stored in the case's
  hash-chained audit log. Otherwise the local 14B labels the case, as on main.
- **Failure handling (#68).** If the cloud fails mid-case, the audit pauses
  (`CloudPaused`, `core/audit/_local_model.py`); the expert retries the cloud or re-runs the
  whole case locally, so one case never mixes models. Every request body is written to the
  case's hash-chained audit log (`cloud.sent`) before it is sent, and nothing is logged as sent if
  the client cannot be built. Timeout 120 s, 2 retries. A cloud answer that failed its quote or
  format check is asked again on a re-run rather than reused. Each answer is logged as
  `cloud.received` (API-reported model, message and request ids, raw-output SHA-256, #104). The decrypted key is dropped from
  memory when a cloud audit ends.
- **Opus's influence on verdicts.** Indirect, through its labels, and bounded by the rules:
  - A "supports" label never makes a claim SUPPORTED by itself. An expert (or counsel, a tier
    nothing in the app writes yet) must accept it, or code checks alone carry a communication,
    timing or count claim with no label used (rule 3c', rules 0.5.0, #228).
  - A "contradicts" label never makes a claim CONTRADICTED by itself (rules 0.3.0, #98). On a core
    assumption, until an expert accepts it (and unless a failed check or another accepted
    contradiction already decided the claim CONTRADICTED), the claim stays UNPROVEN and the screen and report
    say "Contradiction found, confirm to finalize". On a non-core assumption it never
    contradicts, even accepted; until dismissed it blocks SUPPORTED. The per-claim-type allow-set `_AUTO_CONTRADICT`
    (`core/audit/rules.py`) is empty. An expert can dismiss any label, and a dismissed label
    stops counting.
  - In the Opus case01 run, all 5 CONTRADICTED verdicts came from failed code checks; none came
    from a model label alone.
  - **Known risk:** on the signed probe set (P001-P105), Opus calls same-day "X told the owner..."
    denials and undated denials "contradicts" (4 of 15 contradicts wrong in each arm). That was with
    stance v1.1. Since rules 0.3.0 (#98) such a label no longer makes a claim CONTRADICTED on
    its own; the expert sees "Contradiction found, confirm to finalize", and an expert who
    accepts one still makes the verdict wrong. The cloud prompt, v1.2 (#93), removed every such
    answer in the Opus tests (section 7).
- **Claim proposal and assumption filling stay local.** Opus missed both pre-set bars (claim
  recall 80% vs 90%; sheet-free audit 60% accuracy vs 80%), recorded in
  `/mnt/project-files/baker/cloud-first/steps-check/RESULTS.md`. The same-test comparison Arsh
  chose (2026-10-15, `eval/bench/fair_steps.py`) ran in two halves: Opus (2026-10-16, medium,
  $5.23) claim splitting 95%, audit without the sheet 70%, lenient fills 75%, sheet values 3 of
  20; the 14B (2026-10-19, Mac, eee8d15) 90%, 55%, 60%, 4 of 20; 0 false supported in both.
  Both steps stay local under the written rule
  (`/mnt/project-files/baker/cloud-bench/2026-10-16/fair-14b-vs-opus/DECISION.md`); one run per
  arm.

**Merge state:** #68 merged to main 2026-10-15 (`ed0a3a8`), with the CLAUDE.md wording Arsh
approved (07:29Z). `PROBE_PASSED` lists Opus 5.5 at medium (#101), so a case the expert opts in uses it.

## 5. External services

- **main:** `core/` makes no network calls except for a case the expert opted in to cloud AI (below). No telemetry. The UI serves only 127.0.0.1. Each launch makes a random screen key held in an
  HttpOnly cookie; requests without it are refused, so other accounts on the computer cannot read
  an open case (`ui/screen_key.py`, #215). The
  installers download the pinned model file once at install time (`packaging/`).
- **#68 (on main; used for opted-in cases since #101):** one network integration in `core/`: one HTTPS request (up to three with retries) to the Anthropic API per
  (assumption, record) stance pair (493 requests in the Opus case01 run).
- **eval only:** `eval/bench/claude_bench.py` and `eval/bench/cloud_steps.py` (#68) call
  the Anthropic API on synthetic data, as benchmarks. `eval/bench/open_bench.py` (#225) calls
  hosted open-weight models through OpenRouter on synthetic data, as a benchmark.
- **Plan C, a Mabillon-hosted model (decided, not built).** Arsh decided on 2026-11-07 that the
  app, input files and case database stay on the expert's machine and only filled-in prompts go
  to a Mabillon GPU server, as the default for ordinary cases, still opted in per case; local
  mode stays for cases marked as possibly containing CSAM and strict protective orders. On
  2026-11-08 he chose to move every model job there (stance, claim proposal, assumption filling,
  the AI reviewer and the agents), with DeepSeek V4.1 Flash as the model (project records). None
  of it is on main: `CLAUDE.md` still says local by default with only the stance labeler's
  Anthropic call in `core/`; the server pieces are open draft PR #244 (`deploy/model_server`, not
  used by the app); there is no client in `core/llm/`. DeepSeek V4.1 Flash has been measured as a
  stance labeler only (section 7).

## 6. Rules and models together

| Outcome | What it needs (rules 0.5.0) |
|---|---|
| SUPPORTED | Every core assumption covered (a passing check, or support an expert or counsel accepted); at least one expert- or counsel-accepted support on an observed record; no open complicating or contradicting item; the claim type's key assumption present. Or, for communication, timing and count claims, every core assumption passed all its checks and one cites records (basis checked, no label, no reviewer; rule 3c', #228; not for an "exactly N" count) |
| CONTRADICTED | A failed deterministic check on a core assumption, or a "contradicts" an expert accepted on a core assumption; an unaccepted one on a core assumption shows "Contradiction found, confirm to finalize" (unless a failed check or another accepted contradiction already decided the claim). A failed check or "contradicts" on a non-core assumption never contradicts. A failed non-core check always blocks SUPPORTED; a non-core "contradicts" label blocks it until the expert dismisses it. A failed check on an assumption the testability agent proposed counts once the expert confirms it (rules 0.4.0, #166) |
| UNPROVEN | Anything else, with the uncovered assumptions named |

AI review alone covers nothing in the alpha (`_AI_MAY_COVER` is empty), so a SUPPORTED verdict
is expert-confirmed, supported by the records (code checks), or reviewed by counsel; the last two
never display as confirmed. Nothing in the app or CLI writes a counsel review yet (#228, "Open"),
so on main a SUPPORTED is expert-confirmed or checked. Display tiers: observed, derived, inferred,
ai_reviewed, counsel_reviewed, confirmed.

## 7. Benchmarks and hardware

All on synthetic data. The probe is the signed stance set (`eval/gold/probe/`: 105 items on main since #64); case01 is the 20-claim synthetic case with signed gold.

**Stance labelers, old 88-item probe (v0.3 labels before the follow-up, prompt v1.1, product layout)**
Source: `/mnt/project-files/baker/cloud-bench/2026-10-14c/RESULTS.md`, preregistered.

| Model | Supports recall | Contradicts precision | Traps shown as support | Passes all bars |
|---|---|---|---|---|
| Opus 5.5 medium | 27/27 | 6/6 | 0 | yes |
| Opus 5.5 high | 27/27 | 4/4 | 0 | yes |
| Sonnet 5.5 high | 27/27 | 8/16 | 1 | no |
| Haiku 5.5 medium | 18/27 | 8/10 | 0 | no |
| Qwen3-14B (re-scored from 2026-10-07 answers, prompt v1.0) | 100% | 7/8 | 5 moved traps | no (moved-trap bar) |

The table above used the old 88-item set with only 8 gold contradicts. **Superseded** by the
signed follow-up (P049, P066-P069 relabeled complicates; P089-P105 added; 95 gated items, 11 real
contradicts), signed by Arsh 2026-10-15 and merged in #64.
Opus on that set (`/mnt/project-files/baker/cloud-bench/2026-10-15/RESULTS.md`, preregistered,
$5.21):

| Bar (95 gated items) | Opus high | Opus medium |
|---|---|---|
| Supports recall (>= 90%) | 33/33 | 33/33 |
| Contradicts precision (>= 90%) | **11/15, 73%, fails** | **11/15, 73%, fails** |
| Contradicting shown as supports (0) | 0 | 0 |
| Contradicts recall | 11/11 | 11/11 |

So **with stance v1.1, Opus no longer passes the full cloud rule** (v1.2 below meets it). Every wrong answer is a told-frame or undated
denial (P049, P066-P069, P092, P093). Blind readers sided with the signed labels 12 of 12. The
fix is stance v1.2 (#93), signed by Arsh 2026-10-15: with it Opus scored contradicts precision
10/10, supports recall 33/33, 0 contradicting shown as supports and contradicts recall 10/11
(misses P065), at high and at medium, and its wrong contradicts on new items went from 2 to 0
(24 items) and 1 to 0 (26 items) (`/mnt/project-files/baker/cloud-bench/2026-10-15/told-frame-line/`).
It is the cloud model's prompt only (Arsh, "Opus only", 2026-10-19). The local 14B's stance labels also miss the signed bars: on the signed set with v1.1, the
prompt on main (Arsh's Mac, macOS 15.6.1 arm64, commit `eee8d15` on #76's branch, 2026-10-19; llama-cpp-python 0.3.36, Qwen3-14B Q4_K_M SHA-256 `500a8806…b81f0`), its
contradicts precision is 58% (11 of 19, bar 90%; the count is derived from 100% recall of the
11 gold contradicts) and it shows 6 moved traps as supports (contradicts recall 100%, supports recall 100%, 0 contradicting shown as supports). With v1.2 (same run) the 14B's contradicts precision fell
to 50% (11 of 22) with the same 6 moved traps, which is why the local model keeps v1.1. Source:
`/mnt/project-files/baker/cloud-bench/2026-10-16/fair-14b-vs-opus/local-arm/RESULTS.md`.
Newer local models were screened on the same signed set (Arsh's Mac, macOS 15.6.1 arm64, 24 GB,
commit f9461b9, 2026-10-22, both signed prompts, one run each; reported, #123): Gemma 4 26B-A4B,
Gemma 4 12B and Qwen3.8-27B all failed the contradicts precision bar (41% to 52%, bar 90%) and
showed 1 or 2 moved traps as supports. None passed, so Qwen3-14B stays the local model. Source:
`/mnt/project-files/baker/local-model/2026-10-22-mac-screen-RESULTS.md`.
Hosted open-weight models were screened on the same signed set through OpenRouter (cloud
container, 2026-11-07, both signed prompts, one run each; eval only, #225; hosted answers are
not reproducible): of eleven models, only DeepSeek V4.1 Flash (contradicts precision 92% of 12)
and Kimi K3.1 Pro (100% of 10) passed stage 1, both with prompt v1.2; both scored 95% with 0
false supported on synthetic case01. Neither has been self-hosted or repeat-checked. Source:
`eval/probe/results/2026-11-07-hosted-open-bench.md`.

**case01, real pipeline, simulated expert**

| Labeler | Accuracy (bar 80%) | False supported (bar 0) | Wall time | Cost | Hardware | Date |
|---|---|---|---|---|---|---|
| Opus 5.5 medium (prompt v1.1) | 85% (95% with the #69 fix, replayed offline) | 0 | 26 min (493 calls, 3.2 s each) | $7.83 | Anthropic API | 2026-10-15 |
| Opus 5.5 medium, cloud prompt v1.2 | 95% | 0 | 29 min (493 calls, 3.5 s each) | $8.16 | Anthropic API | 2026-10-20 |
| Sonnet 5.5 medium (prompt v1.0) | 80% | 0 | 16 min | $2.84 | Anthropic API | 2026-10-14 |
| Qwen3-14B Q4 | not measured end to end on current code | | see below | $0 | MacBook Air M4, 24 GB | |

Opus case01 detail: key evidence surfaced for 35% of claims that need it; 6 of 14 such claims
were ready for the expert. In the 2026-10-20 Opus v1.2 case01 run, 374 labels were dropped: 373
irrelevant answers and 1 quote failure. Of 71 gold key records, 44 surfaced, 18 were on claims a
failed core check settles (retrieval skipped by design), 8 were labelled irrelevant and 1 was
dropped at the quote check; retrieval missed none where it ran (`eval/loss_report.py` 1.0.0,
#148).

**Local 14B speed (unverified for today's code)**
- Measured 2026-10-09: 43.0 s per stance call (plain runtime), MacBook Air M4 24 GB.
- Measured 2026-10-12: `flash` runtime, 22.5 s vs 28.3 s per probe call, same output on all 88
  probe items (`core/llm/runtime.py`).
- The often-quoted 6 to 8 hours per case01 is a projection from those per-call numbers and an
  older call count (about 613 calls). Since then the pipeline skips claims already settled by a
  failed check, prompts changed (v1.1, names, members line), and the Opus run made 493 calls.
  A full local case01 run on current main has not been timed. Treat any local runtime as
  **unverified** until `eval/probe/time_case.py` is re-run on the Mac.
- Estimated 2026-10-29 (reported, case04 go/no-go Mac run at 67dabdb, MacBook Air M4 24 GB,
  flash): about 4.9 h of model time for a 48-claim synthetic case, 74% of it stance labelling
  (283 calls, mean 46 s); 59% of stance answers were irrelevant. From `python -m
  eval.run_profile`, which estimates call times from call timestamps (#182).
- Windows and NVIDIA speed: not measured.

**Local 14B repeat check (2026-10-24, reported, #136).** On a MacBook Air M4, macOS 15.6.1,
llama-cpp-python 0.3.36, Qwen3-14B Q4_K_M with stance v1.1: byte-identical stance answers on the
GPU when asked again, after a fresh load and across two case01 audits (105/105, 105/105, 85/85);
CPU only kept every stance and quote but reworded 7 of 20 rationales. Windows and NVIDIA not
measured. Source: `eval/probe/results/2026-10-24-qwen3-14b-repeat-mac.md`.

**Merge gate (model-free, `make eval`)**
The gate swaps the model for a stand-in that labels every retrieved record and a simulated
expert that accepts only signed key evidence. It tests retrieval, checks, assumption sheet,
rules and invariants, not model quality. Last recorded: case01 accuracy 1.00, 0 false
supported; unreviewed run 0.70 (report only; 0.55 before rules 0.5.0, 0.60 before #98); hostile red-team PASS; case02 (hidden, aggregate,
report only) 0.90 accuracy, 0 false supported. See section 10 for the latest run.
The eval has a rubber-stamp simulated expert (`--expert rubber-stamp`); on case01 model-free it
lets 6 of 20 claims through as false supported, with or without the challenge step; and a
fallible simulated expert (`--expert fallible --error-rate RATE`), wrong at a set rate, whose
rate is not set yet (#154).
Validation card (`python -m eval.validation.card`, `make validation-card`, #121): every rate with
a Wilson 95% interval. On case01 0 false supported of 12 non-supported claims allows up to 24%;
73 such claims with zero errors are needed for an upper bound of 5%, 189 for 2%. See
`docs/validation/README.md`.

**Real-export validation (public Hickman iOS 15.3.1 phone).** No accuracy figure exists yet.
- Plan (main): `eval/validation/PREREGISTERED.md`, signed by Arsh 2026-10-24, 106 claims with a
  signed answer key kept outside the repo (#124); scorer `eval/validation/score_hickman.py` (#134).
- Run 1 (reported in `eval/validation/PREREGISTERED_v2.md` on main): a **null result**. It ran
  on AWS (A10G) with the local 14B at commit `30fcf4d`; 0 of 106 claims were tested, because the
  assumption filler refused every proposal; 0 stance calls. Its zero error rates are vacuous and
  are never quoted as an error rate. #139 (merged 2026-10-26) fixed the phone-name, time-zone and
  SUBJECT-2 causes; run 1's 43 model-side refusals are not fixed; the date-first time wording,
  written time zones and export app names behind many of them are read by code since #150
  (unmeasured until a run under a new signed plan).
- Run 2 plan (main): `eval/validation/PREREGISTERED_v2.md` (#140, #141), approved by Arsh
  2026-10-26 23:03 UTC as the file records. Minimum **30** tested claims of 106: below it, run 2
  is reported as "insufficient coverage, no accuracy claim" and no customer material quotes a
  number from it. Verdict measures count only tested claims, as k of n with Wilson intervals.
- Scorer 1.2.0 (main, #142 and #143): reports k tested, each refusal kind and its count, and
  measures over tested claims; a claim counts as tested only when it has a first-pass verdict
  and is not marked "Not tested"; coverage must account for all 106 gold claims or the scorer
  stops. Rescoring run 1's results gives 0 of 106 tested (reported).
- Scorer 1.3.0 (#165): run 3's tiers (code-checked, check unsettled or expert only; minimum 30
  code-checked) and measure 7 (contradicted by a failed check, gold not contradicted), beside the
  1.2.0 measures.
- Run 2 ran at the tag `validation-v1-run2` (`d478705`, on GitHub): insufficient coverage, 9 of
  106 tested, so no accuracy claim (reported in `eval/validation/PREREGISTERED_v3.md`).
- Run 3 plan (`eval/validation/PREREGISTERED_v3.md`, #165, filled in #176): a coverage check on
  the same 106 claims, now development data, at tag `validation-v1-run3` on e5ce04b (on GitHub);
  the replay there predicts 34 code-checked of 106 against a minimum of 30; no accuracy claim
  from it. Approved by Arsh 2026-10-30, binding. No run 3 result is recorded on main; this
  refresh adds none.

## 8. Implemented features (main unless marked)

1. **Import:** Cellebrite Excel and PDF (Physical Analyzer per-category SMS export read on one
   real-format sample; rows the tool lists twice are flagged, not merged, and the count check is
   inconclusive on them, #129); Cellebrite UFDR (unverified on real samples; importer 0.3.0 counts
   Reader 7.48 RelatedModels copies and lists any that match no record, #117; 0.3.1 also matches
   copies held by calls, contacts and accounts, #130); Magnet AXIOM XML and Excel (unverified;
   forwarded and quoted marks on assumed field names, #116); government PDF with local OCR
   (Tesseract). Every evidence source shows a format notice on the case screen, each claim page
   that rests on it and in the report (`core/ingest/tested.py`, #145): UFDR stating
   reportVersion 7.48 gets "Imported without errors from three public test-phone packages (UFDR
   report version 7.48). Counts not yet compared with Cellebrite Reader. Not tested on your case
   data."; every other format or version gets "Not tested: ..." with its version as written. AXIOM
   also keeps its "not yet verified" item. `mabillon ufdr-check` (0.3.0) compares a
   UFDR import with its own report.xml, offline, including message, call, contact and account
   copies (#130). Gate 5a in `docs/PILOT_GATES.md` records what has been run on public packages.
2. **Audit:** claims, assumptions, checks, retrieval, stance, quote check, rules, invariants, with
   background runs, progress, per-claim commits and resume.
   - **Challenge step (on by default):** `mabillon audit --no-challenge`, or "Skip the challenge
     step" on the screen, turns it off for one run. Code's counter-searches on claims close to
     supported, storing only contradicts and complicates labels, each search logged and re-run by
     verify-bundle; its finds are marked "found by the challenge step" on screen and in the
     report; its effect with a real labeler is unmeasured (#154, #162).
   - **Testability step (eval and scripted demo only, off by default):** `eval/run_pipeline.py
     --testability CAP` asks the local model to retry a claim the assumption filler left
     untested; code checks each try with the filler's checks and against the signed sheet, or,
     with no signed sheet, against the claim's own words (every person, phone and account one the
     claim's text names). The claim page shows the try as "Proposed by agent" for the examiner to
     accept or reject; only an acceptance is used, from the next audit on. Each try is logged and
     re-run by verify-bundle, and the report marks it "Proposed by agent, accepted by examiner".
     A failed check on an assumption the agent proposed waits for the expert's confirm (rules
     0.4.0). Its prompt is signed (v1.2). The demo's D02 and D03 are its demo claims, with
     scripted answers (#159, #163, #166).
   - Its go/no-go before pilots (plans/agentic.md) is read by code from one eval run with the
     rubber-stamp expert and a repeat, against Arsh's values (a cap of 2 tries per claim, at least
     40% of at least 15 sheet-testable refusals converted, and at most 2 calls and 120 s per
     claim on the M4 Air) (#168). Two have been run with the local model on the M4 Air, both
     NO-GO, so the step stays off: case04 (2026-10-30; conversion 2 of 34, and 4 tries named
     another person, phone or window) and case05 (2026-11-03; conversion 5 of 33, 15%, every
     other bar passed) (#208). case04 and case05 are spent and give no go/no-go again; case06 is
     the signed held-out set for the next one (#211). The eval's case setup enters the
     affidavits' phone and number names, and `--no-stance` runs a dev check of the filler and the
     step without the stance model (#210).
3. **Expert review screen** (`ui/`, local only, no scripts): claims, evidence accept or dismiss,
   "Support found: do you agree?" before confirmation, verdict confirm or override, notes.
   Optional expert flags on the claim page (wrong label, missed record, verdict disagreement),
   stored as audit-log entries, never changing a verdict; a redacted summary download (on the
   Audit log page since #177) and `mabillon flag-log` for a per-pilot error log (`docs/flags.md`,
   #81). Nothing is sent. Stipulations are edited on Set up and run; the case page shows them and
   the flags summary read-only (#177).
   The claims queue (`/claims`, #108) opens with how many claims need the expert and one count
   per group (#206), then groups the claims (Needs you, Contradicted, Unproven, Supported, and Not
   audited when there are any), with each unproven claim's gap topics on one plain line (#206,
   #222; the claim page and the report print the full gap line for each kind of core assumption
   not covered, `ClaimState.explain_lines()`, `core/review/status.py`); the lines are read from the
   stored verdict and decide nothing. The report (0.10.0) prints the same gap lines. The claim
   page (#109) leads with a "What has to be true" checklist, one line per assumption, shows each
   evidence record among its neighbouring messages as a conversation, and folds the rules'
   assumption and check tables under "Show the rules' working". The sidebar's links (#110, moved
   from top tabs by #167) come in three groups (review; tools to look closer; set-up and record),
   with Cases on the case card and Help in the sidebar's foot (#206), and the case page leads with the claims that
   need the expert and a verdict count, with the source files' SHA-256 hashes folded under
   "Files and their SHA-256 hashes (chain of custody)". An Activity tab lists the examiner's page
   views, and the report has an Examiner activity section whose table is opt-in per case, off by
   default (#111).
4. **Analysis pages (code only, never change verdicts):** Identities (proposed account-to-person
   links, expert confirms), Timeline check and Gaps, Selection audit (what the document left
   out), Context Restore (find pasted exhibit quotes, draft the full-extraction request), Other
   explanations per claim.
5. **Case safety and delivery:** encryption at rest by passphrase (SQLCipher plus AES-256-GCM;
   new cases from the browser form encrypted by default, the box can be unticked; `mabillon init` on
   the CLI makes a plain case), hash-chained audit log, HTML report, `mabillon demo` (the scripted demo
   has a demo-only inconclusive absence claim, which a saved `--from-case` snapshot lacks, and
   `--paired` runs the paired selection audit, #96), `mabillon model-check`. The expert can record
   the document's names for each phone (TARGET PHONE, Item 1); the audit matches claims that use
   them, and every report lists them as the expert's statement (#139). The expert can also
   record the document's names for a number or account id ("the BURNER"), with `mabillon
   name-account`; the audit reads a claim's use of the name as that number, never as a person,
   and every report lists the names as the expert's statement. A name matches with or without a
   leading "the", and a name in capitals (a person's alias, a phone's, a number's or an event's)
   only where it is written in capitals (#209). The expert can also record the document's other
   names for a person (SUBJECT-1, HAL) on the Identities page; each is matched whole, an alias
   that could match two people is refused, and every report lists them as the expert's statement
   (schema 0.6.0, #181); the testability step's lookups and the assumption filler (#186) use them.
   The expert can also enter the events the document defines (the SEARCH) with their days and
   defining words, checked verbatim against the paragraph, on the Set up page; every report lists
   them as the expert's statement (schema 0.7.0, #201).
   Case backup: `mabillon backup` and "Back up this case" make a verified copy of a case folder
   (`core/casework/backup.py`, #230), logged as case.backup; claim moves are logged as
   claim.move (#230). From the first-run walkthrough (#223): re-run verdicts keeps an expert's
   confirmation or override when the verdict is unchanged (logged as verdict.carry); a wrong
   file can be removed before the first audit, logged with its SHA-256 and reason; a new
   recovery key can be made (screen and `mabillon recovery-key`); forms are bound to their case.
   Installers (#132): the Mac installer is "Install Mabillon.command", installing to
   ~/Mabillon/app and ~/Mabillon/models with Desktop launchers "Mabillon" and "Mabillon demo";
   the Windows installer is Mabillon-Setup-<version>.exe (signed by builds of main, Artifact
   Signing), installing to %LOCALAPPDATA%\Programs\Mabillon with the "Mabillon command prompt"
   Start-menu shortcut; an install made under the name Baker is updated in place and keeps its
   model and model setting.
6. **Reproducibility bundle (#104):** `mabillon export-bundle` (examiner's choice after counsel
   review, logged with its SHA-256, encrypted for an encrypted case; opt-in parts include
   "activity") and `mabillon verify-bundle` (offline; re-derives every verdict of the exported
   run from recorded labels and expert decisions; for a bundle from another report or bundle
   version it names the commit to verify with; `docs/bundle.md`); CLI only. Bundle format 1.2.0.
7. **Pilot support (#92):** a Help tab on every screen page with the support contact, a short
   what-Mabillon-does, and a bug report shown in full before it is saved (`/help/bug-report.json`,
   `mabillon bug-report`), built from an allowlist with no case names, paths, text or hashes
   (`core/support/`). Recent unexpected errors are kept in memory only, without messages; no log
   file. The support address is support@getmabillon.com (`core/support/contact.py`).

Merged 2026-10-15: stricter stated time windows, "after <date>" starts the next day (#66; rules
0.2.2 with PR #75, which also refuses a rules-only re-run of an older audit), go-bar scorer fixes and the signed probe
follow-up (#64), red-main test fix (#65), flaky encryption test fix (#67).
Merged 2026-10-15 to 2026-10-19: source-of-truth docs (#71), screen and report agree (#72), UFDR
reader checked on public files (#73), audit log checked on open (#74), rules 0.2.2 (#75), quote
check 1.2.0 (#76), writer from the claim fails closed (#77), curated report against a larger
source of the same phone (#78, synthetic data only, see section 9), small-model training data
(#79, #87), expert flags (#81), pilot documents (#82), count check wording (#83), one changelog
file per PR (#84), merge rulebook (#85), expert reason in the audit log (#86), changed upload
stores nothing (#88), forwarded messages on the record (#89), versions stamped on every result
(#91), forwarded-marks row in the report (#95), demo additions (#96); opt-in cloud Opus stance
labels (#68), gated off until #101; first status refresh (#97).
Merged 2026-10-20: expert confirms every model contradiction, rules 0.3.0 and report 0.8.0 (#98);
stance v1.2 for a cloud model only (#93); the Opus 5.5 entry in `PROBE_PASSED` (#101); status
refreshes (#99, #102); newer local model screen and thinking-template guard (#105); UFDR imports
embedded forwarded or quoted originals (#103); signed Windows installer (#106); copy recipients
are not thread participants (#107).
Merged 2026-10-21: UI redesign: claims overview with gap lines (#108), claim page checklist and
conversation view (#109), tab groups and case page (#110); Help tab and bug report (#92); public
website (#113); validation card (#121); Mac model-screen download retries (#114).
Merged 2026-10-22: progress write throttle and CI step timings (#122); Book a demo form (#118);
reproducibility bundle (#104); CLAUDE.md names Mabillon (#115); examiner activity trail (#111).
Merged 2026-10-24: stance v1.3 local re-probe, both wordings fail, reusable test (#120); the app,
report and docs say Mabillon (#127); UFDR Reader 7.48 RelatedModels copies (#117); local repeat
check tool (#126); Physical Analyzer SMS Excel times (#129); AXIOM forwarded marks (#116);
`mabillon` command and folders (#128); verdict trace in the report (#131); local model screen
entry (#123); status refresh after #110 (#112); installers say Mabillon (#132); cloud request
contents docs (#133); site format wording (#119); validation plan and AWS run script (#124);
validation scorer (#134); ufdr-check record copies (#130); pilot download links tool (#125).
Merged 2026-10-25 to 2026-10-27: local 14B repeat result in the report (#136); "record state"
wording (#137); withheld rationales (#138); device names and designations, phone time zones
(#139); validation run 2 plan (#140, #141); validation scorer coverage and 1.2.0 (#142, #143).
Merged 2026-10-27 to 2026-10-28: gate 5 split and status refresh (#144); "Not tested" notice
(#145); website (#146, #156, #157, #158); pilot link check (#147); key-evidence loss report
(#148); site look in the app and report (#149); filler reads affidavit times, accounts, call
lengths (#150, #152, #153); synthetic case03 (#151); challenge step behind a flag and the
rubber-stamp expert (#154); Native Messages note (#155); filler guards and code fills (#160,
#164).
Merged 2026-10-29 to 2026-10-31: testability agent, eval only (#159, #163); challenge step on by
default (#162); quote folding, run 3 plan and scorer 1.3.0 (#165, #176); rules 0.4.0 (#166);
quiet dashboard look (#167); testability go/no-go reader (#168, #183); more claims checkable
(#169, #172); synthetic case04 and case05 held-out sets (#170, #188); design skill (#171); site
landing (#173, #175); design-critique fixes (#174, #177, #178, #179, #180, #184); speed work
(#182, #185, #187); person aliases (#181, #186).
Merged 2026-11-01 to 2026-11-04: case05 signed (#189); filler exchange and durations (#190);
go/no-go provenance (#192); app look and declutter (#193 to #198); stance training data and
held-out told frames (#199, #202); case events (#201); page positions (#204); simpler app
(#206); structure cleanup (#207); case05 go/no-go result (#208); number names, filler 5 (#209);
eval case setup (#210); busy port (#212); plain "why" lines (#213); site walkthrough (#214);
per-launch screen key (#215); quoted words in the report (#217, #218).
Merged 2026-11-05 to 2026-11-08: Set up CSS (#200); demo-page fixes (#216); near-miss supports
(#220); site homepage and dark mode (#221, #229); app look (#222, #226); first-run fixes (#223);
repeat check on an AWS GPU (#224); hosted open-weight screen, eval only (#225); case03 signed
(#161); Greptile as the merge gate (#227, #232); rules 0.5.0 (#228); backups and dependency scan
(#230); Windows pilot checks (#231); Safari check (#234); Supported override needs accepted
support (#205); Mabillon window app (#219); refusal quotes cited (#235).
Closed without merging: #238 and #239 (the counsel review actor and counsel guidance; the
counsel-as-examiner direction was dropped 2026-11-07), and #191, #233, #237.
Open: #240 (per-claim guidance, draft), #241 (hosted agent bench, eval only, draft), #243
(sign-in, built and off by default), #244 (plan C model server pieces, draft), #203 (site,
draft), and Dependabot #236 and #242.
Branch only: small stance model (#50, parked). PRs #70, #80, #90 and #100 are empty Grok
Product review PRs, never merged.

## 9. Known limitations

1. **A label whose quote fails the check is lost, whatever its stance (issue #69).** The check
   runs before a label's stance is used, so a dropped "contradicts" or "complicates" could let a
   claim with other accepted support go SUPPORTED. The systematic cause is fixed by #76: contacts
   and calls now read the same for the labeler and the check (`core/audit/invariants.py:81`,
   through `core.enrich.records`), and a test checks every case01 record. A label still drops
   when its quote is not verbatim, has no letter or digit, or takes in only Mabillon's words or a
   placeholder such as "(no name)", and the report shows only a count.
   Replayed offline through the new check (2026-10-15, no model call): every supports,
   contradicts and complicates label of Opus's stored no-sheet case01 run passes (108); Sonnet
   and Haiku (2026-10-14) each lose 2, all on a message whose whole body is "?". The 14B's
   stored runs were not replayed. Opus replay: case01 85% to 95% (sheet), 60% to 70% (no sheet).
   The small model's generated call rows still print the report's time (guide rule 28), unlike
   the product; #50 is not merged, and aligning them is the "Custom model for Baker" thread's.
2. **Opus's wrong "contradicts" on told-frame and undated denials** (section 7). These are
   probe labels, not measured verdicts. With stance v1.1, under rules 0.2.x, such a label on a
   core assumption could have made a wrong CONTRADICTED; since rules 0.3.0 (#98) it cannot on
   its own, though an expert who accepts one still could. The cloud prompt, v1.2 (#93), removed
   every such answer in the Opus tests; with it Opus misses one real contradiction (P065), a
   label that, absent a failed check or other evidence, could leave a claim UNPROVEN.
3. **Real-data formats unverified.** UFDR and AXIOM readers were built from documentation and
   synthetic samples. No real case extraction has been imported. #73 checked the reader on two
   non-Cellebrite test files (27 of 27 records). `mabillon ufdr-check` found 0 differences on three
   public Cellebrite Reader 7.48 packages of Josh Hickman's test phones (#117 and #130, reported;
   pilot gate 5a), but the counts have not been compared with Cellebrite Reader's own, so the
   UFDR reader stays unverified. Cellebrite Excel was run on one real-format Physical Analyzer SMS
   export (#129, reported); no real AXIOM export has been imported. Forwarded messages, and messages carrying a forwarded or quoted original, fail
   closed (#73, merged 2026-10-16): they can neither support nor contradict a claim, checks resting on
   them are inconclusive, and the claim page and report warn. With the schema change Arsh signed
   on 2026-10-16 (PR #89, merged 2026-10-19) the record itself says
   forwarded, with the original author when the extraction names one; the sender field still
   shows the forwarder. The UFDR importer imports each embedded forwarded or quoted
   original (one level) as its own record at `<locator>/Embedded[n]`, marked forwarded with its
   own sender as written, so it fails closed too (#103). The AXIOM importer does the same for one level of quoted original (#116, merged 2026-10-24; field names unverified on a real export). Cases made before then keep only the
   coverage list (same fail-closed behaviour, no author); the report's Versions table says which
   mode a case is in ("Forwarded marks", #95). Native Messages records do not say whether a
   message is an iMessage or an SMS; the report and claim page say so on each claim resting on
   them (#155). Each source's format notice says whether its format and version were tested
   (#145, section 8 item 1).
4. **Local runtime per case unknown on current code** (section 7). **The local 14B's stance
   labels miss the signed bars:** on the signed set with v1.1, the prompt on main (Arsh's Mac,
   macOS 15.6.1 arm64, `eee8d15`, 2026-10-19), its contradicts precision is 58% (11 of 19, bar 90%) and
   it shows 6 moved traps as supports. Since rules 0.3.0 (#98) a model's "contradicts" never makes
   a claim CONTRADICTED without an expert's acceptance, so a wrong one cannot
   cause a wrong verdict on its own; it costs a review, and still risks one if the expert accepts it. Source:
   `/mnt/project-files/baker/cloud-bench/2026-10-16/fair-14b-vs-opus/local-arm/RESULTS.md`.
5. **Evidence recall is modest.** Opus case01 surfaced key evidence for 35% of claims needing it;
   14 of 20 claims depend on the expert finding or accepting key evidence. Where it ran, the
   fixed retrieval found every key record on case01; the loss is at the stance step (#148).
6. **Writer read from the claim's words (fixed in #77).** When the 14B leaves a sender assumption
   without a person, code reads the writer from the claim (`stated_sender`,
   `core/audit/assumption_filler.py`, from #53). Before #77 it named the wrong person when the
   quote was handed on after the verb ("PETROV texted REYES, who responded 'ok'" gave PETROV), so
   the sender check tested the wrong person (inferred, not measured). #77 fails closed on these
   phrasings: the claim stays without a writer and is refused (UNPROVEN). It is a phrasing guard
   with an allowlist, not a parser. The eval did not move (case01 has no such phrasing).
7. **Curated report against a larger source (on main since #78, merged 2026-10-18).** Lists what a UFDR of the
   same phone holds near each claim that a curated report does not. Tested only on synthetic
   pairs; not checked on any real export. Pairing rests on a shared phone-owner account and the
   same stated device model; no serial number or IMEI is compared. The
   fail-closed rules are strict: a few report records not found hold back most nearby records as
   "may be in the report", and under 95% found lists nothing (`docs/selection-audit.md`).
8. **Other gaps:** no translation in the pipeline; no embeddings; with
   cloud (#68) a key saved for a plain (unencrypted) case, or before a case is open, is an owner-only plain
   file (an encrypted case seals its own key under the case key); experts still need the 14B
   installed even with cloud on. Assumption filler limits: a call length with a half, two parts or
   a bound ("more than a minute and a half") is read by code as a range of seconds (#153); an
   account the claim writes by a number in another format, a person's name or one account's
   display name is found by code, and a number or display name several accounts carry is refused,
   never merged (#152); a time zone written beside a claim's time must match the phone's zone at
   that time, or the claim's range is refused; "between approximately X and Y", 24-hour times and
   zones other than US and UTC are left to the model (#150). A case encrypted after import keeps
   those input files' names (#230). The report's # column of a spreadsheet export is not stored;
   cards cite the spreadsheet row (#223).
9. **Count check said "deleted" (fixed in #83, merged 2026-10-15).** Before #83 the count
   check's detail read "N of them are flagged deleted" when counted messages carried the source's
   deletion flag, which breaks the rule that Mabillon never says "deleted". It now reads "N of them
   carry the source's deletion flag" (count check 1.0.1; 1.0.2 since #107; 1.0.3 since #129). Since 1.1.0 (#169) it also counts calls, and since 1.2.0 (#172) one side's messages ("X sent Y three messages") and "exchanged" messages (at least one each way, never failed on one side's silence).
10. **Cloud caveats (opted-in case).** Retention at Anthropic depends on the expert's own account
   and is not verified by Mabillon; the per-case attestation is self-certified (Mabillon records
   who, when and the exact words, but cannot check the order or consents); hosted labels cannot
   be regenerated, only the recorded labels and rules re-checked (#133).
11. **Code-checked Supported on curated reports (rules 0.5.0, #228).** The same-account check can
   still pass on a curated report that leaves out a second account with the same name, so a
   checked SUPPORTED resting on it could miss that account. "Exactly N" counts are kept with the
   expert for the same reason. Checked SUPPORTED holds 0 false supported only on synthetic data
   with signed assumption sheets; it is unmeasured on filler-made assumptions and on real exports.

## 10. Tests and results (main `9c4e8b3`)

Run 2026-11-08 in a Linux x86_64 cloud container (Python 3.12.3), on main's code (the working
copy differed from `9c4e8b3` only in this refresh's docs):

| Check | Result |
|---|---|
| Lint and format (`ruff`) | clean, 768 files |
| Tests (`pytest`) | 4020 passed, 9 skipped |
| case01 model-free gate | PASS: accuracy 1.00, 0 false supported |
| case01 unreviewed (report only) | accuracy 0.70, 0 false supported (code-checked supported since rules 0.5.0) |
| Hostile red team | PASS: none of the 7 structural claims went supported |
| case02 hidden case (aggregate, report only) | accuracy 0.90, 0 false supported |

CI (GitHub Actions `checks`, Ubuntu and Windows, local clock set to Pacific) runs the same
`make check` on every push. CI also runs pip-audit (`dependency-audit` workflow) and Dependabot
opens monthly update PRs (#230). Greptile reviews every PR, and its clean pass is the merge gate
(#227, `docs/MERGING.md`).

## 11. Pilot readiness

**Not pilot-ready for real case data yet.** The pass/fail gates are in
[`docs/PILOT_GATES.md`](PILOT_GATES.md): 14 of 19 met (gate 17 by #92, merged 2026-10-21; gate 1, CI green on 7 consecutive pushes to main through #110, 2026-10-21; gate 10, the signed Windows installer, by the signed main build of 2026-10-20; gate 19, no model-only Contradicted, by #98; gate 2 by #76, gate 3 by #91, gate 14 by the case02 key signed 2026-10-12, gate 6 by #72, gate 7 by #74,
gate 8 by merging #68, gate 12, the buyer documents, by #82; gate 13, the known integrity bugs, by #86 and #88; gate 15, stopped runs never look
complete, was already in place; 18 by the feedback form #82 publishes as
`docs/PILOT_FEEDBACK_FORM.md`). Gates 13 to 18 fold in Grok's
pilot-ready list. Ready: the demo case, the review screen, encryption,
the Mac and Windows installers, and a pilot kit (data handling, limitations, agreement outline,
feedback form, demo script, go/kill scorecard) in `/mnt/project-files/baker/pilot/`.

Documents for pilots and buyers (#82, merged): onboarding kit
(`docs/PILOT_ONBOARDING.md`), methods note an examiner can cite (`docs/METHODS.md`, no accuracy
figures), and security and privacy pack with a data-flow diagram (`docs/SECURITY_PRIVACY.md`).
Nobody outside the project has tried the onboarding kit yet (gate 11).

Gate 5 is split into 5a, UFDR from Cellebrite Reader 7.48, the first pilot's scope, and 5b, the
other formats, after the first pilot (#144). Neither is met.
The first pilot accepts only UFDR Reader 7.48, and every other format or version must show "not
tested" on screen and in the report; that notice exists on main (#145, section 8 item 1)
(`docs/PILOT_GATES.md`, "Pilot rule for gate 5").

Pilots also wait for plan C, the Mabillon-hosted model (section 5): decided by Arsh on
2026-11-07 and 2026-11-08 (project records), not built on main.

Before a first real case (the full list is the gates file):
1. Time a full local case01 on the Mac for a real runtime (#76 merged, so the 14B's
   contact and call quotes pass the check, section 9).
2. Gate 5a: compare the import's counts with Cellebrite Reader's own on the three public Reader
   7.48 packages (or Arsh waives it in writing), and build the "not tested" banner for every
   other format and version.
3. Opt-in cloud (#68) is available for a case whose protective order allows it: `PROBE_PASSED`
   lists Opus 5.5 at medium (#101, signed 2026-10-20). Conditions before a first real case uses
   it: the expert has checked their Anthropic account's retention (ZDR or not), the key is saved
   into the encrypted case with `$MABILLON_ANTHROPIC_API_KEY` and `~/.mabillon/cloud.json` unset,
   and counsel has confirmed the protective order and the client's consent behind the
   attestation. Where the tool's reliability may be challenged in court, run the case locally.

Measuring errors in a pilot: experts can flag wrong labels, missed records and verdicts they
disagree with; a redacted summary they choose to share feeds a per-pilot error log. Rates from it
are lower bounds, since flagging is optional. Unused so far.

No pilot has started and no expert has used Mabillon on a real case (per project records; this
cannot be checked from code).

## 12. Customer-facing claims

Rows 1, 2 and 8 re-checked 2026-11-08 on main `9c4e8b3` (rules 0.5.0). Otherwise checked 2026-10-15 against main `7a14437` (line numbers unchanged on `ae8f24e`; `core/audit/rules.py`, `core/audit/invariants.py` and `core/report/html.py` lines re-checked 2026-10-16 on #76 with main `79ad922` merged in, since #76 shifts the last two) and branch #68 (`3c6c1ec`), for the proposed line:
"Mabillon tests the government's specific claims; versioned rules decide verdicts; nothing is
supported until your expert accepts it; runs locally with no network calls."
Since #101 the last clause needs the opt-in qualifier for cloud cases; use row 6's safe wording.

| # | Claim | Status | Evidence | Safe wording |
|---|---|---|---|---|
| 1 | Verdicts come from versioned rules | **True** | `decide_verdict` is the only automated verdict path (`core/audit/rules.py:1`); an expert override is written directly by `override_verdict` (`core/review/actions.py:359`), as the expert's decision; an override to Supported needs expert-accepted support and cites it (#205), except that one the code checks had supported keeps the checked basis (#228); `RULE_VERSION = "0.5.0"` (`core/audit/rules.py:152`) is stored on every decision (`core/audit/rules.py:389`) and printed in the report (`core/report/html.py:1058`, `:1328`). Models only label evidence. | "Versioned rules decide verdicts; your expert can override" |
| 2 | Nothing is Supported until the expert accepts it | **No longer true** (rules 0.5.0, #228) | Code checks alone can support communication, timing and count claims (rule 3c', `_CODE_MAY_SUPPORT`, `core/audit/rules.py:169`), shown as "Supported by the records (code checks)", with no model label and no reviewer; counsel review would give "Supported (reviewed by counsel)", but nothing in the app writes one yet. A model label still never makes a claim SUPPORTED: AI acceptance covers nothing (`_AI_MAY_COVER` empty, `core/audit/rules.py:160`), and the invariants re-check every SUPPORTED on its basis and fail the run otherwise (`core/audit/invariants.py`). A model "contradicts" needs the expert's acceptance before a claim is CONTRADICTED (rules 0.3.0, #98). | Do not use. Replacement wording is Arsh's call (customer-facing) |
| 3 | "Not found" says what was searched | **True for absence and count findings** | The absence check states what it searched and why the sources can or cannot show an absence (`core/audit/checks/absence.py:1-6`, `:40`, `:112-135`); a curated report can never pass an absence (`core/audit/checks/absence.py:123`); the report has a "Searches and coverage" section (`core/report/html.py:489-519`). An UNPROVEN claim with no evidence names the uncovered assumptions, not a search log. | "When Mabillon finds no contact or counts records, it says what it searched and what the source could show" |
| 4 | The selection audit shows what was left out around each quote | **Partly true** | Shows each quoted, exhibit or examiner-tagged message in its exchange, with the messages not picked (`core/selection/audit.py:1-29`). Limits: a quote is placed only when its words fit one message, otherwise it is listed as found N times and nothing around it is counted as left out (`core/selection/picks.py:17-23`); names and quotes under two words are not looked up (`core/selection/picks.py:5-11`); messages an examiner left out of a curated report are not in the case to show (`core/selection/audit.py:27-29`), unless the case also holds a larger source of the same phone: then the paired selection audit (#78, `core/selection/paired.py`, `docs/selection-audit.md`; tested on synthetic pairs only) lists that source's records the report does not hold near each claim, failing closed when matching is uncertain (section 9). | "...around each quote it can place in the extraction" |
| 5 | Every report has an audit packet: source hashes, model, prompt and rule versions, tamper-evident log | **True, with one nuance** | Page views (time, examiner, page, items) are in the same hash-chained log; time on page is not proof of reading (#111). A reproducibility bundle carries what the verdicts rest on (the whole case on request), and `mabillon verify-bundle` re-derives the verdicts offline (#104). Sources with SHA-256 (`core/report/html.py:678-688`), versions and model runs with model SHA-256, prompt version, parameters and seed (`core/report/html.py:690-691`, `:557-593`, `:723-737`), Mabillon build (release and git commit), pipeline, rule and quote-check versions in the report's top line and its Run section (`core/report/html.py:612-623`, `:709-713`; PR #91 for the build, the top line and the seed in the versions table), audit-log summary with hash-chain result, last hash and expert actions (`core/report/html.py:738-764`, `core/review/audit_log.py:47-225`). Nuance: the report shows a summary and the expert entries, not every log entry. The chain detects edits to entries; anchors (`case.db.anchors.jsonl`, the newest entry's number and hash, written when a case opens and when a report is built) detect entries cut from the end back to the newest anchor. Evidence decisions log the expert's typed reason, and a stored reason or status that no longer matches its log entry, or an expert review added or removed without one, blocks the case (PR #86, merged; decisions logged before it carry no reason and are not compared). Neither catches a change to the database and the anchor file together, or entries added and cut between two anchors; there is no signature or external anchor beyond a saved report's last hash. The log is checked when a case opens, on every page while it is open (report and download included), and before encrypting or changing the passphrase; a failed check blocks review and reporting in the screen and the CLI (fail closed; `core/review/audit_log.py` `require_intact`, `ui/app.py` `open_case` and `/report`, `cli/main.py` `_open`; #74). | "A hash-chained audit log; the report prints its last hash" |
| 6 | Runs locally with no network calls | **True for every case not opted in to cloud** | main: true for every case not opted in; `PROBE_PASSED` lists Opus 5.5 at medium (#101). `core/` makes no network calls, the screen binds only 127.0.0.1 (`ui/server.py:19`); the installers download the pinned model once at install. #68 (merged 2026-10-15) adds the opt-in Opus stance integration, one HTTPS request per stance pair (up to three with retries) to api.anthropic.com (`core/llm/cloud.py`), used only for a case the expert opts in. Cloud stays off until the expert attests per case, so "local by default" stays true. "No network calls" would not be true for opted-in cases. | "Local by default; cloud AI only when your case allows it and you opt in" (Arsh's choice, 2026-10-15 07:10Z) |
| 7 | UFDR tested on real-format exports | **Not yet claimable** (true after #117 and gate 5a sign-off; 5a is not met) | #117, #130, Baker Eval re-run (reported) | "Tested on real-format Cellebrite UFDR exports from public test phones (Reader 7.48); other versions not yet tested" |
| 8 | The rule that sets each status is published | **True** | The verdict rules are one file in the public repository (`core/audit/rules.py`, `RULE_VERSION = "0.5.0"`); each decided claim in the report traces its verdict per core assumption to what the rules relied on (#131), and `mabillon verify-bundle` re-derives verdicts offline (#104). Used for the positioning line against Longeye (project records, 2026-11-07). | "Longeye shows its sources; we also show the rule" |

The public website (`site/`, getmabillon.com) uses only the safe wording above and the one-pager;
update it when these claims change. The site's Book a demo form (`workers/demo-form`) emails
requests to the team and stores nothing.

Claims Mabillon should not make yet: "nothing is supported until your expert accepts it" (row 2,
since rules 0.5.0); "files never leave your machine" or any hosted-model wording, because plan C
is not built (section 5) and its customer wording still needs Arsh's sign-off; "validated",
"accurate" or "court-ready"; any speed figure for local runs (not measured on current code,
section 7), any accuracy figure on real data (all numbers are synthetic; validation run 1 was a
null result and run 2 has not run), any error rate from synthetic case01 (0 of 12 false supported
bounds the rate only to 0-24%), that UFDR imports are verified beyond Cellebrite Reader 7.48
exports of public test phones, or that Cellebrite Excel or AXIOM imports are tested on real
exports. Local labels may be described as regenerating exactly only for the 14B with stance
prompt v1.1 on the tested Mac setup; not across machines, and never for a cloud model.
