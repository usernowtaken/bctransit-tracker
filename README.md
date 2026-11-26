# Bus Radar V4.0 Alpha 2 — Metro Vancouver Art & NIS Fix

## Railway setup (one replica)

1. Extract this archive directly into your existing repository root, preserving the existing Railway volume and variables. Commit and deploy.
2. In Railway → your Bus Radar service → Variables, set `TRANSLINK_API_KEY` to your TransLink developer key exactly as issued. Never commit the key or put it in browser JavaScript. Rotate the key if it has been exposed. No key is included in this archive.
3. Use an existing persistent Railway volume mounted at `/data` (or your existing mount path). Set `TRANSLINK_BUDGET_DB=/data/translink-budget.sqlite3` (adjust mount path). If `BCT_HISTORY_DB` points to an existing persistent directory, the budget defaults to the same directory; the existing history DB itself is not changed. Railway deployment with no configured persistent storage fails closed for TransLink. Do not delete the budget database or run multiple replicas with independent budgets. Local development defaults to `cache/translink-budget.sqlite3`.
4. Leave `TRANSLINK_DAILY_BUDGET` unset (default 950 attempts per rolling 24h) unless TransLink has explicitly approved a different allowance. `TRANSLINK_GPS_SECONDS` defaults to 20, minimum 15. Set a higher value if conserving quota. Deploy/restart after changing variables.
5. Select Metro Vancouver (Alpha). The browser initially checks the shared cache every 10 seconds (20 seconds in data saver mode). Expect an asynchronous first feed fetch and separate static metadata loading. Health checks do not start Vancouver polling. See `/api/health?system=vancouver` for status and quota (no key exposed).

## Quota and accuracy

- One shared authenticated worker, idle unless a Vancouver vehicle snapshot was requested in the last 35 seconds. All active browsers share the same upstream feed; browser refreshes don't directly invoke TransLink. Idle grace may consume a final request.
- 950 attempts per rolling 24 hours including failed requests; allocated caps: 760 GPS, 142 trip updates, 47 alerts (949 total by rounding). 51 requests are left outside these caps as a margin against the published 1,000. Other applications using the same key are NOT accounted for. Use a dedicated key. Budget reservations are SQLite-transactional and survive restarts on a persistent volume; if the DB fails the worker pauses rather than issuing unmetered requests. Daily budget increases require agency approval.
- GPS starts at ~20s while viewed; slows to at least 40s after 50% of GPS cap and 90s after 80%. Trip updates start at 120s and slow with GPS; alerts every 600s. All intervals are minimums, not a guaranteed refresh rate. 401/403 and 429 trigger shared backoff. Quota exhaustion leaves cached positions with an explicit status; there is no fabricated GPS. History is recorded only while tracking is active, and only for vehicle-provided timestamps in Vancouver.
- No authenticated requests when the key is missing. Static schedules are a separate public ZIP, fetched on demand then at most daily on success. A cached local index is loaded lazily. Vancouver uses bus/trolley routes, a near-term schedule service window, only referenced shapes, per-stop timetable caches, shared enriched snapshots, unchanged revisions, compressed HTTP responses, viewport culling and larger low-zoom clusters. All route groups are visible even for >300 buses; ungrouped list has a 300-row cap and search can narrow it. Vancouver off-route/NIS inference and route-aligned bearing are deferred pending scale/accuracy testing; raw bearings are used. Selected-marker extrapolation is disabled for Vancouver. BC Transit systems retain their previous rates and behavior.
- Vancouver fleet numbers/model labels are preliminary candidate matches, not verified live assignments. Unknown numeric display labels can be shown with unknown model. Every Vancouver bus uses PLACEHOLDER / N/A; existing BC Transit drawings are preserved. No simulated train or ferry locations. If the feed includes non-bus records, known non-bus routes are excluded once static metadata is available.
- Official API: https://www.translink.ca/about-us/doing-business-with-translink/app-developer-resources/gtfs/gtfs-realtime ; static schedules: https://www.translink.ca/about-us/doing-business-with-translink/app-developer-resources/gtfs/gtfs-data ; terms: https://developer.translink.ca/TermsOfUse/WebApi . Required attribution is displayed in the Vancouver map/sidebar.

