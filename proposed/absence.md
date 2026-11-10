# Proposed: absence (no contact with a phone as one side)

Branch `fix/absence`. What is built needs no frozen file. This file holds the one contract change
that would make the design cleaner, and three rulings for Arsh. Nothing here is needed for the
fix to be safe.

## What is built (no frozen file touched)

"There was no contact between the TARGET PHONE and (212) 555-0144 before March 12, 2026." The model
names the phone in `phones` and one other party. The filler (`_phone_as_party`, then
`_absence_parties` in `core/audit/assumption_filler.py`) reads both sides from the claim's words,
the same way it does when the model names no party (ruling R5). The phone's side is its exact
owner by confirmed stipulation: the one person a confirmed `device_owner` stipulation ties to the
phone, used only when that person's accounts are exactly the phone's own (`_exact_owner`). So
the check searches the phone's own accounts and no other. The model's party must be the one party
the claim writes.

The limit of this design: the phone's side can only be a person id, because
`AssumptionParams` treats all `account_ids` as one party. So:
- a phone with no confirmed owner stipulation is refused, even though its own accounts are
  observed and need no stipulation;
- the stored text reads "No contact between person:dev:X:owner and ...", and a model reads it as
  "PETROV (the user of the TARGET PHONE)". What gets searched is the same, because
  `_exact_owner` requires the person's accounts to equal the phone's own. But the words name a
  person where the claim named a phone.

## Contract change (optional, frozen: core/contracts.py, core/audit/assumptions.py, checks)

Give `AssumptionParams` a field that makes one side "this phone's own accounts" without a person:

```diff
--- a/core/contracts.py
+++ b/core/contracts.py
@@ class AssumptionParams(BaseModel):
     device_ids: tuple[str, ...] = ()
+    # One side is this phone's own accounts on it (accounts.device_id = the phone), as the
+    # phone recorded them: observed, never a person or a stipulation. Must be one of device_ids.
+    own_side: str | None = None
```

After that change, these follow (not frozen; they would come in the same PR):
- `party_count` adds 1 when `own_side` is set. `_two_parties` stays as it is. A no_contact or
  message_count with `own_side` and one other party then has two parties.
- `checks/_common.parties` adds `Party("own accounts of <device>", {a.key for a in accounts if
  a.device_id == own_side})`, with a note that says so.
- `Names.phone_side(d)` renders "the TARGET PHONE's own accounts", so the text names the phone,
  not a person.
- `_phone_as_party` sets `own_side` instead of the owner person. The owner-stipulation
  requirement goes away for this reading only. Everything else stays: one phone written in the
  claim, the other party read from the words, and the model's party must agree.

Recommendation: do it when contracts next move. It removes the person proxy and lets a phone
with no stipulation be tested. Until then, the stipulation route built here is safe, because it
is exact, and it fails closed.

## Rulings needed (Arsh)

1. **An address with no app named.** "No contact between the TARGET PHONE and x@example.com
   before March 12" (no app). The options:
   (a) refuse (built);
   (b) read every account on the phone whose identifier is that address, on any app, the way
   ruling R5 reads a number.
   I recommend (a) until a ruling. An address used as a login on one app is not clearly the
   same party as the same address on a mail app.
2. **A number no account holds** (one iOS 15 practice claim, once its account resolves). "The
   TARGET PHONE never communicated with (212) 555-0100", where no account in the case holds that
   number. The
   options:
   (a) refuse (built: "the party is on no account on the phone");
   (b) test it, which always comes out inconclusive ("a party has no accounts in the data"), and
   say so.
   (b) never passes, so it is safe, and it would put on record that the number appears on no
   record of the phone. I recommend (b) only with a ruling, because it reads an absence where
   code has no party at all.
3. **"Any other user" on one app** (one iOS 15 practice claim, in the form "the TARGET PHONE's
   Telegram account exchanged no direct messages with any other Telegram user in March 2026"). No template takes "anyone" as a
   party, and "direct messages" is a one-kind scope that the absence check does not read. It is
   refused now and stays refused. Testing it would need a new template (no message of a kind
   on one app in a range, on one phone), not a reading rule.
