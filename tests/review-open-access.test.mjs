import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createReviewHandler} from '../netlify/lib/review-core.mjs';

async function fixture(){
 const values=new Map([
  ['settings/sharing',{audience:'anyone-with-link'}],
  ['grants/publisher',{enabled:true}],
  ['grants/aaron-bach-v01',{enabled:true}],
  ['grants/disabled',{enabled:false}],
 ]);
 const manifests=new Map(['publisher','aaron-bach-v01','disabled'].map(id=>[
  `${id}/manifest`,{files:{'index.html':{type:'text/html',size:50},'movie.mp4':{type:'video/mp4',size:7},'captions.srt':{type:'text/plain',size:7},'package.zip':{type:'application/zip',size:7}}}
 ]));
 const mediaCalls=[];
 const state={get:async key=>values.get(key)??null};
 const content={get:async key=>manifests.get(key)??(key.endsWith('/index.html')?'<html><body><main>Review package</main></body></html>':null)};
 const handler=createReviewHandler({state,content,sendCode:async()=>assert.fail('No email should be sent'),readMedia:async(key,range)=>{
  mediaCalls.push({key,range});
  return range?{body:'vid',status:206,headers:{'Content-Length':'3','Content-Range':'bytes 0-2/7'}}:{body:'content',status:200,headers:{'Content-Length':'7'}};
 }});
 const call=(suffix='',options={})=>handler(new Request(`https://signalroompodcast.com/review/${suffix}`,options));
 return {values,mediaCalls,call};
}

test('publisher, episode and each material type open without cookies or identity',async()=>{
 const f=await fixture();
 for(const path of ['publisher/','aaron-bach-v01/','aaron-bach-v01/files/movie.mp4','aaron-bach-v01/files/captions.srt','aaron-bach-v01/files/package.zip']){
  const r=await f.call(path);assert.equal(r.status,200,path);assert.equal(r.headers.get('set-cookie'),null);
  assert.match(r.headers.get('x-robots-tag'),/noindex/);assert.match(r.headers.get('cache-control'),/no-store/);
  assert.doesNotMatch(await r.text(),/name="email"|Email me a code/);
 }
});

test('anonymous seeking, HEAD and explicit downloads preserve media behavior',async()=>{
 const f=await fixture();
 const head=await f.call('aaron-bach-v01/files/package.zip?download=1',{method:'HEAD'});
 assert.equal(head.status,200);assert.equal(head.headers.get('content-length'),'7');assert.equal(await head.text(),'');
 assert.equal(head.headers.get('content-disposition'),'attachment; filename="package.zip"');
 const range=await f.call('aaron-bach-v01/files/movie.mp4',{headers:{range:'bytes=0-2'}});
 assert.equal(range.status,206);assert.equal(range.headers.get('content-range'),'bytes 0-2/7');assert.equal(await range.text(),'vid');
 assert.deepEqual(f.mediaCalls,[{key:'aaron-bach-v01/movie.mp4',range:'bytes=0-2'}]);
 assert.equal((await f.call('aaron-bach-v01/files/movie.mp4',{headers:{range:'bytes=0-1,3-4'}})).status,416);
});

test('previous invitation URLs and cached sign-in actions lead to the open room',async()=>{
 const f=await fixture();
 for(const action of ['access/old-expired-link','request','verify','logout']){
  for(const method of ['GET','HEAD','POST']){
   const r=await f.call(`aaron-bach-v01/${action}`,{method});
   assert.equal(r.status,303);assert.equal(r.headers.get('location'),'/review/aaron-bach-v01/');assert.equal(r.headers.get('set-cookie'),null);
  }
 }
});

test('open review access does not expose disabled rooms, unlisted files or writes',async()=>{
 const f=await fixture();
 for(const path of ['disabled/','unknown/','aaron-bach-v01/files/private-source.wav','aaron-bach-v01/files/%2e%2e%2fsecret','aaron-bach-v01/manifest','aaron-bach-v01/settings/sharing'])assert.equal((await f.call(path)).status,404,path);
 for(const method of ['POST','PUT','DELETE'])assert.equal((await f.call('aaron-bach-v01/files/movie.mp4',{method})).status,405);
});

test('sharing can be withdrawn immediately and does not accept unknown audience values',async()=>{
 const f=await fixture();
 for(const value of [undefined,{audience:'invited'},{audience:'public-ish'}]){
  f.values.set('settings/sharing',value);
  assert.equal((await f.call('aaron-bach-v01/files/movie.mp4')).status,401);
  assert.match(await (await f.call('aaron-bach-v01/')).text(),/name="email"/);
 }
});
