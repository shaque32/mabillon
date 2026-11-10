# Rulings needed: time ranges (fix/windows)

No frozen file needs a change for this branch. These are wording calls for Arsh. Nothing
below is built unless it says "built".

## W1. "approximately" on each end of a range (built; please confirm)

`stated_windows` now reads "between approximately X and Y" (also "from about X to Y",
"approximately between X and Y") as X - 8 min to Y + 8 min, and "between X and about Y" as X to
Y + 8 min. This applies the signed "about" rule (ABOUT_MINUTES = 8, case01 sheet C09) to each
approximate end. Only "about", "approximately" and "around" are read; "roughly", "circa" and
the like are still refused. Under that rule the reading is exactly the words, so it is no wider
for an event and no narrower for a count or an absence.
Options: (a) keep it (recommended); (b) read an approximate range only for events, as
the exact X to Y; (c) refuse approximate ranges again.

## W2. Exact counts over approximate or part-of-day edges (not built)

An exact count ("four calls between approximately 11:33 and 11:48 a.m.", "eighteen FaceTime
calls on the evening of May 9") can go wrong both ways. With a wider window, an extra call at
the edge fails a true claim. With a narrower one, a call at the edge is missed. Call counts
never fail (fill f), but message counts do.
Recommendation: count over the inner window (the words without "approximately": X to Y)
and over the outer one (X - 8 to Y + 8). The count passes or fails only when both counts agree;
otherwise it is inconclusive. This is a change to `core/audit/checks/count.py` and its version.

## W3. Parts of the day (C19, D20; A07, A12) (not built, guard kept)

"On the evening of May 9, 2023", "in the early hours of December 12, 2021". The guard stays.
Options:
(a) keep refusing (current; recommended until (b) is signed);
(b) fixed hours, with a narrow core and a wide hull for each part. Example: evening is
    18:00-21:00 core and 17:00-24:00 hull; early hours are 01:00-05:00 core and 00:00-06:00
    hull. An event is tested on the core and an absence on the hull. A count is decided only
    when the core and the hull agree (as in W2).
The hours themselves are the ruling: no claim text fixes them.

## W4. Dates joined by "and" without "between" (not built)

`stated_windows` (by docstring) and `check_window` read "on March 20 and March 23, 2026" as
March 20 through March 23. That is wider than the words for an event (a call on March 21
passes), and for an absence a contact on March 21 fails a true claim. "Between March 20 and
March 23" is a true range and is not affected.
Recommendation: read "A and B" with no "between" or "from" as two days. Either give it one
assumption per day (both must pass), or refuse it until that exists.

## W5. "after 10:00 a.m. on May 7, 2023" in an absence (not built)

Fill c reads it as the rest of May 7, and so does `stated_part_day`, whichever order the claim
writes. Written date first ("On May 7, 2023, there was no contact ... after 10:00 a.m.") it
plainly means that day. Written time first ("there was no contact ... after 10:00 a.m. on May
7, 2023"), it may mean from then on, to the extraction's end. In that case the rest of the day
is narrower than the words, and an absence could pass that a contact on May 8 breaks.
Recommendation: keep fill c for the date-first form. For the time-first form, use R5's
extraction edge, or refuse.

## W6. "beginning at approximately 8:00 p.m." (C17) (not built, refused)

Reading it as "at about 8 p.m." would test that a message was sent near 8 p.m., not that the
exchange began then: an earlier message makes the claim false. Recommendation: keep refusing.
Another option is for an event to need a record at about the time and none in the hour before.
That is a new check.
