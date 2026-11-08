"""Small, on-demand GTFS-Realtime Service Alerts parser for BC Transit Bus Radar.

Alerts are informational. Route relevance must be based on GTFS entity selectors,
not on text or the visible route number alone. No data is fabricated when the
provider's feed is unavailable.
"""
from __future__ import annotations
import time
from typing import Any

EFFECTS = {
    1: 'No service', 2: 'Reduced service', 3: 'Significant delays',
    4: 'Detour', 5: 'Additional service', 6: 'Modified service',
    7: 'Other effect', 8: 'Unknown effect', 9: 'Stop moved',
    10: 'No effect', 11: 'Accessibility issue',
}


def _translated(field: Any) -> str:
    choices = list(getattr(field, 'translation', ()))
    for candidate in choices:
        if str(getattr(candidate, 'language', '')).lower().startswith('en'):
            return str(candidate.text).strip()[:1600]
    return str(choices[0].text).strip()[:1600] if choices else ''


def _active(periods: Any, now: int) -> bool:
    periods = list(periods)
    if not periods:
        return True
    for period in periods:
        start = int(period.start) if period.HasField('start') else 0
        end = int(period.end) if period.HasField('end') else 2**62
        if start <= now <= end:
            return True
    return False


def parse_alert_feed(body: bytes, pb: Any, now: int | None = None) -> dict[str, Any]:
    now = int(time.time()) if now is None else int(now)
    feed = pb.FeedMessage()
    feed.ParseFromString(body)
    if not feed.HasField('header'):
        raise ValueError('Missing GTFS-Realtime header in alerts feed')
    entries = []
    for entity in feed.entity:
        if getattr(entity, 'is_deleted', False) or not entity.HasField('alert'):
            continue
        alert = entity.alert
        periods = list(getattr(alert, 'communication_period', [])) or list(alert.active_period)
        if not _active(periods, now):
            continue
        selectors = []
        for selector in alert.informed_entity:
            trip_id = selector.trip.trip_id if selector.HasField('trip') else ''
            selectors.append({
                'route_id': selector.route_id if selector.HasField('route_id') else '',
                'stop_id': selector.stop_id if selector.HasField('stop_id') else '',
                'trip_id': trip_id,
                'agency_id': selector.agency_id if selector.HasField('agency_id') else '',
            })
        header = _translated(alert.header_text) if alert.HasField('header_text') else ''
        description = _translated(alert.description_text) if alert.HasField('description_text') else ''
        url = _translated(alert.url) if alert.HasField('url') else ''
        if not url.lower().startswith(('https://', 'http://')):
            url = ''
        # No HTML is trusted from the GTFS feed. The browser renders textContent only.
        entries.append({
            'id': str(entity.id)[:160],
            'title': header or EFFECTS.get(int(alert.effect), 'Service notice'),
            'description': description,
            'effect': EFFECTS.get(int(alert.effect), 'Service notice'),
            'url': url,
            'selectors': selectors,
        })
        if len(entries) >= 100:
            break
    return {'alerts': entries, 'feed_timestamp': int(feed.header.timestamp) if feed.header.HasField('timestamp') else None,
            'fetched_at': now}


def alert_applies(selectors: list[dict], route_id: str = '', trip_id: str = '', stop_id: str = '') -> bool:
    """Any GTFS selector can match, but all its fields must match together."""
    if not selectors:
        return True
    for selector in selectors:
        rid, tid, sid = selector.get('route_id'), selector.get('trip_id'), selector.get('stop_id')
        if rid and str(rid) != str(route_id):
            continue
        if tid and str(tid) != str(trip_id):
            continue
        if sid and str(sid) != str(stop_id):
            continue
        # Never match a stop-only alert to a route when the stop is unknown.
        return True
    return False
