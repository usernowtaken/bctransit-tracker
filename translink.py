"""TransLink provider: shared demand-driven polling and durable request limits.
No credentials in URLs returned to clients, files, or exception messages.
"""
import os, sqlite3, time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError

STATIC_URL = 'https://gtfs-static.translink.ca/gtfs/google_transit.zip'
ENDPOINTS = {'vehicle':'gtfsposition','trip':'gtfsrealtime','alerts':'gtfsalerts'}
BASE = 'https://gtfsapi.translink.ca/v3/'

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

class RequestBudget:
    def __init__(self, path, limit=950):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.limit = max(1, int(limit))
        # Reserve independently for each endpoint, preventing trip/alert traffic
        # from consuming the vehicle budget. Rolling window is conservative.
        self.caps = {'vehicle':max(1,int(self.limit*.80)), 'trip':int(self.limit*.15), 'alerts':int(self.limit*.05)}
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS requests (ts REAL NOT NULL, kind TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS request_ts ON requests(ts)')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10)
        try:
            with db: yield db
        finally: db.close()
    def counts(self, now=None):
        now=time.time() if now is None else now
        with self.connect() as db:
            rows=db.execute('SELECT kind,count(*) FROM requests WHERE ts>? GROUP BY kind',(now-86400,)).fetchall()
        return {k:dict(rows).get(k,0) for k in ENDPOINTS}
    def reserve(self, kind, now=None):
        now=time.time() if now is None else now
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM requests WHERE ts<=?',(now-86400,))
            total, used=db.execute('SELECT count(*),coalesce(sum(kind=?),0) FROM requests',(kind,)).fetchone()
            if total>=self.limit or used>=self.caps[kind]: return False
            db.execute('INSERT INTO requests VALUES (?,?)',(now,kind))
            return True

class TransLink:
    def __init__(self, path, key=None, limit=None):
        self.key=(os.getenv('TRANSLINK_API_KEY','') if key is None else key).strip()
        self.budget=RequestBudget(path, limit if limit is not None else int(os.getenv('TRANSLINK_DAILY_BUDGET','950')))
        self.last_view=0.0
        self.lease_seconds=35
        self.last_try={k:-1e12 for k in ENDPOINTS}
        self.failures={k:0 for k in ENDPOINTS}
        self.retry_at={k:0.0 for k in ENDPOINTS}
        self.error=None
        self.blocked_until=0.0
        self.opener=build_opener(NoRedirect())
        self._status_cache=None
        self._status_at=0.0
    def touch(self): self.last_view=time.monotonic()
    def active(self): return bool(self.last_view and time.monotonic()-self.last_view<self.lease_seconds)
    def interval(self, counts=None):
        counts=self.budget.counts() if counts is None else counts
        fraction=counts['vehicle']/self.budget.caps['vehicle']
        base=max(15,int(os.getenv('TRANSLINK_GPS_SECONDS','20')))
        return max(base,90 if fraction>=.80 else 40 if fraction>=.50 else base)
    def status(self):
        now=time.monotonic()
        if self._status_cache is None or now-self._status_at>=5:
            counts=self.budget.counts(); self._status_at=now
            self._status_cache={'used':sum(counts.values()),'limit':self.budget.limit,'remaining':max(0,self.budget.limit-sum(counts.values())), 'by_feed':counts,'caps':self.budget.caps,'gps_seconds':self.interval(counts)}
        cached=self._status_cache
        if cached is None: return self.status()
        return {**cached,'configured':bool(self.key),'active':self.active(), 'blocked':time.time()<self.blocked_until}
    def fetch(self, kind, max_bytes):
        # All authenticated calls pass through this one gate, including failures.
        if not self.key or time.time()<self.blocked_until: return None
        now=time.monotonic()
        if now<self.retry_at[kind]: return None
        if not self.budget.reserve(kind): return None
        self._status_cache=None; self.last_try[kind]=now
        url=BASE+ENDPOINTS[kind]+'?'+urlencode({'apikey':self.key})
        try:
            req=Request(url,headers={'Accept':'application/octet-stream','User-Agent':'BusRadar/4.0-alpha'})
            with self.opener.open(req,timeout=12) as response:
                body=response.read(max_bytes+1)
                if len(body)>max_bytes: raise ValueError('Feed too large')
            self.failures[kind]=0; self.error=None
            return body
        except HTTPError as exc:
            code=exc.code
            # Auth failures and quota errors are not retried aggressively.
            if code in (401,403): self.blocked_until=time.time()+3600
            if code==429:
                try: retry=max(3600,int(exc.headers.get("Retry-After", "86400")))
                except (TypeError,ValueError,AttributeError): retry=86400
                self.blocked_until=time.time()+retry
            self.error=f'TransLink HTTP {code}'
        except Exception:
            self.error='TransLink feed request failed'
        self.failures[kind]+=1
        self.retry_at[kind]=now+min(900,60*2**min(self.failures[kind]-1,4))
        raise RuntimeError(self.error) from None
