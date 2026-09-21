// Local operator tool. Never prints credentials or verification codes.
import { readFile, writeFile, readdir, stat } from 'node:fs/promises';
import { openAsBlob } from 'node:fs';
import { createHash } from 'node:crypto';
import { getStore } from '@netlify/blobs';
import path from 'node:path';
const siteID='98c71b47-cb1e-4eb2-8255-963349df8ccf';
const config=JSON.parse(await readFile(path.join(process.env.APPDATA,'netlify/Config/config.json'),'utf8'));
const token=config.users[config.userId].auth.token;
const state=getStore({name:'sr-review-access',siteID,token,consistency:'strong'});
const content=getStore({name:'sr-review-content',siteID,token,consistency:'strong'});
const [command,episode,source,...emails]=process.argv.slice(2);
if(command==='upload'){
 if(!episode||!source)throw new Error('Usage: upload episode absolute-package-path');
 const files={};
 const types={'.mp4':'video/mp4','.mp3':'audio/mpeg','.vtt':'text/vtt; charset=utf-8','.srt':'text/plain; charset=utf-8','.md':'text/plain; charset=utf-8','.txt':'text/plain; charset=utf-8','.jpg':'image/jpeg','.html':'text/html; charset=utf-8'};
 const paths=[];
 for(const dir of ['masters','reels','highlights','artwork','posts'])for(const f of await readdir(path.join(source,dir)))if(types[path.extname(f)])paths.push(`${dir}/${f}`);
 paths.push(...['Episode_Package.md','Chapters.txt','Transcript.md','Highlights_and_Promos.md'].map(f=>`metadata/${f}`),'qa/QA.md');
 for(const relative of paths){
  const file=path.join(source,relative),size=(await stat(file)).size;
  const blob=await openAsBlob(file);const hasher=createHash('sha256');for await(const chunk of blob.stream())hasher.update(chunk);const sha256=hasher.digest('hex');
  const key=`${episode}/${relative}`,old=await content.getMetadata(key);
  if(old?.metadata?.sha256!==sha256){await content.set(key,blob,{metadata:{sha256,size}});}
  const check=await content.getMetadata(key);if(check?.metadata?.sha256!==sha256||check?.metadata?.size!==size)throw new Error(`Verification failed: ${relative}`);
  files[relative]={size,type:types[path.extname(relative)],sha256};console.log(`Verified ${relative}`);
 }
 let h=await readFile(path.join(source,'Review.html'),'utf8');
 h=h.replace('<html>','<html lang="en">').replace('<meta charset="utf-8">','<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow">');
 h=h.replace('<a href="DELIVERY.md">Delivery guide</a> · ','');
 h=h.replace('Revision 06 · Full episode, eight shorts, two extended highlights. All players start paused.','Private guest review · Revision 06 · Full episode, eight shorts, two extended highlights.');
 h=h.replace('</style>','article{border:1px solid #4b365e}video{border-radius:8px}main{grid-template-columns:repeat(auto-fit,minmax(min(100%,350px),1fr))}a{display:inline-block;margin:4px 0}button{font:inherit;border:1px solid #a593bd;color:#fff;background:transparent;border-radius:8px;padding:8px 18px;cursor:pointer}@media(max-width:600px){body{margin:20px auto;padding:0 16px}article{padding:16px}h1{font-size:28px}}footer{margin:32px 0;color:#ccc}</style>');
 h=h.replace(/(href|src|poster)="([^"#][^"]*)"/g,(match,attr,url)=>{if(!files[url])throw new Error(`Unmapped gallery link: ${url}`);return `${attr}="/review/${episode}/files/${url}"`;});
 h=h.replace('</body>',`<footer><p>Review copies. Please check captions and flag any edits before release.</p><form method="post" action="/review/${episode}/logout"><button>Sign out</button></form></footer></body>`);
 await content.set(`${episode}/index.html`,h);
 files['index.html']={size:Buffer.byteLength(h),type:'text/html; charset=utf-8'};
 await content.setJSON(`${episode}/manifest`,{files,updated:new Date().toISOString()});
 await writeFile(path.join(source,'Protected_Portal_Transfer.json'),JSON.stringify({episode,files},null,2));
 console.log(`Private package verified: ${Object.keys(files).length} files`);
}else if(command==='grant'){
 const recipients=[source,...emails].filter(Boolean).map(s=>s.toLowerCase());
 if(!recipients.length||recipients.some(s=>!/^\S+@\S+\.\S+$/.test(s)))throw new Error('Provide approved emails');
 await state.setJSON(`grants/${episode}`,{enabled:true,emails:recipients});
 const result=await state.get(`grants/${episode}`,{type:'json'});console.log(JSON.stringify({episode,enabled:result.enabled,reviewers:result.emails}));
}else if(command==='check-email'){
 const sr=await fetch(`https://api.netlify.com/api/v1/sites/${siteID}`,{headers:{Authorization:`Bearer ${token}`}});const site=await sr.json();
 const er=await fetch(`https://api.netlify.com/api/v1/accounts/${site.account_id}/env?site_id=${siteID}`,{headers:{Authorization:`Bearer ${token}`}});const env=await er.json();
 const value=key=>env.find(e=>e.key===key)?.values.find(v=>v.context==='all'||v.context==='production')?.value;
 const k=value('RESEND_API_KEY');const rr=await fetch('https://api.resend.com/domains',{headers:{Authorization:`Bearer ${k}`}});const domains=await rr.json();console.log(JSON.stringify({status:rr.status,keyPresent:!!k,contexts:env.find(e=>e.key==='RESEND_API_KEY')?.values.map(v=>v.context),message:domains.message,from:value('AUTOREPLY_FROM'),domains:domains.data?.map(d=>({name:d.name,status:d.status}))}));
}else throw new Error('Use upload, grant, or check-email');
