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
const origin = 'http://127.0.0.1:3107', f = '/api/finlens/companies/AAA/freshness', a = '/api/finlens/companies/AAA/financials/annual';
const row = (path, start, extra = {}) => ({ request: {}, method: 'GET', url: origin + path, pin: path === a ? '0' : undefined, start, ...extra });
const replay = () => [row(f,1,{failed:2,error:'net::ERR_ABORTED'}),row(f,3,{status:200,finished:4}),row(a,5,{failed:6,error:'net::ERR_ABORTED'}),row(a,7,{status:200,finished:8})];
const good = () => [row(f,1,{status:200,finished:2}),row(a,3,{status:200,finished:4})];
let n=0; function test(name, fn) { fn(); console.log(`ok ${++n} - ${name}`); }
test('observed two replays with successful replacements',()=>assert.equal(check(replay(),9).length,2));
test('zero cancellations and two completed requests',()=>assert.deepEqual(check(good(),9),[]));
test('duplicate cancellation rejects',()=>{const x=replay();x.push(row(a,8,{failed:8,error:'net::ERR_ABORTED'}));assert.throws(()=>check(x,9));});
test('wrong pin rejects',()=>{const x=replay();x[2].pin='1';assert.throws(()=>check(x,9));});
test('wrong method rejects',()=>{const x=replay();x[0].method='POST';assert.throws(()=>check(x,9));});
test('wrong company cancellation rejects',()=>{const x=replay();x[0].url=origin+'/api/finlens/companies/BBB/freshness';assert.throws(()=>check(x,9));});
test('missing replacement rejects',()=>{const x=replay();x.splice(1,1);assert.throws(()=>check(x,9));});
test('failed replacement rejects',()=>{const x=replay();x[1].status=503;assert.throws(()=>check(x,9));});
test('unrelated aborted request rejects',()=>{const x=good();x.push(row('/api/finlens/companies/AAA/sources',5,{failed:6,error:'net::ERR_ABORTED'}));assert.throws(()=>check(x,9));});
test('late failure rejects',()=>{const x=replay();x[0].failed=10;assert.throws(()=>check(x,9));});
test('late start or replacement rejects',()=>{const x=replay();x[3].finished=10;assert.throws(()=>check(x,9));});
test('duplicate successful response rejects',()=>{const x=good();x.push(row(a,5,{status:200,finished:6}));assert.throws(()=>check(x,9));});
test('other error rejects',()=>{const x=replay();x[0].error='net::ERR_FAILED';assert.throws(()=>check(x,9));});
test('replacement ordering and identity verified',()=>{const x=replay();x[1].start=0;assert.throws(()=>check(x,9));const y=replay();y[1].request=y[0].request;assert.throws(()=>check(y,9));});
test('wrong origin and query reject',()=>{const x=good();x[0].url='http://example.test'+f;assert.throws(()=>check(x,9));const y=good();y[1].url+='?fiscal_year=2024';assert.throws(()=>check(y,9));});
function fakeRequest(path, pin, error = 'net::ERR_ABORTED') { return { method:()=> 'GET', url:()=>origin+path,
  headers:()=>pin === undefined ? {} : {'x-finlens-data-version':pin}, failure:()=>({errorText:error}) }; }
function harness() { const handlers={}; const page={ on:(name,fn)=>{handlers[name]=fn;} };
  const audit=record(page); return {audit,emit:(name,value)=>handlers[name](value)}; }
function emitSuccess(h, req) { h.emit('request',req);h.emit('response',{request:()=>req,status:()=>200});h.emit('requestfinished',req); }
function emitReplay(h, path, pin) { const old=fakeRequest(path,pin), next=fakeRequest(path,pin);
  h.emit('request',old);h.emit('requestfailed',old);emitSuccess(h,next);return {old,next}; }
test('recorder binds request objects and orders success and failure',()=>{const h=harness();const x=emitReplay(h,f,undefined);emitSuccess(h,fakeRequest(a,'0'));const b=h.audit.boundary();assert.equal(check(h.audit.records,b,h.audit.violations).length,1);assert.equal(h.audit.records[0].request,x.old);assert(h.audit.records[0].start<h.audit.records[0].failed);assert(h.audit.records[1].start<h.audit.records[1].finished);});
test('unknown scoped response, finish and failure reject against valid baseline',()=>{for(const event of ['response','requestfinished','requestfailed']){const h=harness(),req=fakeRequest(f);emitSuccess(h,fakeRequest(f));emitSuccess(h,fakeRequest(a,'0'));const before=h.audit.boundary();assert.deepEqual(check(h.audit.records,before,h.audit.violations),[]);h.emit(event,event==='response'?{request:()=>req,status:()=>200}:req);assert.equal(h.audit.violations.length,1);assert.throws(()=>check(h.audit.records,before,h.audit.violations),/Unbound request lifecycle event/);}});
test('unknown unrelated failure rejects',()=>{const h=harness();emitSuccess(h,fakeRequest(f));emitSuccess(h,fakeRequest(a,'0'));h.emit('requestfailed',fakeRequest('/other'));assert.throws(()=>check(h.audit.records,h.audit.boundary(),h.audit.violations));});
test('post-boundary scoped start rejects',()=>{const h=harness();emitSuccess(h,fakeRequest(f));emitSuccess(h,fakeRequest(a,'0'));const b=h.audit.boundary();h.emit('request',fakeRequest(a,'0'));assert.throws(()=>check(h.audit.records,b,h.audit.violations));});
test('post-boundary scoped finish or failure rejects with valid pre-boundary control',()=>{for(const terminal of ['requestfinished','requestfailed']) for(const late of [false,true]){const h=harness(),old=fakeRequest(f);h.emit('request',old);const row=h.audit.records.at(-1);if(terminal==='requestfinished') h.emit('response',{request:()=>old,status:()=>200});else emitSuccess(h,fakeRequest(f));emitSuccess(h,fakeRequest(a,'0'));if(!late) h.emit(terminal,old);const b=h.audit.boundary();if(late) h.emit(terminal,old);const event=terminal==='requestfinished'?row.finished:row.failed;assert.equal(row.request,old);assert(row.start<b);assert.equal(event>b,late);if(late) assert.throws(()=>check(h.audit.records,b,h.audit.violations));else assert.doesNotThrow(()=>check(h.audit.records,b,h.audit.violations));}});
test('200 without requestfinished rejects',()=>{const h=harness(),req=fakeRequest(f);h.emit('request',req);h.emit('response',{request:()=>req,status:()=>200});emitSuccess(h,fakeRequest(a,'0'));assert.throws(()=>check(h.audit.records,h.audit.boundary(),h.audit.violations));});
test('extra scoped pending request rejects',()=>{const h=harness();emitSuccess(h,fakeRequest(f));emitSuccess(h,fakeRequest(a,'0'));h.emit('request',fakeRequest(a,'0'));assert.throws(()=>check(h.audit.records,h.audit.boundary(),h.audit.violations));});
console.log(JSON.stringify({checks:n,outcome:'PASS_OFFLINE_ONLY',browserExecuted:false}));