**Alpha validation limits:** no network DNS access to TransLink in the build environment, so the supplied key, exact raw live descriptor format, live GPS cadence, static archive size and Railway RAM usage have not been verified. The GTFS protobuf dependency could not be installed locally; deployment installs it via requirements.txt. Offline budget/fleet tests and simulated integration checks do not establish live feed compatibility. First deploy is intended for testing, not production-grade service. Do not use the same key on another app during quota testing.

---

# V3.4.13 — iOS & iPadOS compatibility

This update builds on V3.4.12. No Apple developer account, native app, or additional hosting is required. Recommended target: iOS/iPadOS 16.4 or later; use a current Safari release. Apple touch devices get Home Screen installation help, including desktop-style iPad user agents; portrait touch tablets use the bottom sheet, wide landscape tablets use the split view. Keyboard/viewport changes and safe-area offsets are handled without disabling pinch zoom. Resume, back/forward restore and reconnection refresh the live map, selected arrivals and open departures panel. GPS consent remains opt-in; stale location callbacks are rejected after switching systems or hiding location. Offline shell caching does not cache API data or map tiles.

Install: open the HTTPS Railway URL in Safari, use Settings → Home Screen → Install Bus Radar for instructions, then Safari Share (or More) → Add to Home Screen → enable Open as Web App if offered → Add. See https://support.apple.com/en-ca/guide/ipad/ipad8f1f7a29/ipados .

Testing: see tests/mobile_browser_check.py and tests/test_apple_v3413.cjs. Physical iPhone/iPad testing is still required for Safari keyboard, permissions, safe-area and Home Screen behavior. Browser smoke tests use Chromium with Apple user-agent/touch profiles and mocked feed data, not WebKit or real GPS. Push notifications and background tracking are not implemented.

---

# BC Transit Bus Radar V3.4.12 — Cowichan Valley + Kelowna Gen 4 art reference

Built on V3.4.9. Original fleet sheet artwork and its cropped illustrations remain unchanged; the uploaded regional and LFSe PNGs are included.

- **Cowichan Valley** is a fourth selectable system with its own BC Transit GTFS
  and live vehicle/trip/alert feeds (`operatorIds=10`). Shows local routes and
  the commuter 66 CVX/99 SVX into Victoria plus route 70 NCX toward Nanaimo.
  The map and GPS bounds include both destinations; shared data and history are
  independently scoped under `cowichan`. Includes mobile system picker, route
  shortcuts, vehicle search/sharing, routes/stops and GPS history support.
- **Cowichan fleets:** model candidates for Vicinity 30-foot 40xx, Vicinity
  35-foot 44xx, suburban 2008 NovaBus 9290–9300, 2022 ARBOC 2842–2844,
  other light-duty models marked unknown, and broader provincial NovaBus
  production families as model-only fallbacks. Published assignments and recent
  tracker observations are documented in `REGIONAL-FLEETS.md`.
- **Regional Gen 4 photo:** identified NovaBus LFS Gen 4 buses in Kelowna,
  Chilliwack/FVX and Cowichan now use the supplied Gen 3 reference image.
  Their model labels and filters remain Gen 4; image is a reference, not an
  exact depiction of those buses. Genuinely unrepresented vehicle types
  continue to show **PLACEHOLDER / N/A**.
- Only fleet numbers consistent with bounded GTFS feed label formats and model
  cohorts are presented as **candidates**, not independently verified fleet IDs.
  Production family is not evidence that a particular unit is currently based
  in Cowichan. On a mobile home-screen/PWA deployment, cache is bumped to 3.4.12.
- Back-end feed endpoints were confirmed from Mobility Database (operator 10).
  Automated tests cover Cowichan fleet mapping, feeds, cross-region history,
  and the Kelowna-only image override. Live feed behavior on Railway still
  requires checking a deployed instance during service hours.

---

# BC Transit Bus Radar V3.4.6 — regional model and placeholder expansion

This release builds on V3.4.5, with all supplied PNG artwork unmodified.

