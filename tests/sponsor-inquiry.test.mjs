import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {handler}=require('../netlify/functions/submission-created.js');
test('sponsor inquiry uses owner notification and never the guest database',async()=>{
 const oldFetch=global.fetch,oldEnv={...process.env};let calls=[];
 process.env.RESEND_API_KEY='test';process.env.AUTOREPLY_FROM='owner@example.test';process.env.LEAD_NOTIFY_TO='owner@example.test';
 delete process.env.AIRTABLE_PAT;
 global.fetch=async(url,options)=>{calls.push({url,options});return {ok:true};};
 try{
 const event={httpMethod:'POST',body:JSON.stringify({payload:{id:'test-submission',form_name:'sponsor-inquiry',data:{name:'Test',email:'person@example.test',organization:'Example',message:'Campaign'}}})};
 assert.equal((await handler(event)).statusCode,200);assert.equal(calls.length,1);assert.equal(calls[0].url,'https://api.resend.com/emails');
 const mail=JSON.parse(calls[0].options.body);assert.deepEqual(mail.to,['owner@example.test']);assert.equal(mail.subject,'New Signal Room sponsorship inquiry');assert.equal(calls[0].options.headers['Idempotency-Key'],'sponsor-test-submission');
 calls=[];const bot=JSON.parse(event.body);bot.payload.data['bot-field']='spam';await handler({...event,body:JSON.stringify(bot)});assert.equal(calls.length,0);
 global.fetch=async()=>({ok:false});assert.equal((await handler(event)).statusCode,502);
 }finally{global.fetch=oldFetch;for(const key of Object.keys(process.env))if(!(key in oldEnv))delete process.env[key];Object.assign(process.env,oldEnv);}
});
