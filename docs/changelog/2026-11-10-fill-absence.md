## 2026-11-10: No contact between a phone and one other party is read, not refused
- Changed: A no-contact claim that names a phone as one side and one other party is now filled
  ("There was no contact between the TARGET PHONE and (212) 555-0144 before March 12, 2026",
  "The TARGET PHONE never communicated with REYES over Telegram"). Before this, the hosted model
  put the phone in `phones` and the other side in `accounts` or `people`. That left one party,
  and the template refused the claim ("name exactly two parties"), so it was never tested.
  - The phone's side is that phone's own accounts on it, never whoever held it. It is entered
    as the phone's exact owner by confirmed stipulation, used only when that person's accounts
    are exactly the phone's own (`_exact_owner`).
  - Code reads both sides from the claim's words, as when the model names no party (ruling R5),
    with every guard that path has. The model's party must be the one the claim writes.
  - A number is read on every app the claim leaves open, not only the app the model wrote, so
    contact on another app is not missed. An address ("x@example.com") is read only on an app
    the claim names.
  - Refused: no confirmed owner stipulation, or an owner with accounts beyond the phone; two
    phones; a phone the case does not hold; the phone with nobody else; the phone's own number
    as the other side; a party the model took from elsewhere; and wording beyond plain
    contact. A part of a stated day ("after 10:00 a.m. EDT", read by `stated_part_day`) is
    the range's own words, not another clause.
  - The phone's own name no longer counts as a channel word ("the TARGET PHONE" does not name
    the Phone app).
  - In the absence check, a party with no account on an app the claim names, in the searched
    sources, makes the finding inconclusive and says so. It is never a pass: "never communicated
    with SMITH over Instagram" shows nothing when no Instagram account is known to be
    SMITH's. The check version is not bumped here; the lead bumps once.
  - Code: `_phone_as_party`, `_absence_parties`, `_given_is_read` and `_phone_owner` in
    `core/audit/assumption_filler.py`; `_party_gaps` in `core/audit/checks/absence.py`.
- Where: branch fix/absence, not yet in a PR
- Verified: `tests/test_fill_absence.py`, 23 tests on synthetic case01, and the existing filler
  and check tests. I replayed the stored hosted-model answers (no model call) through the
  branch:
  - iOS 15 practice phone: three claims refused before are now tested. Two fail on records
    inside their ranges. One is inconclusive: unknown fidelity, and its party has no account
    on the named app.
  - Android 12 practice phone: one claim refused before is now tested, inconclusive (unknown
    fidelity).
  - No other claim on either phone changed.
  - `make check` passed on 2026-11-10, in the agent's cloud container: 4129 tests passed and
    7 skipped. case01 model-free: accuracy 1.00, false-supported 0. The hostile run passed. The
    case02 aggregate accuracy was 0.90, false-supported 0. Every eval number matches the base
    commit 7f1cc67.
- Open: The phone's side is a person id (the owner), so the text names that person where the
  claim names the phone. What is searched is the same. A contract field for "this phone's own
  accounts" would remove this, and is proposed in `proposed/absence.md` with three rulings: an
  address with no app, a number no account holds, and "any other user". A claim of no contact with "any
  other user" of an app stays refused. A claim whose number no account holds stays refused.
- Affects: capabilities (more no-contact claims tested); verdicts (a check can now fail, so the
  verdict is contradicted, on claims that were untested; a party with no account on a named app
  can no longer pass)
- Status doc: pending: section 2, step 5 (Assumptions): after "open no-contact ranges (...) to
  the extraction's first or last dated record", add "; a no-contact claim between one phone and
  one other party reads the phone as its own accounts, through its exact owner by confirmed
  stipulation, with the other party read from the claim's words (a number on every app the
  claim leaves open, an address only on an app it names), and refuses otherwise". Section 2,
  step 6 (Checks): add "the absence check is inconclusive, never a pass, when a party holds no
  account on an app the claim names".
