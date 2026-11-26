"""Synthetic static/HTTP integration test. Requires requirements.txt; no live requests."""
import tempfile, pathlib, time, os, json, threading, urllib.request, zipfile, io, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
from unittest.mock import patch
from datetime import datetime
buf=io.BytesIO(); today=datetime.now(app.TIMEZONE).strftime('%Y%m%d')
with zipfile.ZipFile(buf,'w') as z:
 z.writestr('routes.txt','route_id,route_short_name,route_long_name,route_type\nbus,99,B Line,3\ntrain,Expo,Expo Line,1\ntrolley,20,Victoria,11\n')
 z.writestr('trips.txt','route_id,service_id,trip_id,trip_headsign,block_id,shape_id\nbus,s,trip,UBC,b,s1\ntrain,s,rail,Waterfront,,s2\ntrolley,s,trolleytrip,Downtown,b2,s3\n')
 z.writestr('calendar_dates.txt',f'service_id,date,exception_type\ns,{today},1\n')
 z.writestr('stops.txt','stop_id,stop_name,stop_lat,stop_lon\na,Stop A,49.2,-123.1\nb,Stop B,49.22,-123.11\n')
 z.writestr('stop_times.txt','trip_id,arrival_time,departure_time,stop_id,stop_sequence\ntrip,12:00:00,12:00:00,a,1\ntrip,12:15:00,12:15:00,b,2\nrail,12:00:00,12:00:00,a,1\ntrolleytrip,12:00:00,12:00:00,a,1\n')
index=app.parse_static_gtfs(buf.getvalue(),bus_only=True); assert set(index['routes'])=={'bus','trolley'};assert 'rail' not in index['trips']
with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'TRANSLINK_BUDGET_DB':str(pathlib.Path(tmp)/'budget.db'),'TRANSLINK_API_KEY':'offline-test-only'}):
 tracker=app.Tracker('vancouver');tracker.update_index(index,persist=False)
 now=int(time.time());tracker.vehicles=[{'id':'a','descriptor_id':'18024','label':'V18024','lat':49.2,'lon':-123.1,'route_id':'bus','trip_id':'trip','timestamp':now,'timestamp_source':'vehicle'},{'id':'train','lat':49.2,'lon':-123.1,'route_id':'train','trip_id':'rail','timestamp':now}];tracker.fetched_at=now;tracker.feed_timestamp=now
 app.Handler.trackers={'vancouver':tracker}; server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
 base=f'http://127.0.0.1:{server.server_port}'
 def get(p):return json.load(urllib.request.urlopen(base+p))
 health=get('/api/health?system=vancouver');assert not tracker.translink.active();assert health['api_budget']['used']==0
 data=get('/api/vehicles?system=vancouver');assert tracker.translink.active();assert data['count']==1; assert data['vehicles'][0]['fleet_number']=='18024'; assert data['vehicles'][0]['route']=='99';assert 'offline-test-only' not in json.dumps(data)
 data2=get('/api/vehicles?system=vancouver&since='+str(data['revision']));assert data2['unchanged'] and 'api_budget' in data2
 assert get('/api/alerts?system=vancouver')['ready']==False;assert tracker.translink.status()['used']==0
 server.shutdown();server.server_close()
print('Vancouver static bus-only, snapshot, HTTP routing, no network on health/alerts, cache and credential isolation PASS')
