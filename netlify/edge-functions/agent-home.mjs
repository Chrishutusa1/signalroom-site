export default async function(request, context) {
  const response = await context.next();
  const headers = new Headers(response.headers);
  headers.set('Link', '<https://signalroompodcast.com/llms.txt>; rel="describedby"; type="text/markdown", <https://signalroompodcast.com/.well-known/api-catalog>; rel="api-catalog"');
  headers.set('Vary', [...new Set([...(headers.get('Vary') || '').split(',').map(s=>s.trim()).filter(Boolean), 'Accept'])].join(', '));
  const accepted = (request.headers.get('Accept') || '').split(',').map(part=>{
    const [type,...params]=part.trim().split(';');
    const q=params.find(p=>p.trim().startsWith('q='));
    return {type:type.toLowerCase(), q:q ? Number(q.trim().slice(2)) : 1};
  });
  const md=accepted.find(t=>t.type==='text/markdown');
  const html=accepted.find(t=>t.type==='text/html');
  if (['GET','HEAD'].includes(request.method) && response.status===200 && md?.q>0 && md.q >= (html?.q || 0)) {
    const markdown = await fetch(new URL('/index.md',request.url));
    if (markdown.ok) {
      headers.set('Content-Type','text/markdown; charset=utf-8');
      headers.set('Cache-Control','no-store');
      for(const name of ['content-length','content-encoding','etag','netlify-cdn-cache-control','age']) headers.delete(name);
      return new Response(request.method==='HEAD'?null:markdown.body,{status:200,headers});
    }
  }
  return new Response(response.body,{status:response.status,headers});
}
export const config = {path:'/'};
