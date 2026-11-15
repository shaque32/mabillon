## 2026-11-15: Rule pack format and trap harness for carrier records (eval only) (#260)
- Changed: Added `eval/rulepacks/`: a versioned, hashed rule pack format for one evidence type
  (layout field maps with a stated time zone, existing assumption templates, and guards that
  can only turn a check result inconclusive), a deterministic synthetic generator of carrier
  call records in two invented layouts, 10 reference claims (3 true, 7 traps), and a harness
  that drops a pack on any false supported, on a guard that blocks no trap or names a trap no claim has (rule-kill), or on
  a supported claim that survives mutation of its records. First step of
  `baker/plans/rule-drafting.md` (AI-drafted rule packs per evidence type).
- Where: PR #260 (branch claude/project-thread-zweeky)
- Verified: `pytest tests/test_rulepacks.py` (13 tests) on the cloud container, 2026-11-15.
  Harness on the reference pack: 10/10 claims as expected in both layouts, 0 false supported,
  each guard blocks its named traps, no insensitive supported claim. Reading a UTC or Central
  time as Eastern lets one trap through as a false supported, so the traps catch it.
- Open: Eval only: no `core/ingest/` reader for carrier records, no `SourceKind` for them, and
  nothing in the app loads a pack (those need signed contracts, schema and rules.py changes,
  PR 3 of the plan). The layouts are invented, not checked against any real carrier format.
  Carrier SMS rows are counted and skipped. The CDR source is treated as complete for its dates,
  which real carrier records may not be. No AI-drafted pack has been run yet.
- Affects: none (eval tooling; no capability, privacy, model or customer-facing claim changes)
- Status doc: no change
