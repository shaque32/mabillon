# Rule packs and the trap harness

A **rule pack** is one versioned, hashed bundle of reading rules for one evidence type: how
each file layout maps to records (columns, time zone, direction and type codes), which existing
assumption templates its claims use, and **guards** (record types on which no check may pass or
fail). Packs are meant to be drafted quickly, by a person or an AI session, then broken on
purpose by this harness, then signed by an examiner and Arsh. Plan:
`baker/plans/rule-drafting.md` in the project files.

A pack never decides a verdict. `core/audit/rules.py` does, on the check results. A guard can
only turn a pass or fail into inconclusive, so a pack can move a claim away from SUPPORTED or
CONTRADICTED and never toward them. Nothing in the pack format can widen a verdict path: which
claim types code may make SUPPORTED stays in rules.py.

Status: eval only. No reader in `core/ingest/` reads carrier records yet, and nothing in the
app loads a pack. Records load as `SourceKind.SYNTHETIC`.

```
python -m eval.rulepacks.harness eval/rulepacks/packs/carrier-cdr-reference.json
python -m eval.rulepacks.harness <pack.json> --json   # the full report
python -m eval.rulepacks.harness <pack.json> --claims reference,blind --cards
```

| File | What it is |
|---|---|
| `pack.py` | The pack format (pydantic), its validator and its hash (signatures and status left out) |
| `carrier.py` | Synthetic carrier call records in two invented layouts (the generator) |
| `reader.py` | The reader that maps a carrier file through a pack's layout |
| `claim_api.py` | What a claim looks like (`GoldClaim`) and helpers to write one |
| `carrier_claims.py` | 10 reference claims: 3 true, 7 traps, each with its expected verdict (the development set) |
| `harness.py` | Runs a pack over one or more claim sets and applies the gate below |
| `packs/carrier-cdr-reference.json` | Hand-built reference pack the tests use; not drafted and not signed |
| `DRAFTING.md` | How an AI session drafts a pack and a blind session writes its traps, with both fixed briefs |
| `formats/` | The invented carriers' format guides and sample files, all a drafter is given |
| `check_layout.py` | The drafter's one tool: validates a pack and reads each sample, knowing no claims |

## The gate

A pack is dropped (exit code 1, `DROP`) unless all of these hold:

0. **Coverage:** the pack has a layout for each synthetic file and no layout without one, and
   lists every assumption template the claims use.
1. **Every claim as expected**, in every layout: zero false supported, and no true claim or
   contradiction lost to a guard that blocks too much.
2. **Rule-kill:** removing each guard in turn lets some trap through as a false supported that
   the full pack holds, including every trap it names. A guard that blocks nothing, or that
   names a trap no claim has, fails the gate. A draft's guards name no traps (its drafter never
   saw them); `--cards` prints what each one blocks, for the people who sign it.
3. **Sensitivity:** every SUPPORTED claim stops being SUPPORTED when the records it rests on
   are mutated, once with the time moved six hours and once (for a claim about who placed a
   call) with the direction flipped.

Beside the gate the harness reports **layout mistakes**: each wrong zone and a flipped direction
map, and which claims each one changes from the pack's own result. A mistake that changes
nothing is a gap in the claim set.
On the reference pack, reading a UTC or Central time as Eastern lets a trap through as a false
supported; a flipped direction map does not, because the caller check refuses a row whose
parties sit on the wrong side for its direction.

The validator also refuses a layout whose zone the header does not state (`zone_evidence` must
be a known zone word that stands alone at the end of a label in the time column's header, so
"Time (UTC-05:00)" and "Central Standard Time" are refused, and it must mean that zone). The
list of zone words is human-owned.

The reader skips and counts malformed rows (wrong field count, or a length that is not 1 to 9
ASCII digits of whole seconds), stores a blank length as unknown rather than 0, and keeps a
local time that daylight saving repeats or skips with its raw value and no UTC time.

## The reference claims

| Claim | Expected | What it tests |
|---|---|---|
| g-in-call, g-out-call, g-dst-call | supported (checked) | direction, length, a call after daylight saving began |
| t-direction | contradicted | the record shows the call came in |
| t-voicemail, t-count-voicemail | unproven | a voicemail leg is not a conversation (guard voicemail-leg) |
| t-forwarded | unproven | a forwarded leg may never have reached the handset (guard forwarded-leg) |
| t-holder | unproven | a subscriber record is not proof of who used the number (core rule: links stay proposed) |
| t-zone-utc, t-zone-central | unproven | a printed UTC or Central time read as Eastern |

These test the harness and are the development set. A drafted pack's own traps come from a
separate session that never sees the draft (`DRAFTING.md`), then an examiner's, then a sealed
held-out set.
