import { randomUUID } from 'node:crypto';
export const config = {path:'/a2a'};
const directory='Signal Room public reading resources:\nhttps://signalroompodcast.com/llms.txt — reading guide\nhttps://signalroompodcast.com/episodes — episode archive\nhttps://signalroompodcast.com/sitemap.xml — canonical page index\nhttps://signalroompodcast.com/contact — human inquiries\nRead the relevant episode and cite its canonical URL. This directory service does not answer clinical questions or perform transactions.';
export default async function(request) {
  if(request.method!=='POST') return new Response(null,{status:405,headers:{Allow:'POST'}});
  if(Number(request.headers.get('content-length')||0)>16384) return new Response('Request too large',{status:413});
  const raw=await request.text();
  if(new TextEncoder().encode(raw).length>16384) return new Response('Request too large',{status:413});
  let rpc;
  const reply=(body)=>Response.json({jsonrpc:'2.0',id:rpc?.id??null,...body},{headers:{'Cache-Control':'no-store'}});
  const error=(code,message)=>reply({error:{code,message}});
  try{rpc=JSON.parse(raw);}catch{return error(-32700,'Parse error');}
  if(!rpc || Array.isArray(rpc)||rpc.jsonrpc!=='2.0'||!['string','number'].includes(typeof rpc.id)||typeof rpc.method!=='string') return error(-32600,'Invalid Request');
  if(['tasks/get','tasks/cancel'].includes(rpc.method)) return error(-32001,'Task not found');
  if(rpc.method!=='message/send') return error(-32601,'Method not found');
  const m=rpc.params?.message;
  if(!m || m.kind!=='message'||m.role!=='user'||typeof m.messageId!=='string'||!Array.isArray(m.parts)||!m.parts.length||m.parts.some(p=>p.kind!=='text'||typeof p.text!=='string')) return error(-32602,'Provide a user message containing text parts');
  if(m.taskId) return error(-32001,'Task not found');
  const modes=rpc.params?.configuration?.acceptedOutputModes;
  if(modes && (!Array.isArray(modes)||!modes.includes('text/plain'))) return error(-32005,'Only text/plain output is supported');
  return reply({result:{kind:'message',messageId:randomUUID(),role:'agent',parts:[{kind:'text',text:directory}]}});
}