- **Kelowna:** separate 2006/2007/2008 Gen 2 NovaBus groups; 2009 Gen 3;
  2013/2015 and 2017 Gen 4; 70xx electric (provisional); historical
  Grande West/Yaxing Vicinity 3007/3011/3012; reported Vicinity 35-foot
  4400/4403; and individually documented 2024 ARBOC 2922.
- **Chilliwack/FVX:** add 4034, named 4401–4402 and 4439–4441 Vicinity
  35-foot units, early Vicinity 3005, light-duty 27xx–29xx, and separate Nova
  production years. The broad 44xx fallback is a provincial *model candidate*,
  not verified Chilliwack allocation.
- **Abbotsford/Mission within the combined Chilliwack/FVX feed:** classify
  1148–1277 XN40 CNG and 4200–4248 Vicinity 30-foot CNG; the exact allocation
  varies. Observed vehicles include 1214/1219 and 4232/4233.
- **Artwork:** preserve all originals exactly. If the matching drawing is not
  in this project, the details panel **and artwork gallery** display the
  literal text `PLACEHOLDER / N/A` rather than misleading art. This includes
  early Vicinity, Vicinity 35-foot, Vicinity 30-foot CNG, ARBOC and Gen 4 LFS.
  Existing Nova Gen 2/3, Nova LFSe+, Vicinity 30, and XN40 reference art remain.
- Added model-filter dropdown entries for new Vicinity families and bumped the
  PWA service-worker shell version so Android gets the latest UI.
- **Uncertainty:** Current physical fleet identity inferred from GTFS-RT
  labels/descriptor IDs is a candidate, not independently verified. A model
  production range does not prove a vehicle is currently based in that system.
  Do not use unknown or arbitrary ID suffixes as confirmed fleet numbers.

See `REGIONAL-FLEETS.md` for the scope, examples, and source references.

**Install:** unpack the ZIP into your GitHub project, commit/push, then redeploy
Railway. Preserve your existing `BCT_HISTORY_DB`, Railway volume, and settings.
For a bus that still reads unknown, inspect the raw Feed label and Feed vehicle ID
in the Technical details section and send both values for further debugging.

---

# BC Transit Bus Radar V3.4.5 — regional fleet detection improvement

This update builds directly on V3.4.4 without modifying the original supplied
bus drawings or changing the regional UI, GPS trails, routes, favourites, etc.

- Improve Chilliwack/Kelowna identification from `VehicleDescriptor.id` or
  `FeedEntity.id` when the feed does not contain a usable `label`. Previously
  these fallback IDs were accepted only when exactly four digits long.
- Recognize bounded 10-digit `3131xx` candidate identifiers for regional feeds
  *only* when their final four digits match that region's mapped fleet series.
  Preserve Victoria's stricter, already-tested `313135xxxx` convention.
- Recognize explicitly labelled numbers (e.g., `Bus #9217`) but never derive
  fleet numbers from an arbitrary suffix, a trip ID, or an unrecognized prefix.
- Extend regional series: Kelowna early 9201–9210 NovaBus LFS; Chilliwack
  Vicinity 30-foot 4060–4073 and Vicinity 35-foot 4400–4474. The 35-foot
  series deliberately has NO IMAGE because no accurate 35-foot art was supplied.
- All feed-derived fleet IDs are shown as candidates, not independently verified
  physical registrations. GTFS realtime does not guarantee that labels and IDs
  are fleet numbers.

**Live-feed limitation:** This package was regression-tested offline. The public
GTFS-RT binary endpoints could not be downloaded from this environment, so their
current `label` and `id` fields were not directly examined. If a vehicle still
shows unknown, expand **Technical details** in its profile and inspect **Feed
label** and **Feed vehicle ID**. That distinguishes unsupported label formats
from missing fleet information. Do not guess numbers from the route or position.

Deploy normally by committing the full ZIP contents to GitHub and redeploying
Railway. Keep the existing Railway volume, `BCT_HISTORY_DB`, and settings.
The V3.4.5 service-worker cache name avoids a stale mobile build.

---

# BC Transit Bus Radar V3.4.4 — regional feature parity

