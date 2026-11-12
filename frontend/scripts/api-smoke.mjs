// Exercise the REAL Flask backend, not a mock. Never print input patient features.
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { requestJson } from '../src/lib/api.js';
import { extractReport } from '../src/lib/report.js';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const samplePath = path.resolve(scriptDir,'../../data/samples/report_with_question.json');
const target = process.env.API_SMOKE_BASE_URL || 'http://127.0.0.1:5000';

try {
  const health = await requestJson('/api/health',{baseUrl:target, timeoutMs:12000});
  const ready = ['patient_data','deep_learning','neo4j','rule_based','coordinator','explanation'].every(k=>health.integrations?.[k]==='ready');
  if (!ready) throw new Error('Backend chưa ready: ' + JSON.stringify(health.integrations));
  console.log('PASS health: 6/6 integrations ready; ' + health.phase);
  const data = JSON.parse(await readFile(samplePath, 'utf8'));
  const result = await requestJson('/api/report/generate',{payload:data,baseUrl:target,timeoutMs:120000});
  const report = extractReport(result);
  if (!report || !report.text?.includes('BÁO CÁO') || result.payload.steps.length !== 5) throw new Error('Báo cáo không đạt hợp đồng của Phase 6');
  const sources = report.sources?.filter(s=>s.origin==='kg_rag'&&s.url?.startsWith('https://')) || [];
  if(sources.length===0) throw new Error('Báo cáo thiếu nguồn Neo4j HTTPS từ câu hỏi mẫu');
  console.log('PASS /api/report/generate: report_ready, 5 agent steps, ' + sources.length + ' Neo4j sources');
  console.log('PASS Unicode và cấu trúc: ' + report.text.slice(0,32).split('\n')[0]);
  console.log('KẾT LUẬN: REAL API SMOKE PASS');
} catch(error) {
  console.error('REAL API SMOKE FAILED:',error.message);
  process.exitCode=1;
}
