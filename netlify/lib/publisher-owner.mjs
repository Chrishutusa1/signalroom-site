const BASE='/review/publisher/',COOKIE='__Secure-sr_publisher_owner',AGE=2592000;
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const random=()=>Array.from(crypto.getRandomValues(new Uint8Array(32)),b=>b.toString(16).padStart(2,'0')).join('');
const token=r=>r.headers.get('cookie')?.split(';').map(s=>s.trim()).find(s=>s.startsWith(COOKIE+'='))?.slice(COOKIE.length+1);
const cookie=(v,age=AGE)=>`${COOKIE}=${v}; Path=${BASE}; HttpOnly; Secure; SameSite=Lax; Max-Age=${age}`;
const ownerEmail=c=>c?.enabled&&typeof c.email==='string'?c.email.trim().toLowerCase():null;

export async function isPublisherOwner(request,{state,hash,now}){
 const value=token(request);if(!value||!/^[a-f0-9]{64}$/.test(value))return false;
 const [config,session]=await Promise.all([state.get('settings/publisher-owner',{type:'json'}),state.get(`owner/sessions/${await hash(value)}`,{type:'json'})]);
 const email=ownerEmail(config);
 return !!(email&&session?.email===email&&Number.isFinite(session.expires)&&session.expires>now);
}

const signIn=(message='',verify=false,email='')=>`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Publisher owner sign-in | The Signal Room</title><style>*{box-sizing:border-box}body{margin:0;background:#160d24;color:#f9f6ff;font:17px/1.6 system-ui;min-height:100vh;display:grid;place-items:center;padding:24px}.card{width:min(100%,480px);background:#251936;border:1px solid #604578;border-radius:18px;padding:32px}.brand{color:#ffe054;font-size:13px;letter-spacing:.16em}h1{font-size:30px;line-height:1.2}p{color:#d4cadd}label{display:block;margin:18px 0 7px}input,button{font:inherit;width:100%;border-radius:8px;padding:12px}input{border:1px solid #a393b6;background:#160d24;color:white}button{background:#ffe054;color:#180d20;font-weight:700;border:0;margin-top:20px;cursor:pointer}a{color:#ffe054}.message{border-left:3px solid #ffe054;padding-left:14px}.small{font-size:14px}</style></head><body><main class="card"><div class="brand">THE SIGNAL ROOM · OWNER ACCESS</div><h1>${verify?'Check your email':'Your publisher navigation'}</h1><p>${verify?'Enter the eight-digit code sent to your owner email. It expires in ten minutes.':'Sign in with your owner email to show your private navigation bar.'}</p>${message?`<p class="message" role="status">${escape(message)}</p>`:''}<form data-native-submit method="post" action="${BASE}owner/${verify?'verify':'request'}"><label for="email">Email address</label><input id="email" name="email" type="email" autocomplete="email" required maxlength="254" value="${escape(email)}">${verify?'<label for="code">Verification code</label><input id="code" name="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{8}" maxlength="8" required>':''}<button>${verify?'Show my navigation':'Email me a sign-in code'}</button></form>${verify?`<p><a href="${BASE}owner/">Request a new code</a></p>`:''}<p class="small">This browser remembers your owner sign-in for 30 days. Guests can still open shared review links without signing in.</p><p><a href="${BASE}">Open the shared publisher directory</a></p></main></body></html>`;

export async function handlePublisherOwner(request,{action,state,sendCode,hash,count,html,response,now,ip}){
 const url=new URL(request.url),step=action.replace(/^owner\/?/,'').replace(/\/$/,'');
 if(!['','request','verify','logout','jump'].includes(step))return response('Not found',404);
 const config=await state.get('settings/publisher-owner',{type:'json'}),owner=ownerEmail(config);
 if(!owner)return response('Owner sign-in is not configured.',503);
 if(step===''||step==='jump'){
  if(!['GET','HEAD'].includes(request.method))return response('Method not allowed',405);
  const signedIn=await isPublisherOwner(request,{state,hash,now});
  if(step==='')return signedIn?response(null,303,{Location:BASE}):html(signIn());
  if(!signedIn)return response(null,303,{Location:BASE+'owner/'});
  const episode=url.searchParams.get('episode')||'';
  if(!/^[a-z0-9-]{1,80}$/.test(episode))return response('Choose an episode from the directory.',400);
  const grant=await state.get(`grants/${episode}`,{type:'json'});
  return grant?.enabled?response(null,303,{Location:`/review/${episode}/`}):response('This review room is unavailable.',404);
 }
 if(request.method!=='POST')return response('Method not allowed',405);
 if(request.headers.get('origin')!==url.origin)return response('Request not allowed',403);
 if(step==='logout'){
  const value=token(request);if(value&&/^[a-f0-9]{64}$/.test(value))await state.delete(`owner/sessions/${await hash(value)}`);
  return response(null,303,{Location:BASE,'Set-Cookie':cookie('',0)});
 }
 if(Number(request.headers.get('content-length'))>2048)return response('Request too large',413);
 const body=await request.text();if(body.length>2048)return response('Request too large',413);
 const form=new URLSearchParams(body),email=(form.get('email')||'').trim().toLowerCase();
 if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)||email.length>254)return html(signIn('Enter a valid email address.'),400);
 const who=await hash(email),source=await hash(ip||'unknown'),key=`owner/otp/${who}`;
 if(step==='request'){
  if(!await count(state,`owner/rate/ip/${source}`,20,now)||!await count(state,`owner/rate/email/${who}`,6,now))return html(signIn('Please wait before requesting another code.'),429);
  if(email===owner){
   const prior=await state.getWithMetadata(key,{type:'json'});
   if(!prior?.data?.sentAt||now-prior.data.sentAt>=60000){
    const code=String(crypto.getRandomValues(new Uint32Array(1))[0]%100000000).padStart(8,'0'),salt=random();
    const next={email,salt,digest:await hash(salt+code),sentAt:now,expires:now+600000,attempts:0,used:false};
    const saved=await state.setJSON(key,next,prior?{onlyIfMatch:prior.etag}:{onlyIfNew:true});
    if(saved.modified){
     try{await sendCode(email,code,{purpose:'publisher-owner'});}
     catch{await state.setJSON(key,{...next,used:true},{onlyIfMatch:saved.etag});return html(signIn('Email delivery is temporarily unavailable. Please try again shortly.'),503);}
    }
   }
  }
  return html(signIn('If this address has owner access, a code is on its way.',true,email));
 }
 if(!await count(state,`owner/rate/verify/${source}`,60,now))return html(signIn('Please wait before trying again.',true,email),429);
 const prior=await state.getWithMetadata(key,{type:'json'}),v=prior?.data,code=form.get('code')||'';
 if(!v||v.used||v.expires<=now||v.attempts>=5)return html(signIn('That code is invalid or expired. Request a new code.',true,email),403);
 const valid=email===owner&&v.email===owner&&/^[0-9]{8}$/.test(code)&&await hash(v.salt+code)===v.digest;
 const result=await state.setJSON(key,{...v,attempts:v.attempts+1,used:valid||v.attempts+1>=5},{onlyIfMatch:prior.etag});
 if(!valid||!result.modified)return html(signIn('That code is invalid or expired.',true,email),403);
 const value=random();await state.setJSON(`owner/sessions/${await hash(value)}`,{email:owner,createdAt:now,expires:now+AGE*1000});
 return response(null,303,{Location:BASE,'Set-Cookie':cookie(value)});
}

