# Validation v4: held-out Android 13 accuracy test on hosted Opus (pre-registration)

Status: **Plan signed by Arsh on 2026-11-10 at 19:13 UTC ("Approved as written" on the signing card), with the proposed numbers: $60 cap per pass, bar 4 at most 5%, bar 6 at least 95%, reader 3 a GPT model through OpenRouter.** Freeze record not yet filled in or approved. Paid steps still need his spend OK. Written 2026-11-10 in the "Real-world accuracy
validation" thread from the project's v4 plan, its claim-writing guide draft and
`PREREGISTERED_v3.md`. Nothing in it changes after any
developer or the run machine sees a v4 claim or answer.

Signing has two steps:
1. **Plan signature (done, 2026-11-10 19:13 UTC):** Arsh approves this text, including every number marked "Arsh sets".
   Claim writing starts only after this.
2. **Freeze addendum (before the run):** the hashes in "Freeze record" are filled in and Arsh
   approves them. The run starts only after this.

## 1. What this test is, and what it may let us say
- One scored run of Mabillon on a phone extraction it has never seen, on the pilot setup:
  hosted Opus 5.5 for the model jobs, rules 0.5.0, given claims, no assumption sheet.
- It is the first number Mabillon may quote. If every pass/fail bar below passes, the wording
  we may use is of this shape, with the real figures: "On a public Android 13 extraction it had
  never seen, 0 of N claims that were not true came out Supported (95% upper bound X%), across
  150 claims written and labeled blind." Every disclosure in section 10 travels with it.
- It never lets us say "validated", "court-ready", "accurate" without a figure, or anything about
  real case data. One public test phone is one phone.
- iOS 15 and Android 12 are development data. Their numbers are never quoted.

## 2. Data
| Item | Value |
| --- | --- |
| Phone | Google Pixel 5a, Android 13, public Hickman image (Digital Corpora) |
| Package | `baker/ufdr-public/packages/a13.ufdr`, SHA-256 `4e35731ce028cc184bfdb179023f7fe6e033c2157f897f9533fc36f0adb6a675` |
| report.xml inside it | SHA-256 `86588608113eaa6676e2206639d6a6b0ef1fde1b35c148b5ae649363e07ac5a2` (the run driver's `--report-sha256`) |
| Creator's log | `android_13_imagecreation_solution.pdf` is password-protected, so it is not used |
| Truth | the extraction's own records, read by a plain XML reader (`dump_ufdr.py`, ElementTree, imports nothing from Mabillon) |

What developers have seen of this phone: Mabillon's importer was fixed with all three public
packages in view (#117), and record counts were looked at. No developer has read its messages,
calls or contacts, and none will before scoring.

## 3. Roles and isolation
| Role | Who | Sees | Never sees |
| --- | --- | --- | --- |
| Claim writer | a fresh session with no repo and no project memory | the A13 dump, this plan's sections 4 and 5, the writing rules | Mabillon's code, templates, checks, fill rules, any run or replay |
| Readers 1 and 2 | fresh sessions, same rules | claims, dump, the reader instructions | the writer's labels, each other, anything Mabillon made |
| Reader 3 | a model from another family (Arsh sets: which model and host) | the same | the same |
| Adjudicator | Arsh | the three readers' labels and reasons, the cited records | Mabillon output |
| Blind sample | Arsh or Yazen labels a random 30 claims blind (seeded draw, seed in the freeze record) | claims, dump | every other label |
| Run machine | the cloud workspace | the claims file and the definitions file only | any label or key |
| This thread and every developer | | the claims only after the run finishes; the key only through the scorer | the claims or key before the run |

## 4. Claims
**Count and mix, fixed now.** 150 claims. Every result is reported per kind, so a strong kind
cannot hide a weak one.

| Kind | Claims | `claim_type` |
| --- | --- | --- |
| Quoted message (who sent which words, on which app, when) | 30 | communication |
| Contact without a quote (a call or messages between two parties at a time) | 20 | communication |
| Timing | 15 | timing |
| Count | 15 | count |
| Absence | 15 | absence |
| Identity | 20 | identity |
| Meaning | 15 | content_meaning |
| Event or role | 20 | event or role |

**Verdict mix.** About 50 supported, 50 contradicted, 50 unproven by the writer's intent. At
least **100 claims must be not supported** in the signed key. If the signed key has fewer, the
writer adds not-supported claims of the short kinds before the freeze.

**Writing rules** (guide section 4, unchanged): the government's voice, one claim per line, real
affiant variety (number formats, display names, local times with or without a zone,
"approximately", group chats, paraphrase as well as quotes), planted traps (a UTC time shown as
local, the other party named only by number, a contact saved under a misleading name), and never
"guilty", "innocent", "leader" or "deleted" as a conclusion.

**Files the writer hands over.**
- `claims.jsonl`: one row per claim, `{"claim_id", "page", "para_no", "text", "claim_type"}`,
  paragraphs 1 to 150 in order, no labels.
- `definitions.json`: the affidavit's header. The phone is the TARGET PHONE and SUBJECT-1 used
  it; any other SUBJECT-n the header defines by a telephone number, as `{"SUBJECT-2": "<number>"}`;
  and the phone's time zone if the affidavit states one (the driver's `--phone-zone`).
  This is the premise of the affidavit, not a claim, as R4 was for iOS 15.
- `writer-private/`: the writer's intended label and the records each claim rests on. Only the
  adjudicator opens it, and only for disputed claims.

## 5. Answer key
- Each reader labels every claim: verdict (supported, contradicted, unproven), core assumptions,
  key records (dump `source_index`) and a one-line reason, using the iOS 15 reader definitions:
  supported means the extraction shows every part of the claim as worded; contradicted means a
  record shows a part is false; unproven is everything else, including inference beyond the
  records, and an absence the extraction cannot establish.
- Absence claims: the key is set by a script from a structured form (parties, apps, window), so
  no reader judgement decides them.
- Code checks every cited `source_index` exists in the dump.
- Unanimous claims take the shared label. The rest go to Arsh with all three reasons.
- Reported before adjudication: Fleiss' kappa across the three readers, and agreement of the
  blind 30-claim sample with the signed key.
- The key is written as `gold.jsonl` in the `GoldClaim` format (`core/contracts.py`), key records
  as `ufdr:source_index:N`, `labeled_by` Arsh. Arsh signs it before the freeze.

## 6. Code, frozen at a tag
The tag `validation-v4` goes on a main commit after these merge:
- #255 (filler fixes, FILLER_VERSION 7) and the safety PR that follows it (sender 1.2.0,
  time 1.1.0, FILLER_VERSION 8, the 19 re-signed synthetic rows approved 2026-11-10).