V3.4.4 brings Greater Victoria's existing features to **Kelowna** and **Chilliwack / Fraser Valley Express**, using the same UI and controls. No bus artwork has been changed. Both regions now support fleet-number favourite/share links and fleet-number last-known history lookups when the feed identifies the fleet number.

### What is available in all three regions

- Live buses, route/direction search and filters; route shapes, stops, stop ETAs, and next *different* scheduled route when static GTFS vehicle blocks are available
- User-friendly NIS inference (generic destination labels and 100 m off-route heuristic), route-aligned bearings when GTFS shape evidence is good, optional motion smoothing
- GPS trails and activity history, saved routes/stops/buses, shared bus links, last known GPS fix labelled **NOT LIVE**
- Realtime/scheduled route-based nearby departures; mobile bottom sheet with direction swiping, desktop map hover or Android map taps
- On-demand service alerts, amenities with evidence/unknown labels, bus drawings or **NO IMAGE** when appropriate
- Light/dark mode, colour/spacing/motion customization, installable Android PWA, Lite/data-saver modes

### Region-specific precautions

- **Chilliwack/FVX** uses a shared Fraser Valley GTFS feed (operator 13). Live buses, *newly recorded* GPS history, stop catalogue, departures, next-route block predictions and service alerts are now scoped to the displayed routes (51–59, 66, 71, 72). This prevents Abbotsford/Mission services from appearing by accident. Operator-wide alerts without resolvable route/stop/trip selectors are intentionally omitted rather than incorrectly assigned to Chilliwack.
- **Kelowna** uses operator 47's feed separately. Its newer 70xx electric identification is still a provisional fleet-series match. Verified small-bus drawings are not available and show **NO IMAGE**.
- **Fleet number reliability:** labels are matched only to known, region-specific four-digit fleet ranges. A raw four-digit vehicle descriptor ID can be used as a tentative fallback; arbitrary suffixes and trip IDs are never treated as fleet numbers. Unknown units stay unknown.
- **Amenities:** USB charging and interior LCD installation cannot be verified per regional bus from GPS feeds. Such features remain **Unknown** where evidence is insufficient.
- Scheduled block continuations, NextRide and realtime ETAs depend on region-specific published metadata; missing data is never filled in with invented timings. Realtime coverage may differ between systems.
- Settings and favourites are stored in the browser. Previously stored favourites, UI customization and SQLite history are not reset. The SQLite history database adds a backward-compatible `fleet_number` column and index for new observations; existing history records remain available.

### Deployment

Replace project files in GitHub, **commit and push**, and deploy the newest commit on Railway. The Dockerfile includes all backend modules, including `service_alerts.py`. Keep your existing `BCT_HISTORY_DB`, Railway volume, and `CARTO_BASEMAPS_KEY`. The PWA cache in that baseline is **v3.4.4** (raised to **v3.4.5** in this update).

### Tests

Offline regression checks cover shared-operator route isolation, public stops, scheduled/live departures, scoped alerts, raw fleet identifiers, next-route blocks, saved last-known history, and correct historic storage. The full GTFS-Realtime protobuf feed-decoding test needs the real package from `requirements.txt` and remains a deployment/live-environment check. 

---

## V3.4.3 — Passenger-first interface cleanup

This release reduces visible explanatory text, keeps the useful information at the top of a bus profile, puts detailed stop lists behind an extra disclosure, and groups common actions into compact rows. Original fleet art, backend, GPS history, animations, NIS and route logic are unchanged. Critical estimated-vs-live caveats remain accessible in **About estimates** and the route/status panels.

# BC Transit Bus Radar V3.4 — UI customization and smoother motion

A lightweight, unofficial GTFS-Realtime bus tracker for Greater Victoria,
Chilliwack and Kelowna, building on V3.2. Hosted as a Python service with a
vanilla JavaScript + Leaflet web UI and an installable Android PWA.

## New in V3.4

- **Dedicated Settings menu:** accessible from the map header, with light/dark
  mode, six accent presets and custom colour picker, normal/large text, three
  animation levels, map-centre reference (dot/crosshair/hidden), bus marker
  size, sidebar density, route labels, estimated motion, next scheduled trip
  overlay, Lite mode, data saver, and map hover/tap departure previews. Saved
  per browser; a reset button restores *display preferences only*.
