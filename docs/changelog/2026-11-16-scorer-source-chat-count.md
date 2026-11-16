## 2026-11-16: The validation scorer's import count compares source chats with source chats
- Changed: scorer 1.4.1 (`eval/validation/score_hickman.py`, `import_counts`). Bar 8's chat
  count now reads the source chats behind Mabillon's imported messages, from each message's
  locator ("Chat[12]/Messages[3]"). Before, it counted Mabillon's threads. The importer keys
  SMS and MMS threads by the counterpart's number, so two source chats with one number become
  one thread with every message kept, and the count reported a difference where no record was
  lost. The new count still catches a chat whose messages fail to import. Approved by Arsh on
  2026-11-16 for the next held-out run; a run already scored keeps the scorer it was scored
  with.
- Where: PR #262
- Verified: `tests/test_validation_score.py` (new: two source chats merged into one thread
  count as two, and a standalone message names no chat); the whole file passes locally (25).
  `make check` runs on GitHub CI.
- Open: the message, call and contact counts are unchanged.
- Affects: the validation scorer only (bar 8). No verdict, capability, privacy or network
  change, and no customer-facing claim.
- Status doc: pending: section on validation tooling: "validation scorer 1.3.0" becomes
  "validation scorer 1.4.1".
