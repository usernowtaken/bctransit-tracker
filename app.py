"""BC Transit Bus Radar V3.0 Beta: unofficial multi-region live vehicle map.

Requires Python >=3.10, gtfs-realtime-bindings, tzdata (Windows timezone lookup).
All predictions are schedule-based and unconfirmed.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timedelta, timezone
import gzip
import io
import json
import math
import sqlite3
import mimetypes
import os
from pathlib import Path
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
import zipfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from fleet_identity import identify_vehicle
from service_alerts import parse_alert_feed
from gps_history import GPSHistory
from zoneinfo import ZoneInfo

try:
    from google.transit import gtfs_realtime_pb2
except ImportError as exc:
    raise SystemExit("Missing GTFS decoder. Run setup.bat or pip install -r requirements.txt") from exc

BASE = Path(__file__).resolve().parent
WEB_DIR = BASE / "web"
CACHE_DIR = BASE / "cache"
INDEX_PATH = CACHE_DIR / "gtfs_v2.json.gz"  # Old Victoria cache, for backwards compatibility
# Operator IDs come from BC Transit's public GTFS links. Operator 13 is a
# *shared* Fraser Valley feed: its Chilliwack view is filtered by public route.
SYSTEMS = {
    "victoria": {"name": "Greater Victoria", "operator": 48, "center": [48.48, -123.49], "zoom": 10,
                 "bounds": (48.15, 49.05, -124.50, -122.70)},
    "chilliwack": {"name": "Chilliwack / Fraser Valley Express", "operator": 13,
                   "center": [49.157, -121.951], "zoom": 11,
                   "bounds": (48.85, 49.50, -122.65, -121.1),
                   # 66 extends to Abbotsford; 71 and 72 serve nearby communities.
                   "routes": {"51", "52", "53", "54", "55", "56", "57", "58", "59", "66", "71", "72"},
                   "unassigned_bounds": (49.08, 49.25, -122.08, -121.68)},
    "kelowna": {"name": "Kelowna", "operator": 47, "center": [49.887, -119.496], "zoom": 11,
                "bounds": (49.45, 50.55, -120.7, -118.65)},
}

def system_feed_url(system_id: str, kind: str) -> str:
    op = SYSTEMS[system_id]["operator"]
    base = "https://bct.tmix.se/"
    if kind == "static":
        return f"{base}Tmix.Cap.TdExport.WebApi/gtfs/?operatorIds={op}"
    if kind == "vehicle":
        return f"{base}gtfs-realtime/vehicleupdates.pb?operatorIds={op}"
    if kind == "trip":
        return f"{base}gtfs-realtime/tripupdates.pb?operatorIds={op}"
    if kind == "alerts":
        return f"{base}gtfs-realtime/alerts.pb?operatorIds={op}"
    raise ValueError("Unsupported feed type")

POLL_SECONDS = max(15, int(os.environ.get("BCT_POLL_SECONDS", "15")))
# Avoid 3 simultaneous large GTFS ZIP decompressions on small Railway plans.
STATIC_PARSE_LOCK = threading.Lock()
MAX_FEED_BYTES = 12 * 1024 * 1024
MAX_ZIP_BYTES = 85 * 1024 * 1024
REQUEST_TIMEOUT = 16
USER_AGENT = "BCTransitBusRadar/3.3 (unofficial public transit map)"
TIMEZONE = ZoneInfo("America/Vancouver")

OFF_ROUTE_THRESHOLD_M = 100  # user-selected heuristic; route detours / GPS noise can trigger off-route warnings
NEAR_ROUTE_THRESHOLD_M = 300
MAX_POSITION_AGE_S = 300
FALLBACK_COLORS = ("#5de2bd", "#75b8fa", "#f3c569", "#bd9cfa", "#ff938a", "#86d7de", "#cbdc81")


def fetch_bytes(url: str, max_bytes: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream,*/*"})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        length = response.headers.get("Content-Length")
        if length and int(length) > max_bytes:
            raise ValueError("Remote file larger than permitted")
        result = response.read(max_bytes + 1)
        if len(result) > max_bytes:
            raise ValueError("Remote file exceeded download limit")
        return result


def parse_vehicle_feed(body: bytes, system_id: str = "victoria") -> tuple[list[dict[str, Any]], int | None]:
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(body)
    if not feed.HasField("header"):
        raise ValueError("Missing GTFS-Realtime header")
    stamp = int(feed.header.timestamp) if feed.header.HasField("timestamp") else None
    output = []
    min_lat, max_lat, min_lon, max_lon = SYSTEMS[system_id]["bounds"]
    for entity in feed.entity:
        if not entity.HasField("vehicle") or entity.is_deleted:
            continue
        vehicle = entity.vehicle
        if not vehicle.HasField("position"):
            continue
        position = vehicle.position
        lat, lon = float(position.latitude), float(position.longitude)
        if not (math.isfinite(lat) and math.isfinite(lon) and min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
            continue
        descriptor = vehicle.vehicle if vehicle.HasField("vehicle") else None
        trip = vehicle.trip if vehicle.HasField("trip") else None
        identity = (descriptor.id if descriptor and descriptor.id else entity.id) or entity.id
        output.append({
            "id": str(identity), "lat": round(lat, 6), "lon": round(lon, 6),
            "bearing": round(position.bearing, 1) if position.HasField("bearing") else None,
            "speed_mps": round(position.speed, 2) if position.HasField("speed") else None,
            "timestamp": int(vehicle.timestamp) if vehicle.HasField("timestamp") else stamp,
            "timestamp_source": "vehicle" if vehicle.HasField("timestamp") else "feed",
            "route_id": trip.route_id if trip and trip.route_id else None,
            "trip_id": trip.trip_id if trip and trip.trip_id else None,
            "start_date": trip.start_date if trip and trip.start_date else None,
            "start_time": trip.start_time if trip and trip.start_time else None,
            "label": descriptor.label if descriptor and descriptor.label else None,
            "stop_sequence": int(vehicle.current_stop_sequence) if vehicle.HasField("current_stop_sequence") else None,
            "stop_id": vehicle.stop_id if vehicle.HasField("stop_id") else None,
            "stop_status": int(vehicle.current_status) if vehicle.HasField("current_status") else 2,
            "occupancy": int(vehicle.occupancy_status) if vehicle.HasField("occupancy_status") else None,
            "congestion": int(vehicle.congestion_level) if vehicle.HasField("congestion_level") else None,
        })
    return output, stamp


def parse_trip_update_feed(body: bytes) -> tuple[dict[str, Any], int | None]:
    """Read stop-specific GTFS-RT predictions. No prediction is invented for missing updates."""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(body)
    if not feed.HasField("header"):
        raise ValueError("Missing GTFS-Realtime header for trip updates")
    stamp = int(feed.header.timestamp) if feed.header.HasField("timestamp") else None
    updates: dict[str, Any] = {}
    for entity in feed.entity:
        if not entity.HasField("trip_update") or entity.is_deleted:
            continue
        update = entity.trip_update
        trip_id = update.trip.trip_id if update.HasField("trip") else ""
        if not trip_id:
            continue
        stops = []
        for item in update.stop_time_update:
            # A skipped stop is not an arrival, even if another time field exists.
            if item.HasField("schedule_relationship") and int(item.schedule_relationship) == 1:
                continue
            arrival = item.arrival if item.HasField("arrival") else (
                item.departure if item.HasField("departure") else None)
            prediction = int(arrival.time) if arrival is not None and arrival.HasField("time") else None
            delay = int(arrival.delay) if arrival is not None and arrival.HasField("delay") else None
            if prediction is None and delay is None:
                continue
            stops.append({
                "sequence": int(item.stop_sequence) if item.HasField("stop_sequence") else None,
                "id": item.stop_id if item.HasField("stop_id") else None,
                "predicted_at": prediction, "delay_seconds": delay,
            })
        updates[trip_id] = {
            "timestamp": int(update.timestamp) if update.HasField("timestamp") else stamp,
            "start_date": update.trip.start_date if update.HasField("trip") and update.trip.start_date else None,
            "stops": stops,
        }
    return updates, stamp


def _csv_rows(archive: zipfile.ZipFile, filename: str, required: bool = True):
    match = next((part for part in archive.namelist() if part.rsplit("/", 1)[-1].lower() == filename), None)
    if not match:
        if required:
            raise ValueError(f"GTFS missing {filename}")
        return
    entry = archive.getinfo(match)
    if entry.file_size > 180 * 1024 * 1024:
        raise ValueError(f"GTFS {filename} exceeds safety limit")
    with archive.open(match) as binary:
        reader = csv.DictReader(io.TextIOWrapper(binary, encoding="utf-8-sig", newline=""))
        yield from reader


def _gtfs_time(value: str | None) -> int | None:
    try:
        h, m, s = [int(part) for part in (value or "").split(":")]
        if 0 <= h <= 48 and 0 <= m < 60 and 0 <= s < 60:
            return h * 3600 + m * 60 + s
    except (ValueError, TypeError):
        pass
    return None


def _safe_hex(value: str | None) -> str | None:
    value = (value or "").strip().lstrip("#")
    if len(value) == 6 and all(ch in "0123456789ABCDEFabcdef" for ch in value):
        return f"#{value.upper()}"
    return None


def _simplify(points: list[list[float]], tolerance_m: float = 9.0) -> list[list[float]]:
    """Lightweight Douglas–Peucker in local projected metres. Coordinates [lat, lon]."""
    if len(points) <= 2:
        return points
    lat_scale = 111000.0
    lon_scale = 111000.0 * math.cos(math.radians(points[len(points)//2][0]))
    xy = [(p[1] * lon_scale, p[0] * lat_scale) for p in points]
    keep = {0, len(points) - 1}
    stack = [(0, len(points)-1)]
    threshold = tolerance_m*tolerance_m
    while stack:
        start, end = stack.pop()
        x1, y1 = xy[start]; x2, y2 = xy[end]
        dx, dy = x2-x1, y2-y1
        length2 = dx*dx + dy*dy
        worst, idx = -1.0, None
        for i in range(start+1, end):
            x,y = xy[i]
            u = max(0.0, min(1.0, ((x-x1)*dx + (y-y1)*dy)/length2)) if length2 else 0
            dist = (x-x1-u*dx)**2 + (y-y1-u*dy)**2
            if dist > worst:
                worst, idx = dist, i
        if worst > threshold and idx is not None:
            keep.add(idx)
            stack.extend([(start,idx),(idx,end)])
    return [points[i] for i in sorted(keep)]


def parse_static_gtfs(blob: bytes) -> dict[str, Any]:
    routes, trips, stops, shapes, service_days, exceptions = {}, {}, {}, {}, {}, defaultdict(dict)
    trip_stops = defaultdict(list)
    blocks = defaultdict(list)
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        for row in _csv_rows(archive, "routes.txt"):
            rid = (row.get("route_id") or "").strip()
            if rid:
                routes[rid] = {"short": (row.get("route_short_name") or "").strip(),
                               "long": (row.get("route_long_name") or "").strip(),
                               "color": _safe_hex(row.get("route_color")),
                               "text_color": _safe_hex(row.get("route_text_color"))}
        for row in _csv_rows(archive, "trips.txt"):
            tid = (row.get("trip_id") or "").strip()
            if tid:
                trips[tid] = {"route_id": (row.get("route_id") or "").strip(),
                              "headsign": (row.get("trip_headsign") or "").strip(),
                              "block_id": (row.get("block_id") or "").strip(),
                              "service_id": (row.get("service_id") or "").strip(),
                              "shape_id": (row.get("shape_id") or "").strip(),
                              "first": None, "last": None}
        for row in _csv_rows(archive, "stops.txt"):
            sid = (row.get("stop_id") or "").strip()
            if not sid:
                continue
            try:
                lat, lon = float(row.get("stop_lat") or ""), float(row.get("stop_lon") or "")
                if not (math.isfinite(lat) and math.isfinite(lon)):
                    continue
            except ValueError:
                continue
            stops[sid] = [row.get("stop_name") or "Unknown stop", round(lat, 6), round(lon, 6)]
        for row in _csv_rows(archive, "stop_times.txt"):
            tid = row.get("trip_id") or ""
            if tid not in trips:
                continue
            try:
                sequence = int(row.get("stop_sequence") or "")
            except ValueError:
                continue
            arrival = _gtfs_time(row.get("arrival_time"))
            departure = _gtfs_time(row.get("departure_time"))
            # No time at non-timepoint stops is normal. Use available endpoints.
            trip_stops[tid].append([sequence, row.get("stop_id") or "", arrival, departure])
        for tid, entries in trip_stops.items():
            entries.sort(key=lambda r: r[0])
            times = [v for r in entries for v in r[2:] if v is not None]
            if times:
                trips[tid]["first"] = entries[0][3] if entries[0][3] is not None else entries[0][2]
                trips[tid]["last"] = entries[-1][2] if entries[-1][2] is not None else entries[-1][3]
                if trips[tid]["first"] is None: trips[tid]["first"] = min(times)
                if trips[tid]["last"] is None: trips[tid]["last"] = max(times)
            if trips[tid]["block_id"] and trips[tid]["first"] is not None:
                blocks[trips[tid]["block_id"]].append(tid)
        for block_trips in blocks.values():
            block_trips.sort(key=lambda tid: trips[tid]["first"])
        for row in _csv_rows(archive, "calendar.txt", required=False):
            service_id = row.get("service_id") or ""
            if service_id:
                service_days[service_id] = {"start": row.get("start_date") or "", "end": row.get("end_date") or "",
                    "weekdays": [row.get(day) == "1" for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")]}
        for row in _csv_rows(archive, "calendar_dates.txt", required=False):
            service_id = row.get("service_id") or ""
            if service_id and (row.get("exception_type") or "") in ("1", "2"):
                exceptions[service_id][row.get("date") or ""] = int(row["exception_type"])
        # Shape points only are prepared for on-demand detail requests, never sent in bulk.
        raw_shapes = defaultdict(list)
        for row in _csv_rows(archive, "shapes.txt", required=False):
            sid = (row.get("shape_id") or "").strip()
            if not sid:
                continue
            try:
                lat, lon = float(row["shape_pt_lat"]), float(row["shape_pt_lon"])
                seq = int(row["shape_pt_sequence"])
            except (KeyError, ValueError):
                continue
            if math.isfinite(lat) and math.isfinite(lon):
                raw_shapes[sid].append((seq, [round(lat,6), round(lon,6)]))
        for sid, items in raw_shapes.items():
            items.sort(key=lambda p:p[0])
            simplified = _simplify([p for _,p in items])
            if len(simplified) > 2400:
                step = math.ceil(len(simplified)/2400)
                simplified = simplified[::step] + ([simplified[-1]] if simplified[-1] != simplified[::step][-1] else [])
            shapes[sid] = simplified
    if not routes or not trips:
        raise ValueError("GTFS routes or trips missing")
    route_shapes = build_route_shapes(trips, shapes)
    return {"routes": routes, "trips": trips, "stops": stops, "trip_stops": dict(trip_stops),
            "shapes": shapes, "route_shapes": route_shapes, "route_short_ids": build_route_short_ids(routes),
            "blocks": dict(blocks), "service_days": service_days,
            "exceptions": dict(exceptions), "updated_at": int(time.time())}


def build_route_shapes(trips: dict[str, Any], shapes: dict[str, Any]) -> dict[str, list[str]]:
    """Group unique shape IDs by public route, avoiding per-vehicle trip scans."""
    grouped = defaultdict(set)
    for trip in trips.values():
        rid, sid = trip.get("route_id"), trip.get("shape_id")
        if rid and sid and sid in shapes:
            grouped[rid].add(sid)
    return {rid:sorted(sids) for rid,sids in grouped.items()}


def build_route_short_ids(routes: dict[str, Any]) -> dict[str, list[str]]:
    grouped = defaultdict(list)
    for rid, route in routes.items():
        if route.get("short"):
            grouped[str(route["short"]).upper()].append(rid)
    return dict(grouped)


def service_active(index: dict[str, Any], service_id: str, date: datetime) -> bool:
    ymd = date.strftime("%Y%m%d")
    exception = index.get("exceptions", {}).get(service_id, {}).get(ymd)
    if exception is not None:
        return exception == 1
    calendar = index.get("service_days", {}).get(service_id)
    return bool(calendar and calendar["start"] <= ymd <= calendar["end"] and calendar["weekdays"][date.weekday()])


def resolve_service_day(index: dict[str, Any], vehicle: dict[str, Any], now: datetime) -> datetime | None:
    trip = index.get("trips", {}).get(vehicle.get("trip_id") or "", {})
    service_id = trip.get("service_id")
    if not service_id:
        return None
    start_date = vehicle.get("start_date")
    if start_date:
        try:
            candidate = datetime.strptime(start_date, "%Y%m%d")
        except ValueError:
            return None
        return candidate if service_active(index, service_id, candidate) else None
    first, last = trip.get("first"), trip.get("last")
    if first is None or last is None:
        return None
    current = now.hour*3600 + now.minute*60 + now.second
    for offset in (0, -1):
        candidate = now + timedelta(days=offset)
        if not service_active(index, service_id, candidate):
            continue
        current_relative = current - offset*86400
        if first-7200 <= current_relative <= last+7200:
            return candidate
    return None


def _stop_brief(index: dict[str, Any], entry: list) -> dict[str, Any] | None:
    stop = index.get("stops", {}).get(entry[1])
    if not stop:
        return None
    sec = entry[2] if entry[2] is not None else entry[3]
    return {"id": entry[1], "sequence": entry[0], "name": stop[0], "lat": stop[1], "lon": stop[2],
            "scheduled": f"{(sec//3600)%24:02d}:{(sec%3600)//60:02d}" + (" (+1d)" if sec >= 86400 else "") if sec is not None else None,
            "scheduled_seconds": sec}


def stop_context(index: dict[str, Any], vehicle: dict[str, Any], now: datetime) -> dict[str, Any]:
    entries = index.get("trip_stops", {}).get(vehicle.get("trip_id") or "", [])
    if not entries:
        return {"basis": "unavailable", "previous": None, "next": None, "upcoming": []}
    current_index = None
    seq = vehicle.get("stop_sequence")
    if seq is not None:
        current_index = next((i for i, r in enumerate(entries) if r[0] == seq), None)
    if current_index is None and vehicle.get("stop_id"):
        current_index = next((i for i, r in enumerate(entries) if r[1] == vehicle["stop_id"]), None)
    if current_index is not None:
        # 'STOPPED_AT': stop_sequence points to stop being served, not next stop.
        at_stop = vehicle.get("stop_status") == 1
        next_index = current_index+1 if at_stop else current_index
        previous_index = current_index if at_stop else current_index-1
        basis = "Reported stop position"
    else:
        # Timetable estimate; not a claim that the bus actually reached that stop.
        service_day = resolve_service_day(index, vehicle, now)
        if service_day is None:
            return {"basis": "unavailable", "previous": None, "next": None, "upcoming": []}
        offset = (now.date() - service_day.date()).days * 86400
        current_sec = now.hour*3600 + now.minute*60 + now.second + offset
        next_index = next((i for i, r in enumerate(entries) if (r[2] if r[2] is not None else r[3]) is not None
                       and (r[2] if r[2] is not None else r[3]) >= current_sec), len(entries))
        previous_index = next_index-1
        basis = "Timetable estimate (not GPS-confirmed)"
    prev = _stop_brief(index, entries[previous_index]) if 0 <= previous_index < len(entries) else None
    nxt = _stop_brief(index, entries[next_index]) if 0 <= next_index < len(entries) else None
    upcoming = [_stop_brief(index, entry) for entry in entries[next_index:next_index+5]]
    return {"basis": basis, "previous": prev, "next": nxt, "upcoming": [x for x in upcoming if x]}


def next_run(index: dict[str, Any], vehicle: dict[str, Any], now: datetime) -> dict[str, Any] | None:
    trip_id = vehicle.get("trip_id") or ""
    trip = index.get("trips", {}).get(trip_id)
    if not trip or not trip.get("block_id") or trip.get("last") is None:
        return None
    # Avoid predictions for vehicles with stale/outdated or unspecified position timestamps.
    stamp = vehicle.get("timestamp")
    if not isinstance(stamp, int) or abs(now.timestamp()-stamp) > 600:
        return None
    service_day = resolve_service_day(index, vehicle, now)
    if service_day is None:
        return None
    current_end = trip["last"]
    options = []
    for tid in index.get("blocks", {}).get(trip["block_id"], []):
        if tid == trip_id:
            continue
        nxt = index["trips"][tid]
        first = nxt.get("first")
        if first is None or first < current_end-60 or first-current_end > 4*3600:
            continue
        if not service_active(index, nxt.get("service_id") or "", service_day):
            continue
        options.append((first, tid))
    if not options:
        return None
    first, tid = min(options)
    candidate = index["trips"][tid]
    route = index["routes"].get(candidate["route_id"], {})
    current_route_id = trip.get("route_id")
    return {"route": route.get("short") or None,
            "route_name": route.get("long") or None,
            "headsign": candidate.get("headsign") or None,
            "trip_id": tid,
            "starts_at": f"{(first//3600)%24:02d}:{(first%3600)//60:02d}" + (" (+1d)" if first>=86400 else ""),
            "different_route": candidate.get("route_id") != current_route_id,
            "basis": "GTFS block schedule — unconfirmed vehicle assignment"}



def route_distance_m(lat: float, lon: float, polyline: list[list[float]]) -> float | None:
    """Minimum GPS-to-polyline distance in local projected metres (not to stops).

    Segments rather than vertices are essential: a bus can be on a long segment
    even when it is far from the closest recorded GTFS shape point.
    """
    if len(polyline) < 2:
        return None
    x_scale = 111195.0 * math.cos(math.radians(lat))
    y_scale = 111195.0
    best_sq = float("inf")
    last = polyline[0]
    for point in polyline[1:]:
        ax, ay = (last[1] - lon)*x_scale, (last[0] - lat)*y_scale
        bx, by = (point[1] - lon)*x_scale, (point[0] - lat)*y_scale
        dx, dy = bx-ax, by-ay
        length_sq = dx*dx + dy*dy
        t = max(0.0, min(1.0, -(ax*dx + ay*dy)/length_sq)) if length_sq else 0.0
        dist_sq = (ax+t*dx)**2 + (ay+t*dy)**2
        best_sq = min(best_sq, dist_sq)
        last = point
    return math.sqrt(best_sq)


def route_proximity(index: dict[str, Any], vehicle: dict[str, Any], now_ts: float | None = None) -> dict[str, Any]:
    """Match live GPS against any published path for the *reported route*.

    A valid trip ID is preferred, but its absence no longer blocks a route-level
    check when the realtime feed still identifies the route. A missing route or
    stale GPS stays unknown, never automatically NIS.
    """
    unknown = {"state": "unknown", "distance_m": None, "basis": "No comparable published route geometry"}
    stamp = vehicle.get("timestamp")
    now_ts = time.time() if now_ts is None else now_ts
    if not isinstance(stamp, (int, float)) or stamp <= 0 or not -60 <= now_ts-stamp <= MAX_POSITION_AGE_S:
        return {**unknown, "basis": "GPS timestamp missing or stale"}
    trip_id = vehicle.get("trip_id") or ""
    trip = index.get("trips", {}).get(trip_id, {})
    reported_route = vehicle.get("route_id")
    trip_route = trip.get("route_id")
    routes = index.get("routes", {})
    route_shapes = index.get("route_shapes", {})
    short_ids = index.get("route_short_ids") or build_route_short_ids(routes)
    route_ids: list[str] = []
    # A live reported route should take precedence over an old, inconsistent trip.
    if reported_route:
        if reported_route in routes:
            route_ids = [reported_route]
        else:
            route_ids = short_ids.get(str(reported_route).upper(), [])
    if not route_ids and trip_route and (not reported_route or reported_route == trip_route):
        route_ids = [trip_route]
    if not route_ids:
        return {**unknown, "basis": "No matching route ID in the published schedule"}
    shape_ids: set[str] = set()
    for rid in route_ids:
        shape_ids.update(route_shapes.get(rid, []))
    if trip.get("shape_id") and trip_route in route_ids:
        shape_ids.add(trip["shape_id"])
    if not shape_ids:
        return {**unknown, "basis": "This route has no usable GTFS shape"}
    try:
        lat, lon = float(vehicle["lat"]), float(vehicle["lon"])
        if not math.isfinite(lat) or not math.isfinite(lon):
            return unknown
    except (TypeError, ValueError, KeyError):
        return unknown
    best = None
    for sid in shape_ids:
        polyline = index.get("shapes", {}).get(sid, [])
        if len(polyline) < 2:
            continue
        distance = route_distance_m(lat, lon, polyline)
        if distance is not None and (best is None or distance < best):
            best = distance
        if best is not None and best <= 3:
            break
    if best is None:
        return unknown
    # 'near' is for the *closest* published variant: avoids false warnings for
    # legit branches, short turns, or differing inbound/outbound trip shapes.
    used_fallback = not trip or trip_route not in route_ids or not trip.get("shape_id")
    basis = ("GPS distance to published shapes for reported route (no matching trip)"
             if used_fallback else "GPS distance to nearest published variant of reported route")
    return {"state": "far" if best > OFF_ROUTE_THRESHOLD_M else "near",
            "distance_m": round(best), "basis": basis,
            "threshold_m": OFF_ROUTE_THRESHOLD_M}


def update_proximity_observations(index: dict[str, Any], vehicles: list[dict[str, Any]],
                                  previous: dict[str, dict[str, Any]], now_ts: float | None = None
                                  ) -> dict[str, dict[str, Any]]:
    """Confirm a potential deadhead only after two DISTINCT fresh GPS observations.

    Repeated feed downloads of the identical GPS timestamp/position never
    increase the counter, and changing trips resets the confirmation.
    """
    now_ts = time.time() if now_ts is None else now_ts
    updated = {}
    for vehicle in vehicles:
        ident = vehicle.get("id")
        if not ident:
            continue
        proximity = route_proximity(index, vehicle, now_ts)
        prior = previous.get(ident, {})
        trip_id = vehicle.get("trip_id")
        stamp = vehicle.get("timestamp")
        coords = (vehicle.get("lat"), vehicle.get("lon"))
        same_trip = prior.get("trip_id") == trip_id and prior.get("route_id") == vehicle.get("route_id")
        # After a long reporting gap, restart the off-route evidence streak.
        if isinstance(stamp, (int, float)) and isinstance(prior.get("timestamp"), (int, float)):
            if stamp - prior["timestamp"] > MAX_POSITION_AGE_S:
                same_trip = False
        # When only the GTFS-RT feed header time is available, a new header
        # timestamp is NOT proof of a new vehicle GPS fix. Require movement.
        same_observation = same_trip and (prior.get("timestamp") == stamp and prior.get("coords") == coords
            or (vehicle.get("timestamp_source") == "feed" and prior.get("coords") == coords))
        if proximity["state"] == "far":
            count = prior.get("far_observations", 0) if same_trip and prior.get("state") in ("far", "possible_nis", "likely_nis") else 0
            if not same_observation:
                count += 1
            elif count == 0:
                count = 1
            first_far_ts = (prior.get("first_far_ts") if same_trip and prior.get("state") in
                            ("far", "possible_nis", "likely_nis") else None)
            if not isinstance(first_far_ts, (int,float)):
                first_far_ts = stamp
            duration = stamp - first_far_ts if isinstance(stamp, (int,float)) else 0
            # Persistent evidence raises confidence but *never* proves the
            # destination sign or official operating state is Not In Service.
            if count >= 3 and duration >= 45:
                proximity["state"] = "likely_nis"
            elif count >= 2:
                proximity["state"] = "possible_nis"
            else:
                proximity["state"] = "far"
            proximity["observations"] = count
        else:
            count = 0
            first_far_ts = None
        updated[ident] = {**proximity, "trip_id": trip_id, "route_id": vehicle.get("route_id"), "timestamp": stamp,
                          "coords": coords, "far_observations": count, "first_far_ts": first_far_ts}
    return updated


def route_color(route: dict[str, Any], route_id: str | None) -> str:
    if route.get("color"):
        return route["color"]
    value = route.get("short") or route_id or "0"
    n = 0
    for c in value:
        n = (n*33 + ord(c)) % len(FALLBACK_COLORS)
    return FALLBACK_COLORS[n]


class Tracker:
    def __init__(self, system_id: str = "victoria", history: GPSHistory | None = None) -> None:
        if system_id not in SYSTEMS:
            raise ValueError("Unknown transit system")
        self.system_id = system_id
        self.history = history
        self.name = SYSTEMS[system_id]["name"]
        # Keep static route databases and live vehicles separate per system.
        self.index_path = CACHE_DIR / f"gtfs_v27_{system_id}.json.gz"
        self.urls = {kind: system_feed_url(system_id, kind) for kind in ("vehicle", "trip", "static", "alerts")}
        self.alerts: dict[str, Any] | None = None
        self.alerts_last_try = 0
        self.alerts_error: str | None = None
        self.alerts_fetch_lock = threading.Lock()
        self.lock = threading.RLock()
        self.index: dict[str, Any] = {"routes": {}, "trips": {}, "updated_at": None}
        self.vehicles: list[dict[str, Any]] = []
        self.proximity_observations: dict[str, dict[str, Any]] = {}
        self.trip_updates: dict[str, Any] = {}
        self.trip_feed_timestamp: int | None = None
        self.trip_feed_fetched_at: int | None = None
        self.trip_feed_error: str | None = None
        self.feed_timestamp: int | None = None
        self.fetched_at: int | None = None
        self.last_error: str | None = None
        self.gtfs_error: str | None = None
        self.revision = 0
        self._snapshot_cache = None
        self._stop_timetable_index = None  # lazy: nearby board never delays startup
        self._load_index()

    def _load_index(self) -> None:
        try:
            with gzip.open((self.index_path if self.index_path.exists() else INDEX_PATH if self.system_id == "victoria" else self.index_path), "rt", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data.get("routes"), dict) and isinstance(data.get("trip_stops"), dict):
                if "route_shapes" not in data:
                    data["route_shapes"] = build_route_shapes(data.get("trips", {}), data.get("shapes", {}))
                if "route_short_ids" not in data:
                    data["route_short_ids"] = build_route_short_ids(data.get("routes", {}))
                self.index = data
                print(f"[GTFS] Loaded local cache: {len(data['trips'])} trips")
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def update_index(self, index: dict[str, Any], persist: bool = True) -> None:
        if "route_shapes" not in index:
            index["route_shapes"] = build_route_shapes(index.get("trips", {}), index.get("shapes", {}))
        if "route_short_ids" not in index:
            index["route_short_ids"] = build_route_short_ids(index.get("routes", {}))
        with self.lock:
            self.index = index
            self._stop_timetable_index = None
            # A refreshed GTFS shape may differ; retain only matching observations.
            self.proximity_observations = update_proximity_observations(
                index, self.vehicles, {}, time.time())
            self.gtfs_error = None
            self.revision += 1
            self._snapshot_cache = None
        if persist:
            try:
                CACHE_DIR.mkdir(exist_ok=True)
                temp = self.index_path.with_suffix(".tmp")
                with gzip.open(temp, "wt", encoding="utf-8", compresslevel=5) as f:
                    json.dump(index, f, separators=(",", ":"))
                temp.replace(self.index_path)
            except OSError as exc:
                print(f"[GTFS] Cache save failed: {exc}")

    def update_feed(self, data: bytes) -> None:
        vehicles, stamp = parse_vehicle_feed(data, self.system_id)
        with self.lock:
            self.vehicles = vehicles
            self.proximity_observations = update_proximity_observations(
                self.index, vehicles, self.proximity_observations, time.time())
            self.feed_timestamp = stamp
            self.fetched_at = int(time.time())
            self.last_error = None
            self.revision += 1
            self._snapshot_cache = None
            # Freeze the observed proximity evidence with this GPS snapshot.
            recorded_proximity = dict(self.proximity_observations)
        # Write after releasing the tracker lock so history disk IO never holds
        # up live snapshot requests. History failures must not kill the live feed.
        if self.history is not None:
            try:
                self.history.append(self.system_id, vehicles, self.index, proximity=recorded_proximity)
            except Exception as exc:
                print(f"[{self.system_id}:history] Recording failed: {exc}")

    def update_trip_feed(self, data: bytes) -> None:
        updates, stamp = parse_trip_update_feed(data)
        with self.lock:
            self.trip_updates = updates
            self.trip_feed_timestamp = stamp
            self.trip_feed_fetched_at = int(time.time())
            self.trip_feed_error = None

    def get_alerts(self) -> dict[str, Any]:
        """Lazy, bounded 3-minute cache; never slows the primary GPS feed."""
        now = time.time()
        with self.lock:
            cached = self.alerts
            if now - self.alerts_last_try < (180 if cached else 45):
                if cached:
                    return {**cached, 'error': self.alerts_error}
                return {'alerts': [], 'ready': False, 'error': self.alerts_error or 'Alerts not loaded'}
        with self.alerts_fetch_lock:
            with self.lock:
                cached = self.alerts
                if time.time() - self.alerts_last_try < (180 if cached else 45):
                    if cached:
                        return {**cached, 'error': self.alerts_error}
                    return {'alerts': [], 'ready': False, 'error': self.alerts_error or 'Alerts unavailable'}
                self.alerts_last_try = time.time()
            try:
                parsed = parse_alert_feed(fetch_bytes(self.urls['alerts'], MAX_FEED_BYTES), gtfs_realtime_pb2)
                with self.lock:
                    self.alerts = {**parsed, 'ready': True}
                    self.alerts_error = None
            except Exception as exc:
                with self.lock:
                    self.alerts_error = str(exc)[:250]
            with self.lock:
                if self.alerts:
                    return {**self.alerts, 'error': self.alerts_error}
                return {'alerts': [], 'ready': False, 'error': self.alerts_error or 'Alerts unavailable'}

    def arrivals_for_trip(self, trip_id: str) -> dict[str, Any]:
        """Only explicit fresh predictions or a GTFS-RT delay are called 'estimated'."""
        with self.lock:
            update = self.trip_updates.get(trip_id)
            index = self.index
            fetched_at = self.trip_feed_fetched_at
            error = self.trip_feed_error
            trip = index.get("trips", {}).get(trip_id, {})
            rows = index.get("trip_stops", {}).get(trip_id, [])
            if not update:
                return {"trip_id": trip_id, "status": "unavailable", "stops": [], "error": error}
            vehicle = next((v for v in self.vehicles if v.get("trip_id") == trip_id), None)
            if (vehicle and vehicle.get("start_date") and update.get("start_date")
                    and vehicle["start_date"] != update["start_date"]):
                return {"trip_id": trip_id, "status": "unavailable", "stops": [],
                        "error": "Live trip service date differs from prediction"}
            stamp = update.get("timestamp") or self.trip_feed_timestamp or fetched_at
            if not stamp or abs(time.time() - stamp) > 180:
                return {"trip_id": trip_id, "status": "stale", "stops": [], "error": error}
            service_date = update.get("start_date")
            service_base = None
            if service_date:
                try:
                    service_base = datetime.strptime(service_date, "%Y%m%d").replace(tzinfo=TIMEZONE)
                except ValueError:
                    pass
            if service_base is None:
                # Fall back to the current live vehicle's service day for delay-only events.
                if vehicle:
                    service_base = resolve_service_day(index, vehicle, datetime.now(TIMEZONE))
                    if service_base:
                        service_base = service_base.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=TIMEZONE)
            by_seq = {r[0]: r for r in rows}
            by_id: dict[str, list] = defaultdict(list)
            for r in rows:
                by_id[r[1]].append(r)
            predictions = []
            for event in update["stops"]:
                seq = event.get("sequence")
                row = by_seq.get(seq) if seq is not None else None
                if not row and event.get("id") and len(by_id.get(event["id"], [])) == 1:
                    row = by_id[event["id"]][0]
                if not row:
                    continue
                when = event.get("predicted_at")
                if when is None and event.get("delay_seconds") is not None and service_base is not None:
                    scheduled = row[2] if row[2] is not None else row[3]
                    if scheduled is not None:
                        when = int((service_base + timedelta(seconds=scheduled + event["delay_seconds"])).timestamp())
                if when is not None and when > 0:
                    predictions.append({"sequence": row[0], "id": row[1], "predicted_at": when})
            return {"trip_id": trip_id, "status": "live" if predictions else "unavailable",
                    "fetched_at": fetched_at, "stops": predictions, "error": error}

    def snapshot(self, since: int | None = None) -> dict[str, Any]:
        with self.lock:
            # An off-route warning must expire even if BC Transit stops sending
            # new frames. Bump revision so browsers polling with ?since=...
            # receive a fresh snapshot rather than a perpetual unchanged reply.
            if self._snapshot_cache is not None and any(
                    v.get("route_proximity", {}).get("state") in ("far", "possible_nis", "likely_nis")
                    and isinstance(v.get("timestamp"), (int, float))
                    and time.time()-v["timestamp"] > MAX_POSITION_AGE_S
                    for v in self._snapshot_cache.get("vehicles", [])):
                self._snapshot_cache = None
                self.revision += 1
            if since is not None and since == self.revision:
                return {"unchanged": True, "revision": self.revision, "server_now": int(time.time()),
                        "error": self.last_error, "metadata_error": self.gtfs_error, "system": self.system_id}
            if self._snapshot_cache is not None:
                return {**self._snapshot_cache, "server_now": int(time.time()),
                        "error": self.last_error, "metadata_error": self.gtfs_error, "system": self.system_id}
            index = self.index
            now = datetime.fromtimestamp(time.time(), TIMEZONE)
            enriched = []
            for v in self.vehicles:
                trip = index["trips"].get(v.get("trip_id") or "", {})
                rid = v.get("route_id") or trip.get("route_id")
                route = index["routes"].get(rid or "", {})
                public_route = route.get("short") or None
                if not public_route and rid and len(rid) <= 4 and rid.replace("X", "").isdigit():
                    public_route = rid
                # Operator 13 includes Central Fraser Valley and Abbotsford.
                # Chilliwack shows only its published local / FVX route numbers;
                # include unassigned vehicles only while physically in Chilliwack.
                if self.system_id == "chilliwack":
                    allowed = SYSTEMS["chilliwack"]["routes"]
                    if public_route:
                        if str(public_route).strip().upper() not in allowed:
                            continue
                    else:
                        a, b, c, d = SYSTEMS["chilliwack"]["unassigned_bounds"]
                        if not (a <= v["lat"] <= b and c <= v["lon"] <= d):
                            continue
                proximity = self.proximity_observations.get(v.get("id") or "")
                if not proximity or proximity.get("trip_id") != v.get("trip_id") or proximity.get("timestamp") != v.get("timestamp"):
                    proximity = update_proximity_observations(index, [v], {}, now.timestamp()).get(v.get("id") or "", {})
                # If a previously valid GPS observation has since gone stale,
                # stop claiming a confirmed proximity classification.
                if not isinstance(v.get("timestamp"), (int, float)) or now.timestamp()-v["timestamp"] > MAX_POSITION_AGE_S:
                    proximity = route_proximity(index, v, now.timestamp())
                public_proximity = {key:proximity.get(key) for key in ("state", "distance_m", "basis", "threshold_m", "observations")}
                enriched.append({**v, **identify_vehicle(self.system_id, v.get("label")), "route": public_route, "route_name": route.get("long") or None,
                    "route_proximity": public_proximity,
                    "headsign": trip.get("headsign") or None, "route_color": route_color(route, rid),
                    "route_text_color": route.get("text_color") or None,
                    "block_id": trip.get("block_id") or None,
                    "stops": stop_context(index, v, now), "next_run": next_run(index, v, now)})
            result = {"vehicles": enriched, "count": len(enriched), "feed_timestamp": self.feed_timestamp,
                      "fetched_at": self.fetched_at, "revision": self.revision,
                      "poll_seconds": POLL_SECONDS, "metadata_ready": bool(index["routes"]),
                      "metadata_updated_at": index.get("updated_at"),
                      "system": self.system_id, "source": f"BC Transit / {self.name}"}
            self._snapshot_cache = result
            return {**result, "server_now": int(time.time()), "error": self.last_error,
                    "metadata_error": self.gtfs_error, "system": self.system_id}

    def all_stops(self) -> dict[str, Any]:
        """On-demand stop catalogue, never bundled with every GPS snapshot.

        The browser filters distances locally; the user's geolocation never needs
        to be included in an HTTP request to the app server.
        """
        with self.lock:
            index = self.index
            rows = index.get("stops", {})
            bounds = SYSTEMS[self.system_id]["bounds"]
            # Chilliwack includes FVX and surrounding communities; keep its
            # stop catalogue geographically limited to this transit view.
            result = [[sid, vals[0], vals[1], vals[2]] for sid, vals in rows.items()
                      if isinstance(vals, (tuple, list)) and len(vals) >= 3
                      and bounds[0] <= vals[1] <= bounds[1]
                      and bounds[2] <= vals[2] <= bounds[3]]
            return {"system": self.system_id, "ready": bool(rows),
                    "updated_at": index.get("updated_at"), "stops": result}

    def nearby_departures(self, stop_ids: list[str], now_ts: int | None = None) -> dict[str, Any]:
        """Published scheduled departures plus *fresh* GTFS-RT predictions.

        Stop IDs (not browser coordinates) are the only location-related input.
        No static index or expensive timetable scan is needed until requested.
        """
        ids = list(dict.fromkeys(str(s) for s in stop_ids if s))[:10]
        now_ts = int(time.time()) if now_ts is None else int(now_ts)
        now = datetime.fromtimestamp(now_ts, TIMEZONE)
        start_window, end_window = now_ts - 60, now_ts + 5400
        with self.lock:
            index = self.index
            if self._stop_timetable_index is None:
                by_stop = defaultdict(list)
                for trip_id, stops in index.get('trip_stops', {}).items():
                    for row in stops:
                        if len(row) < 4:
                            continue
                        sec = row[2] if row[2] is not None else row[3]
                        if sec is not None and row[1]:
                            by_stop[row[1]].append((trip_id, int(sec)))
                self._stop_timetable_index = dict(by_stop)
            table = self._stop_timetable_index
            feed_stamp = self.trip_feed_timestamp or self.trip_feed_fetched_at
            feed_fresh = bool(feed_stamp and abs(now_ts - feed_stamp) <= 180)
            updates = self.trip_updates if feed_fresh else {}
            results = []
            # Include the previous service day for >24h GTFS stop times and the
            # following service day when viewing just before midnight.
            bases = [(now + timedelta(days=delta)).replace(hour=0,minute=0,second=0,microsecond=0)
                     for delta in (-1, 0, 1)]
            for sid in ids:
                stop = index.get('stops', {}).get(sid)
                if not stop:
                    results.append({'stop_id':sid,'name':'Unknown stop','arrivals':[],'status':'unknown_stop'})
                    continue
                upcoming = {}
                for trip_id, sec in table.get(sid, []):
                    trip = index.get('trips', {}).get(trip_id, {})
                    service_id = trip.get('service_id')
                    if not service_id:
                        continue
                    route = index.get('routes', {}).get(trip.get('route_id'), {})
                    for base in bases:
                        at = int((base + timedelta(seconds=sec)).timestamp())
                        if not start_window <= at <= end_window or not service_active(index, service_id, base):
                            continue
                        key = (trip_id, base.strftime('%Y%m%d'))
                        upcoming[key] = {'trip_id':trip_id,'route':route.get('short') or '?',
                                         'destination':trip.get('headsign') or route.get('long') or 'Destination unavailable',
                                         'arrival_at':at,'source':'scheduled', 'scheduled_at':at}
                # TripUpdate is only used with a recent feed and an explicit
                # prediction for this stop. Never call stale GPS 'live'.
                for trip_id, update in updates.items():
                    stamp = update.get('timestamp') or feed_stamp
                    if not stamp or abs(now_ts - stamp) > 180:
                        continue
                    trip = index.get('trips', {}).get(trip_id, {})
                    route = index.get('routes', {}).get(trip.get('route_id'), {})
                    timetable = index.get('trip_stops', {}).get(trip_id, [])
                    by_sequence = {r[0]:r for r in timetable}
                    service_date = update.get('start_date')
                    base = None
                    try:
                        if service_date: base = datetime.strptime(service_date, '%Y%m%d').replace(tzinfo=TIMEZONE)
                    except ValueError:
                        base = None
                    for event in update.get('stops', []):
                        row = by_sequence.get(event.get('sequence')) if event.get('sequence') is not None else None
                        if row is None and event.get('id') == sid:
                            candidates = [r for r in timetable if r[1] == sid]
                            row = candidates[0] if len(candidates) == 1 else None
                        if row is None or row[1] != sid:
                            continue
                        eta = event.get('predicted_at')
                        if eta is None and event.get('delay_seconds') is not None and base:
                            sec = row[2] if row[2] is not None else row[3]
                            if sec is not None: eta = int((base + timedelta(seconds=sec+event['delay_seconds'])).timestamp())
                        if eta is None or not start_window <= eta <= end_window:
                            continue
                        key = (trip_id, service_date or now.strftime('%Y%m%d'))
                        prior = upcoming.get(key)
                        upcoming[key] = {'trip_id':trip_id,'route':route.get('short') or '?',
                                         'destination':trip.get('headsign') or route.get('long') or 'Destination unavailable',
                                         'arrival_at':int(eta),'source':'live',
                                         'scheduled_at':prior['scheduled_at'] if prior else None}
                ordered = sorted(upcoming.values(), key=lambda r:r['arrival_at'])[:7]
                results.append({'stop_id':sid,'name':stop[0], 'arrivals':ordered,
                                'status':'live' if any(r['source']=='live' for r in ordered) else
                                         'scheduled' if ordered else 'empty'})
            return {'system':self.system_id,'updated_at':now_ts,
                    'realtime_fresh':feed_fresh,'stops':results}

    def stop_arrivals(self, stop_id: str) -> dict[str, Any]:
        """Only publish a stop ETA when a fresh GTFS-RT trip update backs it.

        This is a short, on-demand board. Missing predictions remain unknown,
        not a scheduled time masquerading as realtime.
        """
        with self.lock:
            if stop_id not in self.index.get("stops", {}):
                return {"stop_id":stop_id,"status":"unknown_stop","arrivals":[]}
            updates = self.trip_updates
            index = self.index
            now = int(time.time())
            fetched = self.trip_feed_fetched_at
            stamp = self.trip_feed_timestamp or fetched
            if not stamp or abs(now - stamp) > 180:
                return {"stop_id":stop_id,"status":"stale","arrivals":[]}
            matches = []
            for trip_id, update in updates.items():
                updated = update.get("timestamp") or stamp
                if abs(now - updated) > 180:
                    continue
                trip = index.get("trips", {}).get(trip_id, {})
                route = index.get("routes", {}).get(trip.get("route_id"), {})
                timetable = index.get("trip_stops", {}).get(trip_id, [])
                by_sequence = {entry[0]:entry for entry in timetable}
                base = None
                service_date = update.get("start_date")
                if service_date:
                    try:
                        base = datetime.strptime(service_date, "%Y%m%d").replace(tzinfo=TIMEZONE)
                    except ValueError:
                        pass
                for event in update.get("stops", []):
                    sequence = event.get("sequence")
                    row = by_sequence.get(sequence) if sequence is not None else None
                    if row is None and event.get("id") == stop_id:
                        candidates = [r for r in timetable if r[1] == stop_id]
                        row = candidates[0] if len(candidates) == 1 else None
                    if row is None or row[1] != stop_id:
                        continue
                    eta = event.get("predicted_at")
                    if eta is None and event.get("delay_seconds") is not None and base:
                        scheduled = row[2] if row[2] is not None else row[3]
                        if scheduled is not None:
                            eta = int((base + timedelta(seconds=scheduled+event["delay_seconds"])).timestamp())
                    if eta is None or not now-90 <= eta <= now + 7200:
                        continue
                    matches.append({"trip_id":trip_id,"route":route.get("short") or "?",
                                    "destination":trip.get("headsign") or route.get("long") or "Unknown",
                                    "arrival_at":int(eta)})
            matches.sort(key=lambda x: x["arrival_at"])
            # A stop can appear repeatedly in a circular trip; avoid duplicate
            # trip/ETA rows when the feed has multiple equivalent entries.
            seen = set(); unique=[]
            for row in matches:
                key=(row["trip_id"],row["arrival_at"])
                if key not in seen:
                    seen.add(key);unique.append(row)
                if len(unique)>=12:
                    break
            return {"stop_id":stop_id,"status":"live" if unique else "unavailable",
                    "fetched_at":fetched,"arrivals":unique}

    def route_detail(self, trip_id: str) -> dict[str, Any] | None:
        with self.lock:
            index = self.index
            trip = index["trips"].get(trip_id)
            if not trip:
                return None
            route = index["routes"].get(trip["route_id"], {})
            rows = index.get("trip_stops", {}).get(trip_id, [])
            return {"trip_id": trip_id, "route": route.get("short"), "headsign": trip.get("headsign"),
                    "color": route_color(route, trip["route_id"]),
                    "shape": index.get("shapes", {}).get(trip.get("shape_id") or "", []),
                    "stops": [brief for item in rows if (brief := _stop_brief(index,item))]}


def _vehicle_worker(tracker: Tracker) -> None:
    while True:
        try:
            data = fetch_bytes(tracker.urls["vehicle"], MAX_FEED_BYTES)
            tracker.update_feed(data)
            print(f"[{tracker.system_id}:vehicles] {len(tracker.vehicles)} vehicles / {time.strftime('%H:%M:%S')}")
        except Exception as exc:
            with tracker.lock:
                tracker.last_error = f"Vehicle feed: {exc}"
            print(f"[vehicles] ERROR: {exc}")
        time.sleep(POLL_SECONDS)


def _trip_worker(tracker: Tracker) -> None:
    while True:
        try:
            tracker.update_trip_feed(fetch_bytes(tracker.urls["trip"], MAX_FEED_BYTES))
        except Exception as exc:
            with tracker.lock:
                tracker.trip_feed_error = f"Trip-update feed: {exc}"
            print(f"[trip updates] ERROR: {exc}")
        time.sleep(max(20, POLL_SECONDS))


def _static_worker(tracker: Tracker) -> None:
    while True:
        age = time.time() - (tracker.index.get("updated_at") or 0)
        if age < 24*3600:
            time.sleep(min(300, max(30, 24*3600-age)))
            continue
        try:
            print("[GTFS] Fetching stops, shapes, trips and vehicle blocks...")
            with STATIC_PARSE_LOCK:
                index = parse_static_gtfs(fetch_bytes(tracker.urls["static"], MAX_ZIP_BYTES))
                tracker.update_index(index)
            print(f"[GTFS] {len(index['routes'])} routes, {len(index['trips'])} trips, "
                  f"{len(index['blocks'])} scheduled blocks, {len(index['shapes'])} shapes")
        except Exception as exc:
            with tracker.lock:
                tracker.gtfs_error = f"Schedule data: {exc}"
            print(f"[GTFS] ERROR: {exc}")
            time.sleep(600)


mimetypes.add_type("application/manifest+json", ".webmanifest")


class Handler(SimpleHTTPRequestHandler):
    trackers: dict[str, Tracker] = {}

    def _system_tracker(self, query: str) -> Tracker | None:
        params = urllib.parse.parse_qs(query)
        system = params.get("system", ["victoria"])[0]
        return self.trackers.get(system)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/config.js" and os.environ.get("CARTO_BASEMAPS_KEY"):
            # Public basemap browser keys are not secrets. Restrict yours to the deployment host.
            self._javascript("window.BUS_RADAR_CONFIG = {cartoKey: " +
                             json.dumps(os.environ["CARTO_BASEMAPS_KEY"]) + "};\n")
            return
        if parsed.path == "/api/systems":
            self._json({"systems": [{"id": ident, "name": cfg["name"], "center": cfg["center"],
                                      "zoom": cfg["zoom"]} for ident, cfg in SYSTEMS.items()]})
            return
        if parsed.path.startswith("/api/"):
            tracker = self._system_tracker(parsed.query)
            if tracker is None:
                self._json({"error":"Unknown transit system"}, 400)
                return
        if parsed.path == "/api/vehicles":
            params = urllib.parse.parse_qs(parsed.query)
            try: since = int(params.get("since", [""])[0])
            except ValueError: since = None
            self._json(tracker.snapshot(since))
            return
        if parsed.path == "/api/alerts":
            self._json(tracker.get_alerts())
            return
        if parsed.path == "/api/last-known":
            params = urllib.parse.parse_qs(parsed.query)
            fleet = params.get('fleet', [''])[0]
            ident = params.get('vehicle_id', [''])[0]
            if tracker.history is None:
                self._json({'error': 'History recorder unavailable'}, 503)
            else:
                try:
                    self._json(tracker.history.last_known(tracker.system_id, vehicle_id=ident, fleet=fleet))
                except ValueError as exc:
                    self._json({'error': str(exc)}, 400)
                except sqlite3.DatabaseError:
                    self._json({'error': 'History storage unavailable'}, 503)
            return
        if parsed.path == "/api/stops":
            self._json(tracker.all_stops())
            return
        if parsed.path == "/api/nearby-departures":
            params = urllib.parse.parse_qs(parsed.query)
            requested = params.get('stop_id', [])
            if not requested or len(requested) > 10 or any(not sid or len(sid)>128 for sid in requested):
                self._json({'error':'Provide up to ten valid stop IDs'},400)
            else:
                self._json(tracker.nearby_departures(requested))
            return
        if parsed.path == "/api/stop-arrivals":
            params = urllib.parse.parse_qs(parsed.query)
            stop_id = params.get("stop_id", [""])[0]
            if not stop_id or len(stop_id) > 128:
                self._json({"error":"Missing stop ID"},400)
            else:
                self._json(tracker.stop_arrivals(stop_id))
            return
        if parsed.path == "/api/arrivals":
            params = urllib.parse.parse_qs(parsed.query)
            trip_id = params.get("trip_id", [""])[0]
            if not trip_id or len(trip_id) > 256:
                self._json({"error": "Missing trip ID"}, 400)
            else:
                self._json(tracker.arrivals_for_trip(trip_id))
            return
        if parsed.path == "/api/history":
            params = urllib.parse.parse_qs(parsed.query)
            vehicle_id = params.get("vehicle_id", [""])[0]
            try:
                minutes = int(params.get("minutes", ["30"])[0])
                if tracker.history is None:
                    self._json({"error": "History recorder unavailable"}, 503)
                else:
                    self._json(tracker.history.get(tracker.system_id, vehicle_id, minutes))
            except (ValueError, TypeError) as exc:
                self._json({"error": str(exc)}, 400)
            except sqlite3.DatabaseError:
                self._json({"error": "History storage unavailable"}, 503)
            return
        if parsed.path == "/api/activity":
            params = urllib.parse.parse_qs(parsed.query)
            vehicle_id = params.get("vehicle_id", [""])[0]
            try:
                minutes = int(params.get("minutes", ["180"])[0])
                if tracker.history is None:
                    self._json({"error": "History recorder unavailable"}, 503)
                else:
                    self._json(tracker.history.activity(tracker.system_id, vehicle_id, minutes))
            except (ValueError, TypeError) as exc:
                self._json({"error": str(exc)}, 400)
            except sqlite3.DatabaseError:
                self._json({"error": "History storage unavailable"}, 503)
            return
        if parsed.path == "/api/route":
            params = urllib.parse.parse_qs(parsed.query)
            trip_id = params.get("trip_id", [""])[0]
            if not trip_id or len(trip_id) > 256:
                self._json({"error": "Missing trip ID"}, 400)
                return
            detail = tracker.route_detail(trip_id)
            if detail is None:
                self._json({"error": "No GTFS trip metadata for this vehicle"}, 404)
            else:
                self._json(detail)
            return
        if parsed.path == "/api/health":
            snap = tracker.snapshot()
            self._json({k:v for k,v in snap.items() if k != "vehicles"})
            return
        if parsed.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def _javascript(self, data: str) -> None:
        body = data.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/javascript; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: dict[str, Any], code: int = 200) -> None:
        body = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        if len(body) > 4096 and "gzip" in self.headers.get("Accept-Encoding", ""):
            body = gzip.compress(body, compresslevel=3)
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self) -> None:
        path = urllib.parse.urlsplit(self.path).path
        if path == "/config.js" and not os.environ.get("CARTO_BASEMAPS_KEY"):
            self.send_header("Cache-Control", "no-store")
        if not path.startswith("/api/") and path != "/config.js":
            # The SW owns immutable versioned app files; avoid stale HTML/manifest.
            if path in ("/", "/index.html", "/sw.js", "/manifest.webmanifest"):
                self.send_header("Cache-Control", "no-cache, must-revalidate")
            elif path in ("/pwa.js", "/app.js", "/style.css", "/classic.css", "/classic-dark.css", "/mobile.css", "/v27.css", "/v28.css", "/v30.css", "/v30b.css", "/v30rc.css", "/config.js"):
                self.send_header("Cache-Control", "no-cache")
            else:
                self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        super().end_headers()


def run() -> None:
    parser = argparse.ArgumentParser(description="BC Transit Bus Radar V3.3 (multi-system web + Android PWA)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address; use 0.0.0.0 only behind a trusted host")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8765")))
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    # Mount an optional Railway volume at /data and set BCT_HISTORY_DB to
    # /data/history.sqlite3. The default ./cache path is local/ephemeral.
    history_path = os.environ.get("BCT_HISTORY_DB") or str(CACHE_DIR / "history.sqlite3")
    history = None
    try:
        history = GPSHistory(history_path)
        print(f"[history] recording public fleet GPS fixes to {history_path}")
        if not os.environ.get("BCT_HISTORY_DB"):
            print("[history] INFO: default local path is ephemeral on Railway. "
                  "Mount a volume and configure BCT_HISTORY_DB for persistence.")
    except (OSError, sqlite3.Error) as exc:
        print(f"[history] DISABLED: {exc}; live tracking still works")
    trackers = {ident: Tracker(ident, history) for ident in SYSTEMS}
    Handler.trackers = trackers
    try:
        server = ThreadingHTTPServer((args.host, args.port), Handler)
        server.daemon_threads = True
    except OSError as exc:
        raise SystemExit(f"Cannot start server on port {args.port}: {exc}") from exc
    for tracker in trackers.values():
        threading.Thread(target=_vehicle_worker, args=(tracker,), daemon=True).start()
        threading.Thread(target=_trip_worker, args=(tracker,), daemon=True).start()
        threading.Thread(target=_static_worker, args=(tracker,), daemon=True).start()
    url = f"http://127.0.0.1:{args.port}"
    print(f"\nBC Transit Bus Radar V3.3 — serving on {args.host}:{args.port}\n"
          f"Local URL: {url}\nPress Ctrl+C to stop.\n")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.server_close()
        if history is not None:
            history.close()


if __name__ == "__main__":
    run()
