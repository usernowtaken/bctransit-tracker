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
version is `v3.4.0`; refresh the installed PWA after deployment.

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
