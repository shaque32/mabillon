# Validation v5: held-out two-phone LEAPP accuracy test on hosted Opus (pre-registration)

Status: **plan signed by Arsh, 2026-11-21 04:20Z ("ok i okay this plan", project chat), with every
proposed number as written. Freeze addendum (section 11) not yet approved. Nothing in it has
spent anything. Spend OKs so far: the coverage probe C4 only (cap $5, 2026-11-21 04:18Z).**
Written in the "Real-world accuracy validation" thread from v4's signed plan
(`../v4/PREREGISTERED_v4_SIGNED_PLAN.md`), its results (`../v4/a13/runs/RESULTS.md`), the v5
readiness list (`V5_READINESS.md`) and the failure hunt (`FAILURE_HUNT_FINDINGS.md`). Once signed it
goes into the repo as `eval/validation/PREREGISTERED_v5.md`. Nothing in it changes after any
developer or the run machine sees a v5 claim or answer.

Every number marked **Arsh sets** carries a proposed value; signing as written accepts it.

Signing has two steps, as in v4:
1. **Plan signature (now):** Arsh approves this text. Packaging and claim writing start only after it.
2. **Freeze addendum (before the run):** the hashes in section 11 are filled in and Arsh approves
   them. The run starts only after that, and only with his spend OK (section 12).

**Clarifications after signing (2026-11-21, from code review; no number or bar changed):**
the probe's cap sits outside the $112 ceiling (section 7); a C4 top-up replaces claims so the
set stays at 150 and keeps at least 100 not supported (section 7a); a restart's spend counts
against its pass's cap (section 7); the claims and key are frozen before C4, the blind 30 is
drawn from the final set after C4, and the freeze addendum is approved after C4 with its final
hashes and counts (section 12); a paused probe keeps its case for the resume, unopened, and C4's
per-phone count is by the phone a deciding check's records are on (section 7a).

## 1. What this test is, and what it may let us say
- One scored run of Mabillon on a two-phone case it has never imported, on the pilot setup:
  hosted Opus for every model job, rules 0.5.0, given claims, no assumption sheet, phones read
  from LEAPP output through Mabillon's LEAPP importer.
- It is the next number Mabillon may quote (v4 failed bars 4 and 8 and fidelity, so v4 gave none).
  If every pass/fail bar passes, the wording is of this shape, with the real figures: "On a public
  two-phone case (iOS 17 and Android 14) it had never seen, 0 of N claims that were not true came
  out Supported (95% upper bound X%), across 150 claims written and labeled blind." Every
  disclosure in section 10 travels with it.
- It never lets us say "validated", "court-ready", "accurate" without a figure, or anything about
  real case data. Two public test phones are two phones.
- Android 13, iOS 15 and Android 12 are development data. Their numbers are never quoted.

