# Proposed: quotes (rulings and changes this branch did not build)

Branch `fix/quotes`. Three items. Item 1 needs a ruling from Arsh on how claims are typed and
a change to a frozen prompt. Items 2 and 3 are not frozen, but they change what the sender and
time checks pass or fail for every claim, so they need a check version bump by the lead and a
decision; nothing here is built.

## 1. A claim that only reports a message's words verbatim, typed content_meaning

Seen on: a claim of the form `<number> sent a <App> message to the TARGET PHONE reading "<words>"`
(no characterization at all) typed `content_meaning` by the claim model. Its sender and time
checks pass; code adds a core meaning assumption ("Filled from the claim's wording.") and the
claim stays UNPROVEN under rule 2.

What the code says (the reason no non-frozen change can settle it):
- `REQUIRED_TEMPLATES[CONTENT_MEANING] = {"meaning"}` (core/audit/assumption_filler.py) mirrors
  rule 3e (`_REQUIRED_KIND[CONTENT_MEANING] = MEANING`, core/audit/rules.py). Not adding the
  meaning assumption makes `coverage_gap` refuse the whole claim ("no usable meaning
  assumption"), and even if it did not, rule 3e keeps the claim from SUPPORTED. So dropping it
  can only make the claim untested, never settled.
- Covering the meaning with a check does not settle it either: rule 3c' allows code-checked
  SUPPORTED only for `_CODE_MAY_SUPPORT = {COMMUNICATION, TIMING, COUNT}`, so a content_meaning
  claim needs an expert-accepted supporting item under rule 3c whatever its checks say. And a
  check that "the words are in the record" passing a meaning assumption would show the words'
  meaning as derived, which is false: verbatim words are observation, meaning is
  interpretation (rule 2c text, decision 5). Rejected.
- The claims prompt (frozen) already says: use "content_meaning" when the claim says what a
  message meant. A plain report of a message's words was mistyped by the model.

Options:
- A (recommended): fix the typing at its source, the claims prompt. Exact diff to
  `core/audit/prompts/claims.md` (needs a prompt version bump and a re-probe of claim typing):
  ```
  -- "claim_type": one of "communication", "identity", "timing", "content_meaning", "count",
  -  "absence", "role", "event". Use "content_meaning" when the claim says what a message meant,
  -  and "absence" when it says something was not found or did not happen.
  +- "claim_type": one of "communication", "identity", "timing", "content_meaning", "count",
  +  "absence", "role", "event". Use "content_meaning" when the claim says what a message meant
  +  or characterizes it (for example complained, threatened, admitted, "referring to", "shows
  +  that"). A claim that only reports who sent a message, to whom, when, and its words in
  +  quotation marks is "communication" (or "timing" when it turns on the time). Use "absence"
  +  when it says something was not found or did not happen.
  ```
- B: code retypes a content_meaning claim to communication when, outside its quotes, it has
  only parties, an app, a date or time and a verb of sending or a "reading"/colon lead-in, and
  nothing else. Not recommended: it is claim-type logic Arsh signs, a word list of
  "characterizing" verbs is never complete ("noted", "conceded", "boasted"), and a miss turns
  an interpretation claim into a code-checked SUPPORTED.
- C: leave it. The claim stays UNPROVEN until the expert accepts one supporting item (one
  click), which is safe.

Either A or B is only safe after item 2: as a communication claim, a quoted fragment whose
full message says the opposite becomes SUPPORTED by code today.

## 2. A quote that is part of a longer message passes the sender and time checks (pre-existing)

Measured on synthetic case01 on this branch (not committed as a test, as it asserts the wrong
outcome): the communication claim `On March 19, 2026, PETROV texted REYES "text me about it".`
with the model's sender and time range is SUPPORTED (rule 3c', checked) because the record
reads "dont text me about it, use telegram": `messages_with_text` matches any word-aligned
substring (core/audit/checks/_common.py), and the sender and time checks pass on it. On a
content_meaning claim the uncovered meaning keeps it UNPROVEN (tests/test_fill_quotes.py
`test_a_fragment_that_reverses_the_message_stays_unproven`); on communication, timing and count
claims nothing does.

