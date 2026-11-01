import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
'use strict';
const fs = require('node:fs'), assert = require('node:assert/strict');
const ts = require('typescript');
const text = fs.readFileSync(new URL('../e2e/history-missing-detail.spec.ts', import.meta.url), 'utf8');
const file = ts.createSourceFile('history.spec.ts', text, ts.ScriptTarget.Latest, true);
const fn = file.statements.find(n => ts.isFunctionDeclaration(n) && n.name?.text === 'checkInitialHistoryRequests');
assert(fn);
const js = ts.transpileModule(fn.getText(file), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
const check = new Function('URL', js + '; return checkInitialHistoryRequests;')(URL);
const recorderNode = file.statements.find(n => ts.isFunctionDeclaration(n) && n.name?.text === 'recordHistoryRequests');
assert(recorderNode);
const recorderJs = ts.transpileModule(recorderNode.getText(file), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
const record = new Function('URL', recorderJs + '; return recordHistoryRequests;')(URL);
const auditNode = file.statements.find(n => ts.isFunctionDeclaration(n) && n.name?.text === 'historyRequestAudit');
assert(auditNode);
const auditJs = ts.transpileModule(auditNode.getText(file), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
const audit = new Function('URL', auditJs + '; return historyRequestAudit;')(URL);
const origin = 'http://127.0.0.1:3107', f = '/api/finlens/companies/AAA/freshness', a = '/api/finlens/companies/AAA/financials/annual', q = '/api/finlens/companies/AAA/financials/quarters';
const row = (path, start, extra = {}) => ({ request: {}, method: 'GET', url: origin + path, pin: path === f ? undefined : '0', bodyAbsent: true, start, ...extra, ...(extra.status === 200 && path !== f ? {version:'0'} : {}) });
const replay = () => [row(f,1,{failed:2,error:'net::ERR_ABORTED'}),row(f,3,{status:200,finished:4}),row(a,5,{failed:6,error:'net::ERR_ABORTED'}),row(a,7,{status:200,finished:8}),row(q,9,{status:200,finished:10})];
const good = () => [row(f,1,{status:200,finished:2}),row(a,3,{status:200,finished:4}),row(q,5,{status:200,finished:6})];
let n=0; function test(name, fn) { fn(); console.log(`ok ${++n} - ${name}`); }
test('observed two replays with successful replacements',()=>assert.equal(check(replay(),11).length,2));
test('zero cancellations and three completed requests',()=>assert.deepEqual(check(good(),11),[]));
test('duplicate cancellation rejects',()=>{const x=replay();x.push(row(a,8,{failed:8,error:'net::ERR_ABORTED'}));assert.throws(()=>check(x,11));});
test('wrong pin rejects',()=>{const x=replay();x[2].pin='1';assert.throws(()=>check(x,11));});
test('wrong method rejects',()=>{const x=replay();x[0].method='POST';assert.throws(()=>check(x,11));});
test('wrong company cancellation rejects',()=>{const x=replay();x[0].url=origin+'/api/finlens/companies/BBB/freshness';assert.throws(()=>check(x,11));});
test('missing replacement rejects',()=>{const x=replay();x.splice(1,1);assert.throws(()=>check(x,11));});
test('failed replacement rejects',()=>{const x=replay();x[1].status=503;assert.throws(()=>check(x,11));});
test('unrelated aborted request rejects',()=>{const x=good();x.push(row('/api/finlens/companies/AAA/sources',5,{failed:6,error:'net::ERR_ABORTED'}));assert.throws(()=>check(x,11));});
test('late failure rejects',()=>{const x=replay();x[0].failed=12;assert.throws(()=>check(x,11));});
test('late start or replacement rejects',()=>{const x=replay();x[3].finished=12;assert.throws(()=>check(x,11));});
test('duplicate successful response rejects',()=>{const x=good();x.push(row(a,5,{status:200,finished:6}));assert.throws(()=>check(x,11));});
test('other error rejects',()=>{const x=replay();x[0].error='net::ERR_FAILED';assert.throws(()=>check(x,11));});
test('cross-request notification order may invert but identity remains distinct',()=>{const x=replay();x[1].start=0;assert.equal(check(x,11).length,2);const y=replay();y[1].request=y[0].request;assert.throws(()=>check(y,11));});
test('request body and response version must match the declared scope',()=>{const x=good();x[0].bodyAbsent=false;assert.throws(()=>check(x,11));const y=good();y[1].version='1';assert.throws(()=>check(y,11));});
test('audit preserves the nullable baseline and bounded query without request objects',()=>{const x=good();x[1].url+='?fiscal_year=2024';const result=audit(x,[],null);assert.equal(result.boundary,null);assert.equal(result.rows[1].query,'?fiscal_year=2024');assert.equal('request' in result.rows[1],false);assert.equal(audit(x,[],9).boundary,9);});
test('wrong origin and query reject',()=>{const x=good();x[0].url='http://example.test'+f;assert.throws(()=>check(x,11));const y=good();y[1].url+='?fiscal_year=2024';assert.throws(()=>check(y,11));});
function fakeRequest(path, pin, error = 'net::ERR_ABORTED') { return { method:()=> 'GET', url:()=>origin+path, postData:()=>null,
  headers:()=>pin === undefined ? {} : {'x-finlens-data-version':pin}, failure:()=>({errorText:error}) }; }
function harness(seedQuarter = true) { const handlers={}; const page={ on:(name,fn)=>{handlers[name]=fn;} };
  const audit=record(page), h={audit,emit:(name,value)=>handlers[name](value)};
  // Existing freshness/annual recorder cases receive an explicit valid quarter
  // control. Quarter-specific cases opt out and supply their own complete scope.
  if(seedQuarter) emitSuccess(h,fakeRequest(q,'0')); return h; }
function emitSuccess(h, req) { h.emit('request',req);h.emit('response',{request:()=>req,status:()=>200,headers:()=>req.headers()});h.emit('requestfinished',req); }
function emitReplay(h, path, pin) { const old=fakeRequest(path,pin), next=fakeRequest(path,pin);
  h.emit('request',old);h.emit('requestfailed',old);emitSuccess(h,next);return {old,next}; }
test('recorder binds request objects and orders success and failure',()=>{const h=harness();const x=emitReplay(h,f,undefined);emitSuccess(h,fakeRequest(a,'0'));const b=h.audit.boundary();assert.equal(check(h.audit.records,b,h.audit.violations).length,1);const old=h.audit.records.find(r=>r.request===x.old),next=h.audit.records.find(r=>r.request===x.next);assert(old.start<old.failed);assert(next.start<next.finished);});
test('all legal notification interleavings preserve distinct initial replay identities',()=>{for(const path of [f,a,q])for(const order of ['AaBHF','ABaHF','ABHaF','ABHFa','BAaHF','BAHaF','BAHFa','BHAaF','BHAFa','BHFAa']){const h=harness(false),pin=path===f?undefined:'0',old=fakeRequest(path,pin),good=fakeRequest(path,pin);for(const event of order){if(event==='A')h.emit('request',old);if(event==='a')h.emit('requestfailed',old);if(event==='B')h.emit('request',good);if(event==='H')h.emit('response',{request:()=>good,status:()=>200,headers:()=>good.headers()});if(event==='F')h.emit('requestfinished',good);}for(const other of [f,a,q].filter(p=>p!==path))emitSuccess(h,fakeRequest(other,other===f?undefined:'0'));assert.equal(check(h.audit.records,h.audit.boundary(),h.audit.violations).length,1,`${path}/${order}`);}});
test('unknown scoped response, finish and failure reject against valid baseline',()=>{for(const event of ['response','requestfinished','requestfailed']){const h=harness(),req=fakeRequest(f);emitSuccess(h,fakeRequest(f));emitSuccess(h,fakeRequest(a,'0'));const before=h.audit.boundary();assert.deepEqual(check(h.audit.records,before,h.audit.violations),[]);h.emit(event,event==='response'?{request:()=>req,status:()=>200}:req);assert.equal(h.audit.violations.length,1);assert.throws(()=>check(h.audit.records,before,h.audit.violations),/Unbound request lifecycle event/);}});
test('unknown unrelated failure rejects',()=>{const h=harness();emitSuccess(h,fakeRequest(f));emitSuccess(h,fakeRequest(a,'0'));h.emit('requestfailed',fakeRequest('/other'));assert.throws(()=>check(h.audit.records,h.audit.boundary(),h.audit.violations));});
test('post-boundary scoped start rejects',()=>{const h=harness();emitSuccess(h,fakeRequest(f));emitSuccess(h,fakeRequest(a,'0'));const b=h.audit.boundary();h.emit('request',fakeRequest(a,'0'));assert.throws(()=>check(h.audit.records,b,h.audit.violations));});
test('post-boundary scoped finish or failure rejects with valid pre-boundary control',()=>{for(const terminal of ['requestfinished','requestfailed']) for(const late of [false,true]){const h=harness(),old=fakeRequest(f);h.emit('request',old);const row=h.audit.records.at(-1);if(terminal==='requestfinished') h.emit('response',{request:()=>old,status:()=>200,headers:()=>({})});else emitSuccess(h,fakeRequest(f));emitSuccess(h,fakeRequest(a,'0'));if(!late) h.emit(terminal,old);const b=h.audit.boundary();if(late) h.emit(terminal,old);const event=terminal==='requestfinished'?row.finished:row.failed;assert.equal(row.request,old);assert(row.start<b);assert.equal(event>b,late);if(late) assert.throws(()=>check(h.audit.records,b,h.audit.violations));else assert.doesNotThrow(()=>check(h.audit.records,b,h.audit.violations));}});
test('200 without requestfinished rejects',()=>{const h=harness(),req=fakeRequest(f);h.emit('request',req);h.emit('response',{request:()=>req,status:()=>200,headers:()=>({})});emitSuccess(h,fakeRequest(a,'0'));assert.throws(()=>check(h.audit.records,h.audit.boundary(),h.audit.violations));});
test('extra scoped pending request rejects',()=>{const h=harness();emitSuccess(h,fakeRequest(f));emitSuccess(h,fakeRequest(a,'0'));h.emit('request',fakeRequest(a,'0'));assert.throws(()=>check(h.audit.records,h.audit.boundary(),h.audit.violations));});
test('quarter discovery allows zero or one cancellation with an exact distinct completed peer',()=>{
  const x=good();assert.deepEqual(check(x,11),[]);
  const old=row(q,7,{failed:8,error:'net::ERR_ABORTED'});x.push(old);
  assert.deepEqual(check(x,11),[`GET ${q}: net::ERR_ABORTED`]);
  old.request=x[2].request;assert.throws(()=>check(x,11));
});
for(const [name,mutate] of [
  ['wrong pin',x=>{x[3].pin='1';}], ['wrong method',x=>{x[3].method='POST';}],
  ['raw body present',x=>{x[3].bodyAbsent=false;}], ['wrong company',x=>{x[3].url=origin+q.replace('/AAA/','/BBB/');}],
  ['foreign origin',x=>{x[3].url='https://example.test'+q;}],
  ['selected-window query',x=>{x[3].url+='?period=2025-01-01%2C2025-03-31&period=2025-04-01%2C2025-06-30';}],
  ['missing peer',x=>{x.splice(2,1);}], ['failed peer',x=>{x[2].status=503;}],
  ['wrong response version',x=>{x[2].version='1';}], ['headers without finish',x=>{delete x[2].finished;}],
  ['duplicate cancellation',x=>{x.push(row(q,9,{failed:10,error:'net::ERR_ABORTED'}));}],
  ['duplicate success',x=>{x.push(row(q,9,{status:200,finished:10}));}],
  ['cancel after headers',x=>{x[3].status=200;}], ['late terminal',x=>{x[3].failed=12;}],
  ['post-baseline start',x=>{x.push(row(q,11,{status:200,finished:12}));}],
]) test(`quarter discovery rejects ${name} after a valid control`,()=>{
  const x=good();x.push(row(q,7,{failed:8,error:'net::ERR_ABORTED'}));assert.equal(check(x,11).length,1);
  mutate(x);assert.throws(()=>check(x,11));
});
test('quarter recorder rejects raw JSON null bodies and unknown scoped terminal events',()=>{
  for(const raw of ['null',' null ','']) {
    const h=harness(false);emitSuccess(h,fakeRequest(f));emitSuccess(h,fakeRequest(a,'0'));
    const old={...fakeRequest(q,'0'),postData:()=>raw};h.emit('request',old);h.emit('requestfailed',old);emitSuccess(h,fakeRequest(q,'0'));
    assert.equal(h.audit.records.find(r=>r.request===old).bodyAbsent,false);
    assert.throws(()=>check(h.audit.records,h.audit.boundary(),h.audit.violations));
  }
  for(const event of ['response','requestfinished','requestfailed']) {
    const h=harness();emitSuccess(h,fakeRequest(f));emitSuccess(h,fakeRequest(a,'0'));
    const before=h.audit.boundary();assert.deepEqual(check(h.audit.records,before,h.audit.violations),[]);
    const unknown=fakeRequest(q,'0');h.emit(event,event==='response'?{request:()=>unknown,status:()=>200}:unknown);
    assert.equal(h.audit.violations.length,1);assert.throws(()=>check(h.audit.records,before,h.audit.violations));
  }
});
test('quarter audit retains exact query, pin, body absence and terminal boundary',()=>{
  const x=good();x[2].url+='?period=2025-01-16%2C2025-03-31';
  const result=audit(x,[],11), quarter=result.rows.find(r=>r.url===origin+q);
  assert.equal(result.boundary,11);assert.equal(quarter.query,'?period=2025-01-16%2C2025-03-31');
  assert.equal(quarter.pin,'0');assert.equal(quarter.bodyAbsent,true);assert.equal(quarter.finished,6);
});
console.log(JSON.stringify({checks:n,outcome:'PASS_OFFLINE_ONLY',browserExecuted:false}));