- **Map-centre reference:** a small non-interactive marker stays at the exact
  visible Leaflet map centre, separate from the draggable departure preview
  pointer. Can be turned into a crosshair or hidden.
- **Route preview animations:** lightweight slide transitions when switching
  destination directions; gentle entry for nearby departures and the dashed
  next scheduled route. Entirely CSS-based, no big animation library. Both
  the browser's `prefers-reduced-motion` and the local Off setting disable
  decorative animation.
- **Visual GPS smoothing V2:** all selected-marker drawing paths use the same
  visual tracker. An old or repeated GPS timestamp cannot rewind it. Fresh
  GPS fixes smoothly reconcile with bounded short-range estimates instead of
  being snapped directly into place by map refresh. Real feed coordinates,
  ETAs, NIS inference and recorded histories are unaffected. Projection stays
  capped at 8 seconds and 30 m and is labeled as an *estimate*, not GPS.
- **Mobile-friendly controls:** the settings dialog scrolls internally, uses
  42–46px touch controls, and collapses less essential header buttons at
  narrow widths. UI customization respects the simple classic layout.

## Features retained from V3.3

- **NovaBus Gen 3 illustration:** 2009 Gen 3 buses without verified roof
  information use the **raised-rear** illustration by default; verified flat
  examples use the flat drawing. There is no picture-cycling timer. This is an
  illustration fallback, not a claim that every 2009 bus has a raised rear.
  Original bus PNGs are unchanged.
- **Next scheduled route on the map:** when an actively tracked bus has a
  next scheduled GTFS trip/shape, its vehicle page can overlay a **translucent
  dashed route** independent of the current route. The line and legend
  explicitly say it is a *scheduled, unconfirmed* future assignment. Toggle
  it off on the vehicle page. It may be absent if the vehicle block or trip
  geometry is not published.
- **Amenities in vehicle profile:** an optional collapsed section lists USB
  charging, NextRide LCDs, announcements, accessibility, racks and
  double-decker seating when applicable. Entries distinguish documented
  fleet equipment, probable/variable equipment, and unknown individual
  installations. Nothing is inferred from GPS. Bus #1192 and Vicinity 30s
  do not get a presumed NextRide LCD label. **Not a guaranteed per-bus
  equipment inventory.**
- **Route-first nearby departures:** an independent map-level departures
  panel, not a list of stop cards. Shows nearby *routes* with a switcher for
  multiple destinations/directions, up to three upcoming times, and Live
  vs Sched labels. A stop name and approximate walking distance appear
  secondarily to identify where to board. The backend checks up to ten
  nearby published stops when you open or change the panel's location.
- **Map pointer inspection:** when departures are open, mouse hover on desktop
  or map tap on touchscreen moves a small map dot and updates departures near
  that point. The location/reset button returns to your location (when
  enabled) or map centre. Only public GTFS stop IDs, not precise phone
  coordinates, are sent to the server for departures.
- **Android bottom sheet:** near-full-width collapsible panel, vertical
  swipe on handle to open/close, horizontally swipeable route directions,
  larger touch targets, and internally scrolling results. Opening the
  routes/details sheet hides nearby departures to avoid layered controls.
- **Perceived live movement:** an optional lightweight estimate for the
  **selected bus marker only**, based on its last *reported* speed and bearing.
  Projection is limited to 8 seconds / 30 metres, then held until a newer
  real GPS fix arrives. The UI explicitly distinguishes estimated motion
  from actual GPS, which may still update slowly. It does not affect ETAs,
  history, the next-trip route, NIS detection, or other buses. Disabled by
  reduced-motion browser preferences and optional under Display preferences.
- **Mobile focus fix:** prevents a previously offscreen sidebar from
  extending the page's scrollable area and pulling the map upward when
  choosing a destination. Preserves a one-screen PWA layout even at 320px.

## Important feed limitations

The published BC Transit feeds determine how frequently real vehicle
locations and trip predictions change. Refreshing the browser or animating
markers does not create new GPS observations. Live prediction labels depend
on fresh GTFS-RT data; otherwise times are explicitly from the published
GTFS timetable. Scheduled times still require this app's Python backend
connection; they are not an offline database on the phone.

