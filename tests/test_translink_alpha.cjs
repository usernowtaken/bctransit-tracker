const assert=require('node:assert/strict'), fs=require('fs'),path=require('path');
const web=path.join(__dirname,'..','web');const source=fs.readFileSync(path.join(web,'app.js'),'utf8');const html=fs.readFileSync(path.join(web,'index.html'),'utf8');
const state={system:'vancouver'};const choose=new Function('state','BUS_ART','artChoices','localStorage',source.slice(source.indexOf('  const artKey ='),source.indexOf('  const currentView ='))+'\nreturn busArtVariant;')(state,{}, {},{});
for(const model_key of ['tl_xde60','tl_e40','tl_lfs','generic','nova3'])assert.equal(choose({model_key,fleet_number:'18024'}),null);
assert.match(html,/value="vancouver">Metro Vancouver \(Alpha\)/);assert.match(html,/id="tlBudget"/);assert.match(html,/permission of TransLink/);
const shareCode=source.slice(source.indexOf('  function vehicleShareLink('),source.indexOf('  async function shareSelectedBus('));
const share=new Function('state','location','URL',shareCode+'return vehicleShareLink;')(state,{href:'https://example.org/'},URL);
assert.equal(new URL(share({id:'18024',fleet_number:'18024'})).searchParams.get('fleet'),'18024');
console.log('Vancouver placeholder, quota UI and five-digit sharing PASS');
