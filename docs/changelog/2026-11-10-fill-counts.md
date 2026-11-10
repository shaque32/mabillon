## 2026-11-10: Message counts read the phone as a side, an "exchanged" event as its count, and quoted limits as limits
- Changed: four changes to the message-count readers of the assumption filler
  (`core/audit/assumption_filler.py`). Found on two practice replays.
  - The phone as a side (`_phone_side`). Sometimes the model names only the other side and the
    phone, and the claim writes the phone as one side of a direction count: "the TARGET PHONE
    exchanged Signal messages with (212) ...", or "the TARGET PHONE's Kik account sent ten
    messages to <account>". That side is then the phone's owner by confirmed stipulation, and
    only when the owner's accounts are exactly the phone's own, as for a count of calls. It
    applies only in the "sent" and "exchanged" forms, whose every word is already read. In
    "exchanged" the phone must stand as a side: at the clause's start, or after "with" or
    "and". "X exchanged messages on the TARGET PHONE" adds no side.
  - A WhatsApp id is its number (`ident_digits`). Before, the direction readers did not see
    "(212) 555-0144" as the WhatsApp account `12125550144@s.whatsapp.net` that `_accounts`
    had found by that number (ruling R6), so they refused the exchange as naming a third
    party.
  - Quoted limits (`_quotes_name_sides`). A direction count is now refused when the claim
    puts in quotation marks anything but a side's name: 'exchanged "urgent" Telegram
    messages', 'sent REYES one message "about the car"'. Before, the readers blanked quoted
    words, so such a claim read as plain, though the count check reads no content. That was a
    hole on main in the two-person form too. A side's own quoted name ('the GroupMe user "DFIR
    Two"') is read as that side.
  - An "exchanged" claim the model gave as one event (`_exchange_from_event`). The model's
    event becomes a message_count through the same resolution as a model count, with every
    check of the R3 path, and takes the event's place. Conditions: the claim's words read as
    "exchanged ... messages", the model gave exactly one event, and nothing kept is a count, a
    sender or a time range. It never applies to a role. On any refusal the event stays and
    the refusal is recorded. With no number it is at least two, one each way (R3). A
    record_time cannot take an unquoted message, so the count is the template.
  Why: practice claims written in these plain forms were left untested only because the model
  picked the event template or named the phone as a place.
- Where: PR #255
- Verified: on this container, 2026-11-10, no model call.
  - New tests in `tests/test_fill_counts.py` (synthetic case01, 34). 11 fail without the
    change. They cover:
    - the phone as a side;
    - a one-way-only window that stays inconclusive;
    - an account both sides hold;
    - no confirmed owner;
    - the phone as a place, someone's, or not the subject;
    - "more than", "about" and "over" still refused;
    - "received" still refused, a group as receiver among them;
    - quoted limits;
    - the WhatsApp id, and a third number;
    - events that are not exchanges, two events, a role, and an event with a quote.
  - Replay of stored model answers from two practice phones (no model call), 2026-11-10: per-claim results are in the validation fix-round notes in project files, not in the repo. Communication claims that gain a count stay unproven under rule 3e (no identity
    assumption), and an exact count is never supported from checks (rule 3c').
  - `make check` on the merged branch: see the PR.
- Open: no assumption id changes, since no new parameters. Left as they were:
  - call counts by direction;
  - a count whose claim writes no phone;
  - "received" counts.
  The three rulings needed are in the rulings note for this area (project files, validation fix round). A phone's own account written by
  identifier ("the Wickr account <id> on the TARGET PHONE exchanged ...") is still one party
  with the other account, so it stays refused, a follow-up.
- Affects: capabilities (more plain message counts are tested; quoted limits now refuse a
  direction count); no privacy change; no customer-facing claim change
- Status doc: pending: in "2. Pipeline (main)", row "5. Assumptions", after "or "exchanged" messages
  (at least one each way, never failed on one side's silence; #172) are filled", add: "; a
  phone the claim writes as one side of such a count is its exact owner, an "exchanged" claim
  the model gave as one event is read as that count, and a direction count whose claim quotes
  anything but a side's name is refused (fill-counts)"
