## 2026-11-16: A call's other side may be described by its app and given with its id; a plain LEAPP reader and v5's bar 4 measure for validation (#263)
- Changed: filler 11 (`core/audit/assumption_filler.py`, `call_form`, `_caller_params`,
  `_call_parties`). A call's clause may describe its other side by the call's own app ("called
  the Instagram user \"Marc R.,\" user ID 4984...") and give the side's id beside its name (",
  user ID ...", "(user ID ...)"). The caller row is made only when the name and the id are one
  account; another app's name, other words, a person described as an app's user, or an id
  that is a second account leave the caller unread. An app identifier under six characters is
  read as a party only right after an id label ("username lena"), never as a plain word; the
  tokenizer and the party lookup share that one reading, so a short id of another account
  beside a name ("Lena Okafor" username zoe1) is two accounts and names no caller. An id is
  read only whole: "lena" is not read in "lena.2" or "lena..2", in the caller reading and in
  every other place the filler looks for an identifier. An account
  lookup takes a label ("ID", "username", "number") off a written identifier only where a
  space, colon or "#" parts them, so "id42" is looked up as id42, never as 42; it takes off
  every label the id tail reads, "user ID number" included. An id may touch
  its label's colon ("user ID:4984..."), a stated length may follow the id after a comma, and
  "on <app>" may name the app by its alias ("on Teams"). The id never picks between accounts:
  a name that two accounts carry is refused before the id is read. A name and a phone number
  held under two keys are one party (ruling R6), as `_call_parties` already read them, so the
  caller row's own guard now reads them so too. A comma inside a quoted
  name's closing mark is the claim's punctuation, so the call's party lookup reads the name
  without it. Each identifier's patterns are compiled once, and only an id the words hold is
  searched for. Before,
  such a claim kept only its time row, so a reversed direction never showed.
- Also: `eval/validation/dump_lava.py` (new, validation tooling only). A plain reader of a LEAPP
  run's output (`_lava_data.lava` and `_lava_artifacts.db`), standard library only, written from
  the LAVA format and not from the LEAPP importer's code. It counts the tables named as
  messages, calls and contacts from the tables themselves (distinct values of a dedupe column
  where one is given, since iLEAPP's SMS table has one row per attachment), reports the
  manifest's record_count beside each live count, and opens the database read-only. Table and
  column names match as SQLite matches them (only A-Z fold), and a table named twice in the
  kinds file, in any spelling or twice in the same one, stops the reader rather than counting
  twice. A table the kinds file or the manifest names that the database does not hold is
  reported with the manifest's record_count, never as a silent zero. A table marked "skip" has
  its rows reported and its dedupe columns never read. It runs by path
  (`python3 -I eval/validation/dump_lava.py ...`). Validation
  v5's bar 8 will compare Mabillon's import counts with it.
- Also: validation scorer 1.5.0 reports a second bar 4 measure for validation v5 (Arsh's decision
  card, 2026-11-16): a false claim counts as shown with support only when it has supports
  items, no contradicts item, no failed check, and no core assumption left open (every check
  on it inconclusive, or no check and no supporting item). v4's measure and v4's bars are
  unchanged. Tests in `tests/test_validation_score.py`.
- Where: PR #263
- Verified: `tests/test_dump_lava.py` (synthetic LAVA output made in the test). New tests in
  `tests/test_fill_calls.py` (three wordings that get a caller and
  pass its check; five that name no caller, each reaching the caller step with its time row
  made, and the parser's reading of each checked directly; a side described before the verb;
  an id in unbalanced brackets; a username under six characters, read only right after its
  label, as in "username lena"; a short id of another account beside the name; an identifier
  that begins with "id"; an id touching its label's colon; a length after the id; an app's
  alias after "on"; a written id with a username label; an id that only begins with a known
  one, as in "lena.2" or "lena..2"; a written id after "user ID number"; a name and its
  number held under two keys). Filler,
  window, quote, caller, check, axiom, validation and LEAPP reader tests pass locally (1,274
  in that set, 2026-11-17). A replay of
  stored model answers on three development phones (no model call; results in project files
  only) changed one claim, which now gets a caller check (inconclusive: two calls each way
  in its window) instead of only a passing time check.
- Open: a side described before the verb ("the Instagram user ... called X") is not read, and
  a period inside a quoted name's closing mark ('"Marc Garage."') still leaves the name unread
  (fails closed). The comma rule lives only in the call's party lookup: the other readers of a
  quoted name (`_party_tokens`, `_names`, the bracket picker in `_accounts_named`) still keep
  the comma, so a clause such as '"Marc Garage," (live:...)' with two accounts of that name is
  refused (fails closed); one shared quoted-name helper is follow-up work with its own replay.
  A call with one call each way in the stated window stays inconclusive, by design.
- Affects: verdicts (more call claims get a caller check, which fails closed to
  inconclusive); customer-facing claims: none. No privacy or network change.
- Status doc: pending: header "Other versions": filler 11; "validation scorer 1.4.1" becomes "validation scorer 1.5.0".
