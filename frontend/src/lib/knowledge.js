export function validateKnowledgeQuestion(raw) {
  const question = typeof raw === 'string' ? raw.trim() : '';
  const valid = question.length >= 3 && question.length <= 500 && /[\p{L}\p{N}]/u.test(question);
  return { valid, question, error: valid ? '' : 'Câu hỏi cần dài 3–500 ký tự và có nội dung.' };
}
export function extractKnowledgeResult(response) {
  if (response?.status !== 'ok' || response.agent !== 'kg_rag' || !response.payload) return null;
  const kind = response.payload.response_kind;
  if (kind !== 'no_evidence' && kind !== 'grounded_extractive') return null;
  if (kind === 'grounded_extractive' && (!Array.isArray(response.evidence) || !response.evidence.length)) return null;
  return {question:response.payload.question || '', answer:response.payload.answer || '', kind,
    evidence:Array.isArray(response.evidence) ? response.evidence : [], matchedTopics:response.payload.matched_topics || []};
}
