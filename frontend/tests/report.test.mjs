import test from 'node:test';
import assert from 'node:assert/strict';
import { AGENT_LABELS, extractReport, getFieldIssues, fmtDuration, integrationCount, isSafeReferenceUrl } from '../src/lib/report.js';

const validMessage = {agent:'coordinator',status:'ok',payload:{workflow_status:'completed',report_ready:true,steps:[{agent:'explanation'}],report:{report_kind:'educational_evidence_grounded_not_diagnosis',sections:{prediction:{},knowledge:{}}}}};

test('28. accepts only a completed report with verified contract',()=>assert.deepEqual(extractReport(validMessage),validMessage.payload.report));
test('29. rejects incomplete report',()=>assert.equal(extractReport({...validMessage,payload:{...validMessage.payload,report_ready:false}}),null));
test('30. rejects other report kinds',()=>assert.equal(extractReport({...validMessage,payload:{...validMessage.payload,report:{...validMessage.payload.report,report_kind:'diagnosis'}}}),null));
test('31. rejects a failed workflow',()=>assert.equal(extractReport({...validMessage,status:'error'}),null));
test('32. reads errors from Coordinator problems',()=>{
  const issues = getFieldIssues({data:{payload:{problems:[{agent:'patient_data',issues:[{field:'age',message:'Required'}]}]}}});
  assert.equal(issues.age,'Required');
});
test('33. formats duration and omits invalid durations',()=>{
  assert.equal(fmtDuration(1.234),'1.2 ms');assert.equal(fmtDuration(15.8),'16 ms');assert.equal(fmtDuration(undefined),'—');
});
test('34. readiness counts only six required integration keys',()=>{
  assert.equal(integrationCount({patient_data:'ready',deep_learning:'ready',neo4j:'ready',rule_based:'ready',coordinator:'ready',explanation:'ready',monitoring:'ready'}),6);
});
test('35. audit and RL are not mislabeled as ready agents',()=>{
  assert.equal(AGENT_LABELS.monitoring,'Monitoring');assert.equal(AGENT_LABELS.rl,'Reinforcement Learning');
});
test('36. source links must be HTTPS',()=>{
  assert.equal(isSafeReferenceUrl('https://www.niddk.nih.gov/health-information/diabetes'),true);
  assert.equal(isSafeReferenceUrl('javascript:alert(1)'),false);
  assert.equal(isSafeReferenceUrl('http://example.org'),false);
  assert.equal(isSafeReferenceUrl(null),false);
});
