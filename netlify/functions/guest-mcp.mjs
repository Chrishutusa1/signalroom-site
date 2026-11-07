import {getStore} from '@netlify/blobs';
import {McpServer} from '@modelcontextprotocol/sdk/server/mcp.js';
import {WebStandardStreamableHTTPServerTransport} from '@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js';
import {z} from 'zod';
import {verifyGuestToken,allowedEpisodes,readMaterial,METADATA,SCOPE} from '../lib/guest-oauth.mjs';
export const config={path:'/mcp/private'};
export default async function(request){
 const headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'};
 const origin=request.headers.get('origin');
 if(origin&&!['https://signalroompodcast.com','https://chatgpt.com'].includes(origin))return new Response('Forbidden',{status:403,headers});
 let identity;
 try{
  const auth=request.headers.get('authorization')||'';
  if(!auth.startsWith('Bearer ')||auth.length>16000)throw new Error();
  identity=await verifyGuestToken(auth.slice(7));
 }catch{return new Response(null,{status:401,headers:{...headers,'WWW-Authenticate':`Bearer resource_metadata="${METADATA}", scope="${SCOPE}"`}});}
 if(request.method!=='POST')return new Response(null,{status:405,headers:{...headers,Allow:'POST'}});
 const bytes=await request.arrayBuffer();
 if(bytes.byteLength>16384)return new Response('Request too large',{status:413,headers});
 const state=getStore({name:'sr-review-access',consistency:'strong'}),content=getStore({name:'sr-review-content',consistency:'strong'});
 const server=new McpServer({name:'com.signalroompodcast/guest-materials',version:'1.0.0'});
 const securitySchemes=[{type:'oauth2',scopes:[SCOPE]}];
 const annotations={readOnlyHint:true,destructiveHint:false,openWorldHint:false};
 server.registerTool('list_guest_materials',{description:'List text materials explicitly assigned to the signed-in guest.',inputSchema:{},annotations,_meta:{securitySchemes}},async()=>{
  const result=[];
  for(const episode of await allowedEpisodes(state,identity)){
   const manifest=await content.get(`${episode}/manifest`,{type:'json'});
   const files=Object.entries(manifest?.files||{}).filter(([path,item])=>!path.includes('..')&&!path.startsWith('/')&&!path.includes('\\')&&['text/plain','text/markdown','text/vtt','application/x-subrip'].includes(item.type?.split(';')[0])&&Number.isFinite(item.size)&&item.size<=200000).map(([path])=>path);
   result.push({episode,files});
  }
  return {content:[{type:'text',text:JSON.stringify({materials:result,message:result.length?'Only assigned text materials are listed.':'No episode materials have been assigned to this account.'})}]};
 });
 server.registerTool('read_guest_material',{description:'Read one approved text material from an assigned episode.',inputSchema:{episode:z.string().regex(/^[a-z0-9-]{1,80}$/),path:z.string().min(1).max(250)},annotations,_meta:{securitySchemes}},async({episode,path})=>{
  try{return {content:[{type:'text',text:await readMaterial(state,content,identity,episode,path)}]};}
  catch{return {isError:true,content:[{type:'text',text:'Material unavailable or not assigned to this account.'}]};}
 });
 const transport=new WebStandardStreamableHTTPServerTransport({sessionIdGenerator:undefined,enableJsonResponse:true});
 await server.connect(transport);
 try{
  const response=await transport.handleRequest(new Request(request.url,{method:'POST',headers:request.headers,body:bytes}));
  const data=await response.arrayBuffer(),out=new Headers(response.headers);
  for(const [k,v] of Object.entries(headers))out.set(k,v);
  return new Response(data.byteLength?data:null,{status:response.status,headers:out});
 }finally{await server.close();}
}
