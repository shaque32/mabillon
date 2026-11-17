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
```

| File | What it is |
|---|---|
| `pack.py` | The pack format (pydantic), its validator and its hash (signatures and status left out) |
| `carrier.py` | Synthetic carrier call records in two invented layouts, and the reader that maps them through a pack's layout |
| `carrier_claims.py` | 10 reference claims: 3 true, 7 traps, each with its expected verdict |
| `harness.py` | Runs a pack and applies the gate below |
| `packs/carrier-cdr-reference.json` | Hand-built reference pack the tests use; not drafted and not signed |

## The gate

A pack is dropped (exit code 1, `DROP`) unless all of these hold:

0. **Every synthetic layout is covered:** the pack has a layout for each synthetic file and no
   layout without one.
1. **Zero false supported** on every claim, in every layout.
2. **Rule-kill:** removing each guard in turn lets at least one trap it names through as a
   false supported, and every trap it names must get through. A guard that blocks nothing, or
   that names a trap no claim has, fails the gate.
3. **Sensitivity:** every SUPPORTED claim stops being SUPPORTED when the records it rests on
   are mutated (direction flipped, time moved six hours).

Beside the gate the harness reports **layout mistakes**: each wrong zone and a flipped direction
map, and which claims each one changes from the pack's own result. A mistake that changes nothing is a gap in the claim set.
On the reference pack, reading a UTC or Central time as Eastern lets a trap through as a false
supported; a flipped direction map does not, because the caller check refuses a row whose
parties sit on the wrong side for its direction.

The validator also refuses a layout whose zone the header does not state (`zone_evidence` must
be a known zone word in the time column's header, and mean that zone). The list of zone words
is human-owned.

## The reference claims

| Claim | Expected | What it tests |
|---|---|---|
| g-in-call, g-out-call, g-dst-call | supported (checked) | direction, length, a call after daylight saving began |
| t-direction | contradicted | the record shows the call came in |
| t-voicemail, t-count-voicemail | unproven | a voicemail leg is not a conversation (guard voicemail-leg) |
| t-forwarded | unproven | a forwarded leg may never have reached the handset (guard forwarded-leg) |
| t-holder | unproven | a subscriber record is not proof of who used the number (core rule: links stay proposed) |
| t-zone-utc, t-zone-central | unproven | a printed UTC or Central time read as Eastern |

These test the harness. A drafted pack's own traps come from a separate session that never sees
the draft, plus an examiner's, plus a sealed held-out set.
