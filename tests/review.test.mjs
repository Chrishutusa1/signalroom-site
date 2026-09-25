import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createReviewHandler,hash} from '../netlify/lib/review-core.mjs';
class Store {
 constructor(){this.values=new Map();this.n=0;}
 async get(k){return structuredClone(this.values.get(k)?.data??null);}
 async getWithMetadata(k){return structuredClone(this.values.get(k)??null);}
 async setJSON(k,data,opt={}){const prior=this.values.get(k);if(opt.onlyIfNew&&prior||opt.onlyIfMatch&&prior?.etag!==opt.onlyIfMatch)return {modified:false};const etag=String(++this.n);this.values.set(k,{data:structuredClone(data),etag});return {modified:true,etag};}
 async delete(k){this.values.delete(k);}
}
async function fixture(){
 const state=new Store(),content=new Store(),codes=[];let time=1e12;
 await state.setJSON('grants/test',{enabled:true,emails:['guest@example.com']});
 await content.setJSON('test/manifest',{files:{'index.html':{size:7,type:'text/html'},'movie.mp4':{size:7,type:'video/mp4'}}});
 await content.setJSON('test/index.html','private');
 const handler=createReviewHandler({state,content,now:()=>time,sendCode:async(email,code)=>codes.push({email,code}),readMedia:async()=>({body:'private',status:200,headers:{}})});
 const call=(p='',method='GET',body='',session='',origin='https://signalroompodcast.com')=>handler(new Request(`https://signalroompodcast.com/review/test/${p}`,{method,headers:{origin,cookie:session,'content-type':'application/x-www-form-urlencoded'},...(method==='POST'?{body}:{})}),{ip:'192.0.2.1'});
 const login=async()=>{await call('request','POST','email=guest%40example.com');const r=await call('verify','POST',`email=guest%40example.com&code=${codes.at(-1).code}`);return r.headers.get('set-cookie').split(';')[0];};
 return {state,content,codes,call,login,advance:n=>time+=n};
}
test('anonymous users receive a login page and cannot read direct media',async()=>{const f=await fixture();assert.match(await (await f.call()).text(),/Your guest review room/);assert.equal((await f.call('files/movie.mp4')).status,401);});
test('uninvited email is not sent a code and gets the same neutral response',async()=>{const f=await fixture();const r=await f.call('request','POST','email=other%40example.com');assert.equal(r.status,200);assert.equal(f.codes.length,0);assert.match(await r.text(),/If this address is invited/);});
test('valid code creates secure session; replay fails; private content is no-store',async()=>{const f=await fixture();const s=await f.login();const r=await f.call('','GET','',s);assert.match(await r.text(),/^private<script nonce=/);assert.match(r.headers.get('cache-control'),/no-store/);assert.equal((await f.call('verify','POST',`email=guest%40example.com&code=${f.codes[0].code}`)).status,403);});
test('code attempt limit, expiry, and resend throttle',async()=>{const f=await fixture();await f.call('request','POST','email=guest%40example.com');await f.call('request','POST','email=guest%40example.com');assert.equal(f.codes.length,1);for(let i=0;i<5;i++)assert.equal((await f.call('verify','POST','email=guest%40example.com&code=wrong')).status,403);assert.equal((await f.call('verify','POST',`email=guest%40example.com&code=${f.codes[0].code}`)).status,403);f.advance(60001);await f.call('request','POST','email=guest%40example.com');f.advance(600001);assert.equal((await f.call('verify','POST',`email=guest%40example.com&code=${f.codes.at(-1).code}`)).status,403);});
test('concurrent verification permits only one session',async()=>{const f=await fixture();await f.call('request','POST','email=guest%40example.com');const replies=await Promise.all(Array.from({length:8},()=>f.call('verify','POST',`email=guest%40example.com&code=${f.codes[0].code}`)));assert.equal(replies.filter(r=>r.status===303).length,1);});
test('grant removal revokes existing sessions immediately',async()=>{const f=await fixture(),s=await f.login();await f.state.setJSON('grants/test',{enabled:true,emails:[]});assert.equal((await f.call('files/movie.mp4','GET','',s)).status,401);});
test('cross-origin requests, unsupported ranges, traversal and session expiry are denied',async()=>{const f=await fixture();assert.equal((await f.call('request','POST','email=guest%40example.com','','https://evil.example')).status,403);const s=await f.login();assert.equal((await f.call('files/%2e%2e%2fsecret','GET','',s)).status,404);f.advance(28800001);assert.equal((await f.call('files/movie.mp4','GET','',s)).status,401);});
test('logout invalidates the stored session',async()=>{const f=await fixture(),s=await f.login();assert.equal((await f.call('logout','POST','',s)).status,303);assert.equal((await f.call('files/movie.mp4','GET','',s)).status,401);});
test('a token for another episode does not authorize this episode',async()=>{const f=await fixture(),s=await f.login();const entry=[...f.state.values.keys()].find(k=>k.startsWith('sessions/'));const value=await f.state.get(entry);await f.state.setJSON(entry,{...value,episode:'someone-else'});assert.equal((await f.call('files/movie.mp4','GET','',s)).status,401);});

