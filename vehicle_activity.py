"""Build bounded, conservative activity timelines from observed vehicle GPS fixes.

Route fields are *reported* route labels, not a confirmation that a passenger
trip is in service. An off-route observation is NOT confirmed deadheading.
"""
from __future__ import annotations

ALLOWED_WINDOWS = frozenset((60, 180, 720, 1440))
OFF_ROUTE = frozenset(('far', 'possible_nis', 'likely_nis'))
MAX_EVENTS = 120
MAX_ROWS = 8000
GAP_SECONDS = 10 * 60


def build_activity(rows: list[tuple], system: str, vehicle_id: str, minutes: int,
                   now: int, truncated_samples: bool = False) -> dict:
    """rows: chronological (ts, lat, lon, route, trip_id, proximity_state)."""
    events: list[dict] = []
    current: dict | None = None
    previous: tuple | None = None
    switches = 0
    far_fixes = 0
    routes: set[str] = set()

    def status(route: str | None, proximity: str | None) -> str:
        if proximity in OFF_ROUTE:
            return 'off_route'
        if not route:
            return 'unreported'
        return 'reported'

    def begin(row: tuple) -> dict:
        timestamp, lat, lon, route, trip, proximity = row
        return {'kind': status(route, proximity), 'route': route,
                'start_ts': timestamp, 'end_ts': timestamp, 'fixes': 1,
                'start': [round(lat,6),round(lon,6)],
                'end': [round(lat,6),round(lon,6)],
                'trip_id': trip or None,
                'off_route_evidence': proximity if proximity in OFF_ROUTE else None}

    def append_current():
        nonlocal current
        if current is not None:
            events.append(current)
            current = None

    for row in rows:
        ts, lat, lon, route, trip, proximity = row
        route = str(route) if route else None
        row = (ts, lat, lon, route, trip, proximity)
        if route:
            routes.add(route)
        if proximity in OFF_ROUTE:
            far_fixes += 1
        kind = status(route, proximity)
        if previous is not None:
            prev_time, prev_lat, prev_lon, prev_route, prev_trip, prev_prox = previous
            gap = ts - prev_time
            if gap > GAP_SECONDS:
                append_current()
                events.append({'kind':'gap','start_ts':prev_time,'end_ts':ts,
                               'fixes':0,'route':None})
            elif prev_route and route and prev_route != route:
                append_current()
                events.append({'kind':'route_change', 'start_ts':prev_time, 'end_ts':ts,
                               'from_route':prev_route, 'to_route':route, 'route':route,
                               'fixes':0,'end':[round(lat,6),round(lon,6)]})
                switches += 1
        if (current is None or current['route'] != route or current['kind'] != kind):
            append_current()
            current = begin(row)
        else:
            current['end_ts'] = ts
            current['fixes'] += 1
            current['end'] = [round(lat,6),round(lon,6)]
            if proximity in ('possible_nis','likely_nis'):
                current['off_route_evidence'] = proximity
        previous = row
    append_current()
    limited_events = events[-MAX_EVENTS:][::-1]
    return {
        'system':system,'vehicle_id':vehicle_id,'minutes':minutes,
        'recorded_fixes':len(rows),'distinct_routes':sorted(routes),
        'reported_route_changes':switches, 'off_route_observations':far_fixes,
        'events':limited_events,'events_total':len(events),
        'events_truncated':len(events) > MAX_EVENTS,
        'samples_truncated':truncated_samples,
        'recording_since':rows[0][0] if rows else None,
        'server_now':now,
        'disclaimer':('Routes reflect published GPS-linked trip labels, not confirmed passenger service. '
                      'Off-route positions may be detours, stale assignments or deadheading. '
                      'Gaps are not filled in.'),
    }
