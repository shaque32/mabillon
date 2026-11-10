## 2026-11-10: Code reads approximate time ranges and whole months, and the model's window never narrows a count or an absence
- Changed: `core/audit/assumption_filler.py` (time ranges only; no prompt, rule, contract,
  schema or check change).
  - Approximate ranges. `stated_windows` reads "between approximately X and Y" (also "from
    about X to Y", "approximately between X and Y") as X - 8 minutes to Y + 8 minutes, and
    "between X and about Y" as X to Y + 8 minutes. That is the signed "about" rule applied to
    each approximate end. Before, such ranges were left to the model, whose window had only to
    be within 15 minutes of the stated times. A bare first time after "between approximately"
    was also read as a 24-hour time: "2:06" in "between approximately 2:06 and 2:22 p.m." was
    2:06 a.m., so a model's window twelve hours off passed `check_window`.
  - Each time an approximate range states must be one instant in the zone, as each end must
    (`StatedWindow.stated`): on the night the clocks skip 2 a.m., "between approximately 2:05
    and 2:55 a.m." is refused although its widened ends exist.
  - Code's reading of a time of day always wins over the model's window when the model's
    words read as one range. Before, it won only when both ends were within 15 minutes, so a
    model's 8:06 to 8:13 p.m. for "about 7:58 p.m." was kept.
  - The model's window is refused, and code reads the claim's own range, when:
    - the model's words are cut from a longer range the claim writes ("7:58 p.m." from "at
      approximately 7:58 p.m.", "10:00 a.m." from "after 10:00 a.m.", one end of a range),
      or lie inside quoted words;
    - the words give a time of day but no date;
    - the template is a count or an absence and the words leave an end open ("before",
      "after", "since", "beginning at", "by 9 p.m.", "from May 1" with no end). Before, the
      model's open edge was accepted, so a count or absence could search less than the words
      say. Code reads such ranges by R5 (extraction edges) or fill c (rest of the day), or
      refuses them.
  - An open range with a time of day ("after 10:00 a.m. on May 7") stays on that day: its open
    side is a stated time or that day's midnight. Before, an event's end went unchecked, up
    to 400 days.
  - Whole months. `check_window` accepts exactly the whole months the words state ("In April
    and May 2023" is April 1 to June 1; "in May 2023"; "during 2023"), never one of them or a
    month between two stated ones (`months_stated`). `coverage_gap` now refuses a claim dated
    only by a month or a year (outside quoted words) that no time range tests. Before, "In
    April 2023, PETROV wrote ..." could be judged on its sender alone.
- Where: PR #255
- Verified: new `tests/test_fill_windows.py` (67 tests, synthetic case01), covering:
    - the bounds of every approximate form, at their boundary instants, for record_time,
      no_contact and message_count;
    - the clocks skipping and repeating an hour in New York (March 8 and November 1, 2026);
    - a written zone the phone is not in, and an examiner-given zone through `device_zones`;
    - cut, dateless and quoted model words, and the open-edge refusals for counts and
      absences;
    - event open ranges kept on one day;
    - the month forms read and refused, and the month coverage gap.

  Four existing expectations changed on purpose:
    - "between approximately 9:10 and 9:40 p.m." and "between about 9 and 11 p.m." are now
      read (the tests keep "roughly" as unread);
    - a zone after dateless model words is now caught on the claim's own range;
    - a model window whose words are cut from the claim's range ("March 9, 2026" of "between
      March 9, 2026 and March 12, 2026") gives way to code's reading of the claim, which is the
      same range (`tests/test_account_names.py`).

  Replay of stored model answers from two practice phones (no model call), 2026-11-10: per-claim results are in the validation fix-round notes in project files, not in the repo. `make check` on the merged branch: see the PR.
- Open: unmeasured on a model run; the points below are open.
  - The 8 minutes on each approximate end extend the signed "about" rule. That needs Arsh's
    confirmation (rulings note W1).
  - An exact message count over an approximate edge can still fail on a message at the edge
    (W2).
  - Parts of the day are still refused (W3).
  - "on March 20 and March 23" is still read as a span (W4).
  - Time-first "after 10:00 a.m. on May 7" in an absence is still the rest of that day (W5).
- Affects: verdict path (more ranges read by code; some model windows are refused; a claim
  dated only by a month or a year now needs a time range). Fails closed. No privacy, network
  or customer-facing change.
- Status doc: pending: in "Other gaps" (section 8, assumption filler limits), replace
  '"between approximately X and Y", 24-hour times and zones other than US and UTC are left to
  the model (#150)' with '"between approximately X and Y" is read by code as 8 minutes wider at
  each approximate end, and whole stated months are read; 24-hour times and zones other than US
  and UTC are left to the model; a count or an absence never takes the model's open edge'.
