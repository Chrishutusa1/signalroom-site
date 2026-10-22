import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createReviewHandler,hash} from '../netlify/lib/review-core.mjs';
class Store{
 values=new Map();n=0;
 async get(k){return structuredClone(this.values.get(k)?.data??null);}
 async getWithMetadata(k){return structuredClone(this.values.get(k)??null);}
 async setJSON(k,data,o={}){const prior=this.values.get(k);if(o.onlyIfNew&&prior||o.onlyIfMatch&&prior?.etag!==o.onlyIfMatch)return {modified:false};const etag=String(++this.n);this.values.set(k,{data:structuredClone(data),etag});return {modified:true,etag};}
 async delete(k){this.values.delete(k);}
}
async function fixture(){
 const state=new Store(),content=new Store(),codes=[];let now=1e12;
 await state.setJSON('settings/sharing',{audience:'anyone-with-link'});
 await state.setJSON('settings/publisher-owner',{enabled:true,email:'owner@example.com'});
 for(const id of ['publisher','sarah-matt-v02','ted-lindsley-v01']){
  await state.setJSON('grants/'+id,{enabled:true,emails:['guest@example.com']});
  await content.setJSON(id+'/manifest',{files:{'index.html':{size:7,type:'text/html'},'video.mp4':{size:7,type:'video/mp4'}}});
  await content.setJSON(id+'/index.html','<!doctype html><html><head><title>Library</title></head><body><main><article><h2>Ted &amp; Team</h2><textarea id="ted-lindsley-v01">link</textarea></article><article><h2>Sarah Matt</h2><textarea id="sarah-matt-v02">link</textarea></article></main></body></html>');
 }
 const handler=createReviewHandler({state,content,now:()=>now,sendCode:async(email,code,options)=>codes.push({email,code,options}),readMedia:async()=>({body:'content',status:200,headers:{}})});
 const call=(path='publisher/',{method='GET',body='',cookie='',origin='https://signalroompodcast.com'}={})=>handler(new Request('https://signalroompodcast.com/review/'+path,{method,headers:{cookie,origin,'content-type':'application/x-www-form-urlencoded'},...(method==='POST'?{body}:{})}),{ip:'192.0.2.1'});
 const post=(step,body,options={})=>call('publisher/owner/'+step,{method:'POST',body,...options});
 const login=async()=>{await post('request','email=owner%40example.com');const response=await post('verify','email=owner%40example.com&code='+codes.at(-1).code);assert.equal(response.status,303);return response.headers.get('set-cookie');};
 return {state,content,codes,call,post,login,advance:ms=>now+=ms};
}

test('anonymous visitors receive no owner navigation or configuration and keep open downloads',async()=>{
 const f=await fixture();
 for(const path of ['publisher/','publisher/?owner=true&email=owner@example.com','publisher/files/index.html','sarah-matt-v02/']){
  const r=await f.call(path),text=await r.text();assert.equal(r.status,200);assert.doesNotMatch(text,/publisher-owner-nav|owner-episode-jump|owner@example.com/);assert.equal(r.headers.get('set-cookie'),null);
 }
 assert.equal((await f.call('sarah-matt-v02/files/video.mp4')).status,200);
});

test('owner sign-in uses a native form; another email is never sent a code',async()=>{
 const f=await fixture(),page=await (await f.call('publisher/owner/')).text();
 assert.match(page,/form data-native-submit/);assert.doesNotMatch(page,/owner@example.com/);
 const r=await f.post('request','email=guest%40example.com');assert.equal(r.status,200);assert.match(await r.text(),/If this address has owner access/);assert.equal(f.codes.length,0);assert.equal(r.headers.get('set-cookie'),null);
 assert.doesNotMatch(await (await f.call()).text(),/publisher-owner-nav/);
});

test('verified owner receives navigation, alphabetical episode choices and a secure remembered session',async()=>{
 const f=await fixture(),full=await f.login(),cookie=full.split(';')[0];
 for(const flag of ['HttpOnly','Secure','SameSite=Lax','Path=/review/publisher/','Max-Age=2592000'])assert.ok(full.includes(flag));
 assert.deepEqual(f.codes[0].options,{purpose:'publisher-owner'});
 const r=await f.call('publisher/',{cookie}),text=await r.text();
 assert.match(text,/<nav id="publisher-owner-nav"/);assert.match(text,/Publisher library/);assert.match(text,/Signal Room site/);assert.match(text,/Ted &amp; Team/);
 assert.ok(text.indexOf('value="sarah-matt-v02"')<text.indexOf('value="ted-lindsley-v01"'));
 assert.match(r.headers.get('cache-control'),/private, no-store/);assert.equal(r.headers.get('netlify-cdn-cache-control'),'no-store');
 assert.doesNotMatch(await (await f.call('sarah-matt-v02/',{cookie})).text(),/publisher-owner-nav/);
 assert.doesNotMatch(await (await f.call()).text(),/publisher-owner-nav/);
 assert.equal((await f.post('verify','email=owner%40example.com&code='+f.codes[0].code)).status,403);
});