Amenities references (public BC Transit announcements and FAQs):
- https://www.bctransit.com/open-data/
- https://www.bctransit.com/nextride/
- https://www.bctransit.com/victoria/news/article?nid=1529701083907

## Railway deployment

Unzip the *whole* project over the existing GitHub repository and commit.
Deploy that new commit in Railway (do not just redeploy an older image).
The Dockerfile explicitly copies `service_alerts.py`, fixing the earlier
V3.2 import failure. Preserve your existing `CARTO_BASEMAPS_KEY` and
`BCT_HISTORY_DB` settings and Railway history volume. Service worker cache
version in that release was `v3.4.0`; refresh the installed PWA after deployment.

Local Windows setup: `setup.bat`, then `start.bat`. Dependency list is in
`requirements.txt`.

## Validation

- JavaScript syntax check and NovaBus model-specific artwork test passed.
- 15 NovaBus/fleet artwork unit tests passed.
- 5 GTFS timetable/arrival tests passed with an offline test stub for the
  protobuf decoder, plus the 10-stop departure-board scenario.
- Simulated Chromium UI tests: 320px, 390px, 1366px; route direction switching,
  Live versus Sched labels, no horizontal overflow, mobile focus/scroll fix,
  next-trip dashed overlay and amenity cards.
- Fleet PNG integrity checked against the previous V3.2 release.
- Actual Railway deployment and real-time feed responsiveness require
  confirmation after deployment. The local environment lacks the GTFS
  protobuf module needed to run the full backend without test doubles.

V3.4 uses `web/motion.js` as a small dependency-free visual-only motion
engine; the only new build assets are `web/motion.js` and `web/v34.css`.

## V3.4 verification

- New motion engine passed tests for timestamp monotonicity, bounded forward
  estimates, gradual new-fix reconciliation, and disabled-smoothing behaviour.
- Integrated frontend tested in a local, offline Chromium harness with a
  simulated Leaflet map and synthetic vehicle updates at 390px and 1366px.
  No JavaScript errors; centre marker tested against actual map geometry.
- Settings dialog interaction/layout tested at 320, 390, 720, 1366, and
  1920px with no horizontal overflow, including accent and motion choices.
- Existing NovaBus per-fleet artwork test passed. All original bus PNG assets
  are kept unchanged from V3.3.
- Real BC Transit feed and Railway deployment still require live verification.


## V3.4.1 — Kelowna/Fraser Valley model artwork

- Victoria #9434 displays the **exact supplied** `nova_smart.png` Smart LFS drawing, distinct from generic LFS references.
- Kelowna's **likely** 70xx electric NovaBus family displays the exact supplied `nova_lfse.png` LFSe+ drawing. Number-to-model mapping is **provisional** until verified against a current fleet roster. Do not treat this as a GPS-confirmed bus model.
- Kelowna 6000–6029 / 92xx–94xx and Fraser Valley LFS series can use the existing Gen 2/Gen 3 reference drawings. These are fleet-series appearances, not proof of current local assignment.
- Known small 28xx/29xx community / light-duty series display an intentional **NO IMAGE** placeholder in the bus profile. Some are ARBOC-type buses on regular routes; do not call every one handyDART.
- Regional fleet identification accepts explicit four-digit BC Transit vehicle labels (and the previously observed numeric format when the candidate is within a recognized regional model range); unrelated labels stay unknown. Only numbers reported in GTFS vehicle labels are recognized, never fabricated from trip IDs.
- Both new images are copied byte-for-byte; all prior illustrations are preserved unchanged.
- New PWA asset cache: v3.4.1.


## V3.4.3 — Status, bearing and navigation refinement

