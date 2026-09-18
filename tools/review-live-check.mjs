import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {randomBytes,createHash} from 'node:crypto';
import {getStore} from '@netlify/blobs';
const base=process.argv[2];if(!base?.startsWith('https://'))throw new Error('Provide deployed HTTPS origin');
const cfg=JSON.parse(await readFile(path.join(process.env.APPDATA,'netlify/Config/config.json'),'utf8'));
const state=getStore({name:'sr-review-access',siteID:'98c71b47-cb1e-4eb2-8255-963349df8ccf',token:cfg.users[cfg.userId].auth.token,consistency:'strong'});
const hash=s=>createHash('sha256').update(s).digest('hex');
const episode='vasanth-v06',email='cjhutchins01@gmail.com',prefix=`${base}/review/${episode}/`;
const code=String(randomBytes(4).readUInt32BE()%100000000).padStart(8,'0'),salt=randomBytes(32).toString('hex');
const key=`otp/${hash(`${episode}:${email}`)}`;
let sessionKey;
try{
 const anon=await fetch(prefix);if(anon.status!==200||!(await anon.text()).includes('Your guest review room'))throw new Error(`Anonymous page: ${anon.status}`);
 const file='files/masters/vasanth-mudavatu_episode_v06.mp4';
 const denied=await fetch(prefix+file,{method:'HEAD'});if(denied.status!==401)throw new Error(`Anonymous file not denied: ${denied.status}`);
 const prior=await state.get(key,{type:'json'});if(prior&&!prior.used&&prior.expires>Date.now())throw new Error('Active owner challenge exists; leave it intact');
 await state.setJSON(key,{email,episode,salt,digest:hash(salt+code),sentAt:Date.now(),expires:Date.now()+60000,attempts:0,used:false});
 const verified=await fetch(prefix+'verify',{method:'POST',headers:{origin:base,'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({email,code}),redirect:'manual'});
 if(verified.status!==303)throw new Error(`Verify endpoint: ${verified.status} ${(await verified.text()).slice(0,100)}`);
 const setCookie=verified.headers.get('set-cookie');if(!['Secure','HttpOnly','SameSite=Strict'].every(s=>setCookie.includes(s)))throw new Error('Cookie flags missing');
 const cookie=setCookie.split(';')[0];sessionKey=`sessions/${hash(cookie.split('=')[1])}`;
 const gallery=await fetch(prefix,{headers:{cookie}});const h=await gallery.text();if(gallery.status!==200||!h.includes('Vasanth Mudavatu')||h.includes('drive.google.com'))throw new Error('Private gallery failed');
 const links=[...new Set([...h.matchAll(/(?:src|href|poster)="([^"]+)"/g)].map(m=>m[1]))];
 for(const link of links){const r=await fetch(new URL(link,base),{method:'HEAD',headers:{cookie}});if(r.status!==200)throw new Error(`Asset missing: ${link} ${r.status}`);}
 for(const range of ['bytes=0-1023','bytes=1179943178-1179944201','bytes=-128']){
  const r=await fetch(prefix+file,{headers:{cookie,range}});const length=(await r.arrayBuffer()).byteLength;
  if(r.status!==206||length!==(range.endsWith('128')?128:1024))throw new Error(`Range failed: ${range} ${r.status} ${length}`);
 }
 const invalid=await fetch(prefix+file,{headers:{cookie,range:'bytes=9999999999-'}});await invalid.body?.cancel();if(invalid.status!==416)throw new Error(`Invalid range status ${invalid.status}`);
 const replay=await fetch(prefix+'verify',{method:'POST',headers:{origin:base,'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({email,code}),redirect:'manual'});if(replay.status!==403)throw new Error('Code replay accepted');
 const logout=await fetch(prefix+'logout',{method:'POST',headers:{origin:base,cookie},redirect:'manual'});if(logout.status!==303)throw new Error('Logout failed');
 const after=await fetch(prefix+file,{method:'HEAD',headers:{cookie}});if(after.status!==401)throw new Error('Session survived logout');
 console.log(JSON.stringify({origin:base,loginPage:'pass',anonymousMedia:'denied',seededCodeVerification:'pass',emailSending:'not invoked',gallery:'pass',assetLinks:links.length,rangeRequests:'pass',replay:'denied',logout:'pass'}));
}finally{await state.delete(key);if(sessionKey)await state.delete(sessionKey);}
