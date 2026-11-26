const assert=require('node:assert/strict'), fs=require('fs'),path=require('path');
const web=path.join(__dirname,'..','web');const source=fs.readFileSync(path.join(web,'app.js'),'utf8');const html=fs.readFileSync(path.join(web,'index.html'),'utf8');
const state={system:'vancouver'};
const artSource=source.slice(source.indexOf('  const BUS_ART = '),source.indexOf('  const artChoices = '));
const BUS_ART=new Function(artSource+';return BUS_ART;')();
const choose=new Function('state','BUS_ART','artChoices','localStorage',source.slice(source.indexOf('  const artKey ='),source.indexOf('  const currentView ='))+'\nreturn busArtVariant;')(state,BUS_ART, {},{});
for (const [model_key,fleet_art_id] of [['tl_xde60','tl_xde60_rapidbus'],['tl_xde60','tl_xde60'],['tl_e40','tl_e40'],['tl_lfs','tl_lfs_gen2'],['tl_lfs','tl_lfs_gen3'],['tl_lfs','tl_lfs_westvan'],['tl_xd40','tl_xd40_westvan']]) {
  assert.equal(choose({model_key,fleet_art_id}).id,fleet_art_id);
}
assert.equal(choose({model_key:'generic',fleet_art_id:'tl_e40'}),null);
assert.equal(choose({model_key:'tl_xe40',fleet_art_id:null}),null);
assert.equal(choose({model_key:'nova3',fleet_art_id:'nova3'}),null);
assert.equal(choose({model_key:'tl_lfs'}),null);
assert.match(html,/value="vancouver">Metro Vancouver \(Alpha\)/);assert.match(html,/id="tlBudget"/);assert.match(html,/permission of TransLink/);
const shareCode=source.slice(source.indexOf('  function vehicleShareLink('),source.indexOf('  async function shareSelectedBus('));
const share=new Function('state','location','URL',shareCode+'return vehicleShareLink;')(state,{href:'https://example.org/'},URL);
assert.equal(new URL(share({id:'18024',fleet_number:'18024'})).searchParams.get('fleet'),'18024');
console.log('Vancouver art, quota UI and five-digit sharing PASS');
