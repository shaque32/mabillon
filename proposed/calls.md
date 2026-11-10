# Who placed a call: the caller assumption (area "calls")

Branch `fix/calls`. Built without any frozen-file edit. This file is the design, what it
refuses, the two rulings it needs from Arsh, and one optional frozen-file change.

## The problem

A call claim got one assumption, `record_time` (when the call happened). Nothing tested who
placed it, so:

1. Rule 3e (`core/audit/rules.py`) kept every communication claim about a call unproven: a
   communication claim needs a core identity assumption, and a call claim had none.
2. A claim that reverses a call's direction was never caught. Worse, a TIMING claim that states
   a direction ("On ..., at about 8:38 a.m., the TARGET PHONE placed an outgoing telephone call
   to (919) ...") needs only a time assumption under rule 3e, so rule 3c' could make it
   SUPPORTED (checked) on its time alone, with its direction untested. In the Android 12 replay
   (checks only, no labels), A10 was SUPPORTED (checked) this way although its window holds a
   call each way (`call:ios15:Call[4]` outgoing at 08:38, `Call[5]` incoming at 08:43).

## Is a contracts field needed? No, not for this

An earlier note said "Direction needs a contracts field, signed by Arsh". Since contracts 0.5.0
(#172) `AssumptionParams.sent_by` names one side of a two-party assumption ("the side whose
messages a count counts"), and its validator already requires it to be a party the assumption
names. A call has one calling side as a message has one sending side, so the caller is
expressed with existing fields:

- a new template `caller` in `core/audit/assumptions.py` (not frozen): kind IDENTITY, check
  `caller`, required `window`, `channels` (must hold `call`) and `sent_by`; allowed also
  `device_ids`, `duration_s` and the party fields. Exactly two parties; `sent_by` is one
  person, or exactly the accounts (never a handle side: a handle is resolved by the checks, so
  code cannot name it as the caller).
- `sender` cannot be reused: it picks a message by its quoted words (`quoted_text` required),
  and a call has none. `sent_by` on `record_time` cannot either: `record_time` is a TIME
  assumption, and rule 3e needs an IDENTITY one; the kind is the template's.

The only use of `sent_by` the contract's comment describes is a count. The caller template
reads it as "the side the call came from". That is the same meaning, but the comment should
say so (optional diff at the end).

Only code fills `caller` (`CODE_ONLY_TEMPLATES`): the filler's and the testability step's
prompts and schemas leave it out, so the signed assumptions prompt and every stored model
answer are unchanged, and a model answer naming it is refused.

## What the filler reads (`LocalAssumptionFiller._add_caller`, `call_form`)

It runs after code's time-range fill, only when the claim has exactly one call `record_time`
(channel `call`, no quoted words). The claim's words outside quotes are tokenized: each party
`_call_parties` would read (a phone name, a person, a phone number or a name the expert gave
one, a quoted name, an identifier on the call's app) becomes a token. Two readings that overlap
(other than one party's name inside its own longer name) refuse the claim. Then the whole claim
must be exactly:

    [date, time and zone words] A VERB-PHRASE B [length | date and time words] [.]

where A and B are the only two party tokens and the verb phrase is one of:

| Form | Caller |
|---|---|
| A placed / made {a, an, another} [second..fifth] [outgoing] [app] [telephone, phone, cell] call to B | A |
| A called B | A |
| A received {a, an, another} [..] [incoming] [app] [telephone..] call from B | B |
| A missed {a, an, another} [..] [incoming] [app] [telephone..] call from B | B, and missed |
| A had {a, an, N} [app] [telephone..] call(s) with B | none (sides only; used for B33) |

Refused, so no caller is made (the claim keeps rule 3e's "not tested"):

- any denial (`not`, `never`, `no`, `n't`, ...), any clause joiner (`which`, `who`, `after`,
  `while`, `then`, ...), a kind of call (`video`, `audio`, `voice`);
- a direction word the verb does not allow: "placed an incoming call", "received an outgoing
  call", "missed an outgoing call";
- the passive ("was called by"), "a call was placed from A to B", plural calls with a
  direction verb ("placed two calls to"), and any word the forms do not hold: "returned",
  "attempted", "back", "three-way", "answered", "connected";
- a third party token anywhere, a party in the lead, or a lead holding anything but date, time,
  zone and phone words (`_plain_prefix`, "in Spanish, ...");
- a length after the clause that is not the time range's own `duration_s`, or a time range
  with a length the clause does not state;
- sides that are not the time range's parties (`_call_parties` with the clause's phone as a
  side must give exactly the time range's persons and accounts);
- a phone written as a side whose owner is not exactly one person: the phone's side is its
  owner by a confirmed device_owner stipulation whose accounts are exactly the phone's own
  (`_exact_owner`, as call counts already use). With the stipulation unconfirmed, nothing is
  made;
- both sides the same person, or the time range naming a handle.

Adversarial wordings in `tests/test_fill_calls.py::test_wording_that_is_not_a_plain_form_names_no_caller`.

### A missed call

"A missed an incoming call from B" makes the caller assumption (B placed it: a log row
'incoming' or 'missed' agrees, 'outgoing' disagrees) and, beside it, a core `event`
assumption (code-made, no check). The importers write 'missed' only from the literal word, and
a UFDR call whose Direction column says "Incoming" is stored 'incoming' even when its Status
says "Missed" (`core/ingest/cellebrite_common.py`, `stated_call_direction`), so the log does
not reliably record whether an incoming call was answered. The event keeps the claim from
SUPPORTED (checked) on the caller and time alone; only an expert accepting evidence covers it.

## What the check reads (`core/audit/checks/caller.py`, version 1.0.0)

Calls with an account of either side, on the named phone(s) and the apps named beside `call`
(all apps with `call` alone, as the time check), of the stated length if any. For each row:

- the phone's side is the party that the one confirmed device_owner stipulation on the row's
  device makes its owner; no such party, or both, and the row reads no caller;
- the row is a call between them only when the other side's accounts are on it;
- 'outgoing' with the other side as `to` and the from account empty or the phone's own: the
  phone's side placed it. 'incoming' or 'missed' with the other side as `from` and the to
  account empty or the phone's own: the other side placed it. Anything else (direction
  'unknown', or accounts on the wrong side for the direction) reads no caller.

Outcome over the rows inside the window:

- PASS only when every row agrees with `sent_by` and no row is unread;
- FAIL only when every row was placed by the other side, each logged plainly 'incoming' or
  'outgoing' (a 'missed' row never makes a fail), and no row is unread. The detail says a call
  the log does not hold is not seen;
- INCONCLUSIVE otherwise: rows both ways in the window, an unknown direction, a contradictory
  row, a matching call with no usable time (it may be inside the window), a device with no
  one confirmed owner among the sides, no row at all ("Not found does not mean it did not
  happen"), or the two sides sharing an account.
- Duplicate rows (one call logged twice, as the practice data does with "+1..." and bare digits
  under two account ids): both rows are read; the time range's account party already holds
  both ids (ruling R6), so they agree, and the detail names pairs within 60 seconds as possibly
  one call. If two copies disagree, the outcome is inconclusive.

Why a fail is allowed at all: like the sender check's fail for a message, it rests on records
that are there. Calls are picked by parties and time, not content, so a fail can be wrong only
if the claim's call is missing from the log while another call between the same two sides, the
other way round, sits in the same window. The mixed rule keeps a window that holds both
directions from failing.

## Effect on the practice claims (replay, checks only)

See the report. In short: a caller is made for A08, A09, A10, A13, B06, B07, C07 (and outside
the list B01, B04, B25, C24, C25, A11, D31). It passes for A13, B01 and C24; it is inconclusive
for A08, A09, A10, B06, B07 and C07 because each window holds calls both ways. C07 (the known
reversed claim) is therefore not contradicted, but it is no longer shown with support only: its
caller check lists the 12:01 incoming and 12:04 outgoing calls side by side.

## Rulings needed from Arsh

R-calls-1. "answered", "connected" with a stated length ("that was answered and lasted about
one and a half minutes", "that connected and lasted about two minutes"; C06, D14, D15 wording).
Today these words leave the caller unread, so such a claim stays unproven by rule 3e. Options:
(a) keep refusing (current); (b) read "answered and lasted N" / "connected and lasted N" as
the length only, since a call log's length is talk time and a duration in a range above zero
means it connected; (c) add a code-made core `event` assumption for "answered" as for
"missed". Recommendation: (c). It tests the caller, and the answered part stays with the
expert, whose acceptance is needed anyway; (b) rests on a reading of the duration field that
differs between apps and is unverified.

R-calls-2. A fail on a reversed caller is a CONTRADICTED verdict by rule 1a, with no expert
step. Options: (a) as built: a fail contradicts, like the sender check; (b) the caller check's
fail counts only once an expert confirms it, as rules 0.4.0 does for an agent's assumption
(needs a rules.py change and RULE_VERSION bump). Recommendation: (a), because the fail needs
every in-window call of the stated length to be the other way, each plainly logged, and the
report shows the records; but this is the one new path to CONTRADICTED and it is yours to sign.

## Optional frozen-file change (not needed for the code above)

1. Make the contract's comment on `sent_by` say what the caller template reads. Comment only;
   no behavior changes.

```diff
--- a/core/contracts.py
+++ b/core/contracts.py
@@ class AssumptionParams(Model):
-    # The side whose messages a count counts, as ids that are also in person_ids or
-    # account_ids ("SUBJECT-2 sent SUBJECT-1 three messages": sent_by is SUBJECT-2's id).
-    # Empty: messages either way.
+    # The side a message or call came from, as ids that are also in person_ids or
+    # account_ids: whose messages a count counts ("SUBJECT-2 sent SUBJECT-1 three messages":
+    # sent_by is SUBJECT-2's id), or who placed the call a caller assumption names.
+    # Empty: messages either way.
     sent_by: tuple[str, ...] = ()
```

2. What a field would add, if Arsh wants it later: a `placed_by_phone: bool | None` (or a
   direction relative to `device_ids`) would let "the TARGET PHONE placed a call to X" be tested
   when the phone's owner stipulation is unconfirmed or the owner has other linked accounts,
   and would let a handle side be the caller. Today those claims keep no caller (fail closed).
   Not proposed now: it changes contracts and the template for a gain the practice data does
   not show.

## Found, not fixed (another area or a wider change)

The time and count checks (`involves_all` in `core/audit/checks/_common.py`) match a two-party
call only when both sides have an account on the row. A phone's own call log often leaves the
phone's side empty (`from` empty on an outgoing call). So a two-person call claim on the
owner's phone finds no call: B06 and B07's time check says "None found" although
`call:ios15:Call[78]` and `Call[79]` are Telegram calls with SUBJECT-2 at 11:11 and 11:15, and
B33's count counts 0 of them. Both fail closed (inconclusive), but the claims are untested. A
fix would read the phone's side from the row's device and its confirmed owner, as the caller
check does.
