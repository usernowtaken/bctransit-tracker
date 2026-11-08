# BC Transit Bus Radar V3.2 — final interface polish

Features carried forward from V3.1: live fleet map, favourite buses/routes,
service alerts, historical GPS, activity timeline, shareable vehicle links,
vehicle/route filtering, mobile PWA, Greater Victoria/Chilliwack/Kelowna.

## V3.2 changes
- New Vicinity 30′ illustration from the supplied PNG, with only connected
  exterior white made transparent. The uploaded original is retained as
  `web/buses/vicinity30-user-original.png`.
- Removed the NovaBus roof appearance selector. Confirmed roof models use their
  fixed image; unverified 2009 buses alternate every 1.5 seconds.
- Removed personalized artwork copy from public-facing pages.
- Reduced the inferred off-route/NIS distance threshold to 100 metres.
  This is **not confirmation of NIS**; GPS drift and legitimate detours can
  cause false positives. Distinct repeated GPS observations are still required.
- Sidebar close/open now refreshes the Leaflet map after its CSS transition;
  a ResizeObserver handles unusual desktop widths and monitor scaling.
- Added an on-demand **Nearby departures** panel on the map, separate from the
  sidebar. It shows three nearby published stops, scheduled departures
  overridden by fresh GTFS-Realtime predictions when available, and four
  nearby reporting buses with the closest geographical stop to each.
  When browser location is enabled, it uses that location; otherwise it uses
  the current map centre. Only published stop IDs go to the server, never the
  browser's precise coordinates. Departures are refreshed on demand and at
  most once every 45 seconds while the panel is open.

## Deploy
As before: replace the files in GitHub and deploy the newest commit to
Railway. Keep CARTO_BASEMAPS_KEY and BCT_HISTORY_DB settings and the history
volume unchanged. The new service-worker cache version is V3.2.0.

Install dependencies listed in `requirements.txt` to run the backend locally.
