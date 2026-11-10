## 2026-11-09: CLAUDE.md: fast cases on Opus through a zero-retention Anthropic account (#250)
- Changed: Arsh signed new CLAUDE.md wording on 2026-11-09 ("approved", 23:54Z) after a cost
  study on 2026-11-09 estimated our own model server (deploy/model_server, PR #244: AWS
  p5en.48xlarge, 8 x H200, about $63/h on demand by a web price, one request at a time, a cold
  start per case) at $47 to $153 a case. That is an estimate: the server was never booted and its
  speed is unmeasured. Opus 5.5 doing every job cost $4.59 on synthetic case01 (measured
  2026-11-08 through the Anthropic API from a cloud container, list prices on reported tokens). Every model job may now run on the cloud
  model once a case opts in. The only cloud model in core/ stays Claude through the Anthropic
  API, now with a key from an organization that has zero data retention in writing (Mabillon's,
  or the examiner's own organization's). The provider keeps no prompts or answers; retained modes
  such as the Batch API are never used; Mabillon runs no server and keeps no case data. Cloud AI
  is the default choice for an ordinary case; CSAM-flagged cases and cases whose order does not
  allow it stay local; never "offline". Each job uses one model for the whole case, and the report
  names the model for each job. Supersedes the plan C server wording signed 2026-11-08 (#245).
- Where: PR #250
- Verified: make check (see PR). Rules text only; no code changed.
- Open: the code still sends only stance labels to the cloud, on the examiner's own key; routing
  the other jobs, a Mabillon key per pilot and the setup default come as their own PRs. Zero
  retention needs a written Anthropic agreement, which needs the company to exist. Customer
  privacy text is a separate sign-off.
- Affects: privacy (rules for future code), customer-facing claims (no server, no case data kept)
- Status doc: no change