async function invitation(f,overrides={}){
 const secret='a'.repeat(64),key=`invites/${await hash(secret)}`;
 await f.state.setJSON(key,{episode:'test',email:'guest@example.com',expires:1e12+60000,...overrides});
 return {secret,key,open:()=>f.call(`access/${secret}`)};
}
test('anyone link opens without identity or expiry and can renew an expired session',async()=>{
 const f=await fixture();await f.state.setJSON('grants/test',{enabled:true,emails:[]});
 const i=await invitation(f,{email:undefined,audience:'anyone-with-link',expires:null});
 const r=await i.open();assert.equal(r.status,303);const cookie=r.headers.get('set-cookie').split(';')[0];
 const session=await f.state.get(`sessions/${await hash(cookie.split('=')[1])}`);assert.equal(session.email,undefined);assert.equal(session.audience,'anyone-with-link');
 assert.equal((await f.call('files/movie.mp4','GET','',cookie)).status,200);assert.equal(f.codes.length,0);
 f.advance(28800001);assert.equal((await f.call('files/movie.mp4','GET','',cookie)).status,401);assert.equal((await i.open()).status,303);
});
test('anyone link remains episode-scoped and revocable, with optional expiry',async()=>{
 for(const change of ['revoke','disable','expire','scope','audience']){
  const f=await fixture(),i=await invitation(f,{email:undefined,audience:'anyone-with-link',expires:null}),r=await i.open(),cookie=r.headers.get('set-cookie').split(';')[0];
  const prior=await f.state.get(i.key);
  if(change==='revoke')await f.state.setJSON(i.key,{...prior,revoked:true});
  if(change==='disable')await f.state.setJSON('grants/test',{enabled:false});
  if(change==='expire')await f.state.setJSON(i.key,{...prior,expires:1e12});
  if(change==='scope')await f.state.setJSON(i.key,{...prior,episode:'other'});
  if(change==='audience')await f.state.setJSON(i.key,{...prior,audience:undefined});
  assert.ok([401,404].includes((await f.call('files/movie.mp4','GET','',cookie)).status));assert.ok([403,404].includes((await i.open()).status));
 }
});
test('missing or null expiry does not turn ordinary invitations into permanent links',async()=>{
 for(const expires of [null,undefined,'later']){const f=await fixture(),i=await invitation(f,{expires});assert.equal((await i.open()).status,403);}
 const f=await fixture(),token='c'.repeat(64);await f.state.setJSON(`sessions/${await hash(token)}`,{episode:'test',audience:'anyone-with-link',expires:1e12+60000});assert.equal((await f.call('files/movie.mp4','GET','',`__Secure-sr_test=${token}`)).status,401);
});
test('private link opens without email/code, redirects to clean URL and remains reusable',async()=>{
 const f=await fixture(),i=await invitation(f),r=await i.open();
 assert.equal(r.status,303);assert.equal(r.headers.get('location'),'/review/test/');
 const cookie=r.headers.get('set-cookie');for(const flag of ['HttpOnly','Secure','SameSite=Lax','Path=/review/test/','Max-Age=60'])assert.ok(cookie.includes(flag));
 assert.match(r.headers.get('cache-control'),/no-store/);assert.equal(r.headers.get('referrer-policy'),'no-referrer');
 assert.equal(await (await f.call('files/movie.mp4','GET','',cookie.split(';')[0])).text(),'private');
 assert.equal((await i.open()).status,303);assert.equal(f.codes.length,0);
 assert.equal((await f.call(`access/${i.secret}`,'HEAD')).status,405);
});
test('invalid, expired, revoked, other-episode and uninvited links are denied',async()=>{
 for(const overrides of [{expires:1e12},{revoked:true},{episode:'other'},{email:'other@example.com'}]){
  const f=await fixture(),i=await invitation(f,overrides);assert.equal((await i.open()).status,403);
 }
 const f=await fixture();assert.equal((await f.call('access/not-a-secret')).status,403);assert.equal((await f.call('access/'+'b'.repeat(64))).status,403);
});
test('revocation, grant removal and expiry also revoke active invitation sessions',async()=>{
 for(const change of ['revoke','remove','expire']){
  const f=await fixture(),i=await invitation(f),r=await i.open(),cookie=r.headers.get('set-cookie').split(';')[0];
  if(change==='revoke')await f.state.setJSON(i.key,{...(await f.state.get(i.key)),revoked:true});
  if(change==='remove')await f.state.setJSON('grants/test',{enabled:true,emails:[]});
  if(change==='expire')f.advance(60001);
  assert.equal((await f.call('files/movie.mp4','GET','',cookie)).status,401);assert.equal((await i.open()).status,403);
 }
});

