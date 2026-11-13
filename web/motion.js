/* Bus Radar V3.4: visual-only GPS smoothing. Raw feed positions never change. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.BusRadarMotion = api;
})(typeof window !== 'undefined' ? window : null, function () {
  'use strict';
  const R = Math.PI / 180;
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const finite = v => Number.isFinite(Number(v));
  const distance = (a, b) => {
    if (!a || !b) return Infinity;
    const dLat=(b[0]-a[0])*R, dLon=(b[1]-a[1])*R;
    const h=Math.sin(dLat/2)**2 + Math.cos(a[0]*R)*Math.cos(b[0]*R)*Math.sin(dLon/2)**2;
    return 12742000*Math.asin(Math.min(1,Math.sqrt(h)));
  };
  const forward = (p, bearing, metres) => {
    const az=bearing*R;
    return [p[0]+Math.cos(az)*metres/111320,
      p[1]+Math.sin(az)*metres/(111320*Math.max(0.15,Math.cos(p[0]*R)))];
  };
  const ease = t => t*t*(3-2*t);
  class Tracker {
    constructor(system) { this.system=system;this.fix=null;this.blend=null; }
    ingest(vehicle, now=Date.now(), system=this.system) {
      if (!vehicle || !finite(vehicle.lat) || !finite(vehicle.lon) ||
          Math.abs(Number(vehicle.lat))>90 || Math.abs(Number(vehicle.lon))>180 ||
          !finite(vehicle.timestamp) || Number(vehicle.timestamp)<=0) return false;
      if (system !== this.system) {this.system=system;this.fix=null;this.blend=null;}
      const stamp=Number(vehicle.timestamp);
      // Ignore repeated fixes AND delayed/out-of-order upstream snapshots.
      if (this.fix && stamp <= this.fix.timestamp) return false;
      const before=this.sample(now,true);
      const next={point:[Number(vehicle.lat),Number(vehicle.lon)],timestamp:stamp,
        speed:Number(vehicle.speed_mps),bearing:Number(vehicle.bearing),receivedAt:now,
        eligible:(now/1000-stamp>=-15 && now/1000-stamp<=35)};
      this.fix=next;
      if (!before || !before.point || distance(before.point,next.point)>250 ||
          (this.blend && stamp - (this.blend.sourceStamp || 0)>180)) {
        this.blend=null; // A real discontinuity is not animated across town.
      } else {
        const gap=distance(before.point,next.point);
        this.blend={from:before.point,start:now,duration:clamp(1100+gap*40,1350,3600),sourceStamp:stamp};
      }
      return true;
    }
    sample(now=Date.now(), smooth=true) {
      const fix=this.fix;
      if (!fix)return null;
      const age=Math.max(0,now-fix.receivedAt);
      let metres=0;
      if (smooth && fix.eligible && finite(fix.bearing) && fix.bearing>=0 && fix.bearing<=360 &&
          finite(fix.speed) && fix.speed>=0.75 && fix.speed<=18) {
        metres=Math.min(30,Math.min(age/1000,8)*fix.speed*0.65);
      }
      let point=metres>0?forward(fix.point,fix.bearing,metres):fix.point;
      if (smooth && this.blend) {
        const u=clamp((now-this.blend.start)/this.blend.duration,0,1);
        const a=ease(u);
        point=[this.blend.from[0]+(point[0]-this.blend.from[0])*a,
          this.blend.from[1]+(point[1]-this.blend.from[1])*a];
        if(u>=1)this.blend=null;
      }
      return {point,sourceTimestamp:fix.timestamp,estimated:metres>0,
        held:metres>0 && age>=8000,reconciling:!!this.blend,metres};
    }
  }
  return {Tracker,distance,forward};
});
