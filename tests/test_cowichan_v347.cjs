// V4.0 Alpha: Cowichan picker, Kelowna-only Gen 4 image, and new regional artwork.
const fs=require('fs'),path=require('path'),assert=require('assert');
const root=path.join(__dirname,'..');
const src=fs.readFileSync(path.join(root,'web/app.js'),'utf8');
const html=fs.readFileSync(path.join(root,'web/index.html'),'utf8');
const state={system:'kelowna'};
const code=src.slice(src.indexOf('  const artKey ='),src.indexOf('  const currentView ='));
const BUS_ART={nova2:[{id:'nova2'}],nova3:[{id:'nova3'}],vicinity30:[{id:'vicinity30'}],vicinity30cng:[{id:'vicinity30'}],vicinity35:[{id:'vicinity35'}],vicinity_2013:[{id:'vicinity35'}],light_duty:[{id:'handydart_old'},{id:'handydart_new'}],nova_lfse:[{id:'nova_lfse'}]};
const fn=new Function('state','BUS_ART','artChoices','localStorage',code+'\nreturn busArtVariant;');
const choose=fn(state,BUS_ART,{}, {getItem:()=>null});
for(const num of ['6000','6017','6029','9435','9451','9486']) {
  const r=choose({model_key:'nova3',nova_generation:4,fleet_number:num});
  assert.strictEqual(r.id,'nova3',`Kelowna Gen 4 ${num}`);
  assert.match(r.name,/Gen 3 reference/);
}
state.system='cowichan';
assert.strictEqual(choose({model_key:'nova3',nova_generation:4,fleet_number:'9451'}).id,'nova3');
assert.strictEqual(choose({model_key:'vicinity35',fleet_number:'4471'}).id,'vicinity35');
assert.strictEqual(choose({model_key:'light_duty',fleet_number:'2842'}).id,'handydart_new');
assert.strictEqual(choose({model_key:'vicinity30',fleet_number:'4019'}).id,'vicinity30');
assert.strictEqual(choose({model_key:'nova2',nova_generation:2,fleet_number:'9300'}).id,'nova2');
state.system='chilliwack';
assert.strictEqual(choose({model_key:'nova3',nova_generation:4,fleet_number:'9451'}).id,'nova3');
const select=(html.match(/<select id="systemSelect"[\s\S]*?<\/select>/)||[])[0];
assert.match(select,/value="cowichan">Cowichan Valley/);
assert.match(src,/cowichan: \{name:'Cowichan Valley'/);
const sw=fs.readFileSync(path.join(root,'web/sw.js'),'utf8');
assert(sw.includes("victoria-bus-radar-shell-v4.0-alpha"));
console.log('V4.0 Alpha Cowichan and Kelowna Gen 4 regional model images PASS');
