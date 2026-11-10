## 2026-11-10: The filler finds the one message a claim quotes after its recipient and app
- Changed: `_MESSAGE_CUE_RE` in `core/audit/assumption_filler.py`, which says whether a quote is
  a message, took only a verb of writing with a capitalised recipient right before the quote,
  so 'X wrote to Y on App "..."' quoted no message and the code-made meaning was refused ("no
  one quoted message"), which left a content_meaning claim untested. It now also takes "to",
  "the" or a phone number for the recipient and the app the message went by ("on WhatsApp",
  "by iMessage", "via Signal direct message"); no party or app is read from these words.
  `_add_meaning` adds no meaning when the claim quotes two or more messages (one message's
  meaning is not the claim's reading, and the other's writer could go untested), and every
  refusal now says why there is no one quote (no quote, only a name quoted, two messages, no
  lead-in, model words outside a message quote). No meaning assumption is ever covered by a
  check, and no claim type changes.
- Where: PR #PRNUM
- Verified: `tests/test_fill_quotes.py` (synthetic case01: the widened cue and lead-ins that
  stay names; a nested quote; claims that complain, threaten or admit keep an uncovered core
  meaning and stay UNPROVEN with passing sender and time checks; a fragment that reverses its
  message stays UNPROVEN on a content_meaning claim; a paraphrase and a quoted name are refused
  with their reason; two quoted messages get no code meaning; "ok" from several senders is not
  SUPPORTED). Replay of stored model answers from two practice phones (no model call), 2026-11-10: per-claim results are in the validation fix-round notes in project files, not in the repo. `make check` on the merged branch: see the PR.
- Open: three things found here are held for Arsh's ruling and are not in this change.
  (1) The sender check counts an account that no confirmed link ties to anyone as someone
  else, so a claim can be CONTRADICTED on a missing link. A fix is built on a separate branch;
  it changes four rows of the signed synthetic assumption sheets from fail to inconclusive.
  (2) A comma the claim writes inside a closing quotation mark ('"..., ready when needed,"
  shows') makes the checks search for words the message does not hold. The fix is built, and
  held with (1), because finding the message is what exposes (1).
  (3) A quote that is part of a longer message still passes the sender and time checks, so a
  communication claim quoting a fragment whose message says the opposite can be SUPPORTED
  (checked). A clause-aligned guard is built on a separate branch; it changes six signed sheet
  rows. Also open: a plain report of a message's words that the claim model types
  content_meaning stays UNPROVEN until an expert accepts it.
- Affects: capabilities (more content_meaning claims are tested); no privacy, network or
  customer-facing change.
- Status doc: pending: in section 5 (Assumptions) of the pipeline table, after "Code adds a
  meaning assumption on the claim's one quoted message", add "(a message quote may follow its
  recipient and app, 'wrote to Y on App'; none when the claim quotes two messages)".
