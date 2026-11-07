# Victoria Bus Radar V2.6 — Mobile comfort and low-end performance update

Unofficial browser-based live tracking for the Greater Victoria BC Transit fleet.
Built directly on V2.5: same light/dark classic maps, route search, follow bus,
route shapes and stops, possible NIS detection, next scheduled trip lookup,
public-hosting support, and Android installable PWA.

## V2.6 changes

- **One-handed mobile panel.** Open the bottom sheet using the large **Routes** button. Tap the grab handle to expand to nearly full screen or shrink back down. Drag the handle up or down to expand, shrink, or dismiss. Selecting a bus opens a details sheet automatically; closing it leaves a **Bus details** button for quick reopening.
- **Touch-friendly controls.** Larger route buttons, list rows, stop list rows, zoom controls and close buttons (approximately 44–50 CSS pixels), plus a 16px search field to avoid mobile browser auto-zoom. Route shortcuts scroll sideways instead of wrapping into multiple lines. Map stop markers have larger touch targets.
- **Lite mode** (ON by default on mobile; toggle from map header). Clusters buses at more zoom levels, draws fewer separate icons, and omits most map transitions on older devices. This only affects display detail, **not** which bus positions are received or how often BC Transit publishes GPS fixes.
- **Less redundant work.** Stop reattaching map click handlers every GPS refresh; avoid unnecessary fleet-list rebuilding; don't render an invisible list on mobile; reuse the arrival-time formatter; reuse current list scroll positions; check the backend less often on mobile (10 seconds versus 5 seconds on desktop), without modifying the upstream feed cadence.
- **Android PWA cache updated** to V2.6. Light/dark theme and existing V2.5 features remain.

## V2.5 changes

1. **Better off-route checks when a trip ID is missing.** A fresh live GPS fix can now
   be compared with the published shapes of the **reported route** even if the exact
   live `trip_id` can't be matched to GTFS. When there are multiple route variants,
   the nearest published variant is used to reduce false positives.
   - Farther than 600 m: `OFF?` on the first distinct GPS observation.
   - Farther than 600 m on at least two distinct GPS observations: `NIS?`.
   - If the reported route can't be matched to any published shape, GPS is stale,
     or required identifiers are missing, the result remains **Cannot determine**.
   - These indicators **never prove** Not In Service or deadheading. Routes can
     have detours, special operations, or stale assignments.
2. **Simplified vehicle details.** The Next Scheduled Trip panel now appears *below*
   the route/stops panel and follow controls. Technical fields (coordinates, trip
   ID, vehicle block, occupancy, feed route ID, etc.) are under the collapsible
   **Advanced vehicle data** section.
3. **Clickable all-stops list and map markers.** Select a bus, then click any of
   its stops on the map or in the sidebar. Each stop displays:
   - `Estimated arrival: HH:MM` **only** when BC Transit's fresh GTFS-Realtime
     TripUpdates feed has a stop-specific prediction (absolute time or delay).
   - Otherwise `Scheduled arrival: HH:MM` from static GTFS; no made-up live ETA.
   - Or `Arrival time not published` if neither is available.
   - Arrival checks are fetched only when a bus is selected, roughly every 20 s;
     the entire route geometry is cached separately to preserve map speed.
4. **Header cleanup.** Removed the "A faster way to find your bus" subtitle.
5. **CARTO zoom fix included.** Keeps UI zoom to 19 but only requests raster
   basemap tiles through zoom 18 when a CARTO key is configured.
6. **PWA cache bumped to V2.5** so installed Android shortcuts can load the new UI.

## Local setup (Windows)

1. Extract this ZIP into its own folder. Python **3.10+** required.
2. Run `setup.bat` to install `gtfs-realtime-bindings` and `tzdata` if needed.
3. Use your CARTO key in `web/config.js`, or set `CARTO_BASEMAPS_KEY` as an
   environment variable. **Do not commit your key to a public repo.**
4. Run `start.bat` and visit http://127.0.0.1:8765 .
5. Keep the Python server running while the tracker is in use.

## Updating your public Railway / GitHub deployment

1. Keep your existing Railway project, service, domain, and **CARTO_BASEMAPS_KEY**
   environment variable. Do **not** create a second service.
2. Replace the files in your GitHub repository with V2.6's project files.
   Keep the directory structure: `app.py`, `Dockerfile`, `requirements.txt`,
   `web/` and `tests/` at the top level. Leave `web/config.js` without a key
   if Railway supplies it as an environment variable.
3. Commit and push the updated files. Railway should redeploy automatically if
   the GitHub integration is enabled. View its deployment logs if it fails.
4. Reload the website. On Android, fully close and reopen the installed shortcut.
   If it still looks like an older version, revisit the live site in Chrome to let the new
   service worker activate, then reopen the installed app.

## Data sources and limitations

- Vehicle positions: BC Transit Victoria GTFS-Realtime VehiclePositions feed.
- Stop predictions: BC Transit Victoria GTFS-Realtime **TripUpdates** feed.
  Defaults to `https://bct.tmix.se/gtfs-realtime/tripupdates.pb?operatorIds=48`.
  Override with `BCT_TRIP_UPDATES_URL` if necessary.
- Route lines, stop names, scheduled stop times and blocks: static GTFS export.
- Fresh GTFS-RT arrival predictions are requested only for selected trips via
  `/api/arrivals?trip_id=...`. The new trip-update worker runs roughly every
  20 seconds independently of the vehicle feed. The backend does not calculate
  synthetic ETAs from vehicle speed or distance.
- A feed may omit or delay realtime predictions; scheduled times are not
  guarantees of actual arrival. Predictions also may not apply while a bus is
  deadheading/off-route.
- The frontend caches the *interface*, **not** live GPS, predicted arrivals, GTFS
  API responses, map tiles, or personal CARTO configuration.
- This project is **unofficial**, not affiliated with or endorsed by BC Transit.
  Provide attribution and comply with BC Transit's Open Data terms.

## Release testing

- V2.6 JavaScript syntax, Python syntax, and offline desktop/mobile interactions at 320px, 390px and 1366px tested. Offline tests use synthetic buses; browser access to localhost and live data is restricted here.
- The current mobile optimisation is a rendering trade-off: **Lite mode may group buses together at zoom levels where the desktop map shows separate route labels.** Zoom in or turn off Lite to see more individual markers.
- Confirm the new bottom sheet, map taps and PWA update on a physical Android device after deployment.


- Backend syntax checks passed. 13 targeted offline route-proximity / arrival
  tests passed (without the optional external GTFS decoder installed here).
- V2.5 browser checks with synthetic bus/trip/arrival data passed;
  these do not validate the actual BC Transit feed.
- Live feed integration and physical Android PWA installation have **not** been
  verified in this workspace. Your live hosted service is the right place to
  validate the trip-update feed's available fields and off-route thresholds.

## Files

- `app.py`: Python backend; vehicle and trip update feeds, schedule lookup,
  route proximity, `/api/vehicles`, `/api/route`, `/api/arrivals`.
- `web/index.html`: Layout and advanced-data section.
- `web/app.js`: Map, clickable stops, user interactions and arrival display.
- `web/classic.css`, `web/classic-dark.css`: Flat Google-Maps-like themes.
- `web/sw.js`, `web/pwa.js`, `web/manifest.webmanifest`: Android PWA support.
- `tests/`: Backend regression tests. With dependencies installed, run:
  `python -m unittest discover -s tests -v`.