- #254 (every model job on Opus), so the filler runs on the product's cloud path, not the
  driver's stand-in.
- The v4 driver and scorer changes, written and merged before any v4 claim is opened:
  - Run driver: `--source-id` and `--definitions` (today the source id and SUBJECT-2's number
    are fixed to iOS 15 in `hickman_run.py`).
  - Scorer 1.4.0: an R1 card (false Supported, by basis), the repeat comparison for bar 6, and
    every bar computed per kind and overall. No change to measures 1 to 7 as defined.
- This file.

The full change table since run 3's tag (`validation-v1-run3`, e5ce04b) is filled in at the tag,
as in v3, and added to the freeze addendum. Nothing merged after the tag reaches the run.

## 7. Run
- Model `claude-opus-5-5` (pinned id), effort medium, the signed cloud prompts, rules 0.5.0.
- Setup as an examiner would: the driver imports the package, renders the affidavit, adds the
  claims and the header's definitions, and runs `mabillon audit` with its defaults.
- Off, as in the iOS 15 Opus rerun: the AI reviewer, the challenge step and the testability
  agent. None of them can make a claim Supported under rules 0.5.0. `run.json` records each.
- **Pass 1** is the scored run. **Pass 2** runs again from scratch at the same tag, in a new
  folder with no stored answers, for bar 6, and is scored for bars 1 to 3 as well.
- Key: BAKER_BENCH_API_KEY from the cloud workspace. Public data only, so no ZDR agreement is
  needed for this run; no real case data ever runs on this key.
- **Spend cap: Arsh sets.** Estimate $75 to $110 for both passes (iOS 15 Opus rate scaled to 150
  claims). Proposed `--max-usd 60` per pass. A pass that hits its cap or a sticky API failure
  pauses and resumes in the same folder; finished claims reuse their stored answers. A resume is
  not a new pass.
- One scored run. If a pass crashes in a way that leaves no usable case, it restarts from
  scratch at the same tag and the crash is reported. No code change after the claims are opened
  counts toward the number.

