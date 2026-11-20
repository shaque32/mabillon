## 2026-11-18: First AI-drafted rule pack (carrier call records) and blind traps (eval only) (#270)
- Changed: Added the drafting procedure for rule packs (`eval/rulepacks/DRAFTING.md`): one
  Claude Code session drafts a pack from format guides and sample files only, a second session
  that never sees the draft writes traps, and the harness runs the draft on both the reference
  claims and the blind traps. No API spend: both sessions ran inside a Claude Code session.
  Added the round 1 outputs: `packs/carrier-cdr-draft.json` (`carrier-cdr@0.1.0-draft.1`,
  status draft, unsigned) and `claims_blind.py` (18 claims: 14 traps, 4 true). Supporting
  changes: invented format guides and sample files (`formats/`), a drafter-only check tool
  (`check_layout.py`), the reader split from the generator (`reader.py`) and the claim helpers
  from the reference claims (`claim_api.py`) so each session's copy can leave the other's
  inputs out, a draft's guards may name no traps (the harness reports what each one blocks;
  reference and signed packs must still name them, each a trap in the run, and the hash covers
  them, so a pack is re-run with its found traps written in before it is signed), and the
  harness CLI runs several claim sets together and prints one sign-off card per guard
  (`--claims`, `--cards`). Second step of `baker/plans/rule-drafting.md`.
- Where: PR #270 (branch claude/project-thread-zweeky)
- Verified: `pytest tests/test_rulepacks.py` (51 tests) on 2026-11-18 in a Linux cloud
  container (4-core Intel Xeon at 2.10 GHz, Python 3.13; machine model not recorded,
  unverified). Harness on the drafted pack, same container and date, reference and blind sets
  together: 28/28 claims as expected in each layout, 0 false supported, both guards earn their
  place (voicemail-leg blocks 4 traps, forwarded-leg 3), no insensitive supported claim. The
  drafter took about 2.5 minutes and the trap writer about 5.5 minutes (wall-clock times each
  session reported, 2026-11-18, as subagents in the same container; the model service's
  hardware is not known, so these are unverified). The drafted layouts are identical to the
  hand-built reference pack's, and its two guards cover the same record types. `make check` in
  CI on 97d0954 (ubuntu-latest and windows-latest, GitHub runners, 2026-11-18) passed; `make
  eval` there: case01 model-free accuracy 1.00 with 0 false supported (0.70 unreviewed, report
  only), hostile 0 of 7 structural claims supported, case02 aggregate accuracy 0.90 with 0
  false supported, the same as main. This PR does not touch core/, so the eval is not expected
  to move.
- Open: The test was easy and correlated, so it shows the procedure works, not that AI can
  read a real carrier format: the format guides were written by the session that built the
  reference pack, and they state plainly what voicemail and forwarded rows mean; the trap
  writer modelled its own guess of a pack to check its labels. The blind labels are the trap
  writer's judgment, not human gold, and need an examiner's review. Blindness rests on what
  each session's copy held and on its brief; each listed the files it read, all inside its
  copy. The drafter was blind to the claims, not to the records: its sample files are the
  files the harness reads, so it saw every row the traps rest on (DRAFTING.md says samples
  should come from a separate seed next time). A flipped direction map still makes no trap a false supported (the caller check
  refuses it), and the trap writer asked for records the generator lacks (blank lengths, a
  time the clock change skips or repeats, an incoming voicemail from a party a claim names, duplicate rows). Human review
  time for signing is not measured yet. Nothing is signed, and nothing in the app loads a pack.
- Affects: none (eval tooling; no capability, privacy, model or customer-facing claim changes)
- Status doc: no change
