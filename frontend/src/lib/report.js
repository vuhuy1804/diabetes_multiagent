export const AGENT_LABELS = Object.freeze({
  patient_data: 'Patient Data',
  dl_prediction: 'Deep Learning',
  rule_based: 'Rule-Based',
  kg_rag: 'KG / RAG',
  explanation: 'Explanation',
  coordinator: 'Coordinator',
  monitoring: 'Monitoring',
  rl: 'Reinforcement Learning',
});

export function extractReport(message) {
  if (message?.status !== 'ok' || message?.agent !== 'coordinator'
      || message?.payload?.workflow_status !== 'completed'
      || message?.payload?.report_ready !== true
      || message?.payload?.report?.report_kind !== 'educational_evidence_grounded_not_diagnosis'
      || typeof message?.payload?.report?.sections !== 'object'
      || !Array.isArray(message?.payload?.steps)) {
    return null;
  }
  return message.payload.report;
}

export function getProblems(error) {
  const problems = error?.data?.payload?.problems;
  return Array.isArray(problems) ? problems : [];
}

export function getFieldIssues(error) {
  const output = {};
  for (const problem of getProblems(error)) {
    if (!Array.isArray(problem?.issues)) continue;
    for (const issue of problem.issues) {
      if (typeof issue?.field === 'string' && typeof issue?.message === 'string') {
        output[issue.field] = issue.message;
      }
    }
  }
  return output;
}

export function fmtDuration(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  return `${value.toFixed(value < 10 ? 1 : 0)} ms`;
}

export function integrationCount(integrations) {
  if (!integrations || typeof integrations !== 'object') return 0;
  return ['patient_data', 'deep_learning', 'neo4j', 'rule_based', 'coordinator', 'explanation']
    .filter((name) => integrations[name] === 'ready').length;
}

export function isSafeReferenceUrl(url) {
  if (typeof url !== 'string') return false;
  try { return new URL(url).protocol === 'https:'; } catch { return false; }
}
