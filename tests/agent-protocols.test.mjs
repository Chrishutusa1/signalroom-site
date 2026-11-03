import test from 'node:test';
import assert from 'node:assert/strict';
import mcp from '../netlify/functions/agent-mcp.mjs';
import a2a from '../netlify/functions/agent-a2a.mjs';
const req=(path,body,headers={})=>new Request('https://signalroompodcast.com/'+path,{method:'POST',headers:{'Content-Type':'application/json',Accept:'application/json, text/event-stream',...headers},body:JSON.stringify(body)});
test('MCP initializes and lists only public resources',async()=>{
 const r=await mcp(req('mcp',{jsonrpc:'2.0',id:1,method:'initialize',params:{protocolVersion:'2025-11-25',capabilities:{},clientInfo:{name:'test',version:'1'}}}));
 assert.equal(r.status,200);const init=await r.json();assert.equal(init.result.protocolVersion,'2025-11-25');assert(init.result.capabilities.resources);
 const list=await (await mcp(req('mcp',{jsonrpc:'2.0',id:2,method:'resources/list'},{'MCP-Protocol-Version':'2025-11-25'}))).json();
 assert.equal(list.result.resources.length,2);
 assert(list.result.resources.every(r=>r.uri.startsWith('https://signalroompodcast.com/')));
});
test('MCP rejects foreign origins and oversized requests',async()=>{
 assert.equal((await mcp(req('mcp',{}, {Origin:'https://evil.example'}))).status,403);
 assert.equal((await mcp(req('mcp',{data:'x'.repeat(17000)}))).status,413);
});
test('A2A returns directory message and rejects invalid or unsupported requests',async()=>{
 const message={kind:'message',role:'user',messageId:'test',parts:[{kind:'text',text:'Find episodes'}]};
 const call=async(method,params)=> (await a2a(req('a2a',{jsonrpc:'2.0',id:1,method,params}))).json();
 const r=await call('message/send',{message});assert.equal(r.result.kind,'message');assert(r.result.parts[0].text.includes('/episodes'));
 assert.equal((await call('message/send',{})).error.code,-32602);
 assert.equal((await call('message/stream',{})).error.code,-32601);
 assert.equal((await call('tasks/get',{id:'unknown'})).error.code,-32001);
});
