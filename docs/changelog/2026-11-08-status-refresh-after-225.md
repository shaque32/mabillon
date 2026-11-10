## 2026-11-08: Status refresh after #225 (rules 0.5.0, report 0.39.0, plan C not built)
- Changed: `docs/PRODUCT_STATUS.md` was last refreshed on 2026-10-27 (#144) and still said rules
  0.3.0. It now matches main `b8e14e4` (through #243; versions read at `9c4e8b3`, and #243
  changed none of them). It applies the 40 pending
  `Status doc` edits of the PRs merged from #145 to #235 and marks them applied, and sets `Where:`
  to main, with GitHub's merge date, on the 82 entries that still named a PR or branch (two
  entries keep the approval notes their old `Where:` held). It also records, read from code:
  contracts and schema 0.8.0, report 0.39.0, importers 0.3.2 (AXIOM 0.2.1), check versions,
  filler 5, challenge 1.0.0, testability 0.2.0, scorer 1.3.0, and the signed testability prompt
  v1.2. Section 5 adds plan C (the Mabillon-hosted model Arsh chose on 2026-11-07 and 2026-11-08,
  per project records) as decided and not built: no client in `core/llm/`, `CLAUDE.md` unchanged,
  the server pieces in open draft #244. Section 7 records run 2 (9 of 106 tested, as
  `PREREGISTERED_v3.md` reports) and that both validation tags are on GitHub; no run 3 result is
  on main. Section 12 marks row 2 ("Nothing is Supported until the expert accepts it") no longer
  true since rules 0.5.0, leaves its replacement wording to Arsh, adds row 8 (the verdict rule is
  published, behind the line "Longeye shows its sources; we also show the rule"), and lists
  "files never leave your machine" among the claims not to make until plan C ships. Section 8
  lists the merges from #144 to #235, the PRs closed without merging (#238 and #239, the counsel
  direction dropped 2026-11-07) and the open PRs.
- Where: PR #247
- Verified: versions read from code at `9c4e8b3`; merge dates from GitHub's PR list; validation
  tags from `git ls-remote --tags`; `python tools/changelog.py pending` lists nothing; `make
  check` in the PR description. Docs only: no code, signed file or eval number changed.
- Open: line numbers in section 12 rows 3 to 7 were not re-checked. Plan C facts come from
  project records, not code. The 2026-10-30 Mac run times in section 7 are reported, not re-run.
- Affects: customer-facing claims (the status doc now says "nothing is supported until the
  expert accepts it" is no longer true, and that plan C wording is not claimable yet). No
  capability, privacy or performance change.
- Status doc: no change