- Generic multi-terminal route labels (e.g., Royal Oak Exch/Westhills Exch) are tagged *likely NIS*, distinct from true off-route distance inference. Directional labels such as `to Royal Oak Exch` stay in service. Labels are heuristic, not confirmation of physical destination signs.
- Marker arrows use the ordered geometry of the bus's assigned GTFS trip where the GPS fix is recent and near the shape; ambiguous or contradictory cases retain the original feed bearing. Feed heading is never altered.
- Next scheduled route skips same-public-number return trips in the GTFS block, up to 12 hours after the current run; it never implies a confirmed duty change. Dashed next-route overlay remains optional; its floating map legend was removed.
- Stronger sticky `Routes & buses` navigation in profiles, with a desktop map shortcut and mobile route-return button.
- Frontend and PWA versions updated to 3.4.2.

## V3.4.12 asset update

- Added project-owner supplied transparent PNG art for the 35-foot Vicinity, old HandyDART/cutaway, and new HandyDART/cutaway.
- Central Fraser Valley Vicinity 30′ CNG now uses the existing Vicinity 30′ reference image.
- The 2013 Grande West / Yaxing Vicinity now uses the new 35-foot Vicinity reference image, per project-owner request.
- Kelowna Gen 4 Nova buses still use the Gen 3 drawing as a model reference.
- Existing gallery PNGs with opaque white backgrounds were cleaned to transparent for consistent display.

## V3.4.12 LFSe artwork refresh

- Replaced `nova_lfse.png` with the newly supplied LFSe drawing.
- Removed the connected exterior white background from the new LFSe image for gallery/detail consistency.
- Gallery now reflects the new LFSe art automatically via the updated asset file and cache version bump.

## V3.4.12 — gallery refresh and cache fix

- Rebuilt the vehicle gallery with all new supplied PNGs present, a cleaner responsive layout, and one remaining Gen 4 placeholder.
- Fixed gallery link to request `/fleet-gallery.html?v=3.4.12`.
- Set gallery HTML to revalidate instead of retaining stale 24-hour cache; versioned all gallery PNGs and detail view bus image requests.
- The full project is packaged at ZIP root for deployment (no extra `busradar_...` parent folder).

## V3.4.12 — Compact gallery

- Reworked fleet-gallery.html to visually match Bus Radar's classic-dark app styling: neutral grey, slim borders, compact typography, and small artwork cards.
- Shows each of the 15 distinct supplied vehicle drawings once, rather than repeating images in reference-art sections.
- Moved the requested CFV/Yaxing/regional Gen 4 substitutions and remaining missing-art information to one collapsed details section.
- No changes to fleet detection, live tracking, image bytes, or model-to-art mapping.
- Gallery and app cache versions bumped to 3.4.12.

### V3.4.12 regional Gen 4 art revision (display version unchanged)

Chilliwack/FVX and Cowichan identified NovaBus LFS Gen 4 buses now select `nova3.png`, matching Kelowna's existing fallback. Fleet model/generation identification and the gallery's compact layout are unchanged. A separate internal cache revision ensures the same-version PWA refreshes the updated logic.

## V3.4.12 — Mobile UI overhaul
- Map-first startup; mobile navigation for Routes / Bus details, Departures and Near me.
- The Leaflet container uses the remaining screen height above the bus panel instead of extending underneath it. Selecting a bus recentres it in the visible map.
- One vertical scrolling surface for the route list and vehicle details, with a persistent sheet handle and Map button. Tap or swipe the handle to expand/reduce; swipe down from the reduced panel to close.
- Search expands the panel, avoids duplicate clear controls, and adapts to the visual viewport when the keyboard opens. A selected bus remains selected when returning to the map; reopen using Bus details.
- Mobile settings remain accessible at the top, including a reset-map button. Light/dark styles, fleet illustrations and regional fleet mappings are preserved. Phone landscape is covered through a coarse-pointer breakpoint.
- Offline browser smoke test: `python tests/mobile_browser_check.py` (optional Playwright dependency). Tests use synthetic vehicle responses and no external map service; real device, GPS permissions, actual GTFS and Railway deployment require live validation.


## Alpha 2 additions
- Added cleaned transparent TransLink user-supplied drawings across the Metro Vancouver fleet gallery and vehicle panel.
- Added provisional Solaris Trollino 18 support for fleet 28201.
- Reduced false generic-NIS classifications for route labels containing `Via`, including routes such as 52, 15, 40 and 26.
