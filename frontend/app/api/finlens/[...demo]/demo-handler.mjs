const keys=Object.freeze([
 '/companies','/capabilities','/companies/AAA/freshness',
 '/companies/AAA/financials/insights?mode=discover','/companies/AAA/financials/annual',
 '/companies/AAA/financials/quarters','/companies/AAA/financials/summary?period=quarter',
 '/companies/AAA/financials/metrics/revenue?period=quarter&limit=12','/companies/AAA/research-answer',
]);
const prefix='/api/finlens', targetQuestion='{"question":"What was FY2024 revenue?"}';
const cap=512;
function reply(status, body, pin=false, allow) {
 return new Response(body,{status,headers:{
  'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store',
  'X-Content-Type-Options':'nosniff',...(pin?{'X-FinLens-Data-Version':'0'}:{}),...(allow?{Allow:allow}:{}),
 }});
}
function reject(status,code,allow){return reply(status,JSON.stringify({code}),false,allow);}
async function readPost(request,length){
 const reader=request.body?.getReader();
 if(!reader) return {code:400};
 const data=new Uint8Array(cap);
 let n=0, finished=false, timer;
 const timed=new Promise(resolve=>{timer=setTimeout(()=>resolve(null),750);});
 try{
  for(;;){
   const item=await Promise.race([reader.read(),timed]);
   if(item===null)return {code:408};
   if(item.done){finished=true;break;}
   if(!(item.value instanceof Uint8Array))return {code:400};
   if(n+item.value.byteLength>cap)return {code:413};
   data.set(item.value,n);n+=item.value.byteLength;
  }
  if(length!==null&&n!==Number(length))return {code:400};
  return {body:new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(data.subarray(0,n))};
 }catch{return {code:400};}
 finally{clearTimeout(timer);if(!finished)void reader.cancel().catch(()=>{});reader.releaseLock();}
}
export function makeDemoHandler(rows){
 if(!rows||typeof rows!=='object'||Object.keys(rows).length!==keys.length)throw new Error('DEMO_REPLY_TABLE');
 const table=Object.freeze(Object.fromEntries(keys.map(key=>{
  if(!Object.hasOwn(rows,key)||typeof rows[key]!=='string'||rows[key].length>262144)throw new Error('DEMO_REPLY_TABLE');
  const data=JSON.parse(rows[key]);
  if(data===null||typeof data!=='object')throw new Error('DEMO_REPLY_TABLE');
  return [key,rows[key]];
 })));
 return async function handle(request){
  let rawUrl,u;try{rawUrl=Object.getOwnPropertyDescriptor(Request.prototype,'url')?.get?.call(request);u=new URL(rawUrl);}catch{return reject(400,'DEMO_BAD_URL');}
  if(!['http:','https:'].includes(u.protocol)||u.username||u.password||u.hash||rawUrl!==u.origin+u.pathname+u.search||!u.pathname.startsWith(prefix+'/'))
   return reject(404,'DEMO_ROUTE_DENIED');
  const key=u.pathname.slice(prefix.length)+u.search,index=keys.indexOf(key);
  if(index<0)return reject(404,'DEMO_ROUTE_DENIED');
  const method=index===8?'POST':'GET',versioned=index>=3;
  if(request.method!==method)return reject(405,'DEMO_METHOD_DENIED',method);
  const headers=request.headers,pin=headers.get('x-finlens-data-version'), length=headers.get('content-length');
  if(versioned?pin!=='0':pin!==null)return reject(400,'DEMO_PIN_DENIED');
  if(headers.has('content-encoding')||headers.has('transfer-encoding')||headers.has('trailer')||
     length!==null&&!/^(0|[1-9][0-9]{0,2})$/.test(length))return reject(400,'DEMO_FRAMING_DENIED');
  if(length!==null&&Number(length)>cap)return reject(413,'DEMO_BODY_LIMIT');
  if(method==='GET'){
   if(request.body!==null||headers.has('content-type')||(length!==null&&length!=='0'))return reject(400,'DEMO_BODY_DENIED');
   return reply(200,table[key],versioned);
  }
  if(headers.get('origin')!==u.origin)return reject(403,'DEMO_ORIGIN_DENIED');
  if(headers.get('content-type')!=='application/json')return reject(400,'DEMO_BODY_DENIED');
  const parsed=await readPost(request,length);
  if(parsed.code)return reject(parsed.code,parsed.code===413?'DEMO_BODY_LIMIT':parsed.code===408?'DEMO_BODY_TIMEOUT':'DEMO_BODY_DENIED');
  if(parsed.body!==targetQuestion)return reject(400,'DEMO_BODY_DENIED');
  return reply(200,table[key],versioned);
 };
}
