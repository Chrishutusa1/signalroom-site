// Explicit private invitation; dry run unless --apply. Never print the bearer URL.
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {randomBytes,createHash} from 'node:crypto';
import path from 'node:path';
import {getStore} from '@netlify/blobs';
const [episode,address,...flags]=process.argv.slice(2),email=address?.trim().toLowerCase();
if(!/^[a-z0-9-]{1,80}$/.test(episode||'')||!/^\S+@\S+\.\S+$/.test(email||''))throw Error('Usage: review-invite.mjs episode email [--apply]');
const cfg=JSON.parse(await readFile(path.join(process.env.APPDATA,'netlify/Config/config.json'),'utf8'));
const state=getStore({name:'sr-review-access',siteID:'98c71b47-cb1e-4eb2-8255-963349df8ccf',token:cfg.users[cfg.userId].auth.token,consistency:'strong'});
const grantKey=`grants/${episode}`,prior=await state.getWithMetadata(grantKey,{type:'json'});
if(!prior?.data?.enabled)throw Error('Review room is not enabled');
if(!flags.includes('--apply')){
 console.log(JSON.stringify({episode,email,days:30,existingReviewersPreserved:true,apply:false}));
}else{
 const file=path.resolve('.netlify/invites',`${episode}-${email.replace(/[^a-z0-9.-]/g,'_')}.json`);
 try{await readFile(file);throw Error('Invitation output already exists; inspect it before issuing another');}catch(e){if(e.code!=='ENOENT')throw e;}
 const updated={...prior.data,emails:[...new Set([...(prior.data.emails||[]),email])]};
 const changed=await state.setJSON(grantKey,updated,{onlyIfMatch:prior.etag});
 if(!changed.modified)throw Error('Reviewer list changed; retry after checking it');
 const secret=randomBytes(32).toString('hex'),digest=createHash('sha256').update(secret).digest('hex'),expires=Date.now()+30*86400000;
 await state.setJSON(`invites/${digest}`,{episode,email,expires,createdAt:Date.now(),revoked:false},{onlyIfNew:true});
 const invite={episode,email,url:`https://signalroompodcast.com/review/${episode}/access/${secret}`,expires:new Date(expires).toISOString(),key:`invites/${digest}`};
 await mkdir(path.dirname(file),{recursive:true});await writeFile(file,JSON.stringify(invite,null,2),{flag:'wx',mode:0o600});
 console.log(JSON.stringify({episode,email,expires:invite.expires,output:file,existingReviewersPreserved:true}));
}
