## 2026-11-10: The filler finds the one message a claim quotes after its recipient and app, and drops the claim's own comma inside a closing quotation mark
- Changed: `_MESSAGE_CUE_RE` in `core/audit/assumption_filler.py`, which says whether a quote is
  a message, took only a verb of writing with a capitalised recipient right before the quote,
  so 'X wrote to Y on App "..."' quoted no message and the code-made meaning was refused ("no
  one quoted message"), which left a content_meaning claim untested. It now also takes "to",
  "the" or a phone number for the recipient and the app the message went by ("on WhatsApp",
  "by iMessage", "via Signal direct message"); no party or app is read from these words.
  `_add_meaning` adds no meaning when the claim quotes two or more messages (one message's
  meaning is not the claim's reading, and the other's writer could go untested), and every
  refusal now says why there is no one quote (no quote, only a name quoted, two messages, no
  lead-in, model words outside a message quote). Separately, a comma that ends a message's
  quoted words right before the closing mark (American usage, '"Yep, ready when needed,"
  shows ...') is dropped from sender, record_time and meaning words, model-written or
  code-made; before, the checks searched for the comma, which the message does not hold, and
  found nothing. The words stay verbatim from the claim. No meaning assumption is ever covered
  by a check, and no claim type changes.
- Where: branch fix/quotes, not yet in a PR
- Verified: `tests/test_fill_quotes.py` (synthetic case01: the widened cue and lead-ins that
  stay names; a curly quote with the comma inside; a nested quote; claims that complain,
  threaten or admit keep an uncovered core meaning and stay UNPROVEN with passing sender and
  time checks; a fragment that reverses its message stays UNPROVEN; a paraphrase and a quoted
  name are refused with their reason; two quoted messages get no code meaning; "ok" from
  several senders is not SUPPORTED). Replay of the stored practice answers (no model call),
  2026-11-10, cloud container: Android 12 A05 goes from refused to sender pass, time pass,
  meaning uncovered; iOS 15 C21 from sender and time inconclusive (nothing found) to both pass,
  meaning uncovered; iOS 15 B24 from inconclusive to time pass and sender FAIL (see Open); no
  other claim's assumptions or check outcomes change, only refusal wording.
- Open: B24's sender fail comes from the sender check counting an account no confirmed link
  ties to anyone as someone else, which makes the claim CONTRADICTED on a missing link
  (proposed/quotes.md item 3); the lead may hold the comma commit until that is decided. A
  quote that is part of a longer message still passes the sender and time checks, so a
  communication claim quoting a fragment whose message says the opposite is SUPPORTED
  (checked) today, before and after this change (proposed/quotes.md item 2). A plain report of
  a message's words that the claim model types content_meaning stays UNPROVEN until an expert
  accepts it (proposed/quotes.md item 1). A trailing period inside the quote is kept as
  written.
- Affects: verdict path (more content_meaning claims are tested; one practice claim can now be
  CONTRADICTED by a sender fail, see Open); no privacy, network or customer-facing change.
- Status doc: pending: in section 5 (Assumptions) of the pipeline table, after "Code adds a
  meaning assumption on the claim's one quoted message", add "(a message quote may follow its
  recipient and app, 'wrote to Y on App'; none when the claim quotes two messages; a comma
  ending the quoted words before the closing mark is the claim's and is dropped)".
