## 2026-11-10: The examiner can give a phone's time zone when its extraction records none
- Changed: New expert action `set_device_zone` (`core/review/actions.py`). It is available as
  `mabillon set-device-zone --device --zone --by`, and as a "Save time zone" field on the
  devices table in the app, shown only for a phone whose extraction records no zone. Before
  this, a phone with no recorded zone could have no time range read: every timed claim on it
  stayed untested ("the phones do not share one known time zone").
  - The zone must be an IANA place name ("America/New_York"). Abbreviations and offsets are
    refused, since they do not say when the clocks change.
  - It is refused when the extraction records a zone: the source's own is never replaced.
  - An empty zone clears it.
  - The audit log is the record (action `device.timezone`), as for phone names. The report lists
    the zone in Limitations as the expert's statement, not a finding (report 0.40.0).
  - Every reader of a phone's zone now goes through `core/zones.device_zones`, so the given zone
    is read alike everywhere: the filler, the checks, local time, timelines, paired selection
    and the report's "why" lines.
  - Giving, changing or clearing a zone after an audit marks that audit's verdicts as not
    current (`core/review/status.case_changed_after`), counted from the full audit a rules-only
    re-run reuses. The bundle check counts it among the inputs that may change a repair.
  - The validation driver gains `--phone-zone`. The zone is given only when the case is built,
    so a resume that names a different zone is refused.
  - Found on 2026-11-10: the public Android 12 and Android 13 Hickman packages
    (report.xml-only UFDRs) record no device zone, so the Android 12 shakedown tested 0 of 16
    claims.
- Where: PR #253
- Verified: `tests/test_device_zone.py` covers:
  - no range is read before the zone is given, and every reader agrees after;
  - the newest entry wins, and an empty one clears;
  - abbreviations and offsets are refused;
  - a recorded zone is kept;
  - expert only;
  - the report line passes the report text invariants, and the report still defines the
    verdict labels it uses;
  - a zone given after an audit makes its verdicts not current, also after a rules-only re-run.

  `tests/test_validation_run.py` also checks that `--phone-zone` is refused on a package that
  records a zone, and that a resume naming another zone is refused. `make check` ran on 2026-11-10 in the cloud container.
- Open: how often real Android exports lack a device zone is unverified; only the two public
  Hickman packages were checked. The given zone is the examiner's statement, and Mabillon does
  not check it against the records (for example, a phone that changed zones while travelling).
- Affects: capabilities (timed claims on such phones can now be tested); customer-facing (a new
  setup step and a new Limitations line). No privacy, network or verdict-rule change.
- Status doc: pending: under case setup, add "The examiner can give a phone's time zone when
  its extraction records none (listed in Limitations as the examiner's statement)."
