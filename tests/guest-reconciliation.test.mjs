import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const {reconcile}=createRequire(import.meta.url)('../scripts/reconcile-guest-applications.cjs');
test('repeat applicant with a new submission ID remains missing until persisted',()=>{
 const rows=[{submission_id:'older',email:'same@example.test'}];
 const subs=[{id:'new',created_at:'2026-10-05',data:{name:'Applicant',email:'same@example.test'}},{id:'test',created_at:'2026-10-26',data:{name:'TEST - delete'}}];
 const result=reconcile(subs,rows,'2026-10-01');assert.equal(result.missing[0].submission_id,'new');assert.equal(result.tests.length,1);
 assert.equal(reconcile(subs,[...rows,{submission_id:'new'}]).missing.length,0);
 assert.equal(reconcile(subs,rows,'2026-11-01').checked,0);
});
