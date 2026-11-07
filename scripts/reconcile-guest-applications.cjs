/* Read-only Signal Room reconciliation. No notifications or database mutations.
 * DATABASE_URL and NETLIFY_AUTH_TOKEN are required. Optional --since YYYY-MM-DD.
 * Match submission IDs, never email alone: repeat applications can differ.
 */
const {neon}=require('@neondatabase/serverless');
const TEST_NAME=/\btest\b|loop-audit|live-proof|role-test|ui-test|autoreply|scorecard-path|diagnostic/i;
function reconcile(submissions,rows,since='1970-01-01') {
 const ids=new Set(rows.map(x=>x.submission_id));
 const report={since,checked:0,matched:0,tests:[],missing:[]};
 for(const s of submissions){
  if(s.created_at<since)continue;
  const name=(s.data&&s.data.name)||s.name||'';
  if(TEST_NAME.test(name)){report.tests.push(s.id);continue;}
  report.checked++;
  if(ids.has(s.id))report.matched++;
  else report.missing.push({submission_id:s.id,submitted_at:s.created_at});
 }
 return report;
}
async function main(){
 const {DATABASE_URL,NETLIFY_AUTH_TOKEN}=process.env;
 if(!DATABASE_URL||!NETLIFY_AUTH_TOKEN)throw Error('DATABASE_URL and NETLIFY_AUTH_TOKEN are required');
 const i=process.argv.indexOf('--since'),since=i<0?'1970-01-01':process.argv[i+1];
 if(!/^\d{4}-\d{2}-\d{2}$/.test(since||''))throw Error('--since requires YYYY-MM-DD');
 const submissions=[];
 for(let page=1;;page++){
  const r=await fetch(`https://api.netlify.com/api/v1/forms/69c5456bd7d52d00088a50e8/submissions?per_page=100&page=${page}`,{headers:{Authorization:`Bearer ${NETLIFY_AUTH_TOKEN}`}});
  if(!r.ok)throw Error(`Netlify HTTP ${r.status}`);
  const batch=await r.json();submissions.push(...batch);if(batch.length<100)break;
 }
 const sql=neon(DATABASE_URL);
 const rows=await sql`select submission_id from guest_application where submission_id is not null`;
 const result=reconcile(submissions,rows,since);console.log(JSON.stringify(result,null,2));
 if(result.missing.length)process.exitCode=1;
}
module.exports={reconcile};
if(require.main===module)main().catch(e=>{console.error(e.message);process.exitCode=1;});