Proposed (checks sender and time, version bumps; not built): a match passes only when the
quote is sentence-aligned in the body: it starts at the body's start or after a sentence end
(". ", "! ", "? ", a line break) and ends at the body's end or on a sentence end. Otherwise the
row counts as unknown, and the detail prints the whole message.
```
# core/audit/checks/_common.py
+_SENTENCE_GAP = re.compile(r"[.!?]+\s*$|\n\s*$")
+
+def sentence_aligned(quote: str, body: str) -> bool:
+    """True when some place the folded quote sits in the folded body starts a sentence and
+    ends one: 'Let's make this quick' in 'I am. Let's make this quick. I'll send ...', not
+    'text me about it' in 'dont text me about it, use telegram'."""
+    want, text = fold_text(quote).strip(), fold_text(body)
+    for start, end in find_quotes(want, text):
+        head, tail = text[:start], text[end:]
+        starts = not head.strip() or bool(_SENTENCE_GAP.search(head))
+        ends = not tail.strip() or want[-1] in ".!?" or tail.lstrip()[:1] in (".", "!", "?")
+        if starts and ends:
+            return True
+    return False
# core/audit/checks/sender.py, in the loop over rows, before the account lookup
+            if not sentence_aligned(p.quoted_text or "", row.text or ""):
+                unknown.append(row.id)
+                lines.append(f"{row.id} holds the words only inside a longer sentence: "
+                             f"{row.text!r}")
+                continue
# core/audit/checks/timing.py: the same filter on quote-picked rows; a row that holds the words
# only inside a sentence makes the result inconclusive, never a pass or a fail.
```
On the practice data the replays show quotes cut at sentence ends (for example the iOS 15
Wickr message quoted as its middle sentence), which this keeps; the effect on every claim is
unmeasured.

## 3. The sender check fails on an account no one is tied to

`SenderCheck` (core/audit/checks/sender.py) counts every copy whose sender account is not in the
expected party's confirmed accounts as "bad", so it FAILS when the message came from an
account that no confirmed link or stipulation ties to anyone. Rule 1a then makes the claim
CONTRADICTED. On iOS 15 B24, once the claim's comma is dropped (commit "Drop the claim's own
comma inside a closing quotation mark"), the message is found: it came from a Wickr account
that no confirmed link ties to SUBJECT-2 or to anyone else, and the claim goes from UNPROVEN
(nothing found) to CONTRADICTED. That is a missing identity link, not evidence that someone
else wrote it ("Never auto-merge identities" cuts both ways: an unlinked account is not
someone else).

Proposed (sender 1.0.3; not built): a non-matching copy counts as from someone else only when
its account is a phone's own account (`Account.device_id` set) or an expert-confirmed link ties
it to a person; otherwise it counts as unknown:
```
-            (good if row.sender in sender_ids else bad).append(row.id)
+            if row.sender in sender_ids:
+                good.append(row.id)
+            elif acc.is_owner or any(a == acc.id for _, a, _ in data.links):
+                bad.append(row.id)
+            else:
+                unknown.append(row.id)
+                lines.append(f"{row.id}: no confirmed link ties {fmt_key(acc.key)} to anyone")
+                continue
```
Open for the lead: whether an incoming message from an unlinked account should still fail an
owner-sender assumption (the phone's own account on that app is known and is not the sender).
The rule above keeps those as unknown, so some owner-sender fails on the practice phones (B17,
B30, C13, D02, D32 and Android 12 A04) would turn inconclusive where the other account is not linked;
unmeasured. If item 3 is not taken, the lead may prefer to hold the comma commit, which is
what exposes B24.
