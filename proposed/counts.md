# Proposed rulings: counts (fix/counts, 2026-11-10)

Nothing below is implemented. Each needs Arsh's ruling, and the first also a frozen-file
change. Every claim it would reach stays unproven until then, which is the safe outcome.

## 1. Calls counted by direction ("two incoming and two outgoing")

Practice claims: iOS 15 D25 ("four connected calls, two incoming and two outgoing, with a
party displayed as ..."), D19 ("four Session calls with ...: two outgoing and two incoming").

Today: a count of calls reads no direction. `count_op` refuses "incoming", "outgoing",
"placed", "missed" and the like for calls, `_count_rule` (core/audit/assumptions.py) refuses
`sent_by`/`each_way` with 'call', and the count check raises on them. The R2/R3 changelog says
so on purpose ("A count of calls takes neither field: a call log's direction is not read
here").

Filling only the total (4) is not safe: the split is part of the claim, and the total can be
right while the split is wrong ("three incoming and one outgoing"). The assumption would test
the easy half.

Options:
- A. Leave refused (today). Both claims stay unproven, untested.
- B. Read `sent_by` on a call count as the side that placed the call: one assumption per
  stated direction ("two outgoing" is sent_by = the phone's owner, eq 2; "two incoming" is
  sent_by = the other side, eq 2), and fill the total only together with every stated part.
  It needs:
  - the `sent_by` comment in frozen `core/contracts.py` widened from "messages" to "messages,
    or the calls that side placed";
  - `_count_rule` (assumptions.py) to allow it with 'call';
  - CountCheck._calls to count by `calls.from_account_id` and say so in its detail. It must
    treat 'missed' and 'unknown' direction rows as unknown: never counted for either side,
    and inconclusive under "exactly";
  - a reader for "N incoming and M outgoing" that refuses any other one-way word.

Recommendation: B, but only after a ruling on how a call log's 'missed' rows count toward
"incoming" (a missed call is incoming, and it did not connect). Until then, A.

Exact contracts diff wanted for B (comment only, no type change):

```diff
-    # The side whose messages a count counts, as ids that are also in person_ids or
-    # account_ids ("SUBJECT-2 sent SUBJECT-1 three messages": sent_by is SUBJECT-2's id).
+    # The side whose messages a count counts, or for a count of calls the side that placed
+    # them, as ids that are also in person_ids or account_ids ("SUBJECT-2 sent SUBJECT-1
+    # three messages": sent_by is SUBJECT-2's id; "two outgoing calls": the phone's side).
     # Empty: messages either way.
```

## 2. A count whose claim writes no phone (C08)

Practice claim: iOS 15 C08, "On April 28, 2023, SUBJECT-2 sent SUBJECT-1 exactly three Signal
messages." The model named both persons and no phone. The claim writes no phone, so
`message_count needs device_ids` (the template rule is "a count is about one phone").

The code takes only a phone the claim writes, or the one the model names and the claim
writes. Picking a phone the claim does not name is a reading of the claim, not of its words:
the affidavit may have counted on another phone, or across several.

Options:
- A. Leave refused (today).
- B. When the case holds exactly one phone and one side of the count is that phone's exact
  owner (confirmed stipulation, owner's accounts are exactly the phone's own), count on that
  phone. The assumption text names the phone. The check already says what it searched. Fewer
  than claimed is inconclusive. More than "exactly" is a fail: those records are there on a
  phone the claim's own side used, whatever phone the affiant used.
- C. As B, and also with several phones when exactly one of them belongs to a side.

Recommendation: B. A has no wrong verdict, and B reads only the one phone a side owns. C
needs a ruling on which of two sides' phones a count means.

## 3. "Received" counts

No practice claim in this area uses it. "REYES received three messages from PETROV" is the R2
count from the other end. The R2 changelog lists "received" as refused. Reading it would widen
a signed ruling. The adversarial case is a receiver that is a group: a group's members each
"receive" one message, and the count check, which keeps a message whose recipients include a
side, would count a group message as one REYES received.
`tests/test_fill_counts.py::test_a_received_count_stays_refused` pins today's refusal.

Recommendation: leave it refused until a claim needs it. If one does, read only "<person or
account> received <count> ... from <the other side>", under the same allow lists as "sent".
Refuse it when the receiver is a group thread or a group account, which code can tell from
the thread's member count.