test('a forged token or a regular guest session cannot reveal the owner bar',async()=>{
 const f=await fixture(),v='a'.repeat(64),cookie='__Secure-sr_publisher_owner='+v;
 assert.doesNotMatch(await (await f.call('publisher/',{cookie})).text(),/publisher-owner-nav/);
 await f.state.setJSON('sessions/'+await hash(v),{email:'owner@example.com',episode:'publisher',expires:1e12+1000});
 assert.doesNotMatch(await (await f.call('publisher/',{cookie})).text(),/publisher-owner-nav/);
 await f.state.setJSON('owner/sessions/'+await hash(v),{email:'guest@example.com',expires:1e12+1000});
 assert.doesNotMatch(await (await f.call('publisher/',{cookie})).text(),/publisher-owner-nav/);
});

test('jump navigation is authenticated and restricts redirects to enabled local review rooms',async()=>{
 const f=await fixture();assert.equal((await f.call('publisher/owner/jump?episode=ted-lindsley-v01')).headers.get('location'),'/review/publisher/owner/');
 const cookie=(await f.login()).split(';')[0];
 const r=await f.call('publisher/owner/jump?episode=ted-lindsley-v01',{cookie});assert.equal(r.status,303);assert.equal(r.headers.get('location'),'/review/ted-lindsley-v01/');
 assert.equal((await f.call('publisher/owner/jump?episode=https://evil.example',{cookie})).status,400);
 assert.equal((await f.call('publisher/owner/jump?episode=missing',{cookie})).status,404);
});

test('logout, expiration and owner configuration changes immediately hide the bar',async()=>{
 for(const mode of ['logout','expires','disabled','different']){
  const f=await fixture(),cookie=(await f.login()).split(';')[0];
  if(mode==='logout'){const r=await f.post('logout','',{cookie});assert.equal(r.status,303);assert.match(r.headers.get('set-cookie'),/Max-Age=0/);}
  if(mode==='expires')f.advance(2592000001);
  if(mode==='disabled')await f.state.setJSON('settings/publisher-owner',{enabled:false,email:'owner@example.com'});
  if(mode==='different')await f.state.setJSON('settings/publisher-owner',{enabled:true,email:'different@example.com'});
  const r=await f.call('publisher/',{cookie});assert.equal(r.status,200);assert.doesNotMatch(await r.text(),/publisher-owner-nav/);
 }
});

test('cross-origin writes, excess bodies and wrong methods are rejected before sending mail',async()=>{
 const f=await fixture();
 assert.equal((await f.post('request','email=owner%40example.com',{origin:'https://evil.example'})).status,403);
 assert.equal((await f.post('request','email='+ 'x'.repeat(2100))).status,413);
 assert.equal((await f.call('publisher/owner/request')).status,405);
 assert.equal((await f.post('jump','episode=ted-lindsley-v01')).status,405);
 assert.equal((await f.call('publisher/owner/unknown')).status,404);assert.equal(f.codes.length,0);
});

test('owner codes have attempt, resend and expiry limits',async()=>{
 const f=await fixture();await f.post('request','email=owner%40example.com');await f.post('request','email=owner%40example.com');assert.equal(f.codes.length,1);
 for(let i=0;i<5;i++)assert.equal((await f.post('verify','email=owner%40example.com&code=wrong')).status,403);
 assert.equal((await f.post('verify','email=owner%40example.com&code='+f.codes[0].code)).status,403);
 f.advance(60001);await f.post('request','email=owner%40example.com');f.advance(600001);
 assert.equal((await f.post('verify','email=owner%40example.com&code='+f.codes.at(-1).code)).status,403);
});

test('concurrent owner verification accepts a code only once',async()=>{
 const f=await fixture();await f.post('request','email=owner%40example.com');
 const responses=await Promise.all(Array.from({length:6},()=>f.post('verify','email=owner%40example.com&code='+f.codes[0].code)));
 assert.equal(responses.filter(r=>r.status===303).length,1);
});

test('missing owner setup leaves the shared library available',async()=>{
 const f=await fixture();await f.state.delete('settings/publisher-owner');
 assert.equal((await f.call('publisher/owner/')).status,503);assert.equal((await f.call()).status,200);
});
