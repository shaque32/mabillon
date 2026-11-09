## 2026-11-09: Website About us page with the two founders (#PR)
- Changed: New page `site/about.html` (getmabillon.com/about) with short bios and photos of
  Mir Haque (co-founder and CEO) and Shayan Haque (co-founder and CTO), linked from the header
  (hidden on phones, as the other section links are) and from every page's footer. Arsh asked for
  it on 2026-11-09. Bio facts come only from the team slide of the accelerator pitch deck
  (2026-11-07); the photos are the deck's headshots, resized to 320 px JPEGs in `site/img/` and
  served from the site itself, so the privacy page's "fonts and images are served from this site"
  stays true. `styles.css` gains the `.people` rows and every page's `?v=` moves with it.
- Where: PR #PR
- Verified: `tests/test_site_assets.py` passes with the new `?v=`; page checked by screenshot at
  1280 px and 390 px wide in headless Chromium (2026-11-09, cloud container).
- Open: bio wording waits for Arsh's approval before merge. Whether Mir's FBI line needs FBI
  pre-publication review is unconfirmed (it is already in the pitch deck). Whether "MS in
  Analytics at Georgia Tech" is finished or in progress is not recorded; the page repeats the
  deck's wording.
- Affects: customer-facing claims (the site now names the founders and Mir's FBI background); no
  product, privacy or performance change.
- Status doc: no change
