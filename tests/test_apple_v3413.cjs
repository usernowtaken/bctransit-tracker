const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm'),path=require('path');
const root=path.join(__dirname,'..','web');
const pwa=fs.readFileSync(path.join(root,'pwa.js'),'utf8');
function fixture({ua='',platform='',touch=0,standalone=false}={}){
 const elements={},listeners={},docListeners={};
 function element(){return {hidden:true,open:false,events:{},addEventListener(k,f){this.events[k]=f},showModal(){this.open=true},close(){this.open=false}}}
 for(const id of ['installButton','installHelpSection','installHelpButton','installHelp','installHelpClose','v34Settings'])elements[id]=element();
 const classes=new Set();
 const doc={getElementById:id=>elements[id],documentElement:{classList:{toggle(k,v){v?classes.add(k):classes.delete(k)}}},addEventListener(k,f){docListeners[k]=f}};
 const nav={userAgent:ua,platform,maxTouchPoints:touch,standalone};
 const window={matchMedia:()=>({matches:standalone,addEventListener(){}}),addEventListener(k,f){listeners[k]=f},isSecureContext:false};
 vm.runInNewContext(pwa,{navigator:nav,document:doc,window,console});return {elements,listeners,classes};
}
for(const device of [{ua:'iPhone'},{ua:'Macintosh',platform:'MacIntel',touch:5}]){
 const {elements:e,classes}=fixture(device);assert(classes.has('apple-touch'));assert(!e.installHelpSection.hidden);assert(!e.installButton.hidden);e.v34Settings.open=true;e.installHelpButton.events.click();assert(e.installHelp.open);assert(!e.v34Settings.open);e.installHelpClose.events.click();assert(!e.installHelp.open);
}
let {elements:e}=fixture({ua:'iPhone',standalone:true});assert(e.installButton.hidden&&e.installHelpSection.hidden);
const android=fixture({ua:'Android'});assert(android.elements.installButton.hidden);let prompted=false;android.listeners.beforeinstallprompt({preventDefault(){},prompt(){prompted=true}});assert(!android.elements.installButton.hidden);android.elements.installButton.events.click();assert(prompted);assert(android.elements.installButton.hidden);
const app=fs.readFileSync(path.join(root,'app.js'),'utf8');
const resume=app.slice(app.indexOf('    let lastResumeAt=0;'),app.indexOf('\n  }\n  init();'));
let now=10000,counts={gps:0,arrivals:0,board:0},events={},docEvents={};
const state={selected:'vehicle',lastClientPollAt:0};const document={visibilityState:'visible',addEventListener(k,f){docEvents[k]=f}};
vm.runInNewContext(resume,{document,window:{addEventListener(k,f){events[k]=f}},state,Date:{now:()=>now},queueViewportSync(){},renderStatus(){},loadVehicles(){counts.gps++},refreshSelectedArrivals(){counts.arrivals++},boardOpen:()=>true,refreshNearbyBoard(){counts.board++}});
docEvents.visibilitychange();events.pageshow({persisted:true});assert.deepEqual(counts,{gps:1,arrivals:1,board:1});assert.equal(state.lastClientPollAt,10000);now+=2000;events.online();assert.equal(counts.gps,2);document.visibilityState='hidden';events.online();assert.equal(counts.gps,2);
// Exercise the actual location-request function; stale success/error callbacks
// must not mutate a new system or request after its serial is invalidated.
const location=app.slice(app.indexOf('  function requestLocation(){'),app.indexOf('  // Route-first nearby board.'));
let callbacks=[];let el={hidden:true,textContent:''};const locState={system:'victoria',locationRequestSerial:0,locationRequestPending:false,selected:null};
const request=vm.runInNewContext(location+'\nrequestLocation',{state:locState,navigator:{geolocation:{getCurrentPosition(ok,err){callbacks.push({ok,err})}}},$:()=>el,setSidebar(){},leaveDetails(){}});
request();request();assert.equal(callbacks.length,1);locState.locationRequestSerial++;locState.locationRequestPending=false;locState.system='kelowna';request();assert.equal(callbacks.length,2);callbacks[0].err({code:1});assert(locState.locationRequestPending);callbacks[0].ok({coords:{latitude:48,longitude:-123}});assert(!locState.userLocation);callbacks[1].err({code:1});assert(!locState.locationRequestPending);assert.match(el.textContent,/permission denied/);
console.log('Apple install, standalone, Android prompt, resume and location race PASS');
