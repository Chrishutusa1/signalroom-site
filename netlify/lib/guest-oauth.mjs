import { createRemoteJWKSet, jwtVerify } from 'jose';
export const TENANT='24457a8d-f4e8-4771-b491-6a917d698b97';
export const API_ID='025bc72e-52e8-4fc4-b29d-42c24ec2a92c';
export const CLIENT_ID='e9c81893-6a51-4c77-87f3-4a5bec83527f';
export const ISSUER=`https://login.microsoftonline.com/${TENANT}/v2.0`;
export const RESOURCE='https://signalroompodcast.com/mcp/private';
export const SCOPE=`api://${API_ID}/materials.read`;
export const METADATA='https://signalroompodcast.com/.well-known/oauth-protected-resource/mcp/private';
const keys=createRemoteJWKSet(new URL(`https://login.microsoftonline.com/${TENANT}/discovery/v2.0/keys`));
export async function verifyGuestToken(token,keySet=keys){
 const {payload:p}=await jwtVerify(token,keySet,{issuer:ISSUER,audience:API_ID,algorithms:['RS256'],requiredClaims:['exp','iat','nbf','tid','oid','azp','scp']});
 if(p.ver!=='2.0'||p.tid!==TENANT||p.azp!==CLIENT_ID||typeof p.oid!=='string'||! /^[a-f0-9-]{36}$/i.test(p.oid)||!String(p.scp).split(' ').includes('materials.read'))throw new Error('Invalid authorization');
 return {tenant:p.tid,objectId:p.oid};
}
export async function allowedEpisodes(state,identity){
 const assignment=await state.get(`oauth/principals/${identity.tenant}/${identity.objectId}`,{type:'json'});
 if(!assignment?.enabled||!Array.isArray(assignment.episodes))return [];
 const result=[];
 for(const episode of assignment.episodes.slice(0,100)){
  if(typeof episode!=='string'||! /^[a-z0-9-]{1,80}$/.test(episode)||episode==='publisher')continue;
  const grant=await state.get(`grants/${episode}`,{type:'json'});
  if(grant?.enabled)result.push(episode);
 }
 return result;
}
export async function readMaterial(state,content,identity,episode,path){
 if(!(await allowedEpisodes(state,identity)).includes(episode))throw new Error('Material unavailable');
 const manifest=await content.get(`${episode}/manifest`,{type:'json'});
 const item=manifest?.files?.[path];
 if(!item||typeof path!=='string'||path.includes('..')||path.startsWith('/')||path.includes('\\')||!['text/plain','text/markdown','text/vtt','application/x-subrip'].includes(item.type?.split(';')[0])||!Number.isFinite(item.size)||item.size>200000)throw new Error('Material unavailable');
 const text=await content.get(`${episode}/${path}`);
 if(typeof text!=='string'||Buffer.byteLength(text)>200000)throw new Error('Material unavailable');
 return text;
}
