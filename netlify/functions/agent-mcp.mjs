import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { WebStandardStreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js';

export const config = { path: '/mcp' };
export default async function(request) {
  const origin=request.headers.get('origin');
  if(origin && origin!==new URL(request.url).origin) return new Response('Forbidden',{status:403});
  if(request.method==='GET' || request.method==='DELETE') return new Response(null,{status:405,headers:{Allow:'POST'}});
  if(Number(request.headers.get('content-length')||0)>16384) return new Response('Request too large',{status:413});
  if(request.method==='POST') {
    const bytes=await request.arrayBuffer();
    if(bytes.byteLength>16384) return new Response('Request too large',{status:413});
    request=new Request(request.url,{method:'POST',headers:request.headers,body:bytes});
  }
  const server=new McpServer({name:'com.signalroompodcast/public-reading',version:'1.0.0'});
  for(const [name,path,mimeType] of [['reading-guide','/llms.txt','text/markdown'],['sitemap','/sitemap.xml','application/xml']]) {
    const uri='https://signalroompodcast.com'+path;
    server.registerResource(name,uri,{mimeType,description:'Public Signal Room '+name},async()=>{
      const res=await fetch(uri,{signal:AbortSignal.timeout(10000),redirect:'error'});
      if(!res.ok) throw new Error('Public resource unavailable');
      return {contents:[{uri,mimeType,text:await res.text()}]};
    });
  }
  const transport=new WebStandardStreamableHTTPServerTransport({sessionIdGenerator:undefined,enableJsonResponse:true});
  await server.connect(transport);
  try {
    const response=await transport.handleRequest(request);
    const body=await response.arrayBuffer();
    const headers=new Headers(response.headers);headers.set('Cache-Control','no-store');
    return new Response(body.byteLength?body:null,{status:response.status,headers});
  } finally {await server.close();}
}
