import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
const source=fs.readFileSync(new URL('../js/guest-application.js',import.meta.url),'utf8');
function harness({ok=true,valid=true,bot=false,reject=false}={}) {
 let submit,requests=0; const events=[],button={},status={},success={style:{},scrollIntoView(){}};
 const form={style:{},checkValidity:()=>valid,addEventListener:(_,fn)=>submit=fn,querySelector:()=>button};
 class FD extends Map {constructor(){super([['form-name','guest-application'],['email','private@example.test'],['topics','private topic'],['bot-field',bot?'spam':'']]);}}
 vm.runInNewContext(source,{window:{fetch:true,gtag:(...args)=>events.push(args)},document:{getElementById:id=>({'guest-apply-form':form,'guest-apply-status':status,'apply-success':success})[id]},FormData:FD,URLSearchParams,fetch:async()=>{requests++;if(reject)throw Error('offline');return {ok};}});
 return {submit:()=>submit({preventDefault(){}}),events,button,status,success,form,get requests(){return requests;}};
}
test('only successful Netlify acceptance emits once without personal fields',async()=>{
 const h=harness();h.submit();h.submit();await new Promise(r=>setImmediate(r));h.submit();
 assert.equal(h.requests,1);assert.equal(h.events.length,1);assert.equal(h.events[0][1],'guest_application_submit');
 assert(!JSON.stringify(h.events).includes('private'));assert.equal(h.success.style.display,'block');assert.equal(h.form.style.display,'none');
});
test('invalid, honeypot, rejected and failed requests never count as applications',async()=>{
 for(const config of [{valid:false},{bot:true},{ok:false},{reject:true}]){
  const h=harness(config);assert.equal(h.events.length,0);h.submit();await new Promise(r=>setImmediate(r));assert.equal(h.events.length,0);
  if(config.ok===false||config.reject){assert.equal(h.button.disabled,false);h.submit();await new Promise(r=>setImmediate(r));assert.equal(h.requests,2);}
  else assert.equal(h.requests,0);
 }
});
