const encoder = new TextEncoder();
const escape = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const hash = async s => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', encoder.encode(s))), b=>b.toString(16).padStart(2,'0')).join('');
const random = () => Array.from(crypto.getRandomValues(new Uint8Array(32)),b=>b.toString(16).padStart(2,'0')).join('');
const headers = {'Cache-Control':'private, no-store','Netlify-CDN-Cache-Control':'no-store','X-Robots-Tag':'noindex, nofollow, noarchive','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; media-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"};
const response = (body,status=200,extra={}) => new Response(body,{status,headers:{...headers,...extra}});
const cookieName = episode => `__Secure-sr_${episode.replaceAll('-','_')}`;
const cookie = (episode,token,age=28800) => `${cookieName(episode)}=${token}; Path=/review/${episode}/; HttpOnly; Secure; SameSite=Strict; Max-Age=${age}`;
const page = (episode,message='',verify=false,email='') => `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Guest review | The Signal Room</title><style>*{box-sizing:border-box}body{margin:0;background:#160d24;color:#f9f6ff;font:17px/1.6 system-ui;min-height:100vh;display:grid;place-items:center;padding:24px}.card{width:min(100%,480px);background:#251936;border:1px solid #4e3b64;border-radius:18px;padding:36px}.brand{color:#edce65;font-size:14px;letter-spacing:.2em}h1{font-size:30px;line-height:1.2}p{color:#d4cadd}label{display:block;margin:20px 0 8px}input,button{font:inherit;width:100%;border-radius:8px;padding:12px}input{border:1px solid #a393b6;background:#160d24;color:white}button{background:#edce65;color:#1a1226;font-weight:700;border:0;margin-top:20px;cursor:pointer}a{color:#edce65}.message{border-left:3px solid #edce65;padding-left:14px}</style></head><body><main class="card"><div class="brand">THE SIGNAL ROOM</div><h1>${verify?'Check your email':'Your guest review room'}</h1><p>${verify?'Enter the eight-digit code sent to your approved email address. It expires in ten minutes.':'Enter the email address associated with your invitation to open your episode package.'}</p>${message?`<p class="message" role="status">${escape(message)}</p>`:''}<form method="post" action="/review/${episode}/${verify?'verify':'request'}"><label for="email">Email address</label><input id="email" name="email" type="email" autocomplete="email" required maxlength="254" value="${escape(email)}">${verify?'<label for="code">Verification code</label><input id="code" name="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{8}" maxlength="8" required>':''}<button>${verify?'Open review room':'Email me a code'}</button></form>${verify?`<p><a href="/review/${episode}/">Request a new code</a></p>`:''}<p style="font-size:14px">Access is limited to invited reviewers.</p></main></body></html>`;
const submitScript = `document.addEventListener('submit',async event=>{const form=event.target;if(!(form instanceof HTMLFormElement))return;event.preventDefault();const button=form.querySelector('button');button.disabled=true;button.textContent='Please wait…';try{const result=await fetch(form.action,{method:'POST',credentials:'same-origin',body:new URLSearchParams(new FormData(form))});const text=await result.text();if(!result.headers.get('content-type')?.includes('text/html'))throw new Error('Please refresh the page and try again.');const parsed=new DOMParser().parseFromString(text,'text/html');document.head.replaceWith(parsed.head);document.body.replaceWith(parsed.body);history.replaceState(null,'',location.pathname.replace(/\\/(request|verify|logout)$/, '/'));}catch(error){button.disabled=false;button.textContent='Try again';let message=document.getElementById('submit-error');if(!message){message=document.createElement('p');message.id='submit-error';message.setAttribute('role','alert');form.append(message);}message.textContent='We could not complete that request. Please try again.';}});`;
const html = (body,status=200,extra={}) => {
 const nonce=random();
 const rendered=body.replace('</body>',`<script nonce="${nonce}">${submitScript}</script></body>`);
 return response(rendered,status,{'Content-Type':'text/html; charset=utf-8','Content-Security-Policy':headers['Content-Security-Policy']+`; script-src 'nonce-${nonce}'; connect-src 'self'`,...extra});
};
async function count(store,key,limit,now,window=3600000){
  for(let i=0;i<5;i++){
    const prior=await store.getWithMetadata(key,{type:'json'});
    const v=prior?.data?.until>now?prior.data:{n:0,until:now+window};
    if(v.n>=limit)return false;
    const result=await store.setJSON(key,{n:v.n+1,until:v.until},prior?{onlyIfMatch:prior.etag}:{onlyIfNew:true});
    if(result.modified)return true;
  }
  return false;
}
export function createReviewHandler({state,content,sendCode,readMedia,now=()=>Date.now()}){
 return async(request,context={})=>{
  const url=new URL(request.url),m=url.pathname.match(/^\/review\/([a-z0-9-]{1,80})(?:\/(.*))?$/);
  if(!m)return response('Not found',404);
  const [,episode,rawAction='']=m;
  if(!url.pathname.endsWith('/')&&!rawAction&&request.method==='GET')return response(null,303,{Location:`/review/${episode}/`});
  let action;try{action=decodeURIComponent(rawAction);}catch{return response('Not found',404);}
  if(action.includes('..')||action.includes('\\')||action.includes('\0'))return response('Not found',404);
  const grant=await state.get(`grants/${episode}`,{type:'json'});
  if(!grant?.enabled)return response('This review room is unavailable.',404);
  const allowed=email=>grant.emails?.includes(email);
  const time=now();
  if(request.method==='POST'){
    if(request.headers.get('origin')!==url.origin)return response('Request not allowed',403);
    if(!['request','verify','logout'].includes(action))return response('Not found',404);
    if(action==='logout'){
      const token=request.headers.get('cookie')?.split(';').map(s=>s.trim()).find(s=>s.startsWith(cookieName(episode)+'='))?.split('=')[1];
      if(token&&/^[a-f0-9]{64}$/.test(token))await state.delete(`sessions/${await hash(token)}`);
      return response(null,303,{Location:`/review/${episode}/`,'Set-Cookie':cookie(episode,'',0)});
    }
    if(Number(request.headers.get('content-length'))>2048)return response('Request too large',413);
    const body=await request.text();if(body.length>2048)return response('Request too large',413);
    const form=new URLSearchParams(body),email=(form.get('email')||'').trim().toLowerCase();
    if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)||email.length>254)return html(page(episode,'Enter a valid email address.'),400);
    const who=await hash(`${episode}:${email}`),ip=await hash(`${episode}:${context.ip||'unknown'}`);
    const key=`otp/${who}`;
    if(action==='request'){
      if(!await count(state,`rate/ip/${ip}`,20,time)||!await count(state,`rate/email/${who}`,6,time))return html(page(episode,'Please wait before requesting another code.'),429);
      if(allowed(email)){
        const old=await state.getWithMetadata(key,{type:'json'});
        if(!old?.data?.sentAt||time-old.data.sentAt>=60000){
          const bytes=crypto.getRandomValues(new Uint32Array(1));
          const code=String(bytes[0]%100000000).padStart(8,'0');
          const salt=random();
          const next={digest:await hash(salt+code),salt,email,episode,sentAt:time,expires:time+600000,attempts:0,used:false};
          const saved=await state.setJSON(key,next,old?{onlyIfMatch:old.etag}:{onlyIfNew:true});
          if(saved.modified){
            try{await sendCode(email,code);}catch{await state.setJSON(key,{...next,used:true},{onlyIfMatch:saved.etag});return html(page(episode,'Email delivery is temporarily unavailable. Please try again shortly.'),503);}
          }
        }
      }
      return html(page(episode,'If this address is invited, a code is on its way.',true,email));
    }
    if(!await count(state,`rate/verify/${ip}`,60,time))return html(page(episode,'Please wait before trying again.',true,email),429);
    const old=await state.getWithMetadata(key,{type:'json'}),v=old?.data,code=form.get('code')||'';
    const valid=allowed(email)&&v&&!v.used&&v.expires>time&&v.attempts<5&&/^[0-9]{8}$/.test(code)&&await hash(v.salt+code)===v.digest;
    if(!v||v.used||v.expires<=time||v.attempts>=5)return html(page(episode,'That code is invalid or expired. Request a new code.',true,email),403);
    const result=await state.setJSON(key,{...v,attempts:v.attempts+1,used:valid||v.attempts+1>=5},{onlyIfMatch:old.etag});
    if(!valid||!result.modified)return html(page(episode,'That code is invalid or expired.',true,email),403);
    const token=random();
    await state.setJSON(`sessions/${await hash(token)}`,{episode,email,expires:time+28800000});
    return response(null,303,{Location:`/review/${episode}/`,'Set-Cookie':cookie(episode,token)});
  }
  if(!['GET','HEAD'].includes(request.method))return response('Method not allowed',405);
  const token=request.headers.get('cookie')?.split(';').map(s=>s.trim()).find(s=>s.startsWith(cookieName(episode)+'='))?.split('=')[1];
  const session=token&&/^[a-f0-9]{64}$/.test(token)?await state.get(`sessions/${await hash(token)}`,{type:'json'}):null;
  if(!session||session.episode!==episode||session.expires<=time||!allowed(session.email))return action?response('Please sign in to this review room.',401):html(page(episode));
  const manifest=await content.get(`${episode}/manifest`,{type:'json'});
  if(!manifest)return response('The review package is being prepared.',503);
  const path=action===''?'index.html':action.startsWith('files/')?action.slice(6):null;
  const item=path&&manifest.files[path];
  if(!item)return response('Not found',404);
  const extra={'Content-Type':item.type,'Accept-Ranges':'bytes'};
  if(url.searchParams.has('download'))extra['Content-Disposition']=`attachment; filename="${path.split('/').pop().replace(/[^a-zA-Z0-9._-]/g,'_')}"`;
  if(request.method==='HEAD')return response(null,200,{...extra,'Content-Length':String(item.size)});
  if(path==='index.html')return html(await content.get(`${episode}/index.html`));
  const range=request.headers.get('range');
  if(range&&!/^bytes=\d*-\d*$/.test(range))return response('Unsupported range',416,{'Content-Range':`bytes */${item.size}`});
  const media=await readMedia(`${episode}/${path}`,range,item.size);
  if(!media)return response('File unavailable',404);
  return response(media.body,media.status,{...extra,...media.headers});
 };
}
