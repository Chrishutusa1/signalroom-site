import { getStore } from '@netlify/blobs';
import { createReviewHandler } from './review-core.mjs';

export default async (request,context)=>{
 try{
  const state=getStore({name:'sr-review-access',consistency:'strong'});
  const content=getStore({name:'sr-review-content',consistency:'strong'});
  return await createReviewHandler({state,content,
   sendCode:async(email,code)=>{
    const key=Netlify.env.get('RESEND_API_KEY'),from=Netlify.env.get('AUTOREPLY_FROM');
    if(!key||!from)throw new Error('Email is not configured');
    const res=await fetch('https://api.resend.com/emails',{method:'POST',headers:{Authorization:`Bearer ${key}`,'Content-Type':'application/json'},body:JSON.stringify({from,to:[email],subject:'Your Signal Room review code',text:`Your Signal Room review code is ${code}.\n\nThis code expires in ten minutes and can be used once. If you did not request it, you can ignore this email.`})});
    if(!res.ok)throw new Error('Email delivery failed');
   },
   readMedia:async(key,range,size)=>{
    let info={status:200,headers:{'Content-Length':String(size)}};
    const store=getStore({name:'sr-review-content',consistency:'strong',fetch:async(input,init)=>{
      const h=new Headers(init?.headers);
      // The SDK can first obtain a signed URL; only the object request receives Range.
      const isObject=!h.get('accept')?.includes('json');
      if(range&&isObject)h.set('range',range);
      const r=await fetch(input,{...init,headers:h});
      if(isObject&&range){
        if(r.status===416){info={status:416,headers:{'Content-Range':`bytes */${size}`}};await r.body?.cancel();return new Response('',{status:200});}
        if(r.status!==206){await r.body?.cancel();throw new Error('Media range unavailable');}
        info={status:206,headers:{'Content-Length':r.headers.get('content-length'),'Content-Range':r.headers.get('content-range')}};
        // get(stream) expects 200; preserve the actual 206 status for the browser.
        return new Response(r.body,{status:200,headers:r.headers});
      }
      return r;
    }});
    const body=await store.get(key,{type:'stream'});return body?{body,...info}:null;
   }
  })(request,context);
 }catch(error){
  console.error('Guest review unavailable:',error?.name||'Error');
  return new Response('The review room is temporarily unavailable. Please try again shortly.',{status:503,headers:{'Cache-Control':'no-store','X-Robots-Tag':'noindex, nofollow'}});
 }
};
export const config={path:'/review/*'};
