## 2026-11-10: Who placed a call is tested: a code-filled caller assumption and the caller check
- Changed: A call claim was tested only for when the call happened, so rule 3e kept every
  communication claim about a call unproven, a claim that reversed a call's direction was never
  caught, and a timing claim that states a direction could be supported (checked) on its time
  alone.
  - New template `caller` (`core/audit/assumptions.py`): kind identity, the call's two sides,
    with `sent_by` (contracts 0.5.0) naming the side that placed it. No frozen file changes.
    Only code fills it (`CODE_ONLY_TEMPLATES`). The filler's and the testability step's prompts
    and answer schemas leave it out, so the signed prompt and stored model answers are
    unchanged.
  - The filler (`_add_caller`, `call_form`) makes it only for a claim whose whole wording is one
    plain form: "A placed (made) a call to B", "A called B", "A received a call from B",
    "A missed a call from B". It allows date, time and zone words before the call and a length
    after it. The two sides must be the call time range's parties. A phone written as a side is
    its owner by confirmed stipulation, only when the owner's accounts are exactly the phone's.
    It refuses denials, other clauses, kinds of call, direction words the verb does not allow,
    "answered", "connected", "returned", the passive, a third party, a handle as the caller, and
    a length the time range does not test.
  - "missed" also adds a code-made core event assumption, which only an expert can cover: the
    importers do not reliably record whether an incoming call was answered.
  - New check `caller` 1.0.0 (`core/audit/checks/caller.py`). It reads the direction each call
    row records on the phone that holds it: 'outgoing' means the phone's side placed the call,
    'incoming' or 'missed' means the other side did. The phone's side is the side the device's
    one confirmed owner stipulation names. It passes only when every call between the sides in
    the window (of the stated length, if any) agrees. It fails only when every one was placed by
    the other side, each logged plainly 'incoming' or 'outgoing'. Calls both ways, a direction
    'unknown', a row whose accounts contradict its direction, an untimed matching call, or no
    one confirmed owner each leave it inconclusive. Rows within 60 s are named as possibly one
    call.
  - A phone written as one side of a plain call clause now counts as a side for a call count
    ("the TARGET PHONE had eight Telegram calls with SUBJECT-2"; `_call_parties`
    `phone_is_side`). "On the TARGET PHONE, PETROV called Jonathan" is still refused.
- Where: branch claude/project-thread-ds0ify
- Verified: `tests/test_fill_calls.py` (48 tests, synthetic case01 with invented calls).
  `tests/test_call_parties.py`'s helper now drops the caller assumption, because those tests
  are about the time range. The eval runs the signed assumption sheet, not the filler, so its
  numbers do not move. Replay of stored model answers from two practice phones (no model call), 2026-11-10: per-claim results are in the validation fix-round notes in project files, not in the repo. In that replay a timing claim that had been supported (checked) on
  its time alone, with a call each way in its window, became unproven, and a claim that
  reversed a call's direction moved from passing checks to inconclusive. `make check` on the merged branch: see the PR.
- Open: Two rulings, in the rulings note for this area (project files, validation fix round): reading "answered" or "connected" with a length,
  and whether a caller fail should contradict without an expert step. A comment-only
  contracts diff for `sent_by` is optional. Not fixed (found): the time and count checks miss a
  two-party call row where the phone's own side is blank, so such claims stay inconclusive.
- Affects: capabilities (a new identity check on calls; a new path to SUPPORTED (checked) and
  to CONTRADICTED for call claims), customer-facing claims
- Status doc: pending: section 2, step 5: add "Code reads who placed a call from a claim's plain
  wording ("placed a call to", "called", "received a call from", "missed a call from") as a
  caller assumption (identity), with a core event assumption beside a missed call; a phone
  written as one side of a plain call clause counts as a side for a call count".
  Section 2, step 6: add "caller" to the list of checks. Header "Other versions": add
  "caller 1.0.0 (`core/audit/checks/caller.py`)".
