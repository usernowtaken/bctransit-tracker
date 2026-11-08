/* BC Transit Bus Radar V3.0 — bus reference illustrations; live GPS never simulated. */
(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const SYSTEMS = {
    victoria: {name:'Greater Victoria', center:{lat:48.48, lon:-123.49, zoom:10}, shortcuts:['4','14','50','95']},
    chilliwack: {name:'Chilliwack / FVX', center:{lat:49.157, lon:-121.951, zoom:11}, shortcuts:['51','52','53','66']},
    kelowna: {name:'Kelowna', center:{lat:49.887, lon:-119.496, zoom:11}, shortcuts:['1','8','97']},
  };
  const DEFAULT_SYSTEM = 'victoria';
  const MODEL_ASSETS = new Set(['vicinity30','nova_gen2','nova_gen3','nova_gen4','xn40','xe40','enviro500','enviro500mmc','generic']);
  // NovaBus *generations* are independent of which reference illustration is displayed.
  const NOVA_GENERATION_FILTERS = Object.freeze({nova_gen2:2,nova_gen3:3,nova_gen4:4});
  // Every illustration below is an EXACT pixel crop from the uploaded full.png.
  // Exterior whitespace was made transparent; bus pixels were neither redrawn nor recoloured.
  // Multiple liveries are preferences, not evidence of the physical bus's current paint.
  const BUS_ART = Object.freeze({
    vicinity30: [{id:'vicinity30', name:'Vehicle illustration'}],
    nova2: [{id:'nova2', name:'Vehicle illustration'}],
    nova3: [{id:'nova3', name:'Vehicle illustration'}],
    xn40: [
      {id:'xn40_classic', name:'Classic stripes'},
      {id:'xn40_greenrear', name:'Classic · green rear'},
      {id:'xn40_cng', name:'Green · blue CNG diamond'}
    ],
    xe40: [{id:'xe40', name:'Green · electric'}],
    enviro500: [{id:'enviro500', name:'Vehicle illustration'}],
    enviro500mmc: [
      {id:'enviro500mmc_classic', name:'Classic white'},
      {id:'enviro500mmc_green', name:'Green and white'}
    ]
  });
  const artChoices = (() => {
    try { return JSON.parse(localStorage.getItem('bct_bus_art_variants_v30') || '{}') || {}; }
    catch (_) { return {}; }
  })();
  const artKey = (vehicle) => `${state.system}:${vehicle.fleet_number || vehicle.id}`;
  // A 2009 NovaBus LFS is a known 2009 T-drive, but the public realtime feed
  // cannot tell us whether its individual rear roof is raised. Map only
  // photo-verified IDs here when evidence becomes available; leave unknowns
  // unclassified rather than assuming the entire model-year batch is identical.
  const VERIFIED_NOVA_2009_REAR_ROOFS = Object.freeze({
    '9426': 'raised', // User photo: raised rear, white LED destination sign.
    // Do not infer roof shape from the sign colour on other fleet numbers.
  });
  const VERIFIED_NOVA_BODY = Object.freeze({
    '9287': 'flat',  // User photo: 2008 low/flat rear.
    '9303': 'flat',  // User photo: 2008 low/flat rear.
    '9426': 'raised',// User photo: 2009 raised rear.
    '9434': 'smart', // Documented 2012 Smart Bus prototype, full-length fairings.
  });
  const isNova2009 = (vehicle) => {
    if (state.system !== 'victoria') return false;
    const fleet = String(vehicle?.fleet_number ?? '');
    if (!/^\d{4}$/.test(fleet)) return false;
    return Number(fleet) >= 9319 && Number(fleet) <= 9433 && vehicle?.model_key === 'nova2';
  };
  const novaRearStyle = (vehicle) => {
    if (!isNova2009(vehicle)) return null;
    const fleet = String(vehicle.fleet_number);
    const serverStyle = vehicle.nova_body_variant;
    if (serverStyle === 'raised') return 'raised';
    if (serverStyle === 'flat') return 'standard';
    const verified = VERIFIED_NOVA_2009_REAR_ROOFS[fleet];
    if (verified === 'raised' || verified === 'standard') return verified;
    return 'unknown';
  };

  // Automatic XN40 illustration: production batch is a best-effort proxy for livery,
  // NOT a confirmation of an individual vehicle's paint or bodywork. Victoria only.
  // Keep all original reference illustrations unchanged; only select among existing PNG assets.
  const XN40_FLEET_ART = Object.freeze([
    {first:1148, last:1212, image:'xn40_greenrear'}, // 2019–20 cohort
    {first:1213, last:1253, image:'xn40_classic'},   // 2021–22 cohort
    {first:1254, last:1277, image:'xn40_cng'},       // 2024–25 cohort
  ]);
  const automaticXn40Art = (vehicle) => {
    if (state.system !== 'victoria' || vehicle?.model_key !== 'xn40') return null;
    const fleet = String(vehicle.fleet_number ?? '');
    if (!/^\d{4}$/.test(fleet)) return null;
    const number = Number(fleet);
    const batch = XN40_FLEET_ART.find(row => number >= row.first && number <= row.last);
    return BUS_ART.xn40.find(variant => variant.id === batch?.image) || null;
  };
  // Unverified 2009 LFS units alternate their two existing source drawings.
  // A separate phase origin is kept for each vehicle; known fleet/body records and
  // confirmed appearances NEVER cycle. No new artwork is generated.
  const NOVA_UNKNOWN_CYCLE_MS = 1500;
  const novaCycleStart = new Map();
  const isUnverifiedNova = (vehicle) => isNova2009(vehicle) && novaRearStyle(vehicle) === 'unknown';
  const unverifiedNovaImage = (vehicle, now = Date.now()) => {
    const key = artKey(vehicle);
    if (!novaCycleStart.has(key)) novaCycleStart.set(key, now);
    const phase = Math.floor(Math.max(0, now - novaCycleStart.get(key)) / NOVA_UNKNOWN_CYCLE_MS) % 2;
    return phase === 0 ? 'nova2' : 'nova3';
  };
  const busArtVariant = (vehicle) => {
    // Model remains Gen 3 (2009), regardless of which reference drawing
    // is shown. Confirmed roof appearances stay fixed by fleet number.
    if (isNova2009(vehicle)) {
      const style = novaRearStyle(vehicle);
      const key = style === 'unknown' ? unverifiedNovaImage(vehicle)
        : style === 'raised' ? 'nova3' : 'nova2';
      const name = style === 'unknown'
        ? 'Unverified roof (alternating flat/raised reference drawings)'
        : style === 'raised' ? 'Raised-rear reference drawing' : 'Flat-rear reference drawing';
      return {id:key, name};
    }
    const available = BUS_ART[vehicle?.model_key] || [];
    // Enviro500 MMC: older 2020–21 units retain classic livery; 2025–26 cohort
    // gets green artwork. Only choose from the user's original provided PNGs.
    if (state.system === 'victoria' && vehicle?.model_key === 'enviro500mmc') {
      const fleet = Number(vehicle?.fleet_number);
      if (Number.isInteger(fleet) && fleet >= 9532 && fleet <= 9550)
        return BUS_ART.enviro500mmc.find(v => v.id === 'enviro500mmc_classic');
      if (Number.isInteger(fleet) && fleet >= 9551 && fleet <= 9589)
        return BUS_ART.enviro500mmc.find(v => v.id === 'enviro500mmc_green');
      return null; // Never assign a paint scheme based on an unknown fleet number.
    }
    const chosen = vehicle?.model_key === 'xn40' ? null : available.find((v) => v.id === artChoices[artKey(vehicle)]);
    return chosen || automaticXn40Art(vehicle) || available[0] || null;
  };
  const currentView = () => SYSTEMS[state.system].center;
  const apiPath = (endpoint, extras = {}) => '/api/' + endpoint + '?' + new URLSearchParams({system:state.system, ...extras}).toString();
  const snapshotKey = () => 'bct_latest_snapshot_' + state.system;
  const filterKey = () => 'bct_route_filter_' + state.system;
  const MAX_LIST = 300;
  const CLIENT_REFRESH_MS = 5000; // Mobile uses longer local checks; upstream refresh is still ~15 s.
  const routeCache = new Map();
  // Loaded only when a stop or location feature is requested, not at startup.
  const stopCatalog = new Map();
  const freshnessThreshold = 120;
  const ageSeconds = (v) => Number.isFinite(Number(v?.timestamp)) && Number(v.timestamp) > 0
    ? Math.max(0, Date.now()/1000 - Number(v.timestamp)) : Infinity;
  function metersBetween(a,b,c,d) {
    const rad=Math.PI/180, p1=a*rad, p2=c*rad, dp=(c-a)*rad, dl=(d-b)*rad;
    const h=Math.sin(dp/2)**2 + Math.cos(p1)*Math.cos(p2)*Math.sin(dl/2)**2;
    return 12742000*Math.asin(Math.min(1,Math.sqrt(h)));
  }
  const distanceLabel=(meters) => meters < 1000 ? `${Math.round(meters)} m` : `${(meters/1000).toFixed(1)} km`;
  const localDistance=(v)=>state.userLocation?metersBetween(state.userLocation.lat,state.userLocation.lon,v.lat,v.lon):Infinity;
  const mobile = () => window.matchMedia('(max-width: 720px)').matches;
  const arrivalFormatter = new Intl.DateTimeFormat('en-CA', {timeZone:'America/Vancouver', hour:'2-digit', minute:'2-digit', hour12:false});
  const lowMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const touchScreen = () => window.matchMedia('(pointer: coarse)').matches;
  let lastListSignature = '';
  let lastListStatus = '';

  const state = {
    system: DEFAULT_SYSTEM,
    systemGeneration: 0,
    groupMode: 'route',
    // All grouped routes start COLLAPSED, including after changing systems.
    expandedGroups: new Set(),
    sortBy: 'route',
    serviceFilter: 'all',
    modelFilter: 'all',
    lowBandwidth: false,
    favorites: {routes:[],stops:[],buses:[]},
    pendingShare: null,
    sharedFocusMarker: null,
    userLocation: null,
    locationMarker: null,
    locationCircle: null,
    nearbyStopMarker: null,
    nearbyStopToken: 0,
    locationRequestPending: false,
    lastClientPollAt: 0,
    lastArrivalRefreshAt: 0,
    pendingNearestSort: false,
    density: 'comfortable',
    markerSize: 'normal',
    routeColors: true,
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
    historyLayer: null,
    historyVisible: false,
    historyPoints: [],
    historyWindow: 30,
    historyLastFetch: 0,
    historyRequestSerial: 0,
    historyLoading: false,
    historyScrubMarker: null,
    activityVisible: false,
    activityWindow: 180,
    activityRequestSerial: 0,
    activityLoading: false,
    activityFocusMarker: null,
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
    lite: mobile(),
    sheetMode: 'half',
    boardPending:false, boardQueued:false, boardSerial:0, boardLastFetch:0, boardAt:null, boardPayload:null,
  };

  function safe(value) {
    return String(value ?? '').replace(/[&<>"']/g, (s) => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[s]));
  }
  function mapLabel(vehicle) {
    const state = vehicle?.route_proximity?.state;
    if (state === 'likely_nis') return 'NIS~';
    if (state === 'possible_nis') return 'NIS?';
    if (state === 'far') return 'OFF?';
    return label(vehicle?.route);
  }
  function routeWarning(vehicle) {
    const status = vehicle?.route_proximity?.state;
    return status === 'likely_nis' || status === 'possible_nis' || status === 'far';
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
    return state.vehicles.filter((v) => {
      if (needle) {
        const proximity = v.route_proximity?.state;
        if (needle === 'NIS' || needle === 'NIS?') {
          if (!['possible_nis','likely_nis'].includes(proximity)) return false;
        } else if (needle === 'OFF' || needle === 'OFF?') {
          if (!routeWarning(v)) return false;
        } else if (!(String(v.route || '').toUpperCase().startsWith(needle)
          || String(v.fleet_number || '').startsWith(needle)
          || (needle.length >= 3 && String(v.model || '').toUpperCase().includes(needle)))) return false;
      }
      if (state.modelFilter !== 'all') {
        const novaGeneration = NOVA_GENERATION_FILTERS[state.modelFilter];
        if (novaGeneration) {
          if (Number(v.nova_generation) !== novaGeneration) return false;
        } else if ((v.model_key || 'generic') !== state.modelFilter || (state.modelFilter === 'generic' && v.nova_generation)) return false;
      }
      const proximity = v.route_proximity?.state;
      switch (state.serviceFilter) {
        case 'near': return proximity === 'near';
        case 'off': return routeWarning(v);
        case 'stale': return ageSeconds(v) > freshnessThreshold;
        case 'unknown': return !v.route || proximity === 'unknown';
        default: return true;
      }
    });
  }
  function sortedVehicles() {
    const items = [...filteredVehicles()];
    const routeCmp = (a,b)=>String(a.route || '~').localeCompare(String(b.route || '~'),undefined,{numeric:true});
    items.sort((a,b) => state.sortBy === 'recent'
      ? (ageSeconds(a)-ageSeconds(b) || routeCmp(a,b))
      : state.sortBy === 'nearest' && state.userLocation
        ? (localDistance(a)-localDistance(b) || routeCmp(a,b))
        : (routeCmp(a,b) || String(a.id).localeCompare(String(b.id))));
    return items;
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
    $('statusPill').title = `${current.text} · ${current.sub}`;
    $('statusText').textContent = current.text;
    $('freshness').textContent = current.sub;
    $('busCount').textContent = state.data ? state.vehicles.length.toLocaleString() : '—';
    $('routeCount').textContent = state.data
      ? new Set(state.vehicles.map((v) => v.route).filter(Boolean)).size.toLocaleString()
      : '—';
    $('refreshNote').textContent = `Source: ~${state.data?.poll_seconds || 15}s · Browser: ${state.lowBandwidth ? 25 : mobile() ? 10 : 5}s`;
    if (state.selected && (!mobile() || !state.closed)) updateDetails();
  }
  function displayName(vehicle) {
    return vehicle.headsign || vehicle.route_name || 'Destination unavailable';
  }
  function renderList() {
    // On a phone, don't rebuild an invisible list every time a new GPS frame arrives.
    if (mobile() && (state.closed || state.selected)) {
      state.needsListRefresh = true;
      return;
    }
    state.needsListRefresh = false;
    const list = $('busList');
    const filtered = sortedVehicles();
    $('listHeading').textContent = state.query ? `Buses matching “${state.query}”` : 'Active buses';
    $('resultCount').textContent = filtered.length.toLocaleString();
    let hint = 'Showing the latest available vehicle positions.';
    if (!state.data) hint = 'Connecting to the live feed…';
    else if (state.data.error || state.clientError) hint = 'Live feed unavailable. Showing last received positions, if any.';
    else if (state.restoredCache) hint = 'Previously cached positions; checking for new data…';
    else if (state.data.fetched_at && !state.data.metadata_ready)
      hint = 'Loading route numbers from schedule data. Some routes may show “?”.';
    $('listHint').textContent = hint;
    // Skip needless DOM churn when GPS coordinates change but fleet list text doesn't.
    // Still refresh when the displayed GPS-age bucket changes.
    const signature = `${state.system}|${state.groupMode}|${state.density}|${[...state.expandedGroups].join(',')}|${state.query}|${state.sortBy}|${state.serviceFilter}|${state.modelFilter}|${state.userLocation?.lat ?? ''}|${state.userLocation?.lon ?? ''}|${state.selected}|${filtered.length}|${filtered.slice(0, MAX_LIST).map(v => [v.id, v.route, v.headsign, v.label, v.fleet_number, v.model_key, v.route_proximity?.state, Math.floor(Number(v.timestamp || 0)/60)].join(':')).join('|')}`;
    if (signature === lastListSignature && hint === lastListStatus) return;
    lastListSignature = signature;
    lastListStatus = hint;
    const previousScroll = list.scrollTop;

    const fragment = document.createDocumentFragment();
    // Route and direction grouping is DOM-only; the backend still sends one
    // lightweight snapshot and no separate requests are made per category.
    const vehicleRow = (vehicle) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `bus-item${state.selected === vehicle.id ? ' selected' : ''}`;
      button.setAttribute('role', 'listitem');
      button.setAttribute('aria-label', `${routeWarning(vehicle) ? 'Possibly off scheduled route, ' : ''}reported route ${label(vehicle.route)}, ${displayName(vehicle)}, vehicle ${vehicle.id}`);
      const badge = document.createElement('span');
      badge.className = 'bus-route'; badge.textContent = mapLabel(vehicle);
      badge.classList.toggle('offroute', routeWarning(vehicle));
      badge.style.borderLeft = `3px solid ${routeColor(vehicle)}`;
      const meta = document.createElement('span'); meta.className = 'bus-meta';
      const name = document.createElement('span'); name.className = 'bus-name';
      name.textContent = routeWarning(vehicle) ? `Reported ${label(vehicle.route)} · ${displayName(vehicle)}` : displayName(vehicle);
      const extra = document.createElement('span'); extra.className = 'bus-extra';
      extra.textContent = state.sortBy === 'nearest' && state.userLocation
        ? `${distanceLabel(localDistance(vehicle))} away · ${vehicle.fleet_number ? `Fleet #${vehicle.fleet_number}` : `GPS ${timeAgo(vehicle.timestamp)}`}`
        : vehicle.fleet_number ? `Fleet #${vehicle.fleet_number} · ${vehicle.model || 'Model unknown'}`
          : vehicle.label ? `Feed label: ${vehicle.label}` : `Vehicle ID: ${vehicle.id}`;
      meta.append(name, extra);
      const age = document.createElement('span'); age.className = 'bus-age';
      age.textContent = timeAgo(vehicle.timestamp);
      button.append(badge, meta, age);
      button.addEventListener('click', () => selectVehicle(vehicle.id, true));
      return button;
    };
    if (!filtered.length) {
      const empty = document.createElement('div'); empty.className = 'empty-state';
      empty.textContent = !state.data ? 'Waiting for BC Transit to respond…'
        : state.query ? 'No currently reported buses match this search.'
          : 'No vehicle positions are currently available.';
      fragment.appendChild(empty);
    } else if (state.groupMode === 'none') {
      filtered.slice(0, MAX_LIST).forEach((vehicle) => fragment.appendChild(vehicleRow(vehicle)));
    } else {
      const groups = new Map();
      for (const vehicle of filtered.slice(0, MAX_LIST)) {
        const key = String(vehicle.route || '?');
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(vehicle);
      }
      for (const [routeName, buses] of groups) {
        const routeKey = 'route:' + routeName;
        const folded = !state.expandedGroups.has(routeKey);
        const header = document.createElement('button');
        header.type = 'button'; header.className = 'route-group-heading';
        header.setAttribute('aria-expanded', String(!folded));
        const arrow = document.createElement('span'); arrow.className = 'group-arrow'; arrow.textContent = folded ? '▸' : '▾';
        const badge = document.createElement('span'); badge.className = 'group-badge'; badge.textContent = routeName;
        badge.style.borderLeft = `3px solid ${routeColor(buses[0])}`;
        const title = document.createElement('span'); title.textContent = routeName === '?' ? 'Unknown route' : `Route ${routeName}`;
        const count = document.createElement('small'); count.textContent = `${buses.length} bus${buses.length === 1 ? '' : 'es'}`;
        header.append(arrow, badge, title, count);
        header.addEventListener('click', () => {
          if (state.expandedGroups.has(routeKey)) state.expandedGroups.delete(routeKey);
          else state.expandedGroups.add(routeKey);
          lastListSignature = ''; renderList();
        });
        const row=document.createElement('div');row.className='route-group-header-row';
        const star=document.createElement('button');star.type='button';star.className='group-fav-star';
        const saved=state.favorites.routes.includes(routeName);
        star.textContent=saved?'★':'☆';star.title=saved?'Remove favourite route':'Save favourite route';
        star.setAttribute('aria-label',`${saved?'Remove':'Save'} Route ${routeName} favourite`);
        star.addEventListener('click',()=>toggleFavoriteRoute(routeName));
        row.append(header,star);fragment.appendChild(row);
        if (folded) continue;
        if (state.groupMode !== 'direction') {
          buses.forEach((bus) => fragment.appendChild(vehicleRow(bus)));
        } else {
          const directions = new Map();
          for (const bus of buses) {
            const direction = (bus.headsign || 'Direction unavailable').trim();
            if (!directions.has(direction)) directions.set(direction, []);
            directions.get(direction).push(bus);
          }
          for (const [direction, directionBuses] of directions) {
            const key = `${routeKey}|${direction}`;
            const foldedDirection = !state.expandedGroups.has(key);
            const dirButton = document.createElement('button');
            dirButton.className = 'direction-group-heading'; dirButton.type = 'button';
            dirButton.setAttribute('aria-expanded', String(!foldedDirection));
            const arrow = document.createElement('span'); arrow.textContent = foldedDirection ? '▸' : '▾';
            const title = document.createElement('span'); title.textContent = direction;
            const count = document.createElement('small'); count.textContent = String(directionBuses.length);
            dirButton.append(arrow,title,count);
            dirButton.addEventListener('click', () => {
              if (state.expandedGroups.has(key)) state.expandedGroups.delete(key);
              else state.expandedGroups.add(key);
              lastListSignature = ''; renderList();
            });
            fragment.appendChild(dirButton);
            if (!foldedDirection) directionBuses.forEach((bus) => fragment.appendChild(vehicleRow(bus)));
          }
        }
      }
    }
    list.replaceChildren(fragment);
    list.scrollTop = previousScroll;
    $('listMore').hidden = filtered.length <= MAX_LIST;
    if (filtered.length > MAX_LIST) $('listMore').textContent = `Showing first ${MAX_LIST} of ${filtered.length} buses. Filter by route to narrow results.`;
  }
  // Only the selected, visible vehicle needs an image cycle. We reuse a single
  // cheap timer; it does not restart when the realtime map data refreshes.
  function refreshUnverifiedNovaArtwork() {
    if (document.visibilityState !== 'visible' || !state.selected || (mobile() && state.closed)) return;
    const vehicle = state.vehicles.find(v => v.id === state.selected);
    if (!vehicle || !isUnverifiedNova(vehicle)) return;
    const art = busArtVariant(vehicle);
    const image = $('detailBusImage');
    const desired = '/buses/' + art.id + '.png?v=3.2.0';
    if (image.getAttribute('src') !== desired) {
      image.src = desired;
      image.alt = `${vehicle.model || 'NovaBus LFS'} — unverified roof, alternating ${art.id === 'nova3' ? 'raised' : 'flat'} illustration`;
    }
  }
  function updateDetails() {
    const vehicle = state.vehicles.find((v) => v.id === state.selected);
    if (!vehicle) return;
    $('detailRoute').textContent = label(vehicle.route);
    updateFavoriteRouteButton(vehicle.route);
    updateFavoriteBusButton(vehicle);
    if($('alertsDetailSection').open && alertsCache.has(state.system))renderAlerts('alertsDetailContent',vehicle);
    $('detailTitle').textContent = vehicle.route ? `Route ${vehicle.route}` : 'Route unavailable';
    $('detailDestination').textContent = displayName(vehicle);
    const fleetNumber = vehicle.fleet_number;
    $('detailFleet').textContent = fleetNumber ? `Bus #${fleetNumber}` : 'Fleet number unavailable';
    $('detailFleetConfidence').textContent = fleetNumber ? '' : 'Fleet number unavailable';
    $('detailFleetConfidence').hidden = Boolean(fleetNumber);
    const smart9434 = state.system === 'victoria' && String(fleetNumber) === '9434' && vehicle.model_key === 'nova3';
    $('detailModel').textContent = smart9434 ? 'NovaBus LFS Smart Bus (2012 prototype)' : (vehicle.model || 'Model unknown');
    const smartPanel = $('novaSmartSpecial');
    smartPanel.hidden = !smart9434;
    $('fleetProfile').classList.toggle('smart-prototype', smart9434);
    const bodyVariant = $('detailNovaBody');
    const body = vehicle.nova_body_variant || (state.system === 'victoria' ? VERIFIED_NOVA_BODY[String(fleetNumber)] : null);
    const nova2009 = isNova2009(vehicle);
    let bodyText = '';
    if (body === 'raised') bodyText = String(fleetNumber) === '9426' ? 'Raised rear · white LED sign (photographed)' : 'Raised rear · photographed fleet unit';
    else if (body === 'flat') bodyText = 'Flat rear · photographed fleet unit';
    else if (body === 'smart') bodyText = 'Full-length roof fairings · 2012 Smart Bus prototype';
    else if (nova2009) bodyText = 'Rear roof unverified · cycling flat / raised drawings';
    // Barp's 2009 Victoria gallery documents frameless windows on the 9354+ order.
    const fleetAsNumber = Number(fleetNumber);
    if (nova2009 && fleetAsNumber >= 9354 && fleetAsNumber <= 9433) {
      bodyText += ' · frameless windows (9354+ batch)';
    }
    bodyVariant.hidden = !bodyText;
    bodyVariant.textContent = bodyText;
    $('detailFleetBasis').textContent = fleetNumber
      ? `Source: ${vehicle.fleet_basis || 'BC Transit vehicle label'}; ${vehicle.model_basis || 'fleet roster if available'}. Model and livery are roster-based, not live vehicle inspections.`
      : 'No recognized fleet label for this region. Raw feed label is listed above.';
    const busImage = $('detailBusImage');
    const artSelect = $('detailArtworkVariant');
    const artPicker = $('artworkPicker');
    const artContainer = $('fleetArt');
    const variants = BUS_ART[vehicle.model_key] || [];
    if (artSelect.dataset.modelKey !== (vehicle.model_key || 'generic')) {
      const options = vehicle.model_key === 'xn40'
        ? [{id:'auto', name:'Automatic (fleet-number batch)'}, ...variants]
        : variants;
      artSelect.replaceChildren(...options.map((v) => {
        const option = document.createElement('option');
        option.value = v.id; option.textContent = v.name; return option;
      }));
      artSelect.dataset.modelKey = vehicle.model_key || 'generic';
    }
    // Keep XN40 artwork automatic, but hide its selector for a cleaner profile UI.
    artPicker.hidden = true; // All fleet artwork is automatic; no profile artwork dropdown.
    const chosenArt = busArtVariant(vehicle);
    artContainer.hidden = !chosenArt;
    if (chosenArt) {
      const manualArt = variants.find(v => v.id === artChoices[artKey(vehicle)]);
      artSelect.value = vehicle.model_key === 'xn40' && !manualArt ? 'auto' : chosenArt.id;
      const source = '/buses/' + chosenArt.id + '.png?v=3.2.0';
      if (busImage.getAttribute('src') !== source) busImage.src = source;
      busImage.hidden = false;
      busImage.alt = `${vehicle.model || 'Bus'} — vehicle illustration (${chosenArt.name})`;
    } else {
      busImage.hidden = true; // No generic illustration: use ONLY the supplied images.
      busImage.removeAttribute('src');
    }
    // Roof styles are automatic: verified examples fixed, unknown 2009 units alternating.
    const proximity = vehicle.route_proximity || {};
    const proximityStatus = $('detailProximityStatus');
    const proximityNote = $('detailProximityNote');
    const observedDistance = Number.isFinite(proximity.distance_m)
      ? `${proximity.distance_m.toLocaleString()} m from scheduled route line` : '';
    proximityStatus.className = 'proximity-status';
    if (proximity.state === 'likely_nis') {
      proximityStatus.textContent = 'Likely NIS / deadheading · inferred';
      proximityStatus.classList.add('warning');
      proximityNote.textContent = `${observedDistance}. Off-route in at least three distinct GPS fixes over 45+ seconds. Route ${label(vehicle.route)} is still the reported assignment. This is NOT confirmation of the actual destination sign or service status.`;
    } else if (proximity.state === 'possible_nis') {
      proximityStatus.textContent = 'NIS? · Possible deadheading';
      proximityStatus.classList.add('warning');
      proximityNote.textContent = `${observedDistance}. Distinct GPS observations outside the 100 m buffer. Feed still reports Route ${label(vehicle.route)}; not confirmed NIS. Could be a detour or outdated trip assignment.`;
    } else if (proximity.state === 'far') {
      proximityStatus.textContent = 'Off route · not confirmed NIS';
      proximityStatus.classList.add('caution');
      proximityNote.textContent = `${observedDistance}. One fresh GPS observation beyond 100 m. Waiting for another distinct update before suggesting NIS.`;
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
  function historyTime(timestamp) {
    if (!Number.isFinite(Number(timestamp))) return 'Unknown GPS time';
    return arrivalFormatter.format(new Date(Number(timestamp) * 1000));
  }
  const activityDate = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Vancouver', month: 'short', day: 'numeric', hour:'2-digit', minute:'2-digit', hour12:false
  });
  const activityStamp = (seconds) => Number.isFinite(Number(seconds)) ? activityDate.format(new Date(Number(seconds)*1000)) : 'Unknown';
  function resetActivity() {
    state.activityRequestSerial++;
    state.activityVisible = false;
    state.activityLoading = false;
    if (state.activityFocusMarker && state.map) state.activityFocusMarker.remove();
    state.activityFocusMarker = null;
    $('activityToggle').textContent = 'Show activity timeline';
    $('activityToggle').setAttribute('aria-pressed', 'false');
    $('activityStatus').textContent = 'Load a timeline to view observed routes and possible off-route travel.';
    $('activitySummary').textContent = 'No timeline loaded.';
    $('activityDaySummary').replaceChildren();$('activityDaySummary').hidden=true;
    $('activityEvents').hidden = true;
    $('activityEvents').replaceChildren();
    $('activityRefresh').hidden = true;
  }
  function eventDescription(event) {
    if (event.kind === 'route_change') return 'Observed route label changed between GPS reports.';
    if (event.kind === 'gap') return 'No recorded GPS fixes during this interval.';
    if (event.kind === 'unreported') return 'Vehicle GPS reported without a usable route label.';
    if (event.kind === 'off_route') return event.off_route_evidence === 'likely_nis'
      ? 'Repeated off-route GPS positions. Possible deadheading; NIS unconfirmed.'
      : 'Reported GPS positions away from the published route; detour or deadhead possible.';
    return 'Route label reported in the live feed; passenger service not independently confirmed.';
  }
  function renderActivity(data) {
    renderDaySummary(data);
    const host = $('activityEvents'); host.replaceChildren();
    const events = Array.isArray(data.events) ? data.events : [];
    const changes = Number(data.reported_route_changes)||0;
    const fixes = Number(data.recorded_fixes)||0;
    $('activitySummary').textContent = `${fixes} GPS fixes · ${changes} route label change${changes===1?'':'s'} · ${Number(data.off_route_observations)||0} off-route observations`;
    $('activityStatus').textContent = fixes
      ? `${events.length} activity entries from the past ${state.activityWindow/60} hour${state.activityWindow===60?'':'s'}${data.events_truncated||data.samples_truncated?' · displaying latest entries only':''}.`
      : 'No recorded activity in this period. The server needs time to accumulate GPS history.';
    $('activityRefresh').hidden = false;
    host.hidden = events.length===0;
    for (const event of events) {
      if (!['reported','off_route','unreported','gap','route_change'].includes(event.kind)) continue;
      const row = document.createElement('div');row.className='activity-entry kind-'+event.kind;
      const heading = document.createElement('strong');
      heading.textContent = event.kind==='route_change' ? `Route ${event.from_route} → ${event.to_route}`
        : event.kind==='gap' ? 'Reporting gap'
        : event.kind==='off_route' ? `Possible off-route · ${event.route ? 'Route '+event.route : 'Unreported'}`
        : event.kind==='unreported' ? 'Route not reported'
        : `Reported Route ${event.route}`;
      const time = document.createElement('time');time.className='activity-time';
      time.textContent = event.kind==='route_change' ? `${activityStamp(event.start_ts)} – ${activityStamp(event.end_ts)}`
        : event.start_ts===event.end_ts ? activityStamp(event.end_ts)
        : `${activityStamp(event.start_ts)} – ${activityStamp(event.end_ts)}`;
      const note = document.createElement('small');note.textContent=eventDescription(event);
      const info = document.createElement('div');info.className='activity-entry-copy';info.append(heading,time,note);
      row.append(info);
      if (Array.isArray(event.end) && event.end.length===2 && Number.isFinite(event.end[0]) && Number.isFinite(event.end[1])) {
        const locate=document.createElement('button');locate.type='button';locate.className='mini-button activity-locate';
        locate.textContent='Locate';locate.setAttribute('aria-label',`Locate the recorded position at ${activityStamp(event.end_ts)}`);
        locate.addEventListener('click',()=>{
          if (!state.map || !window.L) return;
          if (state.activityFocusMarker) state.activityFocusMarker.remove();
          state.activityFocusMarker=L.circleMarker(event.end,{radius:8,color:'#fff',weight:2,fillColor:'#c76a19',fillOpacity:1}).addTo(state.map);
          state.map.setView(event.end,Math.max(state.map.getZoom(),13),{animate:false});
          if (mobile())setSheetMode('half');
        });
        row.append(locate);
      }
      host.append(row);
    }
  }
  async function loadActivity() {
    if (!state.selected || !state.activityVisible || state.activityLoading) return;
    const vehicleId=state.selected, region=state.system, serial=++state.activityRequestSerial;
    state.activityLoading=true;
    $('activityStatus').textContent='Loading recorded activity…';
    $('activityRefresh').disabled=true;
    try {
      const response=await fetch(apiPath('activity',{vehicle_id:vehicleId,minutes:state.activityWindow}),{cache:'no-store'});
      if(!response.ok)throw new Error(`Activity HTTP ${response.status}`);
      const data=await response.json();
      if(serial!==state.activityRequestSerial||region!==state.system||vehicleId!==state.selected||!state.activityVisible)return;
      renderActivity(data);
    } catch(error) {
      if(serial===state.activityRequestSerial&&region===state.system&&vehicleId===state.selected) {
        $('activityStatus').textContent=`Activity unavailable (${error.message}). Live tracking still works.`;
      }
    } finally {
      if(serial===state.activityRequestSerial) {state.activityLoading=false;$('activityRefresh').disabled=false;}
    }
  }
  function resetHistory() {
    resetActivity();
    state.historyRequestSerial++;
    state.historyPoints = [];
    state.historyVisible = false;
    state.historyLoading = false;
    state.historyLastFetch = 0;
    state.historyScrubMarker = null;
    if (state.historyLayer) state.historyLayer.clearLayers();
    $('historyToggle').textContent = 'Show movement trail';
    $('historyToggle').setAttribute('aria-pressed','false');
    $('historyStatus').textContent = 'Tap Show movement trail to load recorded GPS fixes for this vehicle.';
    $('historyScrubArea').hidden = true;
  }
  function highlightHistoryPoint(index) {
    const point = state.historyPoints[index];
    if (!point || !state.historyLayer || !state.map) return;
    if (state.historyScrubMarker) state.historyLayer.removeLayer(state.historyScrubMarker);
    state.historyScrubMarker = L.circleMarker([point[1],point[2]], {
      radius:7,color:'#ffffff',weight:2,fillColor:'#d97706',fillOpacity:1,interactive:false,
    }).addTo(state.historyLayer);
    $('historyScrubLabel').textContent = `${historyTime(point[0])} · ${point[3] ? 'Route '+point[3] : 'Route unreported'} · recorded GPS position ${index+1} of ${state.historyPoints.length}`;
  }
  function drawHistory() {
    if (!state.historyLayer) return;
    state.historyLayer.clearLayers();
    state.historyScrubMarker = null;
    if (!state.historyVisible) return;
    const points = state.historyPoints;
    const group = [];
    const segments = [];
    // Prevent misleading connectors when GPS goes offline or teleports.
    const flush=()=>{if(group.length>1) segments.push(group.slice());group.length=0;};
    let last = null;
    for (const point of points) {
      if (last && (point[0]-last[0] > 7*60 || point[0]<=last[0] ||
          metersBetween(point[1],point[2],last[1],last[2]) > Math.max(1250,(point[0]-last[0])*35))) flush();
      group.push([point[1],point[2]]);
      last=point;
    }
    flush();
    for (const segment of segments) {
      L.polyline(segment,{color:state.theme==='dark'?'#ffd17a':'#b86916',weight:4,opacity:.85,interactive:false,dashArray:'6 5'}).addTo(state.historyLayer);
    }
    if (points.length) {
      const first=points[0];
      L.circleMarker([first[1],first[2]],{radius:4,color:'#255e8a',fillColor:'#255e8a',fillOpacity:1,interactive:false}).addTo(state.historyLayer);
      const latest=points.at(-1);
      L.circleMarker([latest[1],latest[2]],{radius:5,color:'#126c35',fillColor:'#27aa59',fillOpacity:1,interactive:false}).addTo(state.historyLayer);
    }
    const scrub=$('historyScrub');
    $('historyScrubArea').hidden = points.length<2;
    if (points.length>=2) {
      // Newly loaded history defaults to the latest point. On subsequent live
      // refreshes preserve the user's position unless it was the old latest.
      const previous=Number(scrub.value);
      const previousMax=Number(scrub.max);
      scrub.min='0';scrub.max=String(points.length-1);
      scrub.value=String(Number.isInteger(previous) && previous>=0 && previous<previousMax ? previous : points.length-1);
      highlightHistoryPoint(Number(scrub.value));
    }
    if (points.length === 0) $('historyStatus').textContent='No stored GPS fixes in this window yet. The recorder starts when this server version launches.';
    else if (points.length === 1) $('historyStatus').textContent='1 GPS fix stored. A trail needs at least two distinct vehicle reports.';
    else $('historyStatus').textContent=`${points.length} real GPS fixes in the past ${state.historyWindow} min · ${segments.length} connected trail segment${segments.length===1?'':'s'}.`;
  }
  async function loadHistory() {
    if (!state.selected || !state.historyVisible || state.historyLoading) return;
    const ident=state.selected, region=state.system, serial=++state.historyRequestSerial;
    state.historyLoading=true;
    $('historyStatus').textContent='Loading recorded positions…';
    try {
      const response=await fetch(apiPath('history',{vehicle_id:ident,minutes:state.historyWindow}),{cache:'no-store'});
      if (!response.ok) throw new Error(`History HTTP ${response.status}`);
      const data=await response.json();
      if (serial!==state.historyRequestSerial || region!==state.system || ident!==state.selected || !state.historyVisible) return;
      state.historyPoints=(Array.isArray(data.points)?data.points:[]).filter((p)=>
        Array.isArray(p)&&p.length>=3&&Number.isFinite(p[0])&&Number.isFinite(p[1])&&Number.isFinite(p[2]));
      state.historyLastFetch=Date.now();
      drawHistory();
    } catch(err) {
      if (serial===state.historyRequestSerial && region===state.system && ident===state.selected) {
        state.historyLastFetch=Date.now();
        $('historyStatus').textContent=`History unavailable (${err.message}). Live bus positions are unaffected.`;
      }
    } finally {
      if (serial===state.historyRequestSerial) state.historyLoading=false;
    }
  }
  function selectVehicle(id, center) {
    const vehicle = state.vehicles.find((v) => v.id === id);
    if (!vehicle) return;
    if (state.selected !== id){ resetHistory(); $('shareVehicleStatus').hidden=true; }
    state.selected = id;
    $('sharedVehicleNotice').hidden=true;
    document.body.classList.add('detail-open');
    $('detailSection').hidden = false;
    document.querySelector('.fleet-section').hidden = true;
    document.querySelector('.search-section').hidden = true;
    document.querySelector('.stats-row').hidden = true;
    $('favoritesSection').hidden = true;
    $('alertsMainSection').hidden = true;
    $('nearbySection').hidden = true;
    $('preferencesSection').hidden = true;
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
    // Tapping a marker shows a thumb-friendly half-height bottom sheet.
    if (mobile()) { setSheetMode('half'); setSidebar(true); }

  }
  function leaveDetails() {
    resetHistory();
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
    $('favoritesSection').hidden = !state.favorites.routes.length && !state.favorites.stops.length && !state.favorites.buses.length;
    $('alertsMainSection').hidden = false;
    $('nearbySection').hidden = !state.userLocation;
    $('preferencesSection').hidden = false;
    lastListSignature = '';
    renderMap();
    renderList();
    updateMobileOpenLabel();
  }
  function setFilter(query) {
    state.query = query.trim().toUpperCase().slice(0, 12);
    lastListSignature = '';
    $('routeSearch').value = state.query;
    $('clearSearch').hidden = !state.query;
    document.querySelectorAll('.quick-chip').forEach((chip) => chip.classList.toggle('active', chip.dataset.route === state.query));
    try { localStorage.setItem(filterKey(), state.query); } catch (_) {}
    renderList();
    renderMap();
  }
  function routeColor(vehicle) {
    const color = vehicle?.route_color;
    if (!state.routeColors) return state.theme === 'dark' ? '#999999' : '#7b7b7b';
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
    return L.divIcon({className:'vehicle-icon',html,iconSize:mobile() ? [54,50] : [46,38],iconAnchor:mobile() ? [27,26] : [23,20]});
  }
  function clusterIcon(count) {
    const html = count === 1 ? '<div class="bus-dot"></div>' : `<div class="bus-cluster">${count}</div>`;
    return L.divIcon({ className:'cluster-icon', html, iconSize:[30,30], iconAnchor:[15,15] });
  }
  function computeVisibleMarkers() {
    const map = state.map;
    const bounds = map.getBounds().pad(0.18);
    const visible = filteredVehicles().filter((v) => bounds.contains([v.lat, v.lon]));
    if (map.getZoom() > (mobile() && state.lite ? 13 : 11)) return visible.map((v) => ({ key:`bus:${v.id}`, lat:v.lat, lon:v.lon, type:'bus', vehicle:v }));
    // Always keep a selected vehicle individually tappable, even when its neighbors are clustered.
    const focused = visible.find((v) => v.id === state.selected);
    // Render fewer markers when zoomed out; map projection gives stable cell sizes.
    const size = mobile() && state.lite ? (map.getZoom() < 10 ? 68 : 58) : (map.getZoom() < 10 ? 46 : 38);
    const groups = new Map();
    for (const v of visible) {
      if (focused && v.id === focused.id) continue;
      const p = map.project([v.lat, v.lon], map.getZoom());
      const x = Math.floor(p.x / size); const y = Math.floor(p.y / size);
      const key = `${x}:${y}`;
      if (!groups.has(key)) groups.set(key, {key:`cluster:${key}`, lat:0, lon:0, count:0, vehicle:v});
      const group = groups.get(key); group.lat += v.lat; group.lon += v.lon; group.count++;
    }
    const rendered = [...groups.values()].map((g) => ({...g, lat:g.lat/g.count, lon:g.lon/g.count, type:'cluster'}));
    if (focused) rendered.push({key:`bus:${focused.id}`,lat:focused.lat,lon:focused.lon,type:'bus',vehicle:focused});
    return rendered;
  }
  function renderMap() {
    if (!state.map) return;
    const desired = computeVisibleMarkers();
    const keep = new Set();
    for (const item of desired) {
      keep.add(item.key);
      const selected = item.type === 'bus' && item.vehicle.id === state.selected;
      const sig = item.type === 'bus'
        ? `b:${mapLabel(item.vehicle)}:${Math.round(item.vehicle.bearing || 0)}:${routeColor(item.vehicle)}:${selected}:${state.query}:${state.markerSize}`
        : `c:${item.count}`;
      let record = state.markers.get(item.key);
      if (!record) {
        const icon = item.type === 'bus' ? markerIcon(item.vehicle, selected) : clusterIcon(item.count);
        const marker = L.marker([item.lat,item.lon], { icon, keyboard: !touchScreen(), zIndexOffset:selected ? 1000 : 0 });
        record = {marker, sig, latest:item};
        // Attach once, read the latest item each time; do not detach/rebind on GPS refresh.
        marker.on('click', () => {
          const current = record.latest;
          if (current.type === 'bus' || current.count === 1) selectVehicle(current.vehicle.id, true);
          else state.map.setView([current.lat, current.lon], Math.min(16, state.map.getZoom()+2), { animate:false });
        });
        marker.addTo(state.map);
        state.markers.set(item.key, record);
      } else {
        record.latest = item;
        const previous = record.marker.getLatLng();
        if (Math.abs(previous.lat-item.lat)>0.000001 || Math.abs(previous.lng-item.lon)>0.000001)
        {
          // Ease only actual position corrections, not map pans or zooms.
          const element = record.marker.getElement();
          if (element && state.positionRefresh && item.type === 'bus' && !lowMotion() && !(mobile() && state.lite)) {
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
      }
    }
    for (const [key, record] of state.markers) {
      if (!keep.has(key)) {record.marker.remove(); state.markers.delete(key);}
    }
  }
  function arrivalForStop(item) {
    const prediction = state.arrivals.get(Number(item.sequence));
    if (prediction && Number.isFinite(prediction.predicted_at)) {
      const time = arrivalFormatter.format(new Date(prediction.predicted_at * 1000));
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
    const listScroll = list.scrollTop;
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
      const wrap=document.createElement('div');wrap.className='stop-list-entry';
      const fav=document.createElement('button');fav.type='button';fav.className='stop-star';
      const stop={id:String(item.id||''),name:item.name};
      const saved=state.favorites.stops.some(s=>s.id===stop.id);
      fav.textContent=saved?'★':'☆';fav.disabled=!stop.id;
      fav.setAttribute('aria-label',`${saved?'Remove':'Save'} favourite stop ${item.name}`);
      fav.addEventListener('click',()=>toggleFavoriteStop(stop));
      wrap.append(button,fav);fragment.append(wrap);
    }
    list.append(fragment);
    list.scrollTop = listScroll;
    for (const item of detail.stops) {
      const marker = state.stopMarkers.get(Number(item.sequence));
      if (marker) marker.setPopupContent(stopPopupContent(item));
    }
  }
  async function refreshSelectedArrivals() {
    state.lastArrivalRefreshAt=Date.now();
    const selected = state.vehicles.find((v) => v.id === state.selected);
    if (!selected?.trip_id) return;
    const tripId = selected.trip_id;
    const activeSystem = state.system;
    if (state.arrivalsPending && state.arrivalsLoadingTrip === tripId) return;
    state.arrivalsPending = true;
    state.arrivalsLoadingTrip = tripId;
    try {
      const response = await fetch(apiPath('arrivals', {trip_id:tripId}), {cache:'no-store'});
      if (!response.ok) throw new Error(`Arrivals HTTP ${response.status}`);
      const payload = await response.json();
      if (activeSystem !== state.system || state.selected !== selected.id || tripId !== state.arrivalsTrip) return;
      state.arrivals = new Map((payload.stops || [])
        .filter((s) => Number.isFinite(s.sequence) && Number.isFinite(s.predicted_at))
        .map((s) => [Number(s.sequence), s]));
      state.arrivalStatus = payload.status || 'unavailable';
      updateStopInterfaces();
    } catch (_) {
      if (activeSystem === state.system && state.selected === selected.id) {
        state.arrivals = new Map();
        state.arrivalStatus = 'unavailable';
        updateStopInterfaces();
      }
    } finally {
      if (activeSystem === state.system && state.arrivalsLoadingTrip === tripId) {
        state.arrivalsPending = false;
        state.arrivalsLoadingTrip = null;
      }
    }
  }
  async function loadSelectedRoute(vehicle) {
    const tripId = vehicle.trip_id;
    state.routeRequestSerial++;
    const token = state.routeRequestSerial;
    const activeSystem = state.system;
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
      if (activeSystem !== state.system || state.selected !== vehicle.id || token !== state.routeRequestSerial) return;
      state.routeDetail = detail;
      state.stopMarkers.clear();
      if (state.routeLayer) state.routeLayer.clearLayers();
      const points = Array.isArray(detail.shape) ? detail.shape : [];
      if (state.routeLayer && points.length > 1) {
        L.polyline(points, {color: state.theme === 'classic' ? '#545454' : '#3f4247', weight: 8, opacity: 0.62, interactive: false}).addTo(state.routeLayer);
        L.polyline(points, {color: state.routeColors ? (detail.color || routeColor(vehicle)) : routeColor(vehicle), weight: 4.5, opacity: 0.98, interactive: false}).addTo(state.routeLayer);
      }
      const current = state.vehicles.find((v) => v.id === state.selected) || vehicle;
      const prev = current.stops?.previous;
      const next = current.stops?.next;
      if (state.routeLayer && Array.isArray(detail.stops)) {
        for (const item of detail.stops) {
          const isNext = next && item.sequence === next.sequence;
          const isPrev = prev && item.sequence === prev.sequence;
          const marker = L.circleMarker([item.lat,item.lon], {
            radius:touchScreen() ? (isNext ? 13 : 11) : (isNext ? 7 : isPrev ? 6 : 4),
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
    if (routeCache.has(`${state.system}:${tripId}`)) { apply(routeCache.get(`${state.system}:${tripId}`)); return; }
    try {
      const response = await fetch(apiPath('route', {trip_id:tripId}), {cache:'no-store'});
      if (!response.ok) throw new Error(`Route data HTTP ${response.status}`);
      const detail = await response.json();
      routeCache.set(`${activeSystem}:${tripId}`, detail);
      if (routeCache.size > 25) routeCache.delete(routeCache.keys().next().value);
      apply(detail);
    } catch (_) {
      if (activeSystem === state.system && state.selected === vehicle.id && token === state.routeRequestSerial) {
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
    if (state.historyVisible && state.historyPoints.length) drawHistory();
    if (save) try { localStorage.setItem('bct_theme', state.theme); } catch (_) {}
  }
  function restoredView() {
    try {
      const v = JSON.parse(localStorage.getItem('bct_last_map_view_' + state.system) || (state.system === 'victoria' ? localStorage.getItem('bct_last_map_view') : 'null') || 'null');
      if (v && Number.isFinite(v.lat) && Number.isFinite(v.lon) && Number.isInteger(v.zoom)
          && Math.abs(v.lat) <= 85 && Math.abs(v.lon) <= 180 && v.zoom >= 4 && v.zoom <= 19)
        return v;
    } catch (_) {}
    return currentView();
  }
  function saveMapView() {
    if (!state.map || state.userLocation) return;
    const point = state.map.getCenter();
    try { localStorage.setItem('bct_last_map_view_' + state.system, JSON.stringify({
      lat: Math.round(point.lat * 1e5)/1e5,
      lon: Math.round(point.lng * 1e5)/1e5,
      zoom: state.map.getZoom()
    })); } catch (_) {}
  }
  let boardMapTimer=null;
  function scheduleBoardUpdate() {clearTimeout(boardMapTimer);boardMapTimer=setTimeout(()=>refreshNearbyBoard(),700);}
  function initMap() {
    if (!mobile()) {
      try {state.closed=localStorage.getItem('bct_desktop_sidebar_closed')==='true';} catch (_) {}
      document.body.classList.toggle('sidebar-hidden',state.closed);
    }
    if (window.innerWidth <= 720) {
      state.closed = true;
      document.body.classList.add('sidebar-hidden');
    }
    if (!window.L) { $('mapUnavailable').hidden = false; return; }
    const view = restoredView();
    const map = L.map('map', { center:[view.lat,view.lon], zoom:view.zoom,
      zoomControl:false, preferCanvas:true, zoomSnap:1, attributionControl:true,
      zoomAnimation: !(mobile() && state.lite), fadeAnimation: !(mobile() && state.lite),
      markerZoomAnimation: !(mobile() && state.lite) });
    // CARTO light_all approximates the plain, practical road-map look.
    // With no CARTO key, keep the familiar light OpenStreetMap fallback.
    const key = window.BUS_RADAR_CONFIG?.cartoKey?.trim() || '';
    state.tileLayer = L.tileLayer(tileUrlForTheme(state.theme), {
      attribution: key ? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attribution/">CARTO</a>' : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      subdomains: key ? 'abcd' : 'abc', maxZoom:19, maxNativeZoom:key ? 18 : 19, crossOrigin:false, updateWhenIdle:true, keepBuffer:mobile() && state.lite ? 1 : 2,
    }).addTo(map);
    L.control.zoom({position:'bottomright'}).addTo(map);
    map.on('zoomend moveend', () => {renderMap(); saveMapView(); if(boardOpen() && !state.userLocation) scheduleBoardUpdate();});
    state.map = map;
    // Monitor the *actual* Leaflet container, including desktop monitor scaling.
    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(() => refreshMapLayout());
      observer.observe($('map'));
    }
    window.addEventListener('resize', refreshMapLayout, {passive:true});
    $('sidebar').addEventListener('transitionend', (event) => {
      if (event.propertyName === 'margin-left' || event.propertyName === 'transform') refreshMapLayout();
    });
    state.routeLayer = L.layerGroup().addTo(map);
    state.historyLayer = L.layerGroup().addTo(map);
  }
  function updateMobileOpenLabel() {
    $('mobileOpenText').textContent = state.selected ? 'Bus details' : 'Routes';
    $('mobileOpen').setAttribute('aria-label', state.selected ? 'Show selected bus details' : 'Open route search and bus list');
  }
  function setSheetMode(mode) {
    state.sheetMode = mode === 'full' ? 'full' : 'half';
    document.body.classList.toggle('sheet-full', state.sheetMode === 'full');
    $('sheetHandle').setAttribute('aria-expanded', String(state.sheetMode === 'full'));
    $('sheetHandle').setAttribute('aria-label', state.sheetMode === 'full' ? 'Reduce bus panel height' : 'Expand bus panel');
    // The map stays full screen behind the sheet, so only a resize refresh is needed.
  }
  // Leaflet must be resized after CSS's 170 ms sidebar transition finishes.
  // A single early invalidateSize leaves grey strips on wider displays.
  let mapLayoutTimer = null;
  function refreshMapLayout() {
    if (!state.map) return;
    const update = () => { if (state.map) state.map.invalidateSize({pan:false, animate:false}); };
    window.requestAnimationFrame(update);
    clearTimeout(mapLayoutTimer);
    mapLayoutTimer = setTimeout(update, 230);
  }
  function setSidebar(visible) {
    state.closed = !visible;
    if (visible && state.needsListRefresh) renderList();
    document.body.classList.toggle('sidebar-hidden', state.closed);
    if (!mobile()) try {localStorage.setItem('bct_desktop_sidebar_closed', String(state.closed));} catch (_) {}
    updateMobileOpenLabel();
    if (visible && mobile()) $('nearbyBoard').open=false;
    if (state.map) refreshMapLayout();
  }
  function setLite(enabled, persist = true) {
    state.lite = Boolean(enabled);
    const btn = $('liteToggle');
    btn.setAttribute('aria-pressed', String(state.lite));
    btn.title = state.lite ? 'Disable lightweight map mode (show more bus markers)' : 'Enable lightweight map mode (reduce map workload)';
    btn.setAttribute('aria-label', btn.title);
    btn.classList.toggle('active', state.lite);
    if (state.map) {
      // React to toggle without repeatedly requesting the same map assets.
      state.markers.forEach(({marker}) => marker.remove());
      state.markers.clear();
      renderMap();
    }
    if (persist) try { localStorage.setItem('bct_mobile_lite', String(state.lite)); } catch (_) {}
  }
  function applyData(data, cached = false) {
    if (!data || !Array.isArray(data.vehicles) || (data.system && data.system !== state.system)) return;
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
          (state.routeStopSignature !== stops && routeCache.has(`${state.system}:${selected.trip_id}`))) {
          loadSelectedRoute(selected);
        }
      }
    }
    if (state.following && state.selected && state.map) {
      const active = state.vehicles.find((v) => v.id === state.selected);
      if (active) state.map.panTo([active.lat,active.lon], {animate:false});
    }
    // Refresh an open trail only after a newer live snapshot and at most once
    // every 20 seconds. No history request on startup, pan, or route filtering.
    if(state.historyVisible && state.selected && Date.now()-state.historyLastFetch>20000) loadHistory();
    state.positionRefresh = true;
    renderStatus(); renderList(); renderMap();
    state.positionRefresh = false;
    if (state.userLocation) renderNearby();
    updateBoardFromVehicles();
    if(state.favorites.buses.length && !state.selected && !$('favoritesSection').hidden) renderFavorites();
    if(state.pendingShare) processSharedLink();
  }
  async function loadVehicles() {
    if (state.requestPending) return;
    state.requestPending = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 9000);
    const requestSystem = state.system;
    const requestGeneration = state.systemGeneration;
    try {
      const extras = state.data && !state.restoredCache ? {since:state.data.revision} : {};
      const response = await fetch(apiPath('vehicles', extras), {cache:'no-store',signal:controller.signal});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (requestSystem !== state.system || requestGeneration !== state.systemGeneration) return;
      if (data.unchanged) {
        if (state.data) { state.data.error = data.error; state.data.metadata_error = data.metadata_error; }
        state.clientError = null; renderStatus(); return;
      }
      if (!Array.isArray(data.vehicles)) throw new Error('Invalid JSON');
      state.clientError = null;
      applyData(data);
      try { sessionStorage.setItem(snapshotKey(),JSON.stringify({ savedAt:Date.now(), data })); } catch (_) {}
    } catch (err) {
      if (requestSystem !== state.system || requestGeneration !== state.systemGeneration) return;
      state.clientError = err.message || 'Cannot reach local server';
      if (!state.data) $('listHint').textContent = 'Local server not responding. Check that app.py is running.';
      renderStatus(); renderList();
    } finally {
      clearTimeout(timeout); if (requestGeneration === state.systemGeneration) state.requestPending = false;
    }
  }
  function renderQuickRoutes() {
    const container = $('quickRoutes'); container.replaceChildren();
    const choices = [['', 'All routes'], ...SYSTEMS[state.system].shortcuts.map(r=>[r,r]), ['NIS','Likely NIS']];
    for (const [value, title] of choices) {
      const button = document.createElement('button'); button.type='button';
      button.className = `quick-chip${value === state.query ? ' active' : ''}`;
      button.dataset.route = value; button.textContent = title;
      button.addEventListener('click', ()=>setFilter(value)); container.appendChild(button);
    }
  }
  // V3.1 — on-demand extras. Neither history, alerts nor last-known lookups are
  // requested during ordinary map startup (except when opening a shared link).
  const alertsCache = new Map();
  const isSavedBus = v => state.favorites.buses.some(x => x.id === String(v.id) || (x.fleet && x.fleet === String(v.fleet_number||'')));
  const busFavouriteKey = v => String(v.fleet_number||v.id);
  function updateFavoriteBusButton(vehicle) {
    $('favoriteBusButton').textContent = isSavedBus(vehicle) ? '★ Saved bus — remove' : '☆ Save this bus';
  }
  function toggleFavoriteBus(vehicle) {
    if (!vehicle) return;
    const id=String(vehicle.id), fleet=String(vehicle.fleet_number || '');
    if (isSavedBus(vehicle)) state.favorites.buses=state.favorites.buses.filter(x => x.id !== id && (!fleet || x.fleet !== fleet));
    else if (state.favorites.buses.length < 40) state.favorites.buses.push({id, fleet, name:fleet ? 'Bus #'+fleet : 'Vehicle '+id.slice(0,22)});
    saveFavorites(); updateFavoriteBusButton(vehicle);
  }
  function currentSavedBus(entry) {
    return state.vehicles.find(v => (entry.fleet && String(v.fleet_number||'') === entry.fleet) || v.id === entry.id);
  }
  function renderSavedVehicles(host) {
    for (const entry of state.favorites.buses) {
      const active=currentSavedBus(entry), row=document.createElement('div');row.className='v31-favorite-vehicle';
      const open=document.createElement('button');open.type='button';open.className='favorite-chip v31-favorite-open';
      open.textContent=`${entry.name} · ${active ? (ageSeconds(active)>120 ? 'stale GPS' : 'reporting')+' · Route '+label(active.route) : 'not reporting'}`;
      open.addEventListener('click',()=>{
        if(active)selectVehicle(active.id,true);
        else showLastKnown({system:state.system, fleet:entry.fleet, vehicle:entry.id});
      });
      const remove=document.createElement('button');remove.type='button';remove.className='v31-favorite-remove';
      remove.textContent='×';remove.title='Remove '+entry.name;remove.setAttribute('aria-label','Remove '+entry.name);
      remove.addEventListener('click',()=>{state.favorites.buses=state.favorites.buses.filter(x=>x!==entry);saveFavorites();});
      row.append(open,remove);host.append(row);
    }
  }
  function vehicleShareLink(vehicle) {
    const link = new URL(location.href);link.search='';link.hash='';
    link.searchParams.set('system',state.system);
    if (state.system === 'victoria' && /^\d{4}$/.test(String(vehicle.fleet_number||''))) link.searchParams.set('fleet',String(vehicle.fleet_number));
    else link.searchParams.set('vehicle',String(vehicle.id));
    return link.href;
  }
  async function shareSelectedBus() {
    const v=state.vehicles.find(x=>x.id===state.selected);if(!v)return;
    const link=vehicleShareLink(v), status=$('shareVehicleStatus');
    try {
      if (navigator.share && touchScreen()) await navigator.share({title:'BC Transit Bus Radar · '+(v.fleet_number ? 'Bus #'+v.fleet_number : 'Vehicle'),url:link});
      else if (navigator.clipboard?.writeText) {await navigator.clipboard.writeText(link);status.textContent='Vehicle link copied.';status.hidden=false;}
      else {window.prompt('Copy this vehicle link',link);status.textContent='Share link ready.';status.hidden=false;}
    } catch(e) {if(e?.name!=='AbortError'){status.textContent='Sharing unavailable. Copy the URL from the browser instead.';status.hidden=false;}}
  }
  function showSharedMessage(title,text,point) {
    const host=$('sharedVehicleNotice');host.replaceChildren();host.hidden=false;
    if(mobile()){setSidebar(true);setSheetMode('half');}
    const heading=document.createElement('strong');heading.textContent=title;
    const body=document.createElement('p');body.textContent=text;
    host.append(heading,body);
    if(point && Number.isFinite(point.lat) && Number.isFinite(point.lon)) {
      const locate=document.createElement('button');locate.className='mini-button';locate.type='button';
      locate.textContent='Show last recorded position';
      locate.addEventListener('click',()=>{
        if(!state.map||!window.L)return;
        if(state.sharedFocusMarker)state.sharedFocusMarker.remove();
        state.sharedFocusMarker=L.circleMarker([point.lat,point.lon],{radius:9,color:'#994411',weight:2,fillColor:'#d78f2e',fillOpacity:.7}).addTo(state.map);
        state.map.setView([point.lat,point.lon],Math.max(13,state.map.getZoom()),{animate:false});
        if(mobile())setSheetMode('half');
      });
      host.append(locate);
    }
  }
  async function showLastKnown(target) {
    const system=state.system;
    showSharedMessage('Bus not currently reporting','Checking the last 24 hours of saved GPS history…');
    try {
      const extras=target.fleet && system==='victoria' ? {fleet:target.fleet} : {vehicle_id:target.vehicle};
      if(!extras.fleet && !extras.vehicle_id)throw new Error('No vehicle identifier');
      const res=await fetch(apiPath('last-known',extras),{cache:'no-store'});
      if(!res.ok)throw new Error('History unavailable');
      const data=await res.json();if(system!==state.system)return;
      if(!data.found){showSharedMessage('Bus not currently reporting','No recorded GPS positions from the last 24 hours.');return;}
      const v=data.vehicle;
      const stamp=new Date(v.timestamp*1000).toLocaleString('en-CA',{timeZone:'America/Vancouver',dateStyle:'medium',timeStyle:'short'});
      showSharedMessage('Last recorded position — NOT LIVE',`${stamp} · Route ${v.route||'unknown'} · the bus may have moved since this GPS report.`,v);
    } catch(err){if(system===state.system)showSharedMessage('Bus not currently reporting','Last recorded information is unavailable: '+err.message);}
  }
  function readShareQuery(){
    const params=new URLSearchParams(location.search),system=params.get('system');
    if(!system || !Object.hasOwn(SYSTEMS,system))return null;
    const fleet=params.get('fleet'), vehicle=params.get('vehicle');
    if (fleet && system==='victoria' && /^\d{4}$/.test(fleet)) return {system,fleet,vehicle:null,checked:false};
    if (vehicle && vehicle.length<=128) return {system,fleet:null,vehicle,checked:false};
    return null;
  }
  function processSharedLink() {
    const target=state.pendingShare;if(!target||target.system!==state.system)return;
    const found=state.vehicles.find(v=>target.fleet ? String(v.fleet_number||'')===target.fleet : v.id===target.vehicle);
    if(found){state.pendingShare=null;$('sharedVehicleNotice').hidden=true;selectVehicle(found.id,true);return;}
    // On first real feed response, show the last recorded fix once; keep watching
    // for the live bus to appear on later snapshots.
    if(!target.checked && state.data?.fetched_at){target.checked=true;showLastKnown(target);}
  }
  function alertMatchesVehicle(entry,vehicle){
    const selectors=entry.selectors||[];
    if(!selectors.length)return true;
    return selectors.some(s=>(!s.route_id || s.route_id===vehicle.route_id) &&
      (!s.trip_id || s.trip_id===vehicle.trip_id) &&
      (!s.stop_id || s.stop_id===vehicle.stop_id));
  }
  function renderAlerts(hostId,vehicle){
    const host=$(hostId);host.replaceChildren();
    const payload=alertsCache.get(state.system)?.data;
    if(!payload){host.textContent='Open this panel to load published service alerts.';return;}
    if(!payload.ready){host.textContent='Service alerts unavailable ('+(payload.error||'source not responding')+').';return;}
    let alerts=Array.isArray(payload.alerts)?payload.alerts:[];
    if(vehicle) alerts=alerts.filter(a=>alertMatchesVehicle(a,vehicle));
    if(!alerts.length){host.textContent=vehicle?'No matching alerts currently published for this vehicle.':'No active alerts in the published feed.';return;}
    for(const alert of alerts.slice(0,35)){
      const item=document.createElement('article');item.className='v31-alert-item';
      const title=document.createElement('strong');title.textContent=alert.title||'Service alert';item.append(title);
      const tag=document.createElement('span');tag.className='v31-alert-tag';tag.textContent=alert.effect||'Service notice';item.append(tag);
      if(alert.description){const desc=document.createElement('small');desc.textContent=alert.description.slice(0,800);item.append(desc);}
      if(alert.url){try {const u=new URL(alert.url);if(['https:','http:'].includes(u.protocol)){
        const a=document.createElement('a');a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';a.textContent='More information';item.append(a);
      }}catch(_){}}
      host.append(item);
    }
    if(payload.error){const notice=document.createElement('p');notice.className='panel-status';notice.textContent='Latest refresh failed; showing previously fetched alerts.';host.prepend(notice);}
  }
  async function loadAlerts(hostId,vehicle=null){
    const system=state.system, current=alertsCache.get(system);
    if(current && Date.now()-current.at<180000){renderAlerts(hostId,vehicle);return;}
    const host=$(hostId);host.textContent='Checking BC Transit service alerts…';
    try {
      const res=await fetch(apiPath('alerts'),{cache:'no-store'});
      if(!res.ok)throw new Error('HTTP '+res.status);
      const data=await res.json();if(system!==state.system)return;
      alertsCache.set(system,{at:Date.now(),data});
      const active=vehicle ? state.vehicles.find(v=>v.id===state.selected) : null;
      if(!vehicle || (active && active.id===vehicle.id))renderAlerts(hostId,active);
    } catch(err){if(system===state.system){alertsCache.set(system,{at:Date.now()-135000,data:{ready:false,error:err.message}});renderAlerts(hostId,vehicle);}}
  }
  function renderDaySummary(data){
    const box=$('activityDaySummary');box.replaceChildren();box.hidden=false;
    const eventRows=Array.isArray(data.events)?data.events:[];
    const latest=eventRows.length ? Math.max(...eventRows.map(e=>Number(e.end_ts)||0)) : 0;
    const allRoutes=Array.isArray(data.distinct_routes)?data.distinct_routes:[];
    const format=t=>t?activityStamp(t):'Unavailable';
    const items=[
      ['First in selected window',format(data.recording_since)],
      ['Last recorded',format(latest)],
      ['Routes observed',allRoutes.length?allRoutes.join(', '):'None recorded'],
      ['Route changes',String(Number(data.reported_route_changes)||0)],
      ['Off-route GPS fixes',String(Number(data.off_route_observations)||0)]
    ];
    for(const [caption,value] of items){const item=document.createElement('div');item.className='v31-activity-stat'+(caption==='Routes observed'?' v31-activity-stat-wide':'');
      const small=document.createElement('small');small.textContent=caption;
      const strong=document.createElement('strong');strong.textContent=value;
      item.append(small,strong);box.append(item);
    }
  }

  function favoriteStorageKey(){return 'bct_favorites_v28_'+state.system;}
  function readFavorites(){
    try {
      const value=JSON.parse(localStorage.getItem(favoriteStorageKey())||'{}');
      state.favorites={routes:Array.isArray(value.routes)?value.routes.filter(v=>typeof v==='string').slice(0,30):[],
        stops:Array.isArray(value.stops)?value.stops.filter(v=>v&&typeof v.id==='string'&&typeof v.name==='string').slice(0,30):[],
        buses:Array.isArray(value.buses)?value.buses.filter(v=>v&&typeof v.id==='string'&&v.id.length<129&&typeof v.name==='string'&&(!v.fleet||/^\d{4}$/.test(v.fleet))).slice(0,40):[]};
    } catch(_){state.favorites={routes:[],stops:[],buses:[]};}
  }
  function saveFavorites(){
    try{localStorage.setItem(favoriteStorageKey(),JSON.stringify(state.favorites));}catch(_){}
    renderFavorites();lastListSignature='';renderList();
    if(state.selected){const current=state.vehicles.find(v=>v.id===state.selected);updateFavoriteRouteButton(current?.route);if(current)updateFavoriteBusButton(current);}
    if(state.userLocation) renderNearby();
    updateBoardFromVehicles();
    if(state.routeDetail) updateStopInterfaces();
  }
  function toggleFavoriteRoute(value){
    const route=String(value||'');if(!route||route==='?')return;
    if(state.favorites.routes.includes(route))state.favorites.routes=state.favorites.routes.filter(r=>r!==route);
    else if(state.favorites.routes.length<30)state.favorites.routes.push(route);
    saveFavorites();
  }
  function toggleFavoriteStop(stop){
    if(!stop?.id)return;
    const id=String(stop.id);
    if(state.favorites.stops.some(s=>s.id===id))state.favorites.stops=state.favorites.stops.filter(s=>s.id!==id);
    else if(state.favorites.stops.length<30)state.favorites.stops.push({id,name:String(stop.name||id)});
    saveFavorites();
  }
  function updateFavoriteRouteButton(route){
    const button=$('favoriteRouteButton');
    const available=Boolean(route && route!=='?');button.disabled=!available;
    button.textContent=available ? (state.favorites.routes.includes(String(route))?'★ Favourite route — remove':'☆ Save Route '+route) : 'Route unavailable to save';
  }
  function renderFavorites(){
    const container=$('favoritesList');container.replaceChildren();
    const routes=state.favorites.routes, stops=state.favorites.stops, buses=state.favorites.buses;
    $('favoritesSection').hidden=Boolean(state.selected)||(!routes.length&&!stops.length&&!buses.length);
    renderSavedVehicles(container);
    for(const route of routes){
      const chip=document.createElement('button');chip.type='button';chip.className='favorite-chip';
      chip.textContent='★ '+route;chip.title='Show Route '+route;
      chip.addEventListener('click',()=>{
        state.expandedGroups.add('route:'+route);setFilter(route);
        if(mobile())setSheetMode('full');
      });container.append(chip);
    }
    for(const stop of stops){
      const chip=document.createElement('button');chip.type='button';chip.className='favorite-chip stop-favorite';
      chip.textContent='★ '+stop.name;chip.title='Find stop '+stop.name;
      chip.addEventListener('click',()=>showFavoriteStop(stop.id));container.append(chip);
    }
  }
  async function loadStopCatalog(){
    if(stopCatalog.has(state.system))return stopCatalog.get(state.system);
    const system=state.system,generation=state.systemGeneration;
    const res=await fetch(apiPath('stops'),{cache:'no-store'});
    if(!res.ok)throw new Error(`Stop feed HTTP ${res.status}`);
    const data=await res.json();
    if(system!==state.system||generation!==state.systemGeneration)throw new Error('Transit system changed');
    if(!data.ready)throw new Error('Stop schedule is not loaded yet; try again shortly');
    const rows=(data.stops||[]).filter(r=>Array.isArray(r)&&r.length>=4&&Number.isFinite(r[2])&&Number.isFinite(r[3]))
      .map(r=>({id:String(r[0]),name:String(r[1]),lat:r[2],lon:r[3]}));
    stopCatalog.set(system,rows);
    return rows;
  }
  function clearLocationMarker(){
    if(state.locationMarker){state.locationMarker.remove();state.locationMarker=null;}
    if(state.locationCircle){state.locationCircle.remove();state.locationCircle=null;}
  }
  function stopLocation(){
    state.userLocation=null;state.pendingNearestSort=false;clearLocationMarker();
    if(boardOpen())refreshNearbyBoard(true);
    $('nearbySection').hidden=true;
    $('locateButton').setAttribute('aria-pressed','false');
    $('locateButton').classList.remove('active');$('locateButton').title='Show my location and nearby buses';
    if(state.sortBy==='nearest'){state.sortBy='route';savePreferences();$('sortSelect').value='route';}
    lastListSignature='';renderList();
  }
  function startLocation(){
    if(state.userLocation){requestLocation();return;}
    if(state.locationRequestPending)return;
    if(!navigator.geolocation){
      $('nearbySection').hidden=false;$('nearbyHint').textContent='Your browser does not support location access.';return;
    }
    if(!$('locationConsent').open){$('locationConsent').showModal();}
  }
  function requestLocation(){
    state.locationRequestPending=true;
    $('nearbySection').hidden=false;
    $('nearbyHint').textContent='Requesting location from your browser…';
    const system=state.system;
    navigator.geolocation.getCurrentPosition(async(pos)=>{
      state.locationRequestPending=false;
      if(system!==state.system)return;
      const {latitude:lat,longitude:lon,accuracy}=pos.coords;
      if(!Number.isFinite(lat)||!Number.isFinite(lon))return;
      state.userLocation={lat,lon,accuracy:Number.isFinite(accuracy)?accuracy:null};
      if(state.pendingNearestSort){state.pendingNearestSort=false;state.sortBy='nearest';savePreferences();$('sortSelect').value='nearest';}
      $('locateButton').setAttribute('aria-pressed','true');$('locateButton').classList.add('active');
      $('locateButton').title='Refresh my location';
      clearLocationMarker();
      if(state.map){
        state.locationMarker=L.circleMarker([lat,lon],{radius:8,color:'#fff',weight:3,fillColor:'#1976d2',fillOpacity:1,interactive:false}).addTo(state.map);
        if(Number.isFinite(accuracy)&&accuracy>0)
          state.locationCircle=L.circle([lat,lon],{radius:accuracy,weight:1,color:'#1976d2',fillColor:'#1976d2',fillOpacity:.09,interactive:false}).addTo(state.map);
        state.map.setView([lat,lon],Math.max(13,state.map.getZoom()),{animate:false});
      }
      setSidebar(true);renderNearby();if(boardOpen())refreshNearbyBoard(true);lastListSignature='';renderList();
      try{await loadStopCatalog();if(state.userLocation&&system===state.system)renderNearby();}
      catch(err){if(system===state.system){$('nearbyHint').textContent='Nearby buses available; stops: '+err.message;renderNearby(true);}}
    },err=>{
      if(system!==state.system)return;
      state.locationRequestPending=false;state.pendingNearestSort=false;
      $('nearbyHint').textContent=err?.code===1?'Location permission denied. You can enable it in your browser settings.'
        : 'Location unavailable. Check GPS/location settings or try again.';
    },{enableHighAccuracy:false,timeout:10000,maximumAge:30000});
  }
  // The nearby board is independent of the sidebar. Browser GPS coordinates
  // are never sent to the server; only publicly published stop IDs are requested.
  const boardOpen = () => Boolean($('nearbyBoard')?.open);
  function boardOrigin() {
    if (state.userLocation) return {lat:state.userLocation.lat,lon:state.userLocation.lon,label:'Near your location'};
    const center=state.map?.getCenter();
    return center ? {lat:center.lat,lon:center.lng,label:'Near map centre'} : null;
  }
  function closestStopToBus(v, stops) {
    let nearest=null, best=Infinity;
    for (const s of stops) {
      const d=metersBetween(v.lat,v.lon,s.lat,s.lon);
      if (d<best){best=d;nearest=s;}
    }
    return nearest ? `${nearest.name} · ${distanceLabel(best)} away` : 'Nearest stop unknown';
  }
  function renderNearbyBoard() {
    if (!boardOpen()) return;
    const host=$('boardResults');host.replaceChildren();
    const origin=boardOrigin();
    if (!origin) { $('boardHint').textContent='Map not ready';return; }
    $('boardHint').textContent=origin.label+' · showing published stops and active vehicles';
    const stops=stopCatalog.get(state.system);
    if (!stops) { host.textContent='Loading stop locations…';return; }
    const proximity=(s)=>metersBetween(origin.lat,origin.lon,s.lat,s.lon);
    const nearby=[...stops].sort((a,b)=>proximity(a)-proximity(b)).slice(0,3);
    const payload=state.boardPayload;
    const hasData=Boolean(payload && state.boardAt?.system===state.system &&
      nearby.every(s=>state.boardAt.ids.includes(s.id)));
    const heading=document.createElement('h3');heading.textContent='Next departures';host.append(heading);
    for (const stop of nearby) {
      const block=document.createElement('section');block.className='v32-board-stop';
      const name=document.createElement('button');name.className='v32-board-stopname';name.type='button';
      name.textContent=`${stop.name}  ·  ${distanceLabel(proximity(stop))}`;
      name.addEventListener('click',()=>focusStop(stop));block.append(name);
      const data=hasData?payload.stops.find(s=>s.stop_id===stop.id):null;
      if (!data) {const note=document.createElement('p');note.textContent='Checking schedule…';block.append(note);}
      else if (!data.arrivals?.length) {const note=document.createElement('p');note.textContent='No upcoming departures published';block.append(note);}
      else for (const a of data.arrivals.slice(0,4)) {
        const item=document.createElement('div');item.className='v32-departure';
        const rt=a.source==='live';
        const mins=Math.max(0,Math.round((a.arrival_at-Date.now()/1000)/60));
        const route=document.createElement('strong');route.className='v32-departure-route';route.textContent=a.route||'?';
        const where=document.createElement('span');where.className='v32-departure-dest';where.textContent=a.destination||'Destination unknown';
        const eta=document.createElement('span');eta.className='v32-departure-eta';eta.textContent=`${mins}m`;
        const stamp=document.createElement('small');stamp.textContent=`${rt?'Live':'Sched'} · ${arrivalFormatter.format(new Date(a.arrival_at*1000))}`;
        stamp.className=rt?'v32-live':'v32-sched';
        item.append(route,where,eta,stamp);block.append(item);
      }
      host.append(block);
    }
    const busHead=document.createElement('h3');busHead.textContent='Closest reporting buses';host.append(busHead);
    const buses=[...state.vehicles].filter(v=>Number.isFinite(v.lat)&&Number.isFinite(v.lon))
      .sort((a,b)=>metersBetween(origin.lat,origin.lon,a.lat,a.lon)-metersBetween(origin.lat,origin.lon,b.lat,b.lon)).slice(0,4);
    if (!buses.length) {const t=document.createElement('p');t.textContent='No buses currently reporting';host.append(t);}
    for (const v of buses) {
      const btn=document.createElement('button');btn.type='button';btn.className='v32-board-bus';
      const nearest=closestStopToBus(v,stops);
      btn.textContent=`Route ${label(v.route)} · Bus ${v.fleet_number||v.id} — ${nearest}${ageSeconds(v)>120?' · stale GPS':''}`;
      btn.addEventListener('click',()=>selectVehicle(v.id,true));host.append(btn);
    }
  }
  async function refreshNearbyBoard(force=false) {
    if (!boardOpen()) return;
    if (state.boardPending) {if (force) state.boardQueued=true;return;}
    const origin=boardOrigin();if (!origin)return;
    const system=state.system, generation=state.systemGeneration;
    state.boardPending=true;
    const token=++state.boardSerial;
    try {
      const stops=await loadStopCatalog();
      if (!boardOpen()||state.system!==system||state.systemGeneration!==generation||token!==state.boardSerial)return;
      const ids=[...stops].sort((a,b)=>metersBetween(origin.lat,origin.lon,a.lat,a.lon)-metersBetween(origin.lat,origin.lon,b.lat,b.lon))
        .slice(0,3).map(s=>s.id);
      if (!ids.length) {state.boardPayload=null;renderNearbyBoard();return;}
      if (!force && state.boardAt?.system===system && ids.join('|')===state.boardAt.ids.join('|') &&
          Date.now()-state.boardLastFetch<45000) {renderNearbyBoard();return;}
      state.boardAt={system,ids};state.boardPayload=null;
      renderNearbyBoard();
      const url=apiPath('nearby-departures')+ids.map(id=>'&stop_id='+encodeURIComponent(id)).join('');
      const resp=await fetch(url,{cache:'no-store'});
      if (!resp.ok)throw new Error('Departure feed unavailable');
      const data=await resp.json();
      if (!boardOpen()||state.system!==system||state.systemGeneration!==generation||token!==state.boardSerial)return;
      state.boardPayload=data;state.boardLastFetch=Date.now();renderNearbyBoard();
    } catch(err) {
      if (system===state.system && token===state.boardSerial) $('boardResults').textContent=err?.message||'Unable to load nearby departures';
    } finally {
      if(token===state.boardSerial){
        state.boardPending=false;
        if(state.boardQueued){state.boardQueued=false;refreshNearbyBoard(true);}
      }
    }
  }
  function updateBoardFromVehicles() { if(boardOpen() && state.boardPayload)renderNearbyBoard(); }
  function renderNearby(keepHint=false){
    if(!state.userLocation)return;
    const point=state.userLocation;
    if(!keepHint)$('nearbyHint').textContent=`Approximate location${point.accuracy?` (±${Math.round(point.accuracy)} m)`:''} · computed on this device`;
    const host=$('nearbyResults');host.replaceChildren();
    const busHeading=document.createElement('h3');busHeading.textContent='Closest reported buses';host.append(busHeading);
    const buses=[...state.vehicles].sort((a,b)=>localDistance(a)-localDistance(b)).slice(0,6);
    if(!buses.length){const empty=document.createElement('p');empty.textContent='No reported buses yet.';host.append(empty);}
    for(const v of buses){
      const button=document.createElement('button');button.className='nearby-item';button.type='button';
      const age=ageSeconds(v)>120?' · stale GPS':'';
      button.textContent=`${mapLabel(v)} · ${displayName(v)} — ${distanceLabel(localDistance(v))}${age}`;
      button.addEventListener('click',()=>selectVehicle(v.id,true));host.append(button);
    }
    const stopHeading=document.createElement('h3');stopHeading.textContent='Closest stops';host.append(stopHeading);
    const rows=stopCatalog.get(state.system);
    if(!rows){const loading=document.createElement('p');loading.textContent='Loading published stops on demand…';host.append(loading);return;}
    const stops=rows.map(r=>({...r,distance:localDistance(r)})).sort((a,b)=>a.distance-b.distance).slice(0,7);
    for(const stop of stops){
      const row=document.createElement('div');row.className='nearby-stop-row';
      const button=document.createElement('button');button.className='nearby-item';button.type='button';
      button.textContent=`${stop.name} · ${distanceLabel(stop.distance)}`;
      button.addEventListener('click',()=>focusStop(stop));
      const star=document.createElement('button');star.type='button';star.className='stop-star';
      const saved=state.favorites.stops.some(s=>s.id===stop.id);star.textContent=saved?'★':'☆';
      star.setAttribute('aria-label',`${saved?'Remove':'Save'} favourite stop ${stop.name}`);
      star.addEventListener('click',()=>toggleFavoriteStop(stop));row.append(button,star);host.append(row);
    }
  }
  async function showFavoriteStop(id){
    const system=state.system;
    try{
      const rows=await loadStopCatalog();
      if(system!==state.system)return;
      const stop=rows.find(s=>s.id===id);
      if(stop)focusStop(stop);
    }catch(err){
      $('nearbySection').hidden=false;$('nearbyHint').textContent='Cannot load saved stop: '+err.message;
      setSidebar(true);
    }
  }
  async function focusStop(stop){
    if(!state.map)return;
    const token=++state.nearbyStopToken,system=state.system;
    if(state.nearbyStopMarker)state.nearbyStopMarker.remove();
    const marker=L.circleMarker([stop.lat,stop.lon],{radius:11,color:'#1b64a8',weight:2,fillColor:'#fff',fillOpacity:1}).addTo(state.map);
    state.nearbyStopMarker=marker;
    marker.bindPopup(`<strong>${safe(stop.name)}</strong><br>Checking live arrivals…`,{maxWidth:285}).openPopup();
    state.map.setView([stop.lat,stop.lon],Math.max(15,state.map.getZoom()),{animate:false});
    if(mobile())setSidebar(false);
    try{
      const response=await fetch(apiPath('stop-arrivals',{stop_id:stop.id}),{cache:'no-store'});
      if(!response.ok)throw new Error('Unavailable');
      const payload=await response.json();
      if(system!==state.system||token!==state.nearbyStopToken)return;
      const arrivals=(payload.arrivals||[]).slice(0,8);
      const rows=arrivals.map(a=>`<div class="arrival-row"><strong>${safe(a.route)}</strong> ${safe(a.destination)} · <b>${safe(arrivalFormatter.format(new Date(a.arrival_at*1000)))}</b></div>`).join('');
      marker.setPopupContent(`<div class="stop-popup"><strong>${safe(stop.name)}</strong><small>${payload.status==='live'?'Live estimated arrivals':'No fresh live predictions available'}</small>${rows||'<span>Nothing currently predicted for this stop.</span>'}</div>`);
    }catch(_){
      if(system===state.system&&token===state.nearbyStopToken)
        marker.setPopupContent(`<strong>${safe(stop.name)}</strong><br>Live arrivals unavailable.`);
    }
  }
  async function checkSystemHealth(){
    const node=$('systemHealthList');node.replaceChildren();
    const loading=document.createElement('div');loading.textContent='Checking feeds…';node.append(loading);
    const systems=Object.entries(SYSTEMS);
    const results=await Promise.all(systems.map(async ([id,cfg])=>{
      const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),6500);
      try{
        const response=await fetch('/api/health?system='+encodeURIComponent(id),{cache:'no-store',signal:controller.signal});
        if(!response.ok)throw new Error('HTTP '+response.status);
        const data=await response.json();
        const ts=Number(data.feed_timestamp||data.fetched_at||0);
        const age=ts?Date.now()/1000-ts:Infinity;
        return {id,name:cfg.name,label:data.error?'Feed issue':!data.fetched_at?'Waiting for GPS':age>120?'Stale GPS':'Fresh GPS',
          cls:data.error||age>120?'stale':'good'};
      }catch(_){return {id,name:cfg.name,label:'Not reachable',cls:'stale'};}
      finally{clearTimeout(timer);}
    }));
    node.replaceChildren();
    for(const info of results){
      const row=document.createElement('div');row.className='health-item';
      const name=document.createElement('span');name.className='health-label';name.textContent=info.name;
      const status=document.createElement('span');status.className='health-state '+info.cls;status.textContent=info.label;
      row.append(name,status);node.append(row);
    }
  }
  function applyPreferences() {
    document.documentElement.dataset.density = state.density;
    document.documentElement.dataset.markerSize = state.markerSize;
    document.documentElement.dataset.routeColors = String(state.routeColors);
    $('densitySelect').value = state.density;
    $('markerSizeSelect').value = state.markerSize;
    $('routeColorsToggle').checked = state.routeColors;
    $('lowBandwidthToggle').checked = state.lowBandwidth;
    $('sortSelect').value=state.sortBy;
    $('serviceFilter').value=state.serviceFilter;
    $('modelSelect').value=state.modelFilter;
    lastListSignature = ''; renderList(); renderMap();
  }
  function savePreferences() {
    try {localStorage.setItem('bct_ui_preferences_v28', JSON.stringify({
      density:state.density, markerSize:state.markerSize, routeColors:state.routeColors,
      groupMode:state.groupMode,sortBy:state.sortBy,
      serviceFilter:state.serviceFilter,modelFilter:state.modelFilter,lowBandwidth:state.lowBandwidth
    }));} catch (_) {}
  }
  function switchSystem(value) {
    if (!Object.hasOwn(SYSTEMS, value) || value === state.system) return;
    saveMapView();
    if (state.selected) leaveDetails();
    state.system = value; state.systemGeneration++;
    $('sharedVehicleNotice').hidden=true;
    if(state.sharedFocusMarker){state.sharedFocusMarker.remove();state.sharedFocusMarker=null;}
    if(state.pendingShare?.system!==value)state.pendingShare=null;
    state.following=false; state.requestPending=false;
    state.vehicles=[]; state.data=null; state.clientError=null; state.restoredCache=false;
    state.expandedGroups.clear(); state.needsListRefresh=false;
    state.userLocation=null;state.pendingNearestSort=false;clearLocationMarker();
    if (state.nearbyStopMarker) {state.nearbyStopMarker.remove();state.nearbyStopMarker=null;}
    $('nearbySection').hidden=true;$('locateButton').setAttribute('aria-pressed','false');
    state.nearbyStopToken++;
    state.boardSerial++;state.boardPending=false;state.boardQueued=false;state.boardPayload=null;state.boardAt=null;state.boardLastFetch=0;
    state.markers.forEach(r=>r.marker.remove()); state.markers.clear();
    if (state.routeLayer) state.routeLayer.clearLayers();
    state.routeTrip=null; state.routeDetail=null; state.routeMetadataStamp=null;
    state.arrivalsTrip=null; state.arrivalsLoadingTrip=null; state.arrivalsPending=false;
    state.arrivals=new Map(); state.arrivalStatus='unavailable';
    lastListSignature=''; lastListStatus='';
    try { localStorage.setItem('bct_current_system',value); state.query=localStorage.getItem(filterKey()) || ''; }
    catch (_) {state.query='';}
    $('systemSelect').value=value;
    $('regionName').textContent=SYSTEMS[value].name.toUpperCase();
    $('alertsMainIntro').textContent=value==='chilliwack'?'Alert feed is shared with the wider Fraser Valley.':'Service alerts load only when this panel is opened.';
    $('routeSearch').placeholder = 'Route, fleet #, or model';
    document.title=`${SYSTEMS[value].name} · Bus Radar`;
    readFavorites(); renderFavorites(); renderQuickRoutes(); setFilter(state.query);
    if($('alertsMainSection').open)loadAlerts('alertsMainContent');
    if (state.map) { const view=restoredView(); state.map.setView([view.lat,view.lon],view.zoom,{animate:false}); }
    renderStatus();
    try {
      const cached=JSON.parse(sessionStorage.getItem(snapshotKey()) || 'null');
      if(cached && Date.now()-cached.savedAt<120000 && cached.data?.system===state.system) applyData(cached.data,true);
    } catch (_) {}
    loadVehicles();
    if (boardOpen()) refreshNearbyBoard(true);
    if (mobile()) setSidebar(false);
  }
  function bindControls() {
    $('activityToggle').addEventListener('click',()=>{
      state.activityVisible=!state.activityVisible;
      state.activityRequestSerial++;
      state.activityLoading=false;
      $('activityToggle').setAttribute('aria-pressed', String(state.activityVisible));
      $('activityToggle').textContent=state.activityVisible?'Hide activity timeline':'Show activity timeline';
      if (state.activityVisible) {loadActivity();}
      else {
        $('activityEvents').hidden=true;
        $('activityRefresh').hidden=true;
        $('activityStatus').textContent='Activity hidden. Tap Show activity timeline to reload.';
        if(state.activityFocusMarker && state.map) state.activityFocusMarker.remove();
        state.activityFocusMarker=null;
      }
    });
    $('activityWindow').addEventListener('change',(event)=>{
      const duration=Number(event.target.value);
      state.activityWindow=[60,180,720,1440].includes(duration)?duration:180;
      state.activityRequestSerial++;state.activityLoading=false;
      if(state.activityVisible)loadActivity();
    });
    $('activityRefresh').addEventListener('click',()=>{state.activityRequestSerial++;state.activityLoading=false;loadActivity();});
    $('historyToggle').addEventListener('click',()=>{
      state.historyVisible=!state.historyVisible;
      $('historyToggle').textContent=state.historyVisible?'Hide movement trail':'Show movement trail';
      $('historyToggle').setAttribute('aria-pressed',String(state.historyVisible));
      if(state.historyVisible){$('historyScrubArea').hidden=true;loadHistory();}
      else {state.historyRequestSerial++;state.historyLoading=false;state.historyPoints=[];state.historyScrubMarker=null;
        if(state.historyLayer)state.historyLayer.clearLayers();
        $('historyStatus').textContent='Trail hidden. Tap Show movement trail to reload.';
        $('historyScrubArea').hidden=true;}
    });
    $('historyWindow').addEventListener('change',ev=>{
      state.historyWindow=[15,30,60].includes(Number(ev.target.value))?Number(ev.target.value):30;
      state.historyLastFetch=0;
      if(state.historyVisible){state.historyRequestSerial++;state.historyLoading=false;state.historyPoints=[];if(state.historyLayer)state.historyLayer.clearLayers();loadHistory();}
    });
    $('historyScrub').addEventListener('input',ev=>highlightHistoryPoint(Number(ev.target.value)));
    $('routeSearch').addEventListener('input', (event) => setFilter(event.target.value));
    $('clearSearch').addEventListener('click', () => {setFilter('');$('routeSearch').focus();});
    $('systemSelect').addEventListener('change', (ev) => switchSystem(ev.target.value));
    $('groupMode').addEventListener('change', (ev) => {
      state.groupMode=ev.target.value; state.expandedGroups.clear(); lastListSignature='';
      savePreferences(); renderList();
    });
    $('densitySelect').addEventListener('change', (ev) => {
      state.density=ev.target.value; savePreferences(); applyPreferences();
    });
    $('markerSizeSelect').addEventListener('change', (ev) => {
      state.markerSize=ev.target.value; savePreferences(); applyPreferences();
    });
    $('lowBandwidthToggle').addEventListener('change', (ev) => {
      state.lowBandwidth=ev.target.checked;savePreferences();renderStatus();
    });
    $('sortSelect').addEventListener('change',(ev)=>{
      if(ev.target.value==='nearest'&&!state.userLocation){state.pendingNearestSort=true;$('sortSelect').value='route';startLocation();return;}
      state.sortBy=ev.target.value;savePreferences();lastListSignature='';renderList();
    });
    $('serviceFilter').addEventListener('change',(ev)=>{
      state.serviceFilter=ev.target.value;savePreferences();lastListSignature='';renderList();renderMap();
    });
    $('expandAll').addEventListener('click',()=>{
      for (const v of filteredVehicles()) state.expandedGroups.add('route:'+String(v.route || '?'));
      if (state.groupMode==='direction') for (const v of filteredVehicles())
        state.expandedGroups.add(`route:${String(v.route||'?')}|${(v.headsign||'Direction unavailable').trim()}`);
      lastListSignature='';renderList();
    });
    $('collapseAll').addEventListener('click',()=>{state.expandedGroups.clear();lastListSignature='';renderList();});
    $('favoriteRouteButton').addEventListener('click',()=>{
      const vehicle=state.vehicles.find(v=>v.id===state.selected);
      if(vehicle?.route)toggleFavoriteRoute(String(vehicle.route));
    });
    $('favoriteBusButton').addEventListener('click',()=>toggleFavoriteBus(state.vehicles.find(v=>v.id===state.selected)));
    $('shareVehicleButton').addEventListener('click',shareSelectedBus);
    $('alertsMainSection').addEventListener('toggle',ev=>{if(ev.target.open)loadAlerts('alertsMainContent');});
    $('alertsDetailSection').addEventListener('toggle',ev=>{if(ev.target.open){const v=state.vehicles.find(v=>v.id===state.selected);if(v)loadAlerts('alertsDetailContent',v);}});
    $('nearbyBoard').addEventListener('toggle',()=>{if(boardOpen()){if(mobile())setSidebar(false);refreshNearbyBoard(true);}});
    $('boardRefresh').addEventListener('click',()=>refreshNearbyBoard(true));
    $('locateButton').addEventListener('click',startLocation);
    $('locationStop').addEventListener('click',stopLocation);
    $('checkSystemHealth').addEventListener('click',checkSystemHealth);
    $('locationCancel').addEventListener('click',()=>{state.pendingNearestSort=false;$('locationConsent').close();});
    $('locationAgree').addEventListener('click',()=>{$('locationConsent').close();requestLocation();});
    $('modelSelect').addEventListener('change', (ev) => {
      state.modelFilter = ['all', ...MODEL_ASSETS].includes(ev.target.value) ? ev.target.value : 'all';
      savePreferences(); lastListSignature = ''; renderList(); renderMap();
    });
    $('detailArtworkVariant').addEventListener('change', (ev) => {
      const vehicle = state.vehicles.find(v => v.id === state.selected);
      if (!vehicle) return;
      const options = BUS_ART[vehicle.model_key] || [];
      if (vehicle.model_key === 'xn40' && ev.target.value === 'auto') {
        delete artChoices[artKey(vehicle)]; // Re-enable fleet-number selection.
      } else {
        if (!options.some(v => v.id === ev.target.value)) return;
        artChoices[artKey(vehicle)] = ev.target.value;
      }
      try { localStorage.setItem('bct_bus_art_variants_v30', JSON.stringify(artChoices)); } catch (_) {}
      updateDetails();
    });
    $('routeColorsToggle').addEventListener('change', (ev) => {
      state.routeColors=ev.target.checked; savePreferences(); applyPreferences();
      if (state.selected) {
        const vehicle=state.vehicles.find(v=>v.id===state.selected);
        if (vehicle) loadSelectedRoute(vehicle);
      }
    });
    $('detailBack').addEventListener('click', leaveDetails);
    $('recenterButton').addEventListener('click', () => {
      const v = state.vehicles.find((p) => p.id === state.selected);
      if (v && state.map) state.map.setView([v.lat,v.lon], Math.max(state.map.getZoom(), 13),{animate:false});
    });
    $('followButton').addEventListener('click', () => {state.following = !state.following;updateDetails();});
    $('themeToggle').addEventListener('click', () => setTheme(state.theme === 'classic' ? 'dark' : 'classic'));
    $('liteToggle').addEventListener('click', () => setLite(!state.lite));
    $('mobileOpen').addEventListener('click', () => {setSheetMode('half'); setSidebar(true);});
    let dragStart = null;
    const handle = $('sheetHandle');
    handle.addEventListener('pointerdown', (event) => {
      dragStart = {y:event.clientY, time:Date.now()};
      if (handle.setPointerCapture) handle.setPointerCapture(event.pointerId);
    });
    handle.addEventListener('pointerup', (event) => {
      if (!dragStart) return;
      const delta = event.clientY - dragStart.y;
      dragStart = null;
      if (delta < -35) setSheetMode('full');
      else if (delta > 70) setSidebar(false);
      else if (delta > 35) setSheetMode('half');
      else setSheetMode(state.sheetMode === 'full' ? 'half' : 'full');
    });
    handle.addEventListener('pointercancel', () => {dragStart = null;});
    $('resetView').addEventListener('click', () => state.map?.setView([currentView().lat,currentView().lon],currentView().zoom,{animate:false}));
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
    try {
      const savedSystem=localStorage.getItem('bct_current_system');
      if (savedSystem && Object.hasOwn(SYSTEMS,savedSystem)) state.system=savedSystem;
    } catch (_) {}
    const share=readShareQuery();
    if(share){state.system=share.system;state.pendingShare=share;}
    $('systemSelect').value=state.system;
    $('regionName').textContent=SYSTEMS[state.system].name.toUpperCase();
    $('alertsMainIntro').textContent=state.system==='chilliwack'?'Alert feed is shared with the wider Fraser Valley.':'Service alerts load only when this panel is opened.';
    $('routeSearch').placeholder = 'Route, fleet #, or model';
    document.title=`${SYSTEMS[state.system].name} · Bus Radar`;
    try {
      const prefs=JSON.parse(localStorage.getItem('bct_ui_preferences_v28') || localStorage.getItem('bct_ui_preferences_v27') || '{}');
      if (['compact','comfortable'].includes(prefs.density)) state.density=prefs.density;
      if (['small','normal','large'].includes(prefs.markerSize)) state.markerSize=prefs.markerSize;
      if (typeof prefs.routeColors==='boolean') state.routeColors=prefs.routeColors;
      if (['none','route','direction'].includes(prefs.groupMode)) state.groupMode=prefs.groupMode;
      if (['route','recent','nearest'].includes(prefs.sortBy)) state.sortBy=prefs.sortBy;
      if (['all','near','off','stale','unknown'].includes(prefs.serviceFilter)) state.serviceFilter=prefs.serviceFilter;
      const oldNovaFilter = {nova2:'nova_gen2',nova3:'nova_gen3'};
      const normalizedModelFilter = oldNovaFilter[prefs.modelFilter] || prefs.modelFilter;
      if (['all',...MODEL_ASSETS].includes(normalizedModelFilter)) state.modelFilter=normalizedModelFilter;
      if (typeof prefs.lowBandwidth==='boolean') state.lowBandwidth=prefs.lowBandwidth;
      // Location consent is not persisted; never imply a nearest sort without GPS.
      if(state.sortBy==='nearest')state.sortBy='route';
      $('groupMode').value=state.groupMode;
    } catch (_) {}
    try { setTheme(localStorage.getItem('bct_theme') || 'classic', false); } catch (_) {setTheme('classic',false);}
    try {state.query=(localStorage.getItem(filterKey()) || (state.system==='victoria' ? localStorage.getItem('bct_route_filter') : '') || '').slice(0,12);} catch (_) {}
    try {state.lite=localStorage.getItem('bct_mobile_lite')===null ? mobile() : localStorage.getItem('bct_mobile_lite')==='true';} catch (_) {state.lite=mobile();}
    setLite(state.lite, false);
    readFavorites(); renderFavorites();
    renderQuickRoutes(); bindControls(); initMap(); setFilter(state.query); applyPreferences(); updateMobileOpenLabel();
    try {
      const cached = JSON.parse(sessionStorage.getItem(snapshotKey()) || 'null');
      if (cached && Date.now()-cached.savedAt < 120000 && cached.data) applyData(cached.data,true);
    } catch (_) {}
    loadVehicles();
    // On slower phones, avoid repeatedly checking the same server cache.
    // This doesn't slow BC Transit's actual upstream feed or initial page load.
    setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      const interval = state.lowBandwidth ? 25000 : mobile() ? 10000 : CLIENT_REFRESH_MS;
      if (Date.now()-state.lastClientPollAt >= interval) {
        state.lastClientPollAt = Date.now();loadVehicles();
      }
    }, CLIENT_REFRESH_MS);
    setInterval(() => { if (document.visibilityState === 'visible') renderStatus(); }, 5000);
    setInterval(() => {if(document.visibilityState==='visible' && boardOpen())refreshNearbyBoard();},45000);
    // Visual-only cycling: does not request extra GPS, map tiles, or history.
    setInterval(refreshUnverifiedNovaArtwork, 500);
    setInterval(() => { if (document.visibilityState === 'visible' && state.selected && (!state.lowBandwidth || Date.now()-state.lastArrivalRefreshAt>=60000)) refreshSelectedArrivals(); }, 20000);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') { loadVehicles(); if (state.selected) refreshSelectedArrivals(); }
    });
  }
  init();
})();
