const fs = require('fs'), path = require('path'), assert = require('assert');
const root = path.join(__dirname,'..');
const src=fs.readFileSync(path.join(root,'web','app.js'),'utf8');
const state={system:'kelowna'};
const code=src.slice(src.indexOf('  const artKey ='),src.indexOf('  const currentView ='));
const BUS_ART={nova2:[{id:'nova2'}],nova3:[{id:'nova3'}]};
const choose = new Function('state','BUS_ART','artChoices','localStorage',code+'\nreturn busArtVariant;')(state,BUS_ART,{}, {getItem:()=>null});
for(const system of ['kelowna','chilliwack','cowichan']) {
  state.system=system;
  for(const fleet of ['9435','9447','9451','9486']) {
    const art=choose({model_key:'nova3', nova_generation:4, fleet_number:fleet});
    assert.strictEqual(art?.id,'nova3', `${system} ${fleet}`);
    assert.match(art?.name||'',/Gen 3 reference/);
  }
}
state.system='victoria';
assert.strictEqual(choose({model_key:'nova3',nova_generation:4,fleet_number:'9451'}).id,'nova3');
state.system='chilliwack';
assert.strictEqual(choose({model_key:'generic',fleet_number:'9999'}),null);
const html=fs.readFileSync(path.join(root,'web','index.html'),'utf8');
const sw=fs.readFileSync(path.join(root,'web','sw.js'),'utf8');
const gallery=fs.readFileSync(path.join(root,'web','fleet-gallery.html'),'utf8');
assert(html.includes('V4.0 Alpha'));
assert(html.includes('/app.js?v=4.0-alpha3'));
assert(sw.includes('victoria-bus-radar-shell-v4.0-alpha3'));
assert(gallery.includes('Kelowna / Chilliwack / Cowichan'));
assert(!gallery.includes('Chilliwack / Cowichan</strong> — PLACEHOLDER'));
console.log('V4.0 Alpha regional Gen 4 reference-art mapping and cache revision PASS');