test('email-only invitation requires its matching address but no passcode',async()=>{
 const f=await fixture(),i=await invitation(f,{requireEmail:true});
 const page=await i.open(),body=await page.text();assert.equal(page.status,200);assert.equal(page.headers.get('set-cookie'),null);
 assert.match(body,/Open review room/);assert.ok(body.includes(`/review/test/access/${i.secret}`));assert.ok(!body.includes('Email me a code'));assert.ok(!body.includes('name="code"'));assert.ok(!body.includes('<script'));
 const wrong=await f.call(`access/${i.secret}`,'POST','email=other%40example.com');assert.equal(wrong.status,403);assert.equal(wrong.headers.get('set-cookie'),null);
 const right=await f.call(`access/${i.secret}`,'POST','email=GUEST%40EXAMPLE.COM');assert.equal(right.status,303);assert.equal(right.headers.get('location'),'/review/test/');
 const cookie=right.headers.get('set-cookie').split(';')[0];assert.equal(await (await f.call('files/movie.mp4','GET','',cookie)).text(),'private');assert.equal(f.codes.length,0);
});
test('email-only invitation rejects cross-origin, oversized and excessive submissions',async()=>{
 const f=await fixture(),i=await invitation(f,{requireEmail:true}),p=`access/${i.secret}`;
 assert.equal((await f.call(p,'POST','email=guest%40example.com','','https://evil.example')).status,403);
 assert.equal((await f.call(p,'POST','email='+ 'x'.repeat(2100))).status,413);
 for(let n=0;n<30;n++)assert.equal((await f.call(p,'POST','email=wrong')).status,403);
 assert.equal((await f.call(p,'POST','email=guest%40example.com')).status,429);
});
test('shortening invitation expiry limits an already issued session',async()=>{
 const f=await fixture(),i=await invitation(f),r=await i.open(),cookie=r.headers.get('set-cookie').split(';')[0];
 await f.state.setJSON(i.key,{...(await f.state.get(i.key)),expires:1e12+1000});f.advance(1001);
 assert.equal((await f.call('files/movie.mp4','GET','',cookie)).status,401);
});
test('one shared invitation admits each listed reviewer and binds their own session',async()=>{
 const f=await fixture(),emails=['one@example.com','two@example.com','three@example.com','four@example.com'];
 await f.state.setJSON('grants/test',{enabled:true,emails:[...emails,'unlisted@example.com']});
 const i=await invitation(f,{email:undefined,emails});assert.equal((await i.open()).status,200);
 for(const email of emails){
  const r=await f.call(`access/${i.secret}`,'POST',new URLSearchParams({email}).toString());assert.equal(r.status,303);
  const cookie=r.headers.get('set-cookie').split(';')[0],session=await f.state.get(`sessions/${await hash(cookie.split('=')[1])}`);assert.equal(session.email,email);
  assert.equal((await f.call('files/movie.mp4','GET','',cookie)).status,200);
 }
 assert.equal((await f.call(`access/${i.secret}`,'POST','email=unlisted%40example.com')).status,403);assert.equal(f.codes.length,0);
});
test('removing one shared reviewer from invitation or grant revokes only that reviewer',async()=>{
 for(const removal of ['invitation','grant']){
  const f=await fixture(),emails=['one@example.com','two@example.com'];await f.state.setJSON('grants/test',{enabled:true,emails});
  const i=await invitation(f,{email:undefined,emails,requireEmail:true});const cookies=[];
  for(const email of emails){const r=await f.call(`access/${i.secret}`,'POST',new URLSearchParams({email}).toString());cookies.push(r.headers.get('set-cookie').split(';')[0]);}
  if(removal==='grant')await f.state.setJSON('grants/test',{enabled:true,emails:[emails[1]]});
  else await f.state.setJSON(i.key,{...(await f.state.get(i.key)),emails:[emails[1]]});
  assert.equal((await f.call('files/movie.mp4','GET','',cookies[0])).status,401);
  assert.equal((await f.call('files/movie.mp4','GET','',cookies[1])).status,200);
  assert.equal((await f.call(`access/${i.secret}`,'POST',new URLSearchParams({email:emails[0]}).toString())).status,403);
 }
});

test('download controls receive a CSP nonce even when a gallery omits its closing body tag',async()=>{
 const f=await fixture(),session=await f.login();
 for(const ending of ['</body></html>','</html>','</BODY></HTML>','']){
  await f.content.setJSON('test/index.html','<html><main><a href="/review/test/files/movie.mp4">MP4</a></main>'+ending);
  const response=await f.call('','GET','',session),body=await response.text();
  assert.match(body,/id="review-download-library"/);assert.match(body,/showSaveFilePicker/);
  const nonce=body.match(/<script nonce="([a-f0-9]+)">/)[1];assert.ok(response.headers.get('content-security-policy').includes("'nonce-"+nonce+"'"));
  assert.equal((body.match(/<script nonce=/g)||[]).length,1);
 }
});