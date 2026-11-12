import test from 'node:test';
import assert from 'node:assert/strict';
import { validateKnowledgeQuestion, extractKnowledgeResult } from '../src/lib/knowledge.js';
import { queryKnowledge, requestJson } from '../src/lib/api.js';
const reply=(data)=>({ok:true,status:200,text:async()=>JSON.stringify(data)});
test('question-only requires no patient features', async()=>{
 let body, path;
 const res=await queryKnowledge('Bệnh tiểu đường nên ăn gì?',{fetchImpl:async(u,o)=>{path=u;body=JSON.parse(o.body);return reply({status:'ok'})}});
 assert.equal(res.status,'ok');assert.equal(path,'/api/knowledge/query');assert.deepEqual(body,{question:'Bệnh tiểu đường nên ăn gì?'});
});
test('question is trimmed',()=>assert.equal(validateKnowledgeQuestion('  Dinh dưỡng ra sao? ').question,'Dinh dưỡng ra sao?'));
test('question empty is rejected',()=>assert.equal(validateKnowledgeQuestion('').valid,false));
test('question punctuation is rejected',()=>assert.equal(validateKnowledgeQuestion('???').valid,false));
test('question too long is rejected',()=>assert.equal(validateKnowledgeQuestion('a'.repeat(501)).valid,false));
test('valid Vietnamese question is accepted',()=>assert.equal(validateKnowledgeQuestion('Bệnh tiểu đường nên ăn gì?').valid,true));
test('knowledge evidence response accepted',()=>{
 const data={status:'ok',agent:'kg_rag',payload:{response_kind:'grounded_extractive',question:'ăn gì?',answer:'rau',matched_topics:['nutrition']},evidence:[{fact_id:'f17',topic_name:'Dinh dưỡng',source:{url:'https://example.org'}}]};
 assert.equal(extractKnowledgeResult(data)?.kind,'grounded_extractive');
});
test('no evidence response displays missing knowledge',()=>{
 const data={status:'ok',agent:'kg_rag',payload:{response_kind:'no_evidence',answer:'Không tìm thấy',matched_topics:[]},evidence:[]};
 assert.equal(extractKnowledgeResult(data)?.kind,'no_evidence');
});
test('forged evidence-free response is rejected',()=>{
 const data={status:'ok',agent:'kg_rag',payload:{response_kind:'grounded_extractive'},evidence:[]};
 assert.equal(extractKnowledgeResult(data),null);
});
test('unrelated agent response is rejected',()=>assert.equal(extractKnowledgeResult({status:'ok',agent:'coordinator'}),null));
