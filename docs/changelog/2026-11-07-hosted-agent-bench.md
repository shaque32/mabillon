## 2026-11-07: Hosted open models as filler and testability agent, on spent case05 (eval only) (#241)
- Changed: `eval/bench/agent_bench.py` runs a spent testability case (case05, or case04)
  through the real pipeline with one hosted open model (DeepSeek V4.1 Flash and Kimi K3.1 Pro
  by default, through #225's `HostedModel` and routing) as both the assumption filler and the
  testability agent, at the dev check's settings (cap 2, signed prompt v1.2, rubber-stamp
  expert, no challenge, no stance). It reports the go/no-go's own step measures, plus the first
  pass's share: claims it kept core assumptions for, and how many of those name only what the
  claim's signed sheet rows name, or a person, phone or window the sheet does not. Why: Arsh
  chose (2026-11-07 08:11Z) to save the held-out case06 for the plan C stack, which moves every
  model job, the agents included, to a self-hosted DeepSeek-class model. This says early, on
  spent data, whether that model makes the step worth the case06 run.
- Where: PR #241, stacked on #225.
- Verified: unit tests with a stand-in API (no network): only case05 and case04 may go out
  (case06, case02, case01 and case03 are refused before any model is made), one model does
  both jobs, every call is logged with its provider, no stance prompt goes out. The dry run
  makes 132 calls on case05 at most (48 first-pass calls, then 2 per claim left untested).
  Estimated at list price with an assumed 1,500 output tokens a call: at most about $0.15
  (DeepSeek) and $2.40 (Kimi). The 14B reference, read from its run of record's database
  (Mac, 2026-11-03): the first pass kept core assumptions for 15 of 48 claims (9 name only what
  the sheet names, 2 a person, phone or window it does not), and the step converted 5 of 33.
- Added after the first DeepSeek run: 36 of its 95 calls stopped at open_bench's 8,000-token
  cap (reasoning counts against it), each one an invalid answer. `--max-tokens` runs a larger cap
  as a second arm, reported beside the first; the first stays the run as fixed beforehand.
- Added 2026-11-10, the Opus arm: Arsh moved every model job to Opus (#250) and chose "Opus check
  on case05 first" (card, 01:13Z). `--claude MODEL` runs core.llm.cloud.ClaudeModel as both jobs
  at the product's effort and max_tokens; a refused, cut-off or failed call is an invalid answer.
  Tests with a stand-in client (no network): case06 refused before any model is made, a key
  needed outside a dry run, cut-off, refusal and wrong-model answers invalid, a retryable failure
  retried. Run on case05 (2026-11-10, cloud container, $1.65, development data): both passes 19 of
  48 (39.6%), first pass 15 matching, step 4 of 17, 1 wrong-window try (C43), 0 invalid.
- Open: hosted results (2026-11-07, case05, cloud thread's container) are development data only. Hosted answers do not
  repeat byte for byte (many providers), so nothing here is a go/no-go: case05 is spent, and the
  result is development data, never quoted as evidence that the step works. The 14B's case05
  answers were on prompt v1.0, so a gap between the two mixes the model and the prompt; the
  14B's dev check on v1.2 (plans/testability-pass.md) would separate them.
- Affects: none for the product. Eval network use: case05's (or case04's) filled-in assumption
  and testability prompts go to OpenRouter and the providers it routes to (data collection
  denied), as `eval/bench/cloud_steps.py` sends case01's to Claude. Synthetic data only; case02
  and case06 never go out, and `core/` makes no new network call.
- Status doc: no change
