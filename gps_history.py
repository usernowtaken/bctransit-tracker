"""Bounded on-server history of publicly reported BC Transit vehicle GPS fixes.

No mobile user's position is recorded. One durable SQLite file is used for all
transit systems, with independent keys for each. Never insert stale replayed
snapshots or fabricate intermediate positions.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any

from vehicle_activity import ALLOWED_WINDOWS, MAX_ROWS, build_activity

RETENTION_S = 24 * 3600
MIN_TIME = 1600000000
MAX_API_POINTS = 500
WINDOWS = frozenset({15, 30, 60})


class GPSHistory:
    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(self.path), timeout=10, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA busy_timeout=10000')
        self.db.execute('PRAGMA synchronous=NORMAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS fixes (
                system TEXT NOT NULL,
                vehicle_id TEXT NOT NULL,
                gps_ts INTEGER NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                route TEXT,
                trip_id TEXT,
                label TEXT,
                recorded_at INTEGER NOT NULL,
                PRIMARY KEY (system, vehicle_id, gps_ts)
            );
            CREATE INDEX IF NOT EXISTS fixes_age ON fixes(gps_ts);
        ''')
        # Add columns without losing a Beta SQLite volume.
        columns = {row[1] for row in self.db.execute('PRAGMA table_info(fixes)')}
        with self.db:
            if 'proximity_state' not in columns:
                self.db.execute('ALTER TABLE fixes ADD COLUMN proximity_state TEXT')
            if 'distance_m' not in columns:
                self.db.execute('ALTER TABLE fixes ADD COLUMN distance_m INTEGER')
        self.last_purge = 0

    def append(self, system: str, vehicles: list[dict[str, Any]], index: dict[str, Any] | None = None,
               now: int | None = None,
               proximity: dict[str, dict[str, Any]] | None = None) -> int:
        """Insert fresh, distinct GPS timestamps once; this is not a route snapper."""
        now = int(time.time() if now is None else now)
        if system not in ('victoria', 'chilliwack', 'kelowna'):
            raise ValueError('Unsupported transit system')
        index = index or {}
        proximity = proximity or {}
        routes = index.get('routes', {})
        trips = index.get('trips', {})
        batch = []
        for vehicle in vehicles:
            ident = str(vehicle.get('id') or '')
            raw_ts = vehicle.get('timestamp')
            lat, lon = vehicle.get('lat'), vehicle.get('lon')
            if not ident or len(ident) > 128 or not isinstance(raw_ts, (float, int)):
                continue
            ts = int(raw_ts)
            if not (MIN_TIME <= ts <= now + 60 and ts >= now - 300):
                continue
            if not (isinstance(lat, (float, int)) and isinstance(lon, (float, int))
                    and math.isfinite(lat) and math.isfinite(lon)
                    and -90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            trip_id = vehicle.get('trip_id') or ''
            trip = trips.get(trip_id, {})
            rid = vehicle.get('route_id') or trip.get('route_id') or ''
            route = routes.get(rid, {}).get('short') or (rid if len(rid) <= 4 else None)
            info = proximity.get(ident) or {}
            prox_status = info.get('state')
            if prox_status not in ('near','far','possible_nis','likely_nis','unknown'):
                prox_status = None
            dist = info.get('distance_m')
            dist = int(dist) if isinstance(dist, (float,int)) and math.isfinite(dist) and 0 <= dist < 1000000 else None
            batch.append((system, ident, ts, lat, lon, str(route)[:24] if route else None,
                          str(trip_id)[:256] if trip_id else None,
                          str(vehicle.get('label') or '')[:128] or None, now, prox_status, dist))
        if not batch and now - self.last_purge < 600:
            return 0
        with self.lock:
            with self.db:
                before = self.db.total_changes
                if batch:
                    self.db.executemany('''INSERT OR IGNORE INTO fixes
                        (system,vehicle_id,gps_ts,lat,lon,route,trip_id,label,recorded_at,proximity_state,distance_m)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)''', batch)
                added = self.db.total_changes - before
                if now - self.last_purge >= 600:
                    self.db.execute('DELETE FROM fixes WHERE gps_ts < ?', (now - RETENTION_S,))
                    self.last_purge = now
        return added

    def get(self, system: str, vehicle_id: str, minutes: int = 30,
            now: int | None = None) -> dict[str, Any]:
        if system not in ('victoria', 'chilliwack', 'kelowna'):
            raise ValueError('Unsupported transit system')
        if not vehicle_id or len(vehicle_id) > 128:
            raise ValueError('Invalid vehicle identifier')
        if minutes not in WINDOWS:
            raise ValueError('History window must be 15, 30 or 60 minutes')
        now = int(time.time() if now is None else now)
        with self.lock:
            rows = self.db.execute('''SELECT gps_ts,lat,lon,route
                FROM fixes WHERE system=? AND vehicle_id=? AND gps_ts>=? AND gps_ts<=?
                ORDER BY gps_ts DESC LIMIT ?''',
                (system, vehicle_id, now - minutes * 60, now + 60, MAX_API_POINTS)).fetchall()
        rows.reverse()
        return {
            'system': system, 'vehicle_id': vehicle_id, 'minutes': minutes,
            'points': [[int(t), round(lat, 6), round(lon, 6), route] for t,lat,lon,route in rows],
            'count': len(rows), 'retention_hours': RETENTION_S // 3600,
            'recording_since': rows[0][0] if rows else None, 'server_now': now,
        }

    def activity(self, system: str, vehicle_id: str, minutes: int = 180,
                 now: int | None = None) -> dict[str, Any]:
        """Summarize recorded observations only; no scheduled routes or interpolated trips."""
        if system not in ('victoria', 'chilliwack', 'kelowna'):
            raise ValueError('Unsupported transit system')
        if not vehicle_id or len(vehicle_id) > 128:
            raise ValueError('Invalid vehicle identifier')
        if minutes not in ALLOWED_WINDOWS:
            raise ValueError('Activity window must be 60, 180, 720 or 1440 minutes')
        now = int(time.time() if now is None else now)
        with self.lock:
            rows = self.db.execute('''SELECT gps_ts,lat,lon,route,trip_id,proximity_state
                FROM fixes WHERE system=? AND vehicle_id=? AND gps_ts>=? AND gps_ts<=?
                ORDER BY gps_ts DESC LIMIT ?''',
                (system, vehicle_id, now - minutes * 60, now + 60, MAX_ROWS + 1)).fetchall()
        truncated = len(rows) > MAX_ROWS
        if truncated:
            rows = rows[:MAX_ROWS]
        rows.reverse()
        return build_activity(rows, system, vehicle_id, minutes, now, truncated)

    def last_known(self, system: str, vehicle_id: str = '', fleet: str = '',
                   now: int | None = None) -> dict[str, Any]:
        """Return the last recorded fix (24 h max), clearly not a live position."""
        if system not in ('victoria', 'chilliwack', 'kelowna'):
            raise ValueError('Unsupported transit system')
        if not vehicle_id and not fleet:
            raise ValueError('Vehicle ID or fleet number required')
        if fleet and (system != 'victoria' or len(fleet) != 4 or not fleet.isdigit()):
            raise ValueError('Fleet lookup requires a four-digit Victoria fleet number')
        if vehicle_id and len(vehicle_id) > 128:
            raise ValueError('Vehicle ID too long')
        now = int(time.time() if now is None else now)
        with self.lock:
            if fleet:
                row = self.db.execute('''SELECT vehicle_id,gps_ts,lat,lon,route,trip_id,label
                    FROM fixes WHERE system=? AND label IN (?,?) AND gps_ts>=? AND gps_ts<=?
                    ORDER BY gps_ts DESC LIMIT 1''',
                    (system, '313135' + fleet, fleet, now-RETENTION_S, now+60)).fetchone()
            else:
                row = self.db.execute('''SELECT vehicle_id,gps_ts,lat,lon,route,trip_id,label
                    FROM fixes WHERE system=? AND vehicle_id=? AND gps_ts>=? AND gps_ts<=?
                    ORDER BY gps_ts DESC LIMIT 1''',
                    (system, vehicle_id, now-RETENTION_S, now+60)).fetchone()
        return {'system': system, 'found': bool(row),
                'vehicle': {'id': row[0], 'timestamp': row[1], 'lat':row[2], 'lon':row[3],
                            'route':row[4], 'trip_id':row[5], 'label':row[6]} if row else None,
                'server_now': now, 'history_only': True}

    def close(self) -> None:
        with self.lock:
            self.db.close()
