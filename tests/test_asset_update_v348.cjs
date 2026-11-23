// V3.4.11 asset mapping and transparent gallery checks.
const fs=require('fs'), path=require('path'), assert=require('assert');
const root=path.join(__dirname,'..');
const src=fs.readFileSync(path.join(root,'web','app.js'),'utf8');
const gallery=fs.readFileSync(path.join(root,'web','fleet-gallery.html'),'utf8');
const state={system:'kelowna'};
const code=src.slice(src.indexOf('  const artKey ='),src.indexOf('  const currentView ='));
const BUS_ART={
  nova2:[{id:'nova2'}], nova3:[{id:'nova3'}], nova_lfse:[{id:'nova_lfse'}],
  vicinity30:[{id:'vicinity30'}], vicinity30cng:[{id:'vicinity30'}],
  vicinity35:[{id:'vicinity35'}], vicinity_2013:[{id:'vicinity35'}],
  light_duty:[{id:'handydart_old'},{id:'handydart_new'}]
};
const fn=new Function('state','BUS_ART','artChoices','localStorage',code+'\nreturn busArtVariant;');
const choose=fn(state,BUS_ART,{}, {getItem:()=>null});
assert.strictEqual(choose({model_key:'vicinity30cng',fleet_number:'4232'}).id,'vicinity30');
assert.strictEqual(choose({model_key:'vicinity35',fleet_number:'4403'}).id,'vicinity35');
assert.strictEqual(choose({model_key:'vicinity_2013',fleet_number:'3007'}).id,'vicinity35');
assert.strictEqual(choose({model_key:'light_duty',fleet_number:'2922'}).id,'handydart_new');
assert.strictEqual(choose({model_key:'light_duty',fleet_number:'2876'}).id,'handydart_old');
state.system='cowichan';
assert.strictEqual(choose({model_key:'light_duty',fleet_number:'2842'}).id,'handydart_new');
assert.strictEqual(choose({model_key:'light_duty',fleet_number:'2819'}).id,'handydart_old');
assert(gallery.includes('/buses/vicinity35.png'));
assert(gallery.includes('/buses/handydart_old.png'));
assert(gallery.includes('/buses/handydart_new.png'));
console.log('V3.4.11 asset update mapping PASS');
