import test from 'node:test';
import assert from 'node:assert/strict';
import { apiUrl, requestJson, ApiError } from '../src/lib/api.js';

const fakeResponse = (data, ok=true, status=200) => ({ok,status,text:async()=>JSON.stringify(data)});

test('18. API URL uses same-origin path by default',()=> assert.equal(apiUrl('/api/health'),'/api/health'));
test('19. API URL supports a configured external base',()=> assert.equal(apiUrl('/api/health','http://127.0.0.1:5000/'),'http://127.0.0.1:5000/api/health'));
test('20. API URL rejects unrelated routes',()=> assert.throws(()=>apiUrl('https://evil.invalid/')));
test('21. GET health has no body and no stored data',async()=>{
  let url, options;
  const payload = await requestJson('/api/health',{fetchImpl:async(u,o)=>{url=u;options=o;return fakeResponse({status:'ok'})}});
  assert.equal(payload.status,'ok');assert.equal(url,'/api/health'); assert.equal(options.method,'GET');assert.equal(options.body,undefined);
});
test('22. POST report sends precisely serialized JSON as UTF-8',async()=>{
  let options;
  const request = {features:{gender:'Female'},question:'Bệnh tiểu đường là gì?'};
  await requestJson('/api/report/generate',{payload:request,fetchImpl:async(_,o)=>{options=o;return fakeResponse({status:'ok'})}});
  assert.equal(options.method,'POST');assert.deepEqual(JSON.parse(options.body),request);assert.match(options.headers['Content-Type'],/utf-8/);
});
test('23. HTTP 400 preserves server validation errors',async()=>{
  const data={status:'error',payload:{problems:[{agent:'patient_data',issues:[{field:'bmi',message:'bad'}]}]}};
  await assert.rejects(requestJson('/api/report/generate',{payload:{},fetchImpl:async()=>fakeResponse(data,false,400)}),e=>e instanceof ApiError&&e.status===400&&e.data?.payload?.problems?.[0]?.issues?.[0]?.field==='bmi');
});
test('24. HTTP 503 reports unavailable service',async()=>{
  await assert.rejects(requestJson('/api/report/generate',{payload:{},fetchImpl:async()=>fakeResponse({status:'error'},false,503)}), e=>e instanceof ApiError&&e.status===503);
});
test('25. non-JSON response is rejected',async()=>{
  await assert.rejects(requestJson('/api/health',{fetchImpl:async()=>({ok:true,status:200,text:async()=>'<html></html>'})}),e=>e.kind==='invalid_json');
});
test('26. network errors are reported without sensitive data',async()=>{
  await assert.rejects(requestJson('/api/health',{fetchImpl:async()=>{throw new TypeError('network')}}),e=>e.kind==='network');
});
test('27. AbortError is converted to a timeout',async()=>{
  await assert.rejects(requestJson('/api/health',{fetchImpl:async()=>{const e=new Error('aborted');e.name='AbortError';throw e;}}),e=>e.kind==='timeout');
});