## 2. Data
| Item | Value |
| --- | --- |
| Phones | Hickman case, Digital Corpora: iPhone 11 on iOS 17.3 and Pixel 7a on Android 14, one case |
| Never used beside them | the iOS 16.1.2 image (an earlier state of the same iPhone) |
| Packages | ALEAPP ed1b63d on the Android 14 image and iLEAPP fb05694 on the iOS 17.3 image (the versions #264 pins), LAVA output zipped, made in a separate session that no developer reads; SHA-256 of each zip in the freeze record |
| Truth | each phone's LEAPP output, read by a plain reader (`dump_lava.py`: sqlite3 and the manifest, imports nothing from Mabillon) |
| Creator logs | given to the readers as context only. The key is set from the extraction; where a log describes an action the extraction does not show, the claim is unproven, and every such case is listed in the write-up, not scored |

What developers have seen of this pair: this thread saw both creator logs' app lists, a
message-overlap count and about ten message lines while choosing the pair (2026-11-14). No
developer has seen either phone's LEAPP output, and none will before scoring.

## 3. Roles and isolation
As v4, with two phones:

| Role | Who | Sees | Never sees |
| --- | --- | --- | --- |
| Packager | a fresh session | the two images, the pinned ALEAPP and iLEAPP | anything after the zips are hashed |
| Claim writer | a fresh session with no repo and no project memory | both phones' `dump_lava` output and LAVA databases, the creator logs, sections 4 and 5, the writing rules | Mabillon's code, templates, checks, fill rules, any run or replay |
| Readers 1 and 2 | fresh sessions, same rules | claims, both dumps, the logs, the reader instructions | the writer's labels, each other, anything Mabillon made |
| Reader 3 | a model from another family. **Arsh sets:** proposed a GPT model through OpenRouter, as in v4 | the same | the same |
| Adjudicator | Arsh | the three readers' labels and reasons, the cited records | Mabillon output |
| Blind sample | Mir or Yazen labels a random 30 claims blind (seeded draw, seed in the freeze record) | claims, dumps | every other label |
| Run machine | the cloud workspace | the claims file, the definitions file and the two zips | any label or key |
| This thread and every developer | | the claims only after the run finishes; the key only through the scorer | the claims, the key or the LEAPP output before the run |

## 4. Claims
**Count, Arsh sets: proposed 150** (the benchmark plan said 120). 150 keeps at least 100
not-supported claims for bar 1 and leaves room for 30 code-checked claims for bar 5.

| Kind | Claims | `claim_type` |
| --- | --- | --- |
| Quoted message (who sent which words, on which app, when) | 25 | communication |
| Contact without a quote (a call or messages between two parties at a time) | 20 | communication |
| Across both phones (one phone's message or call and the other phone's record of it) | 15 | communication |
| Timing | 15 | timing |
| Count | 15 | count |
| Absence (texts and calls only; see below) | 15 | absence |
| Identity | 15 | identity |
| Meaning | 15 | content_meaning |
| Event or role | 15 | event or role |

**Verdict mix.** About a third each supported, contradicted and unproven by the writer's intent;
at least **100 not supported** in the signed key, as in v4. If the key has fewer, the writer adds
not-supported claims of the short kinds before the freeze.

**Writing rules:** v4's (the government's voice, one claim per line, real affiant variety, the
planted traps, never "guilty", "innocent", "leader" or "deleted" as a conclusion), plus:
- Each phone is named in capitals, as v4 named the TARGET PHONE (for example "TARGET PHONE" and
  "SECOND PHONE"), and each claim says which phone or both.
- Absence claims are about native texts and the call log only. LEAPP reads chat apps partially
  (Android chat apps by design; iOS chat apps never in full because of CallKit), so a chat-app
  absence claim can only be unproven and would waste a slot.
- Time wording as an affiant writes it, including claims that time one act from another
  ("within a minute of receiving it"): filler 10 to 12 leave those untested by design, and the
  write-up counts them.

**Files the writer hands over.**
- `claims.jsonl`: `{"claim_id", "page", "para_no", "text", "claim_type"}`, paragraphs 1 to 150 in
  order, no labels.
- `definitions.json`: the affidavit's header, in the driver's two-phone form: `phones` names each
  source id's phone, its user (SUBJECT-1, SUBJECT-2) and, where the affidavit states one, its
  zone; any other SUBJECT-n is defined by a telephone number. The driver stops before any model
  call when a stated zone differs from one the extraction records.
- `writer-private/`: intended labels and records, opened only by the adjudicator for disputes.

## 5. Answer key
As v4, with these changes:
- Key records are written as `lava:<phone>:<table>:<rowid>`, the phone's source id, the LAVA
  table name and its rowid, read from the LAVA database with no Mabillon code. Rows of
  `get_sms_mms_combined` are never cited (it repeats `get_sms_mms` and `get_sms_mms_mms`), and
  only tables in `eval/validation/lava_kinds.json` are cited.
- Code checks every cited row exists before the freeze; the scorer (1.6.0) lists any key row
  that maps to no record or several, with why, and never matches it to a near miss.
- Absence claims: the key is set by a script from a structured form (parties, phone, app,
  window), as in v4.
- Fleiss' kappa across the three readers, computed before adjudication, and the blind 30's
  agreement with the signed key, measured once the sample (drawn after C4) is labeled. Both
  are reported before pass 1.
- `gold.jsonl` in the `GoldClaim` format, `labeled_by` Arsh, signed before the freeze.

## 6. Code, frozen at a tag
The tag `validation-v5` goes on the main commit after #271 (merged 2026-11-21) and #272 merge. Since v4's tag it carries:

| Change | PR |
| --- | --- |
| Filler 10: no range from a time given for another act; caller row beside a handle side | #261 |
| Scorer 1.4.1: chat count by source chats | #262 |
| Filler 11 (the Instagram "user ID N" call wording), `dump_lava.py`, scorer 1.5.0 (bar 4's new measure) | #263 |
| LEAPP importer and its follow-up (app calls, Telegram, iOS Snapchat, fail closed) | #264, #268 |
| Filler 12 and count 1.3.1 (the failure hunt's five classes) | #265 |
| Two-phone run driver (an owner and a zone per phone) | #267 |
| Call-log guard: the build stops before any model call when a call log has rows but no call has a side, or every row was placed by another app; scorer 1.5.1 | #269 |
| Scorer 1.6.0: LEAPP keys and bar 8 by table | #271 |
| Coverage probe driver mode (`--coverage-probe`, gate C4) | #272 |
| This file | |

Versions at the tag: rules 0.5.0, FILLER_VERSION 12, scorer 1.6.0, sender check 1.2.0 (decision B).
The full change table is filled in at the tag and added to the freeze addendum. Nothing merged
after the tag reaches the run.

## 7. Run
- Model `claude-opus-5-5` (pinned id), effort medium, the signed cloud prompts, rules 0.5.0.
- The driver imports both zips (checked against their hashes), renders the affidavit, adds the
  claims and the header, and runs `mabillon audit` with its defaults. AI reviewer, challenge step
  and testability agent off, as in v4; `run.json` records each.
- The passes run only after the coverage gate (section 7a) passes and Arsh gives the spend OK.
- **Pass 1** is the scored run. **Pass 2** runs from scratch at the same tag in a new folder, for
  bar 6, and is scored for bars 1 to 3 as well.
- Key: BAKER_BENCH_API_KEY. Public data only; no real case data ever runs on this key.
- **Spend, Arsh sets.** Estimate $65 to $105 for both passes (v4's $0.26 per claim per pass, up to
  30% more for two phones' context: a guess, not measured), plus about $2 for reader 3. Proposed
  `--max-usd 55` per pass, ceiling $112 for the passes and reader 3 (the C4 probe's own $5 cap
  per attempt is outside it and OK'd separately, so the most v5 can spend is $117, or $122
  with a second probe), inside the free Ultra credit, with the balance
  checked in the console just before the OK. A pass that hits its cap or a sticky API failure
  pauses and resumes in the same folder with stored answers reused; a resume is not a new pass,
  and a pass that hits its cap is not resumed without a new OK. The driver checks a cap before
  each request and counts the request's cost after it, so a run can end above its cap by one
  call: at most about $0.40 on Opus (16,000 output tokens at $20 per million, plus the prompt;
  a bound from the price table, not measured). The C4 probe runs at `--max-usd 4.60` for that
  reason; the passes' OK covers $55 plus that one call each.
- One scored run. A crash that leaves no usable case restarts from scratch at the same tag and is
  reported. What the abandoned attempt spent counts against its pass's $55 cap (the restart runs
  with `--max-usd` set to what is left of it), so a restart never raises the ceiling; a restart
  that needs more needs a new OK.

## 7a. Coverage gate: no pass is paid for until coverage is shown
Bar 5 needs at least 30 code-checked claims (a deterministic check on a core assumption passed or
failed); below that no number is quoted and the passes' money buys nothing. So coverage is
measured before the passes, in four steps. Steps C1 to C3 are free; C4 costs a few dollars and is
the only paid step before the passes.

| # | Step | Cost | Pass if |
| --- | --- | --- | --- |
| C1 | Baseline on current code: v4's 150 claims, stored answers replayed on merged main | free, done | at least 30 code-checked |
| C2 | Data gate on the held-out packages: the driver builds both phones with no model calls, and prints only aggregate counts (readable calls with a side, native texts with a party, per phone; each phone's recorded zone) | free | both phones build; the call-log gate (#269) passes; each phone has one known zone and the two agree (otherwise every windowed claim is refused); at least 20 readable calls and 100 native texts across the pair (Arsh sets) |
| C3 | Claim-mix gate, by script, on the writer's private form before the freeze (no Mabillon output) | free | at least 90 claims of the kinds code can check (communication, timing, count) about native texts, iMessage or the call log; each phone named in capitals; no chat-app absence claims; iOS native-message counts are not counted toward the 90 (they fail closed) |
| C4 | Coverage probe on the frozen claims: the run's own filler and checks on all 150 claims, with no stance labeling, capped; it prints only tier counts per kind and per phone, never a claim, a verdict or a check result, and its case is deleted once counted (a paused probe keeps it for its resume, and nobody opens it) | about $2 to $4 (filler is 150 of v4's 2,203 calls and about 4% of its prompt text: an estimate, not measured), `--max-usd 4.60` so the spend stays under the $5 Arsh OK'd (section 7: a cap can be passed by one call), needs Arsh's OK | at least **40** code-checked of 150 and at least 10 on each phone (Arsh sets) |

C1's result: v4 pass 1 had 42 code-checked and pass 2 had 40. The replays of v4's stored answers
since (on #265, then on merged main 975e37e) changed no check outcome, and the tier depends only
on check outcomes, so 42 stands on current code. This is inferred from the replays, not
recounted, and it is a different claim set from v5's.

**Correction after signing (2026-11-21 04:25Z, a fact, not a changed number or bar):** the
inference above was wrong. A recount that replays pass 1's stored filler answers through the
checks (`recount.py` in the project's validation files, no model calls) reproduces 42 / 19 / 21 at tag
`validation-v4` and gives **39 code-checked** on main 8b66573 (17 unsettled, 20 expert only, 74
untested), with zero false supported or contradicted. The 3 lost (D083, D087, D094) are the
wrong-window claims filler 10 (#261) now refuses, as intended. C1 still passes (at least 30). 39
is v4's claim set, not v5's; v5's claims are written to C3's mix, which v4's were not.

C4's bar (40) is set above bar 5's floor (30) because pass 1 refills every claim afresh: v4's two
passes differed by 2. The probe is used instead of a paid first slice of pass 1 because it covers
all 150 claims for about a twentieth of a pass, where a 15-claim slice would cost more and
measure less.

**If C2, C3 or C4 falls short:** nothing is paid for. Under C2, the writer is told the data
counts and shapes the mix to what the phones hold. Under C3, the writer revises the mix from the
unchanged brief. Under C4, the writer may top up the short kinds once, told only how many claims
of which kinds to add, never which claims fell short or why. The set stays at 150: each new
claim replaces one of the writer's own choosing from a kind code cannot check (identity,
meaning, event or role), picked from the writer's private form by kind alone, and the
replaced claims become development data. The replacements keep the signed key at 100 or more
not-supported claims: a not-supported claim is replaced only by a not-supported one. The new claims are labeled and frozen like the rest,
and the probe runs once more. Short again means no run: the set becomes
development data. No Mabillon code changes in response to C4, since that would tune it to the
held-out claims. The probe's aggregate counts and any top-up are disclosed with every number.

The probe is the driver's `--coverage-probe` mode (`eval/validation/` only, with tests, PR #272),
merged and tried on the development pair before the tag.

## 8. Before scoring: assumption fidelity audit
As v4: an agent that never opens the key reads every tested claim's assumptions against the claim
text. Each must name the claim's own person, phone, window and app, and quote only the claim's
quoted words. Bar: **0** wrong person, phone, window or app (the v4 failure: a time borrowed from
another act), and 0 non-quote words used as a quote. Arsh spot-checks 5 it passed.

## 9. Bars
Scorer 1.6.0 computes each from pass 1, and bars 1 to 3 also from pass 2.

| # | Bar | Pass if | Kind |
| --- | --- | --- | --- |
| 1 | False Supported, the run as it stands (R1, code checks only) | 0 over all not-supported claims (at least 100), in both passes | pass/fail |
| 2 | False Supported after the simulated expert (R2) | 0 | pass/fail |
| 3 | False Contradicted (gold not contradicted), R1 and R2, including measure 7 | 0 | pass/fail |
| 4 | A false claim shown with support only: supports items, no contradicts item, no failed check, **and no core assumption left open** (a check that came back inconclusive, or an assumption no check covers and no item supports), over gold-contradicted claims | at most 5% (Arsh sets) | pass/fail |
| 5 | Coverage: tested k of 150, tiers, every refusal kind | at least 30 code-checked claims, or "insufficient coverage" and no number is quoted | floor |
| 6 | Repeat, pass 2 against pass 1 | no claim Supported in one pass and Contradicted in the other; at least 95% same verdict (Arsh sets); every difference listed with its cause | pass/fail |
| 7 | `mabillon verify-bundle` on pass 1's bundle | passes, 0 differences | pass/fail |
| 8 | Import counts, per phone and per table `lava_kinds.json` reads: Mabillon's records plus the Google Messages copies it skipped against `dump_lava`'s count | every table equal; every skipped copy's pair confirmed by the scorer from the LAVA rows; no record from a table the reader does not count; the LEAPP output agrees with itself on every counted table | pass/fail |
| 9 | Time and API cost per pass | recorded | reported |

Bar 4's wording is decision A (Arsh chose it 2026-11-16). It is looser than v4's: a false claim
with an open check counts as flagged unresolved, not as shown supported, which is what an expert
sees. Every number quoted from v5 says so.

Also reported, never a bar: accuracy over tested claims with its interval, missed Supported,
key-evidence recall, false Supported over tested not-supported claims only, and every figure per
kind and per phone.

**If any pass/fail bar fails,** no accuracy number is quoted, except under the repair rule below.
The result and its cause are written up in project files, the fix is development work, and a new
held-out set is needed before another number can be quoted.

**Repair rule (Arsh sets; proposed).** If a bar fails only because the scorer or the plain reader
counted wrongly, and no Mabillon output changes, the defect may be fixed once: the fix touches
only `eval/validation/`, its test reproduces the miscount on synthetic data, the same stored run
is rescored, and the fix is disclosed beside every number. A defect in Mabillon itself, or
anything that changes a verdict, still means no number and a new held-out set. (Under this rule
v4's bar 8 failure would have been repaired; its bar 4 failure would not.)

## 10. Disclosures that travel with every v5 number
- Two public test phones made by one researcher for a teaching case. Their chats are casual test
  conversations; meaning and event results say less than the rest.
- Truth is the LEAPP output. A record the extraction or LEAPP lost cannot be caught; the creator
  logs were context only.
- This thread saw both creator logs' app lists, a message-overlap count and about ten message
  lines while choosing the pair (2026-11-14).
- The LEAPP importer is new on this path. It was built and checked record for record against the
  UFDR on the development phones (Android 13, iOS 15), not on these.
- Chat apps are read partially on LEAPP: Android chat apps by design, iOS chat apps never in full
  (CallKit). Chat-app absence claims are untestable here, and a two-phone sender question and iOS
  native message counts fail closed (unproven).
- Bar 4 uses decision A's wording, looser than v4's.
- The fixes since v4 were designed on Android 13, iOS 15 and Android 12 development data.
- The writer and two readers are Claude models, the same family as the labeler; one reader is
  from another family, and Mir or Yazen labels 30 blind. Kappa and the sample's agreement are
  reported.
- The simulated expert in bar 2 is code standing in for an examiner, not a person.
- Opus labels are about 99% stable from run to run, not deterministic; bar 6 measures it here.
  Verdicts are deterministic from stored labels (bar 7).
- One extraction path: ALEAPP ed1b63d and iLEAPP fb05694 LAVA output.

## 11. Freeze record (filled in before the run, then approved by Arsh)
| Item | Value |
| --- | --- |
| Tag `validation-v5`, commit | |
| Android 14 LEAPP zip SHA-256 | |
| iOS 17.3 LEAPP zip SHA-256 | |
| `claims.jsonl` SHA-256 | |
| `definitions.json` SHA-256 | |
| `gold.jsonl` SHA-256 (signed key) | |
| Fleiss' kappa before adjudication | |
| Blind 30: seed, labeler, agreement | |
| Not-supported claims in the key | |
| Spend cap per pass, ceiling | |
| Reader 3 model and host | |
| Free credit balance checked (date) | |
| Coverage gate: C2 counts, C3 mix, C4 tier counts (and any top-up) | |

## 12. Steps, owners and cost
| Step | Owner | API cost |
| --- | --- | --- |
| Arsh signs this plan | Arsh | none |
| #271 (merged) and #272 merge; tag `validation-v5` | Arsh merges, this thread tags | none |
| Packages: ALEAPP and iLEAPP on the two images, zips hashed | isolated session | none |
| Writer session makes the dumps' claims and definitions | isolated session | none |
| Readers 1 and 2 label | isolated sessions | none |
| Reader 3 labels (other family) | isolated session | about $2, needs Arsh's OK |
| Coverage gate C2 (data) and C3 (claim mix) | this thread, by script, aggregate counts only | none |
| Adjudication | Arsh | none |
| Claims, key and definitions frozen (hashes recorded) | this thread | none |
| Coverage probe driver mode (#272), tried on the development pair | this thread, Arsh merges | none |
| Coverage gate C4 (probe on the frozen claims; after a top-up, refrozen and probed once more) | this thread | about $2 to $4, cap $5 per attempt; first attempt OK'd by Arsh 2026-11-21, a second needs a new OK |
| Blind 30, drawn at random from the final frozen set after C4 | Mir or Yazen | none |
| Freeze addendum, with the final hashes and the C4 counts, approved | Arsh | none |
| Pass 1 and pass 2 | this thread | $65 to $105 est., needs Arsh's OK |
| Fidelity audit, scoring, write-up (project files only) | this thread | none |