const decode=s=>s.replace(/&(?:amp|lt|gt|quot|apos|#39);/g,x=>({'&amp;':'&','&lt;':'<','&gt;':'>','&quot;':'"','&apos;':"'",'&#39;':"'"}[x]));
export function addPublisherNavigation(body){
 const rooms=[];
 for(const match of body.matchAll(/<article\b[\s\S]*?<\/article>/g)){
  const room=match[0].match(/<textarea\b[^>]*\bid="([a-z0-9-]{1,80})"/),name=match[0].match(/<h2\b[^>]*>([\s\S]*?)<\/h2>/);
  if(room&&name)rooms.push({id:room[1],name:decode(name[1].replace(/<[^>]*>/g,''))});
 }
 rooms.sort((a,b)=>a.name.localeCompare(b.name,'en'));
 const options=rooms.map(x=>`<option value="${x.id}">${escape(x.name)}</option>`).join('');
 const nav=`<nav id="publisher-owner-nav" aria-label="Owner navigation"><div class="sr-owner-inner"><span class="sr-owner-badge">Owner view</span><a href="${BASE}">Publisher library</a><form data-native-submit method="get" action="${BASE}owner/jump"><label for="owner-episode-jump">Jump to episode</label><select id="owner-episode-jump" name="episode" required><option value="">Choose a guest…</option>${options}</select><button type="submit">Open</button></form><a href="/">Signal Room site ↗</a><form data-native-submit method="post" action="${BASE}owner/logout" class="sr-owner-logout"><button type="submit">Sign out</button></form></div></nav>`;
 const style='<style id="publisher-owner-nav-style">#publisher-owner-nav{position:sticky;top:0;z-index:100;background:#160d24f5;border-bottom:1px solid #806296;color:#faf6ff;backdrop-filter:blur(12px)}#publisher-owner-nav .sr-owner-inner{max-width:1440px;margin:auto;padding:12px 24px;display:flex;align-items:center;gap:18px;flex-wrap:wrap}#publisher-owner-nav a{color:#ffe054;text-decoration:none;font-size:14px;font-weight:650;white-space:nowrap}#publisher-owner-nav a:hover{text-decoration:underline}#publisher-owner-nav .sr-owner-badge{font-size:11px;text-transform:uppercase;letter-spacing:.1em;color:#d9c4ee;border:1px solid #806296;border-radius:99px;padding:5px 9px;white-space:nowrap}#publisher-owner-nav form{display:flex;align-items:center;gap:8px;margin:0}#publisher-owner-nav label{font-size:12px;color:#d9c4ee;margin:0;white-space:nowrap}#publisher-owner-nav select{width:clamp(140px,20vw,290px);max-width:100%;min-width:0;border:1px solid #806296;background:#251936;color:#faf6ff;border-radius:6px;padding:8px;font:14px system-ui}#publisher-owner-nav button{width:auto;margin:0;border:1px solid #806296;border-radius:6px;background:#ffe054;color:#180d20;padding:8px 12px;font:650 13px system-ui;cursor:pointer}#publisher-owner-nav .sr-owner-logout{margin-left:auto}#publisher-owner-nav .sr-owner-logout button{background:transparent;color:#d9c4ee}#publisher-owner-nav :focus-visible{outline:3px solid #ffe054;outline-offset:3px}@media(max-width:760px){#publisher-owner-nav .sr-owner-inner{padding:10px 16px;gap:12px}#publisher-owner-nav form:not(.sr-owner-logout){order:4;width:100%}#publisher-owner-nav select{flex:1;width:auto}#publisher-owner-nav .sr-owner-logout{margin-left:auto}}</style>';
 return body.replace(/<\/head\s*>/i,style+'$&').replace(/<body\b[^>]*>/i,'$&'+nav);
}
