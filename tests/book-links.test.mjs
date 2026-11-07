import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../js/book-links.js',import.meta.url),'utf8');
test('book referrals are measured as clicks only on production without blocking navigation',()=>{
 for(const host of ['localhost','deploy-preview.example.netlify.app','signalroompodcast.com']){
  let click;const events=[];
  vm.runInNewContext(source,{location:{hostname:host},document:{addEventListener:(name,fn)=>{assert.equal(name,'click');click=fn;}},window:{gtag:(...args)=>events.push(args)}});
  if(host!=='signalroompodcast.com'){assert.equal(click,undefined);continue;}
  click({target:{closest:()=>null}});assert.equal(events.length,0);
  click({target:{closest:()=>({getAttribute:()=> 'homepage'})}});
  assert.equal(events.length,1);assert.equal(events[0][1],'book_referral_click');
  assert.equal(events[0][2].destination,'chrisjhutchins.com/book/');
  assert.equal(events[0][2].placement,'homepage');
  assert(!JSON.stringify(events).includes('purchase'));
 }
});
