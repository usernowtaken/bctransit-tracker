/* Victoria Bus Radar V2.5 — classic light and classic dark maps; never simulates live buses. */
(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const INITIAL_VIEW = { lat: 48.48, lon: -123.49, zoom: 10 };
  const MAX_LIST = 120;
  const CLIENT_REFRESH_MS = 5000; // Checks local cache; upstream refresh remains 15s by default.
  const routeCache = new Map();
  const state = {
    map: null,
    tileLayer: null,
    theme: 'classic',
    vehicles: [],
    data: null,
    markers: new Map(),
    query: '',
    selected: null,
    following: false,
    requestPending: false,
    clientError: null,
    restoredCache: false,
    closed: false,
    routeLayer: null,
    routeTrip: null,
    routeRequestSerial: 0,
    positionRefresh: false,
    routeMetadataStamp: null,
    routeStopSignature: null,
    needsListRefresh: false,
    routeDetail: null,
    stopMarkers: new Map(),
    arrivalsTrip: null,
    arrivals: new Map(),
    arrivalStatus: 'unavailable',
    arrivalsPending: false,
    arrivalsLoadingTrip: null,
  };

  function safe(value) {
    return String(value ?? '').replace(/[&<>"']/g, (s) => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[s]));
  }
  function mapLabel(vehicle) {
    const state = vehicle?.route_proximity?.state;
    if (state === 'possible_nis') return 'NIS?';
    if (state === 'far') return 'OFF?';
    return label(vehicle?.route);
  }
  function routeWarning(vehicle) {
    const status = vehicle?.route_proximity?.state;
    return status === 'possible_nis' || status === 'far';
  }
  function label(route) { return String(route || '?').slice(0, 7); }
  function timeAgo(timestamp) {
    if (typeof timestamp !== 'number' || timestamp <= 0) return 'Unknown';
    const seconds = Math.max(0, Math.round(Date.now() / 1000 - timestamp));
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    return `${Math.floor(seconds / 3600)}h ago`;
  }
  function filteredVehicles() {
    const needle = state.query.trim().toUpperCase();
    if (!needle) return state.vehicles;
    if (needle === 'NIS' || needle === 'NIS?') return state.vehicles.filter((v) => v.route_proximity?.state === 'possible_nis');
    if (needle === 'OFF' || needle === 'OFF?') return state.vehicles.filter(routeWarning);
    return state.vehicles.filter((v) => String(v.route || '').toUpperCase().startsWith(needle));
  }
  function status() {
    const data = state.data;
    if (!data) return { text: 'CONNECTING', cls: '', sub: 'Awaiting GPS positions' };
    const stamps = state.vehicles.map((v) => Number(v.timestamp || 0));
    const newest = stamps.length ? Math.max(...stamps) : 0;
    const sourceTime = Number(data.feed_timestamp || newest || data.fetched_at || 0);
    const age = sourceTime ? Math.max(0, Date.now() / 1000 - sourceTime) : Infinity;
    if (state.clientError || data.error) return {
      text: 'FEED ISSUE', cls: 'error', sub: sourceTime ? `Data ${timeAgo(sourceTime)}` : 'Feed unavailable',
    };
    if (!data.fetched_at) return { text: 'CONNECTING', cls: '', sub: 'Awaiting GPS positions' };
    if (state.restoredCache || age > 120) return {
      text: state.restoredCache ? 'CACHED' : 'STALE DATA', cls: 'stale',
      sub: sourceTime ? `Data ${timeAgo(sourceTime)}` : 'No GPS time reported',
    };
    if (data.count === 0) return { text: 'NO BUSES', cls: 'stale', sub: 'Feed reports no vehicles' };
    return { text: 'LIVE FEED', cls: 'live', sub: `GPS ${timeAgo(sourceTime)}` };
  }
  function renderStatus() {
    const current = status();
    $('statusPill').className = `status-pill ${current.cls}`;
    $('statusText').textContent = current.text;
    $('freshness').textContent = current.sub;
    $('busCount').textContent = state.data ? state.vehicles.length.toLocaleString() : '—';
    $('routeCount').textContent = state.data
      ? new Set(state.vehicles.map((v) => v.route).filter(Boolean)).size.toLocaleString()
      : '—';
    $('refreshNote').textContent = `Live source: ~${state.data?.poll_seconds || 15}s · Local check: 5s`;
    if (state.selected) updateDetails();
  }
  function displayName(vehicle) {
    return vehicle.headsign || vehicle.route_name || 'Destination unavailable';
  }
  function renderList() {
    // On a phone, don't rebuild an invisible list every time a new GPS frame arrives.
    if (window.innerWidth <= 720 && state.closed && !state.selected) {
      state.needsListRefresh = true;
      return;
    }
    state.needsListRefresh = false;
    const list = $('busList');
    const filtered = [...filteredVehicles()].sort((a, b) => {
      const routeCompare = String(a.route || '~').localeCompare(String(b.route || '~'), undefined, {numeric:true});
      return routeCompare || String(a.id).localeCompare(String(b.id));
    });
    $('listHeading').textContent = state.query ? `Routes matching “${state.query}”` : 'Active buses';
    $('resultCount').textContent = filtered.length.toLocaleString();
    let hint = 'Showing the latest available vehicle positions.';
    if (!state.data) hint = 'Connecting to the live feed…';
    else if (state.data.error || state.clientError) hint = 'Live feed unavailable. Showing last received positions, if any.';
    else if (state.restoredCache) hint = 'Previously cached positions; checking for new data…';
    else if (state.data.fetched_at && !state.data.metadata_ready)
      hint = 'Loading route numbers from schedule data. Some routes may show “?”.';
    $('listHint').textContent = hint;

    const fragment = document.createDocumentFragment();
    if (!filtered.length) {
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.textContent = !state.data ? 'Waiting for BC Transit to respond…'
        : state.query ? 'No currently reported buses match this route.'
          : 'No vehicle positions are currently available.';
      fragment.appendChild(empty);
    } else {
      for (const vehicle of filtered.slice(0, MAX_LIST)) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `bus-item${state.selected === vehicle.id ? ' selected' : ''}`;
        button.setAttribute('role', 'listitem');
        button.setAttribute('aria-label', `${routeWarning(vehicle) ? 'Possibly off scheduled route, ' : ''}reported route ${label(vehicle.route)}, ${displayName(vehicle)}, vehicle ${vehicle.id}`);
        const route = document.createElement('span'); route.className = 'bus-route'; route.textContent = mapLabel(vehicle); route.classList.toggle('offroute', routeWarning(vehicle)); route.style.borderLeft = `3px solid ${routeColor(vehicle)}`;
        const meta = document.createElement('span'); meta.className = 'bus-meta';
        const name = document.createElement('span'); name.className = 'bus-name'; name.textContent = routeWarning(vehicle) ? `Reported route ${label(vehicle.route)} · ${displayName(vehicle)}` : displayName(vehicle);
        const extra = document.createElement('span'); extra.className = 'bus-extra';
        extra.textContent = vehicle.label ? `Feed label: ${vehicle.label}` : `Vehicle ID: ${vehicle.id}`;
        meta.append(name, extra);
        const age = document.createElement('span'); age.className = 'bus-age'; age.textContent = timeAgo(vehicle.timestamp);
        button.append(route, meta, age);
        button.addEventListener('click', () => selectVehicle(vehicle.id, true));
        fragment.appendChild(button);
      }
    }
    list.replaceChildren(fragment);
    $('listMore').hidden = filtered.length <= MAX_LIST;
    if (filtered.length > MAX_LIST) $('listMore').textContent = `Showing first ${MAX_LIST} of ${filtered.length} buses. Filter by route to narrow results.`;
  }
  function updateDetails() {
    const vehicle = state.vehicles.find((v) => v.id === state.selected);
    if (!vehicle) return;
    $('detailRoute').textContent = label(vehicle.route);
    $('detailTitle').textContent = vehicle.route ? `Route ${vehicle.route}` : 'Route unavailable';
    $('detailDestination').textContent = displayName(vehicle);
    const proximity = vehicle.route_proximity || {};
    const proximityStatus = $('detailProximityStatus');
    const proximityNote = $('detailProximityNote');
    const observedDistance = Number.isFinite(proximity.distance_m)
      ? `${proximity.distance_m.toLocaleString()} m from scheduled route line` : '';
    proximityStatus.className = 'proximity-status';
    if (proximity.state === 'possible_nis') {
      proximityStatus.textContent = 'NIS? · Possibly deadheading';
      proximityStatus.classList.add('warning');
      proximityNote.textContent = `${observedDistance}. Repeated GPS observations outside the 600 m buffer. Feed still reports Route ${label(vehicle.route)}; not confirmed NIS. Could be a detour or outdated trip assignment.`;
    } else if (proximity.state === 'far') {
      proximityStatus.textContent = 'OFF? · Away from scheduled route';
      proximityStatus.classList.add('caution');
      proximityNote.textContent = `${observedDistance}. One fresh GPS observation beyond 600 m. Waiting for another distinct update before suggesting NIS.`;
    } else if (proximity.state === 'near') {
      proximityStatus.textContent = 'Near scheduled route';
      proximityStatus.classList.add('good');
      proximityNote.textContent = `${observedDistance}. ${proximity.basis || 'Compared against GTFS geometry'}. Distance is approximate.`;
    } else {
      proximityStatus.textContent = 'Cannot determine';
      proximityNote.textContent = `${proximity.basis || 'No usable trip and GPS geometry.'} Unknown does not mean NIS.`;
    }
    $('detailRouteId').textContent = vehicle.route_id || 'Not supplied';
    $('detailFeedLabel').textContent = vehicle.label || 'Not supplied';
    $('detailId').textContent = vehicle.id || '—';
    $('detailAge').textContent = timeAgo(vehicle.timestamp);
    $('detailSpeed').textContent = Number.isFinite(vehicle.speed_mps) ? `${Math.round(vehicle.speed_mps * 3.6)} km/h` : 'Not provided';
    $('detailBearing').textContent = Number.isFinite(vehicle.bearing) ? `${Math.round(vehicle.bearing)}°` : 'Not provided';
    $('detailLat').textContent = Number(vehicle.lat).toFixed(5);
    $('detailLon').textContent = Number(vehicle.lon).toFixed(5);
    $('detailTrip').textContent = vehicle.trip_id || 'Unavailable';
    $('detailBlock').textContent = vehicle.block_id || 'Not published';
    $('detailOccupancy').textContent = occupancyName(vehicle.occupancy);
    $('detailStopStatus').textContent = vehicle.stop_sequence == null && !vehicle.stop_id
      ? 'Not provided' : ({0:'Approaching stop',1:'At stop',2:'In transit to stop'}[vehicle.stop_status] || 'Unknown');
    $('detailRoute').style.background = routeColor(vehicle);
    const context = vehicle.stops || {};
    $('detailPreviousStop').textContent = context.previous?.name || 'Unknown';
    $('detailNextStop').textContent = context.next?.name || 'Unknown';
    $('detailStopBasis').textContent = (context.basis === 'unavailable' ? 'No stop position information available' : (context.basis || 'Unavailable')) + (routeWarning(vehicle) ? ' · Caution: reported stop progress may not reflect this GPS position.' : '');
    const next = vehicle.next_run;
    if (next) {
      const nextLabel = next.route ? `Route ${next.route}` : 'Next scheduled trip';
      $('detailRouteChange').textContent = `${nextLabel}${next.headsign ? ` · ${next.headsign}` : ''}`;
      $('detailRouteChangeNote').textContent = `${next.different_route ? 'Possible route change' : 'Same route, next trip'} at ${next.starts_at} · Scheduled only; not confirmed${routeWarning(vehicle) ? ' · Vehicle appears off its assigned trip, so this prediction may not apply' : ''}`;
      $('detailRouteChange').style.color = state.theme === 'classic' ? '#1664bb' : '#8ab4f8';
    } else {
      $('detailRouteChange').textContent = 'Not determinable';
      $('detailRouteChangeNote').textContent = vehicle.block_id
        ? 'No safe next-trip match in the published schedule for this service day.'
        : 'No GTFS vehicle block is available. We will not guess the next route.';
      $('detailRouteChange').style.color = '';
    }
    $('detailOverlayStatus').textContent = !vehicle.trip_id ? 'Live feed has no trip ID for this bus' :
      state.routeTrip === vehicle.trip_id ? $('detailOverlayStatus').textContent : 'Retrieving route line and stop locations…';
    $('followButton').textContent = `Follow vehicle: ${state.following ? 'ON' : 'OFF'}`;
    $('followButton').classList.toggle('on', state.following);
  }
  function selectVehicle(id, center) {
    const vehicle = state.vehicles.find((v) => v.id === id);
    if (!vehicle) return;
    state.selected = id;
    document.body.classList.add('detail-open');
    $('detailSection').hidden = false;
    document.querySelector('.fleet-section').hidden = true;
    document.querySelector('.search-section').hidden = true;
    document.querySelector('.stats-row').hidden = true;
    updateDetails();
    if (state.arrivalsTrip !== vehicle.trip_id) {
      state.arrivals = new Map();
      state.arrivalsTrip = vehicle.trip_id || null;
      state.arrivalStatus = 'unavailable';
    }
    loadSelectedRoute(vehicle);
    refreshSelectedArrivals();
    if (center && state.map) state.map.setView([vehicle.lat, vehicle.lon], Math.max(state.map.getZoom(), 13), { animate:false });
    renderMap();
    renderList();
    // Tapping a marker should expose the bus details on phones.
    if (window.innerWidth <= 720) setSidebar(true);
  }
  function leaveDetails() {
    document.body.classList.remove('detail-open');
    state.selected = null;
    state.following = false;
    state.routeRequestSerial++;
    state.routeDetail = null;
    state.stopMarkers.clear();
    state.arrivals = new Map();
    state.arrivalsTrip = null;
    state.arrivalStatus = 'unavailable';
    state.routeTrip = null;
    state.routeMetadataStamp = null;
    state.routeStopSignature = null;
    if (state.routeLayer) state.routeLayer.clearLayers();
    $('detailSection').hidden = true;
    document.querySelector('.fleet-section').hidden = false;
    document.querySelector('.search-section').hidden = false;
    document.querySelector('.stats-row').hidden = false;
    renderMap();
    renderList();
  }
  function setFilter(query) {
    state.query = query.trim().toUpperCase().slice(0, 12);
    $('routeSearch').value = state.query;
    $('clearSearch').hidden = !state.query;
    document.querySelectorAll('.quick-chip').forEach((chip) => chip.classList.toggle('active', chip.dataset.route === state.query));
    try { localStorage.setItem('bct_route_filter', state.query); } catch (_) {}
    renderList();
    renderMap();
  }
  function routeColor(vehicle) {
    const color = vehicle?.route_color;
    return typeof color === 'string' && /^#[0-9A-Fa-f]{6}$/.test(color) ? color : '#59ddb7';
  }
  function occupancyName(value) {
    const names = {0:'Not reported',1:'Empty',2:'Many seats available',3:'Few seats available',4:'Standing room',5:'Crushed standing room',6:'Full',7:'Not accepting passengers'};
    return Object.prototype.hasOwnProperty.call(names,value) ? names[value] : 'Not provided';
  }
  function markerIcon(vehicle, selected) {
    const text = safe(mapLabel(vehicle));
    const colored = selected || (state.query && String(vehicle.route || '').toUpperCase().startsWith(state.query));
    const color = routeColor(vehicle);
    const bearing = Number.isFinite(vehicle.bearing) ? vehicle.bearing : null;
    const arrow = bearing === null ? '' : `<span class="heading-ring" style="--heading:${Math.round(bearing)}deg"><span class="heading-tip"></span></span>`;
    const warning = routeWarning(vehicle) ? ` possible-offroute ${vehicle.route_proximity.state}` : '';
    const html = `<div class="bus-marker v2-marker ${selected ? 'selected' : ''} ${colored ? 'route-colored' : ''}${warning}" style="--route-color:${color}" title="${warning ? safe(`Reported route ${label(vehicle.route)}; possible off-route`) : safe(`Route ${label(vehicle.route)}`)}">${arrow}<span class="marker-label">${text}</span></div>`;
    return L.divIcon({className:'vehicle-icon',html,iconSize:[46,38],iconAnchor:[23,20]});
  }
  function clusterIcon(count) {
    const html = count === 1 ? '<div class="bus-dot"></div>' : `<div class="bus-cluster">${count}</div>`;
    return L.divIcon({ className:'cluster-icon', html, iconSize:[30,30], iconAnchor:[15,15] });
  }
  function computeVisibleMarkers() {
    const map = state.map;
    const bounds = map.getBounds().pad(0.18);
    const visible = filteredVehicles().filter((v) => bounds.contains([v.lat, v.lon]));
    if (map.getZoom() > 11) return visible.map((v) => ({ key:`bus:${v.id}`, lat:v.lat, lon:v.lon, type:'bus', vehicle:v }));
    // Render fewer markers when zoomed out; map projection gives stable cell sizes.
    const size = map.getZoom() < 10 ? 46 : 38;
    const groups = new Map();
    for (const v of visible) {
      const p = map.project([v.lat, v.lon], map.getZoom());
      const x = Math.floor(p.x / size); const y = Math.floor(p.y / size);
      const key = `${x}:${y}`;
      if (!groups.has(key)) groups.set(key, {key:`cluster:${key}`, lat:0, lon:0, count:0, vehicle:v});
      const group = groups.get(key); group.lat += v.lat; group.lon += v.lon; group.count++;
    }
    return [...groups.values()].map((g) => ({...g, lat:g.lat/g.count, lon:g.lon/g.count, type:'cluster'}));
  }
  function renderMap() {
    if (!state.map) return;
    const desired = computeVisibleMarkers();
    const keep = new Set();
    for (const item of desired) {
      keep.add(item.key);
      const selected = item.type === 'bus' && item.vehicle.id === state.selected;
      const sig = item.type === 'bus'
        ? `b:${mapLabel(item.vehicle)}:${Math.round(item.vehicle.bearing || 0)}:${routeColor(item.vehicle)}:${selected}:${state.query}`
        : `c:${item.count}`;
      let record = state.markers.get(item.key);
      if (!record) {
        const icon = item.type === 'bus' ? markerIcon(item.vehicle, selected) : clusterIcon(item.count);
        const marker = L.marker([item.lat,item.lon], { icon, keyboard:true, zIndexOffset:selected ? 1000 : 0 });
        marker.on('click', () => {
          if (item.type === 'bus') selectVehicle(item.vehicle.id, true);
          else if (item.count === 1) selectVehicle(item.vehicle.id, true);
          else state.map.setView([item.lat, item.lon], Math.min(16, state.map.getZoom()+2), { animate:false });
        });
        marker.addTo(state.map);
        record = {marker, sig}; state.markers.set(item.key, record);
      } else {
        const previous = record.marker.getLatLng();
        if (Math.abs(previous.lat-item.lat)>0.000001 || Math.abs(previous.lng-item.lon)>0.000001)
        {
          // Ease only actual position corrections, not map pans or zooms.
          const element = record.marker.getElement();
          if (element && state.positionRefresh && item.type === 'bus' && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            element.style.transition = 'transform 0.8s ease-out';
            setTimeout(() => { if (element.isConnected) element.style.transition = ''; }, 850);
          }
          record.marker.setLatLng([item.lat,item.lon]);
        }
        if (record.sig !== sig) {
          record.marker.setIcon(item.type === 'bus' ? markerIcon(item.vehicle,selected) : clusterIcon(item.count));
          record.marker.setZIndexOffset(selected ? 1000 : 0);
          record.sig = sig;
        }
        // A marker may persist across updates; rebind to the latest vehicle data.
        record.marker.off('click');
        record.marker.on('click', () => {
          if (item.type === 'bus' || item.count === 1) selectVehicle(item.vehicle.id, true);
          else state.map.setView([item.lat,item.lon], Math.min(16,state.map.getZoom()+2), {animate:false});
        });
      }
    }
    for (const [key, record] of state.markers) {
      if (!keep.has(key)) {record.marker.remove(); state.markers.delete(key);}
    }
  }
  function arrivalForStop(item) {
    const prediction = state.arrivals.get(Number(item.sequence));
    if (prediction && Number.isFinite(prediction.predicted_at)) {
      const time = new Intl.DateTimeFormat('en-CA', {
        timeZone:'America/Vancouver', hour:'2-digit', minute:'2-digit', hour12:false,
      }).format(new Date(prediction.predicted_at * 1000));
      return {text:`Estimated arrival: ${time}`, live:true};
    }
    return item.scheduled
      ? {text:`Scheduled arrival: ${item.scheduled}`, live:false}
      : {text:'Arrival time not published', live:false};
  }
  function stopPopupContent(item) {
    const current = state.vehicles.find((v) => v.id === state.selected);
    const prev = current?.stops?.previous?.sequence === item.sequence;
    const next = current?.stops?.next?.sequence === item.sequence;
    const context = next ? 'Next stop' : prev ? 'Previous/current stop' : `Stop ${item.sequence}`;
    const arrival = arrivalForStop(item);
    return `<div class="stop-popup"><strong>${safe(item.name)}</strong>` +
      `<small>${safe(context)}</small>` +
      `<span class="${arrival.live ? 'live-arrival' : ''}">${safe(arrival.text)}</span>` +
      (arrival.live && item.scheduled ? `<small>Timetable: ${safe(item.scheduled)}</small>` : '') +
      (current && routeWarning(current) ? '<small>Bus appears off-route; arrival may not reflect its current location.</small>' : '') +
      '</div>';
  }
  function updateStopInterfaces() {
    const detail = state.routeDetail;
    const status = $('arrivalFeedStatus');
    status.textContent = state.arrivalStatus === 'live'
      ? 'Live estimates from BC Transit trip updates where provided; other times are scheduled.'
      : 'No fresh trip-specific arrival estimates. Times below are scheduled, not live.';
    const list = $('allStopsList');
    list.replaceChildren();
    if (!detail || !Array.isArray(detail.stops) || !detail.stops.length) {
      const message = document.createElement('div');
      message.className = 'stop-list-empty';
      message.textContent = 'No stop list available for this trip.';
      list.append(message);
      return;
    }
    const current = state.vehicles.find((v) => v.id === state.selected);
    const prevSeq = current?.stops?.previous?.sequence;
    const nextSeq = current?.stops?.next?.sequence;
    const fragment = document.createDocumentFragment();
    for (const item of detail.stops) {
      const button = document.createElement('button');
      button.type = 'button';
      const isNext = item.sequence === nextSeq;
      const isPrev = item.sequence === prevSeq;
      button.className = `stop-list-row${isNext ? ' next' : isPrev ? ' previous' : ''}`;
      button.title = `Show ${item.name} on the map`;
      const name = document.createElement('span');
      name.className = 'stop-list-name';
      name.textContent = `${item.sequence}. ${item.name}`;
      const when = document.createElement('span');
      const arrival = arrivalForStop(item);
      when.className = `stop-list-time${arrival.live ? ' estimated' : ''}`;
      when.textContent = arrival.text;
      button.append(name, when);
      button.addEventListener('click', () => {
        const marker = state.stopMarkers.get(Number(item.sequence));
        if (state.map) {
          state.map.setView([item.lat, item.lon], Math.max(14, state.map.getZoom()), {animate:false});
          if (marker) marker.openPopup();
        }
        if (window.innerWidth <= 720) setSidebar(false);
      });
      fragment.append(button);
    }
    list.append(fragment);
    for (const item of detail.stops) {
      const marker = state.stopMarkers.get(Number(item.sequence));
      if (marker) marker.setPopupContent(stopPopupContent(item));
    }
  }
  async function refreshSelectedArrivals() {
    const selected = state.vehicles.find((v) => v.id === state.selected);
    if (!selected?.trip_id) return;
    const tripId = selected.trip_id;
    if (state.arrivalsPending && state.arrivalsLoadingTrip === tripId) return;
    state.arrivalsPending = true;
    state.arrivalsLoadingTrip = tripId;
    try {
      const response = await fetch(`/api/arrivals?trip_id=${encodeURIComponent(tripId)}`, {cache:'no-store'});
      if (!response.ok) throw new Error(`Arrivals HTTP ${response.status}`);
      const payload = await response.json();
      if (state.selected !== selected.id || tripId !== state.arrivalsTrip) return;
      state.arrivals = new Map((payload.stops || [])
        .filter((s) => Number.isFinite(s.sequence) && Number.isFinite(s.predicted_at))
        .map((s) => [Number(s.sequence), s]));
      state.arrivalStatus = payload.status || 'unavailable';
      updateStopInterfaces();
    } catch (_) {
      if (state.selected === selected.id) {
        state.arrivals = new Map();
        state.arrivalStatus = 'unavailable';
        updateStopInterfaces();
      }
    } finally {
      if (state.arrivalsLoadingTrip === tripId) {
        state.arrivalsPending = false;
        state.arrivalsLoadingTrip = null;
      }
    }
  }
  async function loadSelectedRoute(vehicle) {
    const tripId = vehicle.trip_id;
    state.routeRequestSerial++;
    const token = state.routeRequestSerial;
    state.routeTrip = tripId || null;
    state.routeMetadataStamp = state.data?.metadata_updated_at || null;
    state.routeStopSignature = `${vehicle.stops?.previous?.sequence ?? ''}:${vehicle.stops?.next?.sequence ?? ''}`;
    state.routeDetail = null;
    state.stopMarkers.clear();
    if (state.routeLayer) state.routeLayer.clearLayers();
    if (!tripId) {
      $('detailOverlayStatus').textContent = 'No trip identifier supplied';
      updateStopInterfaces();
      return;
    }
    const apply = (detail) => {
      if (state.selected !== vehicle.id || token !== state.routeRequestSerial) return;
      state.routeDetail = detail;
      state.stopMarkers.clear();
      if (state.routeLayer) state.routeLayer.clearLayers();
      const points = Array.isArray(detail.shape) ? detail.shape : [];
      if (state.routeLayer && points.length > 1) {
        L.polyline(points, {color: state.theme === 'classic' ? '#545454' : '#3f4247', weight: 8, opacity: 0.62, interactive: false}).addTo(state.routeLayer);
        L.polyline(points, {color: detail.color || routeColor(vehicle), weight: 4.5, opacity: 0.98, interactive: false}).addTo(state.routeLayer);
      }
      const current = state.vehicles.find((v) => v.id === state.selected) || vehicle;
      const prev = current.stops?.previous;
      const next = current.stops?.next;
      if (state.routeLayer && Array.isArray(detail.stops)) {
        for (const item of detail.stops) {
          const isNext = next && item.sequence === next.sequence;
          const isPrev = prev && item.sequence === prev.sequence;
          const marker = L.circleMarker([item.lat,item.lon], {
            radius:isNext ? 7 : isPrev ? 6 : 4,
            weight:isNext || isPrev ? 2 : 1,
            color:isNext ? (state.theme === 'classic' ? '#1a73e8' : '#8ab4f8') : isPrev ? (state.theme === 'classic' ? '#d97706' : '#e5b45e') : (state.theme === 'classic' ? '#5f6368' : '#969ca4'),
            fillColor:isNext ? (state.theme === 'classic' ? '#1a73e8' : '#8ab4f8') : isPrev ? (state.theme === 'classic' ? '#f9ab00' : '#e5b45e') : (state.theme === 'classic' ? '#ffffff' : '#34373b'),
            fillOpacity:1, opacity:0.95, interactive:true, bubblingMouseEvents:false,
          }).addTo(state.routeLayer);
          marker.bindTooltip(safe(item.name), {direction:'top'});
          marker.bindPopup(stopPopupContent(item), {maxWidth:260});
          state.stopMarkers.set(Number(item.sequence), marker);
        }
      }
      $('detailOverlayStatus').textContent = points.length > 1
        ? `${detail.stops?.length || 0} stops · Click any stop on the map to view its arrival time`
        : 'No route shape published for this trip; showing stops where available';
      updateStopInterfaces();
    };
    if (routeCache.has(tripId)) { apply(routeCache.get(tripId)); return; }
    try {
      const response = await fetch(`/api/route?trip_id=${encodeURIComponent(tripId)}`, {cache:'no-store'});
      if (!response.ok) throw new Error(`Route data HTTP ${response.status}`);
      const detail = await response.json();
      routeCache.set(tripId, detail);
      if (routeCache.size > 25) routeCache.delete(routeCache.keys().next().value);
      apply(detail);
    } catch (_) {
      if (state.selected === vehicle.id && token === state.routeRequestSerial) {
        $('detailOverlayStatus').textContent = 'Route geometry unavailable while schedule data loads';
        updateStopInterfaces();
      }
    }
  }
  function tileUrlForTheme(theme) {
    const key = window.BUS_RADAR_CONFIG?.cartoKey?.trim() || '';
    if (!key) return 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
    const style = theme === 'classic' ? 'light_all' : 'dark_all';
    return `https://{s}.basemaps.cartocdn.com/${style}/{z}/{x}/{y}{r}.png?key=${encodeURIComponent(key)}`;
  }
  function setTheme(theme, save = true) {
    state.theme = theme === 'dark' ? 'dark' : 'classic';
    const classic = state.theme === 'classic';
    document.documentElement.dataset.theme = state.theme;
    const control = $('themeToggle');
    control.querySelector('.theme-toggle-symbol').textContent = classic ? '☀' : '☾';
    control.querySelector('.theme-toggle-label').textContent = classic ? 'Light map' : 'Dark map';
    control.title = classic ? 'Switch to dark map' : 'Switch to light map';
    control.setAttribute('aria-label', control.title);
    control.setAttribute('aria-pressed', String(classic));
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = classic ? '#f7f7f7' : '#202124';
    if (state.tileLayer) state.tileLayer.setUrl(tileUrlForTheme(state.theme));
    if (state.selected) {
      const vehicle = state.vehicles.find((v) => v.id === state.selected);
      if (vehicle) { updateDetails(); loadSelectedRoute(vehicle); }
    }
    if (save) try { localStorage.setItem('bct_theme', state.theme); } catch (_) {}
  }
  function restoredView() {
    try {
      const v = JSON.parse(localStorage.getItem('bct_last_map_view') || 'null');
      if (v && Number.isFinite(v.lat) && Number.isFinite(v.lon) && Number.isInteger(v.zoom)
          && Math.abs(v.lat) <= 85 && Math.abs(v.lon) <= 180 && v.zoom >= 4 && v.zoom <= 19)
        return v;
    } catch (_) {}
    return INITIAL_VIEW;
  }
  function saveMapView() {
    if (!state.map) return;
    const point = state.map.getCenter();
    try { localStorage.setItem('bct_last_map_view', JSON.stringify({
      lat: Math.round(point.lat * 1e5)/1e5,
      lon: Math.round(point.lng * 1e5)/1e5,
      zoom: state.map.getZoom()
    })); } catch (_) {}
  }
  function initMap() {
    if (window.innerWidth <= 720) {
      state.closed = true;
      document.body.classList.add('sidebar-hidden');
    }
    if (!window.L) { $('mapUnavailable').hidden = false; return; }
    const view = restoredView();
    const map = L.map('map', { center:[view.lat,view.lon], zoom:view.zoom,
      zoomControl:false, preferCanvas:true, zoomSnap:1, attributionControl:true });
    // CARTO light_all approximates the plain, practical road-map look.
    // With no CARTO key, keep the familiar light OpenStreetMap fallback.
    const key = window.BUS_RADAR_CONFIG?.cartoKey?.trim() || '';
    state.tileLayer = L.tileLayer(tileUrlForTheme(state.theme), {
      attribution: key ? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attribution/">CARTO</a>' : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      subdomains: key ? 'abcd' : 'abc', maxZoom:19, maxNativeZoom:key ? 18 : 19, crossOrigin:false, updateWhenIdle:true, keepBuffer:2,
    }).addTo(map);
    L.control.zoom({position:'bottomright'}).addTo(map);
    map.on('zoomend moveend', () => {renderMap(); saveMapView();});
    state.map = map;
    state.routeLayer = L.layerGroup().addTo(map);
  }
  function setSidebar(visible) {
    state.closed = !visible;
    if (visible && state.needsListRefresh) renderList();
    document.body.classList.toggle('sidebar-hidden', state.closed);
    setTimeout(() => state.map?.invalidateSize(), 220);
  }
  function applyData(data, cached = false) {
    if (!data || !Array.isArray(data.vehicles)) return;
    state.data = data;
    state.vehicles = data.vehicles.filter((v) => Number.isFinite(v.lat) && Number.isFinite(v.lon) && v.id);
    state.restoredCache = cached;
    if (state.selected && !state.vehicles.some((v) => v.id === state.selected)) leaveDetails();
    if (state.selected) {
      const selected = state.vehicles.find((v) => v.id === state.selected);
      if (selected) {
        if (state.arrivalsTrip !== (selected.trip_id || null)) {
          state.arrivalsTrip = selected.trip_id || null;
          state.arrivals = new Map();
          state.arrivalStatus = 'unavailable';
          refreshSelectedArrivals();
        }
        const stops = `${selected.stops?.previous?.sequence ?? ''}:${selected.stops?.next?.sequence ?? ''}`;
        if (state.routeTrip !== selected.trip_id || state.routeMetadataStamp !== (data.metadata_updated_at || null) ||
          (state.routeStopSignature !== stops && routeCache.has(selected.trip_id))) {
          loadSelectedRoute(selected);
        }
      }
    }
    if (state.following && state.selected && state.map) {
      const active = state.vehicles.find((v) => v.id === state.selected);
      if (active) state.map.panTo([active.lat,active.lon], {animate:false});
    }
    state.positionRefresh = true;
    renderStatus(); renderList(); renderMap();
    state.positionRefresh = false;
  }
  async function loadVehicles() {
    if (state.requestPending) return;
    state.requestPending = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 9000);
    try {
      const since = state.data && !state.restoredCache ? `?since=${state.data.revision}` : '';
      const response = await fetch('/api/vehicles'+since, {cache:'no-store',signal:controller.signal});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (data.unchanged) {
        if (state.data) { state.data.error = data.error; state.data.metadata_error = data.metadata_error; }
        state.clientError = null; renderStatus(); return;
      }
      if (!Array.isArray(data.vehicles)) throw new Error('Invalid JSON');
      state.clientError = null;
      applyData(data);
      try { sessionStorage.setItem('bct_latest_snapshot',JSON.stringify({ savedAt:Date.now(), data })); } catch (_) {}
    } catch (err) {
      state.clientError = err.message || 'Cannot reach local server';
      if (!state.data) $('listHint').textContent = 'Local server not responding. Check that app.py is running.';
      renderStatus(); renderList();
    } finally {
      clearTimeout(timeout); state.requestPending = false;
    }
  }
  function bindControls() {
    $('routeSearch').addEventListener('input', (event) => setFilter(event.target.value));
    $('clearSearch').addEventListener('click', () => {setFilter('');$('routeSearch').focus();});
    document.querySelectorAll('.quick-chip').forEach((chip) => chip.addEventListener('click', () => setFilter(chip.dataset.route)));
    $('detailBack').addEventListener('click', leaveDetails);
    $('recenterButton').addEventListener('click', () => {
      const v = state.vehicles.find((p) => p.id === state.selected);
      if (v && state.map) state.map.setView([v.lat,v.lon], Math.max(state.map.getZoom(), 13),{animate:false});
    });
    $('followButton').addEventListener('click', () => {state.following = !state.following;updateDetails();});
    $('themeToggle').addEventListener('click', () => setTheme(state.theme === 'classic' ? 'dark' : 'classic'));
    $('resetView').addEventListener('click', () => state.map?.setView([INITIAL_VIEW.lat,INITIAL_VIEW.lon],INITIAL_VIEW.zoom,{animate:false}));
    $('menuToggle').addEventListener('click', () => setSidebar(state.closed));
    $('sidebarClose').addEventListener('click', () => setSidebar(false));
    document.addEventListener('keydown', (event) => {
      if (event.key === '/' && event.target.tagName !== 'INPUT') {
        event.preventDefault();
        setSidebar(true);
        $('routeSearch').focus();
      }
      if (event.key === 'Escape') {
        if (state.selected) leaveDetails();
        else if (document.activeElement === $('routeSearch')) {setFilter('');$('routeSearch').blur();}
      }
    });
  }
  function init() {
    try { setTheme(localStorage.getItem('bct_theme') || 'classic', false); } catch (_) { setTheme('classic', false); }
    try { state.query = (localStorage.getItem('bct_route_filter') || '').slice(0, 12); } catch (_) {}
    bindControls(); initMap(); setFilter(state.query);
    try {
      const cached = JSON.parse(sessionStorage.getItem('bct_latest_snapshot') || 'null');
      if (cached && Date.now()-cached.savedAt < 120000 && cached.data) applyData(cached.data,true);
    } catch (_) {}
    loadVehicles();
    setInterval(() => { if (document.visibilityState === 'visible') loadVehicles(); }, CLIENT_REFRESH_MS);
    setInterval(renderStatus, 1000);
    setInterval(() => { if (document.visibilityState === 'visible' && state.selected) refreshSelectedArrivals(); }, 20000);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') { loadVehicles(); if (state.selected) refreshSelectedArrivals(); }
    });
  }
  init();
})();
