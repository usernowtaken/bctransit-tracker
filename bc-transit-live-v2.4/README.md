# Victoria Bus Radar — V2.4

An unofficial, lightweight Greater Victoria BC Transit live bus map. Desktop browser,
mobile browser, and Android home-screen PWA. This version builds directly on V2.3.

## What is new in V2.4

- Installable PWA (Android Chrome, compatible Chromium browsers), with 192/512 icons and maskable icon.
- Mobile map, route list and selected-bus bottom sheet improvements.
- Reopen at your saved map location and zoom, with the existing reset-view button.
- Offline **interface shell** cached; **live GPS, route API responses and map tiles are never
  cached by the service worker**. Map tiles and the Leaflet CDN still need internet access.
- Public-hosting support (`PORT`, `--host`, and a Railway-compatible Dockerfile).
- CARTO key can be provided using a deployment environment variable, without committing
  it to source files. Browser basemap keys are inherently visible to visitors.

## Local Windows launch

1. Extract the ZIP. Python 3.10 or newer is required.
2. Run `setup.bat` the first time to install `gtfs-realtime-bindings` and `tzdata`.
3. Enter your existing CARTO Basemaps key in `web/config.js`, or set
   environment variable `CARTO_BASEMAPS_KEY`. You may leave it empty for the OSM fallback.
4. Run `start.bat`. Open **http://127.0.0.1:8765**.
5. To test installability on desktop Chrome, use its Install option. Android installation
   requires opening the **public HTTPS website** on your phone: localhost on your PC is
   not reachable from Android, and an ordinary HTTP LAN address is not installable.

## Publish on Railway (GitHub workflow)

1. Create a new GitHub repository and upload **the project files** (the root should contain
   `Dockerfile`, `app.py`, `requirements.txt` and `web/`). Avoid committing
   your personal `web/config.js` key; leave `cartoKey: ''` in that file.
2. In Railway, choose **New Project → Deploy from GitHub repo**, then select the repo.
3. Railway builds the provided `Dockerfile`. The server binds to `0.0.0.0` and reads the
   Railway-provided `PORT` variable automatically. Leave the start command at its Docker
   default. If you want a health check, set its path to `/api/health` in Railway settings.
4. Set a Railway service variable named `CARTO_BASEMAPS_KEY` to your key. This is sent to
   browser clients via `/config.js`, so create a *separate* CARTO key restricted to the
   production website domain. Change any existing key restrictions to permit your domain.
5. Under **Settings → Networking**, generate a public Railway domain (or attach your own).
   Confirm `https://your-domain/` shows the map and `/api/health` responds.
6. Disable Railway Serverless/App Sleeping for this service if you want reliable instant
   opening. Hosting may cost money; check Railway's current billing and quota.
7. The app is suitable for a first public test, **not yet hardened for large public traffic**:
   monitor usage, logs and upstream GTFS fetch reliability. Railway's filesystem is
   ephemeral; GTFS schedule cache can be repopulated after deployment/restart.

## Android home-screen install

1. Open your **HTTPS-hosted** site in Chrome on Android.
2. Open the Chrome menu → **Install app** or **Add to Home screen**.
   The website may also expose a small download/install icon in the map top bar.
3. Launch **Bus Radar** from your home screen, in its own standalone window.
4. No APK, Google Play account or Android Studio is needed.

## Key files

| File | Purpose |
|------|---------|
| `app.py` | Original V2.3 backend + public host/port and configuration endpoint |
| `web/app.js` | V2.3 tracker + saved map viewport and mobile detail opening |
| `web/classic.css`, `web/classic-dark.css` | The existing simple light/dark styles |
| `web/mobile.css` | Mobile-only refinements |
| `web/pwa.js` | Installs the service worker and exposes a native install prompt |
| `web/sw.js` | Stores the UI shell only (no GPS, schedule APIs, config, or map tiles) |
| `web/manifest.webmanifest` | Android shortcut name, standalone display and icons |
| `Dockerfile` | Ready-to-configure public Railway deployment |

## Important limits and attribution

- **Not affiliated with or endorsed by BC Transit.** Live data comes from BC Transit
  published open data: https://www.bctransit.com/open-data/
- Next-run predictions from static GTFS block schedules remain **unconfirmed**.
- `OFF?` / `NIS?` are heuristic estimates, **not confirmed Not In Service** statuses.
- The app cannot speed up BC Transit's underlying GPS feed. Client checks are around 5s;
  backend source fetching defaults to 15s.
- Map tiles and Leaflet are supplied by third parties. Keep attribution to CARTO and OSM.
- Public basemap API keys are visible to browsers even when served via environment vars;
  **restrict them to your domain** in the CARTO dashboard.
- No simulated vehicles are included. If the feed fails, the map reports a feed issue.
