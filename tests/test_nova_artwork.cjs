/* Focused no-browser test of existing NovaBus artwork resolution logic. */
const fs = require('fs');
const assert = require('assert');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8');
const start = src.indexOf('  const artKey =');
const end = src.indexOf('  const currentView =');
assert(start >= 0 && end > start);
const chunk = src.slice(start,end);
const state = {system:'victoria'};
const BUS_ART = {
  enviro500mmc:[{id:'enviro500mmc_classic'},{id:'enviro500mmc_green'}],
  nova2:[{id:'nova2',name:'Gen 2 original drawing'}],
  nova3:[{id:'nova3',name:'Gen 3 original drawing'}],
  xn40:[{id:'xn40_classic'},{id:'xn40_greenrear'},{id:'xn40_cng'}]
};
const localStorage = {getItem:()=>null};
const artChoices = {};
const funcs = new Function('state','BUS_ART','artChoices','localStorage', chunk + '\nreturn {novaRearStyle,busArtVariant,novaCycleStart,NOVA_UNKNOWN_CYCLE_MS,isUnverifiedNova};')(state,BUS_ART,artChoices,localStorage);
const bus = (number,model_key='nova2',extra={}) => ({id:'bus-'+number,fleet_number:String(number),model_key,...extra});
assert.strictEqual(funcs.novaRearStyle(bus(9426)),'raised');
assert.strictEqual(funcs.busArtVariant(bus(9426)).id,'nova3');
assert.strictEqual(funcs.busArtVariant(bus(9332)).id,'nova2');
assert.strictEqual(funcs.novaRearStyle(bus(9332)),'unknown');
assert.strictEqual(funcs.isUnverifiedNova(bus(9332)),true);
// Unknown buses alternate independently; verified buses never participate.
funcs.novaCycleStart.set('victoria:9332', Date.now() - funcs.NOVA_UNKNOWN_CYCLE_MS - 100);
assert.strictEqual(funcs.busArtVariant(bus(9332)).id,'nova3');
assert.strictEqual(funcs.busArtVariant(bus(9426)).id,'nova3');
assert.strictEqual(funcs.isUnverifiedNova(bus(9426)),false);
assert.strictEqual(funcs.busArtVariant(bus(9340)).id,'nova2');
assert.strictEqual(funcs.isUnverifiedNova(bus(9340)),true);
assert.strictEqual(funcs.busArtVariant(bus(9287)).id,'nova2');
assert.strictEqual(funcs.busArtVariant(bus(9434,'nova3',{nova_body_variant:'smart'})).id,'nova3');
assert.strictEqual(funcs.busArtVariant(bus(9532,'enviro500mmc')).id,'enviro500mmc_classic');
assert.strictEqual(funcs.busArtVariant(bus(9550,'enviro500mmc')).id,'enviro500mmc_classic');
assert.strictEqual(funcs.busArtVariant(bus(9551,'enviro500mmc')).id,'enviro500mmc_green');
assert.strictEqual(funcs.busArtVariant(bus(9589,'enviro500mmc')).id,'enviro500mmc_green');
assert.strictEqual(funcs.busArtVariant(bus(9426)).id,'nova3','confirmed fleet remains fixed');
state.system='kelowna';
assert.strictEqual(funcs.busArtVariant(bus(9426)).id,'nova2','Victoria mapping must not apply elsewhere');
console.log('Nova per-fleet artwork logic PASS');
