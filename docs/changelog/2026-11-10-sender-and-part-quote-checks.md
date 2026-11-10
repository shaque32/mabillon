## 2026-11-10: The sender check fails only on a record or a confirmed fact, and no check judges part of a sentence
- Changed: two safety fixes to the deterministic checks, and one filler fix, found on the
  practice runs of 2026-11-10.
  - Sender check 1.1.0 (`core/audit/checks/sender.py`, `_someone_else`). A copy counts as
    someone else's only when (a) its sender is one of a phone's own accounts that is not among
    the expected sender's, (b) a confirmed link or stipulation ties its sender to another
    person, or (c) the expected sender is the phone's owner and the record shows the phone
    received the message. Any other sender is unknown, so the check is inconclusive. Before,
    an account no confirmed link ties to anyone counted as someone else, so a missing identity
    link could make a claim CONTRADICTED: a second number of the same person is not another
    person.
  - Sender check 1.2.0 and time check 1.1.0 (`sentence_aligned` in
    `core/audit/checks/_common.py`). A message that holds the claim's words only inside a
    longer clause ("text me about it" in "dont text me about it, use telegram") is never
    judged. Its copy is unknown to the sender check, and its time is not used. Before, such a
    fragment passed both checks, so a communication claim whose message says the opposite could
    be SUPPORTED (checked). Words that are a whole message, a whole sentence, or a clause ended
    by a comma or a sentence mark still match. A clause mark after a denial or a report
    ("never say: bring the cash", "he said, bring the cash", "I didnt tell him, ...": the cue
    read in the last three words before the mark) starts no quote, so those words are never
    judged either (Greptile on #257).
  - Filler (`_without_claims_comma`, FILLER_VERSION 8). A comma the claim writes inside a
    closing quotation mark ('"..., ready when needed," shows') is the claim's punctuation and is
    dropped from the quoted words, so the checks search for words the message holds. It was held
    back from #255 until the sender fix, because finding more messages exposes the sender gap.
  - Filler coverage (`unbound_person` and `coverage_gap` in `core/audit/assumption_filler.py`,
    FILLER_VERSION 9; the testability step uses the same gate). A communication, timing or
    count claim now needs every person it names outside quoted words bound to a core
    assumption: named in it, or tied to an account it names by a confirmed identity link, or
    the confirmed owner of a phone that holds that account as its own (matched by account
    key, as the checks read a party). The one a quoted message went to is asked for too
    (Arsh's decision of 2026-11-10: a checked SUPPORTED proves who received the message): a
    person by name, and a handle or number written as the recipient through a core time or
    count row naming both sides. Code adds the one recipient the claim writes to a message's
    time row ("On March 12, 2026, PETROV wrote to @northstar: ..." is timed between PETROV
    and @northstar), and gives a time row with no side the claim's one sender. An undated
    "PETROV texted REYES: ..." stays unproven, since only a time or count check can test
    REYES. A person named only inside a kept time range's words is not asked for. A day the
    claim dates from another ("Two days before the LOCKER BURGLARY", "the
    next morning", "later that night") needs a time range even when that other day is no
    defined event. Either gap leaves the claim unproven. Before, case05 C04 ("Two days before
    the LOCKER BURGLARY, SUBJECT-1 texted the COURIER from the BURNER: ...") kept one sender row
    on the BURNER's account and went SUPPORTED (checked) with SUBJECT-1's use of the BURNER and
    the day untested (agents bench of 2026-11-10, gold unproven).
  - Signed sheets re-signed by Arsh on 2026-11-10 (approved as written, labels kept): 19 rows of `eval/gold/case02`, `case04`,
    `case05` and `case06` move to inconclusive, and five contradicted claims on case04 to case06
    move to unproven. The draft keys (`eval/synthetic/case0{2,4,5,6}*`) match, and each case04
    to case06 signing sheet lists the moved rows under "Check change (2026-11-10)".
- Where: PR #257
- Verified: new tests in `tests/test_fill_quotes.py` for the sender rule (a phone's own account,
  a confirmed link, a received copy, an account linked to nobody) and for whole and part
  sentences, with the adversarial fragments; `tests/checks/test_unit.py` and
  `tests/test_axiom.py` updated for the new rule. A replay of stored model answers from two
  practice phones (no model call) is recorded in project files: the one false contradiction it
  found becomes inconclusive, and the correct contradictions stay. `make check` on 2026-11-10,
  Linux cloud container, at the head of PR #257: 4,413 passed, 7 skipped. Eval unchanged:
  case01 unreviewed 0.70 (report only), after the simulated expert 1.00 with 0 false
  supported, hostile PASS, case02 aggregate 0.90 with 0 false supported.
- Open: the signed case01 sheet (`eval/gold/case01/assumptions.jsonl`) does not name the
  recipient on C05 and C16, so the model-free eval, which reads the sheets, still scores
  them on the writer alone; changing it needs Arsh's signature. An undated quoted message to
  a named person can no longer be SUPPORTED (checked). A quote set off by quotation marks inside a message ('wade said "bring the cash
  friday"') is still part of a sentence, so it stays inconclusive; reading it as whole would
  also pass 'never say "..."'. Five synthetic contradictions now rest on an expert's decision,
  not a check.
- Affects: verdicts (fewer CONTRADICTED and SUPPORTED (checked) outcomes from the sender and
  time checks; both fail closed to inconclusive); customer-facing claims (a contradiction from
  the sender check now always rests on a record or a confirmed fact, and a SUPPORTED
  (checked) on a quoted message now tests both who sent it and who received it). No privacy
  or network change.
- Status doc: pending: section 2, step 6 (Checks): add "the sender check fails only when a
  record or a confirmed fact says the sender is someone else (a phone's own account, a confirmed
  link, or a copy the owner's phone received), and the sender and time checks never judge words
  that are only part of a sentence of a message"; step 5 (Assumptions): add "a communication, timing or count claim is
  tested only when every person it names, the one a quoted message went to included, is tied
  to the records its assumptions test, and a day it dates from another day has a time range";
  header "Other versions": sender 1.2.0, time 1.1.0, filler 9.
