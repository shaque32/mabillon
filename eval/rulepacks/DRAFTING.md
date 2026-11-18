# Drafting a rule pack with AI

How a new evidence type gets a rule pack: one AI session drafts the pack, a second AI session
that never sees the draft writes traps, the harness tries to break the pack with them, and only
a pack that survives goes to an examiner and Arsh to sign. Neither session uses API spend: each
is a Claude Code session working from a fixed brief. Plan: `baker/plans/rule-drafting.md` in
the project files.

A pack never decides a verdict, and nothing in this procedure lets a model set one. The drafter
writes reading rules and guards in the closed pack format (`pack.py`); `core/audit/rules.py`
decides every verdict from the human-written checks.

## Roles and what each may see

| Role | Sees | Never sees | Writes |
|---|---|---|---|
| Drafter | the format guides and sample files in `formats/`, `pack.py`, `reader.py`, `check_layout.py`, `core/audit/assumptions.py`, `core/audit/checks/`, `core/audit/rules.py`, `core/contracts.py` | any claim or trap, the generator (`carrier.py`), the harness, any other pack, this repo's history | one pack JSON, status `draft`, guards with no `blocks` |
| Trap writer | the format guides and samples, the generator `carrier.py` (the records' truth), `claim_api.py`, `reader.py`, `pack.py`, the core files above | the draft pack, any other pack, the reference claims (`carrier_claims.py`), the harness | `claims_blind.py`: true claims and traps, each with the verdict a correct, cautious audit returns |
| Harness | everything | | the report: the gate, what each guard blocks, layout mistakes |
| Examiner and Arsh | the pack, its harness report and one card per guard | | signatures, or a list of changes |

Each session runs in its own copy of the repository that holds only what its row allows, with
no git history, from its own brief below, and with no context shared with the other. That is
enforced by what the copy holds and by the brief. A session could still open a file outside its
copy by path, so each one lists every file it read, and the orchestrating session checks that
list before using its output.

## Rounds

1. **Round 1, blind.** The drafter writes the pack from the guides and samples only. The trap
   writer writes its set at the same time. The harness runs the pack on the reference claims
   (`carrier_claims.py`, the development set) and the blind set (held out).
2. A pack that passes goes to signing. A pack that is dropped is reported as dropped, with
   which gate failed. It is not edited to pass by the session that ran the harness.
3. **Round 2 and later, if dropped.** A fresh drafter session gets the round 1 pack and the
   harness report **on the development set only**: which reference claim came out wrong and
   why. It never sees the blind traps or their results beyond one line: how many were wrong.
   Each round is a new pack version (`0.1.0-draft.2`, and so on).
4. The blind set's verdict labels are the trap writer's judgment, not human gold. An examiner
   reviews each label before the pack is signed. A label the examiner corrects is corrected
   in its own commit that says so, never to make a pack pass.

## What is measured

The time from the start of round 1 to a pack that passes, the number of rounds, and later the
human review time for signing (examiner and Arsh). Each report says which of these are
measured and which are not yet.

## Brief: drafter (round 1)

> You are drafting a rule pack for carrier call detail records for Mabillon, a tool that audits
> government claims about phone evidence for the criminal defense. Correctness is the product:
> one wrong "supported" in front of an expert destroys trust. Read `CLAUDE.md` first.
>
> Your working copy holds the format guides `eval/rulepacks/formats/carrier-a.md` and
> `carrier-b.md`, their sample files in `eval/rulepacks/formats/samples/`, the pack format
> `eval/rulepacks/pack.py`, the reader `eval/rulepacks/reader.py`, and the core audit code.
> Read only files inside your working copy. Do not look for claims, traps, other packs, a
> harness or git history; none of them is in your copy, and using one would spoil the test.
>
> Write one pack to `eval/rulepacks/packs/carrier-cdr-draft.json`: id `carrier-cdr`, version
> `0.1.0-draft.1`, status `draft`, `drafted_by` `ai:claude-code drafter session, brief round 1`,
> evidence type "Carrier call detail records, voice rows (synthetic layouts Carrier A and
> Carrier B)". It needs:
>
> - one layout per carrier, ids `carrier-a` and `carrier-b`, mapping each column, code and the
>   stated time zone exactly as the guide and the sample show. A zone must be one the file's
>   own header states (`pack.py`, `ZONE_WORDS`);
> - the assumption templates a carrier call claim needs, from `core/audit/assumptions.py`;
> - guards: record types on which no check may pass or fail, because a row of that type does
>   not show what a check would take it to show. Give each guard an id and a plain-English
>   `text` an examiner can sign in a minute. Leave `blocks` empty: you have not seen the traps,
>   and the harness finds what each guard blocks. A guard that blocks nothing is cut, and a
>   guard on a type that true claims rest on loses true claims, so add a guard only where the
>   guide gives a reason.
>
> Check the pack with `python -m eval.rulepacks.check_layout eval/rulepacks/packs/carrier-cdr-draft.json`
> until it validates and each sample reads with no unmapped or malformed rows you cannot
> explain. Do not edit any other file.
>
> Report back: the pack path; for each layout and guard, one line on why, citing the guide;
> anything in the guides you found unclear; every file you read; and your start and end time.

## Brief: trap writer (round 1)

> You are writing a blind trap set for carrier call detail records for Mabillon, a tool that
> audits government claims about phone evidence for the criminal defense. A separate session
> is drafting the rule pack these traps will test; you will never see it, and it will never
> see your traps. Correctness is the product: one wrong "supported" in front of an expert
> destroys trust. Read `CLAUDE.md` first.
>
> Your working copy holds the format guides and samples in `eval/rulepacks/formats/`, the
> synthetic generator `eval/rulepacks/carrier.py` (the truth of what happened), the claim
> helpers `eval/rulepacks/claim_api.py`, the reader, the pack format and the core audit code
> (`core/audit/assumptions.py`, `core/audit/checks/`, `core/audit/rules.py`,
> `core/contracts.py`). Read only files inside your working copy. Do not look for packs,
> reference claims, a harness or git history; none of them is in your copy.
>
> Write `eval/rulepacks/claims_blind.py` defining `BLIND_CLAIMS: tuple[GoldClaim, ...]`. Each
> claim is a sentence the government might write about SUBJECT-1's line, in US Eastern time as
> an affidavit would state it, with the assumptions a reviewer would fill (templates from
> `core/audit/assumptions.py`; `claim_api.call` builds a call claim) and the verdict a correct,
> cautious audit returns under `core/audit/rules.py`. Ids start with `b-`. Write:
>
> - at least 12 traps (`trap=True`): claims the records do not support, that a pack with a
>   plausible mistake would mark SUPPORTED: a misread zone or daylight saving time, a flipped
>   or misread code, a record type that does not show what the claim says, a count or a length
>   that includes the wrong rows, a person the records do not tie to a number;
> - at least 4 true claims (`trap=False`, expected SUPPORTED) of kinds a pack that guards too
>   much would lose.
>
> Use only events that exist in `carrier.py`; do not change it. Work out each expected verdict
> from the events and the verdict rules, and say in `tests` what the claim tests. Where you are
> unsure of the right verdict, leave the claim out and list it in your report. Make sure the
> file imports and every claim instantiates (`core.audit.assumptions.instantiate`). Do not
> edit any other file.
>
> Report back: the file path; per claim, one line on why its expected verdict is right; claims
> you left out and why; records you wished existed; every file you read; and your start and end
> time.
