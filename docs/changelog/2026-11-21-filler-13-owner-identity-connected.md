## 2026-11-21: Filler 13 and time check 1.2.0: more call claims code can test (#273)
- Changed: found by a coverage recount that replays stored filler answers with no model calls
  (`baker/validation/coverage-recount/recount.py`, project files).
  - Assumption filler 12 to 13 (`core/audit/assumption_filler.py`). It refuses a model's
    person_identity that names no account and no handle, only one person who is the one
    confirmed owner of a phone whose accounts are exactly theirs ("The account belongs to
    SUBJECT-1"), on a communication, timing or count claim, and only a row with no time
    and no quoted message (one with a time says who held the phone then). No check or reviewer could test
    it, and as a core assumption it kept true call claims unproven (v4 Android 13 D077). The
    row is kept when it could say more: two or more people, a person who is no phone's one
    owner (or owns two
    phones, or has a link to an account elsewhere), a phone those people do not own, or an
    app none of their phones holds an account on. On an identity or event claim the row is
    always kept: it is the claim itself, for the expert.
  - "connected" is read beside a call length a row tests (a tested length is never below one
    second), as "answered" already was, but only the call's own ("the call connected and
    lasted", "that connected for"), read before any party is blanked; "connected" with an
    object ("SUBJECT-1 connected REYES with ...") stays unread. A call "that was answered (or connected) and lasted
    ..." gets its code-made caller row.
  - Two more caller wordings: "SUBJECT-1 placed a WhatsApp call from the TARGET PHONE to ...",
    read only when the person is that phone's exact owner by confirmed stipulation and the
    time range searches that phone; and an id with no label beside the other side's name
    ('"ThisIs DfirTwo," live:.cid.5638f9306b7b8594'), read only when the name and the id are
    one account, as with a labelled id.
  - A person's number is timed as the number: "a call from SUBJECT-2's number, (919)
    888-7386" or "called SUBJECT-2 at (919) 888-7386" made the person and the number two
    parties, so the time check found no call. The person comes off the call's time range only
    when the claim writes them right before the number in one of those forms and a core
    person_identity row ties that person to those accounts, on one call's time range only;
    whose number it is stays that
    row's to test. These wordings give no caller row, so a core event row (no check covers
    it) keeps who placed the call for the expert: the call found with the number never
    carries the claim on its own.
  - Time check 1.1.1 to 1.2.0 (`core/audit/checks/timing.py`): a call row that leaves the
    phone's own side blank (iOS and UFDR call logs name only the other side) is a call
    between the phone's owner and that side, when the phone's one confirmed device_owner
    stipulation makes one of the two parties its owner, as the caller check already read it.
    A side with no accounts in the data gets no row, and the detail names each row read this
    way. The time check never fails on a call, so this only lets calls be found. The owner rule
    moved to `core/audit/checks/_common.py` (`phone_side`), shared with the caller check.
- Where: PR #273
- Verified: `tests/test_fill_calls.py` (22 new test functions: the owner row refused and the claim then
  SUPPORTED on its checks, and kept where it says more; caller read after "answered/connected
  and lasted", also after the call's app; reversed caller CONTRADICTED; "connected" without a
  length unread; a call from the owner's phone gets its caller and the check passes, but not
  for a non-owner or another phone; an unlabelled id gets a caller, not when it is another
  account; a blank phone side is the owner's call, never another person's; a person's number
  timed as the number, the claim still UNPROVEN on the identity and event rows, a reversed
  caller beside a person's number held by the event row, and the person kept without the
  identity row or when written as a second party; an identity claim keeps its owner row; a
  row read through the owner's stipulation says so, and an owner with no accounts gets none;
  only the call's own "connected" is plain, never "Reyes was connected", "connected ... by PETROV" or a handle such as "@connected"). `tests/checks` and
  the filler, testability, replay and timeline test files: 1,425 passed. `make eval` unchanged: case01 model-free 1.00
  (unreviewed 0.70), 0 false supported, hostile PASS (0 of 7 structural claims supported),
  case02 aggregate 0.90, 0 false supported (run on this head). Cloud container, Linux x86_64, 4 CPUs,
  2026-11-21. Free replay of stored answers (development data, no spend), Android 13 v4 pass 1
  (150 claims) and iOS 15 dev (106): 0 false Supported, 0 false Contradicted before and
  after. Code-checked 39 to 41 on Android 13 (D022, D023) and 39 to 41 on iOS 15 (B06, B07).
  One claim gains a code verdict before stance labels (A13 D077 SUPPORTED, gold supported);
  with the run's stored labels it stays unproven (a "complicates" label). D103 and C11 gain a
  caller row that stays inconclusive (calls both ways inside the "about" window). The full
  suite (`make check`, ubuntu and windows) is CI's run on the PR's final head, recorded in the
  PR description; an entry cannot record CI on its own commit.
- Open: measured on development phones only; the v5 claim set decides v5 coverage. Counts and
  absences a claim scopes to "the call log" stay unread: the absence and count checks read
  every record on an app, not calls alone. The weekday check still asks both sides on a call
  row.
- Affects: capabilities (which call claims code can test)
- Status doc: pending: section 2 table, step 5 (Assumptions): add "Filler 13 refuses a
  person_identity naming no account, handle, time or quoted message, on a communication,
  timing or count claim,
  only when it names one person, the one confirmed owner of a phone whose accounts are
  exactly theirs, and every phone and app it names is one of their phones or an
  app their phones' accounts hold (a shared owner, another phone or another app keeps the
  row); reads "connected" beside a tested call length; reads a call 'that was answered (or
  connected) and lasted ...', 'placed a call from the TARGET PHONE to ...' (its exact owner
  only) and an unlabelled id beside a name (one account only) for its caller row; and times
  'a call from SUBJECT-2's number, (919) ...' as the number when a core identity row ties them,
  with a core event row for the rest (#273)." Section 2 table, step 6 (Checks): add "The time check reads a call row that leaves
  the phone's side blank as the phone owner's call, by the one confirmed device_owner
  stipulation (#273)." Header "Other versions": assumption filler 13, time 1.2.0.
