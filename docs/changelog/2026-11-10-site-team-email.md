## 2026-11-10: Website contact address is now team@getmabillon.com
- Changed: Every address on getmabillon.com (index, about, demo, demo-thanks, 404, privacy and the
  demo form's "unavailable" message in `site/demo.js`) now reads team@getmabillon.com instead of
  support@getmabillon.com. Arsh moved getmabillon.com mail to Google Workspace on 2026-11-09; its
  MX records now point to Google, so Cloudflare Email Routing no longer forwards support@. The
  privacy page's Email and demo form sections now say mail goes to our Google Workspace inbox
  (was "forwarded by Cloudflare Email Routing to our team's Gmail inbox"), and its effective date
  moves to 10 November 2026. `demo.js?v=` moves on every page. The demo form still posts to the
  Worker at forms.getmabillon.com/demo; only its `NOTIFY_TO` secret (set in the Cloudflare
  dashboard, not in this repo) needs to become team@getmabillon.com. The README step says so.
- Where: PR #251 (branch claude/project-thread-gtr06l)
- Verified: `tests/test_site_assets.py` passes. No search hit for support@ remains under `site/`.
  Delivery to team@ and the Worker's send after the MX change are untested.
- Open: The app's Help tab (`core/support/contact.py`), docs and the license Worker still name
  support@getmabillon.com; that address works only if it is added as an alias in Google
  Workspace. The privacy wording needs Arsh's approval before merge.
- Affects: customer-facing contact address and the privacy page's description of email handling.
  No product, model or performance change.
- Status doc: no change
