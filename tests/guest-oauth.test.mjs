import test from 'node:test';
import assert from 'node:assert/strict';
import {generateKeyPair,SignJWT} from 'jose';
import {verifyGuestToken,allowedEpisodes,readMaterial,TENANT,CLIENT_ID,API_ID,ISSUER} from '../netlify/lib/guest-oauth.mjs';
import handler from '../netlify/functions/guest-mcp.mjs';
const identity={tenant:TENANT,objectId:'11111111-1111-4111-8111-111111111111'};
test('token validation checks signature, issuer, audience, expiry, tenant, client and delegated scope',async()=>{
 const {privateKey,publicKey}=await generateKeyPair('RS256');
 const sign=async(overrides={})=>new SignJWT({ver:'2.0',tid:TENANT,oid:identity.objectId,azp:CLIENT_ID,scp:'materials.read',iss:ISSUER,aud:API_ID,iat:Math.floor(Date.now()/1000),nbf:Math.floor(Date.now()/1000)-1,exp:Math.floor(Date.now()/1000)+60,...overrides}).setProtectedHeader({alg:'RS256'}).sign(privateKey);
 assert.deepEqual(await verifyGuestToken(await sign(),publicKey),identity);
 for(const bad of [{iss:'https://evil.example'},{aud:'other'},{exp:1},{tid:'other'},{azp:'other'},{scp:'User.Read'},{oid:undefined},{ver:'1.0'}])await assert.rejects(()=>sign(bad).then(t=>verifyGuestToken(t,publicKey)));
 const other=await generateKeyPair('RS256');await assert.rejects(()=>sign().then(t=>verifyGuestToken(t,other.publicKey)));
});
test('assignments deny unassigned users, cross-episode reads, traversal, and revoked grants',async()=>{
 const db=new Map(),state={get:async k=>db.get(k)},content={get:async k=>k.endsWith('/manifest')?{files:{'notes.txt':{type:'text/plain',size:5},'secret.html':{type:'text/html',size:5}}}:'hello'};
 assert.deepEqual(await allowedEpisodes(state,identity),[]);
 db.set(`oauth/principals/${TENANT}/${identity.objectId}`,{enabled:true,episodes:['approved','publisher','../escape']});db.set('grants/approved',{enabled:true});
 assert.deepEqual(await allowedEpisodes(state,identity),['approved']);
 assert.equal(await readMaterial(state,content,identity,'approved','notes.txt'),'hello');
 for(const [episode,path] of [['other','notes.txt'],['approved','../notes.txt'],['approved','secret.html']])await assert.rejects(()=>readMaterial(state,content,identity,episode,path));
 db.set('grants/approved',{enabled:false});await assert.rejects(()=>readMaterial(state,content,identity,'approved','notes.txt'));
});
test('anonymous clients receive discovery challenge and no guest data',async()=>{
 const r=await handler(new Request('https://signalroompodcast.com/mcp/private'));
 assert.equal(r.status,401);assert(r.headers.get('www-authenticate').includes('oauth-protected-resource/mcp/private'));assert.equal(await r.text(),'');
});