## 8. Before scoring: assumption fidelity audit
As v3: an agent that never opens the key reads every tested claim's assumptions against the
claim text. Each must name the claim's own person, phone, window and app, and quote only the
claim's quoted words. Bar: **0** wrong person, phone, window or app, and 0 non-quote words used
as a quote. Arsh spot-checks 5 it passed. Any failure is reported with its claim.

## 9. Bars
The scorer (1.4.0 at the tag) computes each from pass 1, and bars 1 to 3 also from pass 2.

| # | Bar | Pass if | Kind |
| --- | --- | --- | --- |
| 1 | False Supported, the run as it stands (R1, code checks only) | 0, over all not-supported claims (at least 100; Wilson 95% upper bound 3.7% at 100), in both passes | pass/fail |
| 2 | False Supported after the simulated expert (R2) | 0 | pass/fail |
| 3 | False Contradicted (gold not contradicted), R1 and R2, including measure 7 | 0 | pass/fail |
| 4 | A false claim shown with support only (supports items, no contradicts item, no failed check), over gold-contradicted claims | at most 5% (Arsh sets) | pass/fail |
| 5 | Coverage: tested k of 150, tiers (code-checked, check unsettled, expert only), every refusal kind | at least 30 code-checked claims, or the result is "insufficient coverage" and no number is quoted | floor |
| 6 | Repeat, pass 2 against pass 1 | no claim Supported in one pass and Contradicted in the other; at least 95% same verdict (Arsh sets); every difference listed with its cause | pass/fail |
| 7 | `mabillon verify-bundle` on pass 1's bundle; re-deciding from stored labels gives the same verdicts | passes, 0 differences | pass/fail |
| 8 | `mabillon ufdr-check` on the package; import counts against the dump | 0 differences | pass/fail |
| 9 | Time and API cost per pass | recorded | reported |

Also reported, never a bar: accuracy over tested claims with its interval, missed Supported,
key-evidence recall, false Supported over tested not-supported claims only (a claim that was
never tested cannot be falsely Supported, so this smaller denominator is shown beside bar 1),
and every figure per kind.

**If any pass/fail bar fails,** no accuracy number is quoted. The result and its cause are
written up in project files, the fix is development work, and a new held-out set is needed
before another number can be quoted. Android 13 is then development data too.

## 10. Disclosures that travel with every v4 number
- One public test phone, made by a researcher. Its chats are casual test conversations, not the
  multi-party threads real affidavits describe; meaning and event results say less than the rest.
- Truth is the extraction's records, not a creator's log (the A13 log is locked). A record the
  extraction lost cannot be caught.
- The writer and two readers are Claude models, the same family as the labeler; one reader is
  from another family, and Arsh or Yazen labels 30 blind. Kappa and the sample's agreement are
  reported.
- The simulated expert in bar 2 is code standing in for an examiner, not a person.
- Mabillon's importer was fixed with this package in view (#117); its records were not read.
- The fixes since run 3 were designed on iOS 15 and Android 12 development data.
- Opus labels are about 99% stable from run to run, not deterministic; bar 6 measures it here.
  Verdicts are deterministic from stored labels (bar 7).
- One extraction tool and version (Cellebrite Reader 7.48 UFDR).

## 11. Freeze record (filled in before the run, then approved by Arsh)
| Item | Value |
| --- | --- |
| Tag `validation-v4`, commit | |
| `claims.jsonl` SHA-256 | |
| `definitions.json` SHA-256 | |
| `gold.jsonl` SHA-256 (signed key) | |
| Fleiss' kappa before adjudication | |
| Blind 30-claim sample: seed, agreement | |
| Not-supported claims in the key | |
| Spend cap per pass | |
| Reader 3 model and host | |

## 12. Steps, owners and cost
| Step | Owner | API cost |
| --- | --- | --- |
| Arsh signs this plan (section numbers marked "Arsh sets") | Arsh | none |
| Driver and scorer changes; #255, safety PR and #254 merge; tag | this thread, Arsh merges | none |
| Writer session makes the dump, claims and definitions | isolated session | none |
| Readers 1 and 2 label | isolated sessions | none |
| Reader 3 labels (other family) | isolated session | a few dollars, needs Arsh's OK |
| Adjudication and blind 30 | Arsh (about 1 to 2 hours) | none |
| Freeze addendum approved | Arsh | none |
| Pass 1 and pass 2 | this thread | $75 to $110 est., needs Arsh's OK |
| Fidelity audit, scoring, write-up (project files only) | this thread | none |
