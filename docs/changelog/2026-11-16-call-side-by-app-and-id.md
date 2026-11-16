## 2026-11-16: A call's other side may be described by its app and given with its id; a plain LEAPP reader and v5's bar 4 measure for validation
- Changed: filler 11 (`core/audit/assumption_filler.py`, `call_form`, `_caller_params`,
  `_call_parties`). A call's clause may describe its other side by the call's own app ("called
  the Instagram user \"Marc R.,\" user ID 4984...") and give the side's id beside its name (",
  user ID ...", "(user ID ...)"). The caller row is made only when the name and the id are one
  account; another app's name, other words, a person described as an app's user, or an id
  that is a second account leave the caller unread. A comma inside a quoted name's closing
  mark is the claim's punctuation, so the name is looked up without it. Before, such a claim
  kept only its time row, so a reversed direction never showed.
- Also: `eval/validation/dump_lava.py` (new, validation tooling only). A plain reader of a LEAPP
  run's output (`_lava_data.lava` and `_lava_artifacts.db`), standard library only, written from
  the LAVA format and not from the LEAPP importer's code. It counts the tables named as
  messages, calls and contacts from the tables themselves (distinct values of a dedupe column
  where one is given, since iLEAPP's SMS table has one row per attachment), reports the
  manifest's record_count beside each live count, and opens the database read-only. Validation
  v5's bar 8 will compare Mabillon's import counts with it.
- Also: validation scorer 1.5.0 reports a second bar 4 measure for validation v5 (Arsh's decision
  card, 2026-11-16): a false claim counts as shown with support only when it has supports
  items, no contradicts item, no failed check, and no core assumption left open (every check
  on it inconclusive, or no check and no supporting item). v4's measure and v4's bars are
  unchanged. Tests in `tests/test_validation_score.py`.
- Where: PR #263
- Verified: `tests/test_dump_lava.py` (synthetic LAVA output made in the test). New tests in
  `tests/test_fill_calls.py` (three wordings that get a caller and
  pass its check; four that name no caller; a side described before the verb). Filler,
  window, quote, caller, check, axiom and validation tests pass locally (1,773). A replay of
  stored model answers on three development phones (no model call; results in project files
  only) changed one claim, which now gets a caller check (inconclusive: two calls each way
  in its window) instead of only a passing time check.
- Open: a side described before the verb ("the Instagram user ... called X") is not read.
  A call with one call each way in the stated window stays inconclusive, by design.
- Affects: verdicts (more call claims get a caller check, which fails closed to
  inconclusive); customer-facing claims: none. No privacy or network change.
- Status doc: pending: header "Other versions": filler 11; "validation scorer 1.4.1" becomes "validation scorer 1.5.0".
