"""Phase 8 API: adds Monitoring/Audit to the trusted full MAS workflow.

Legacy endpoints preserve inputs, HTTP semantics and the 5-step report trace.
SQLite stores metadata only, no medical features or question/report text.
"""
from __future__ import annotations

import atexit
from uuid import uuid4

from flask import Blueprint, jsonify, request

from agents.dl_prediction_agent import DLPredictionAgent
from agents.patient_data_agent import PatientDataAgent
from agents.kg_rag_agent import KGRAGAgent
from agents.rule_based_agent import RuleBasedAgent
from agents.explanation_agent import ExplanationAgent
from agents.monitoring_agent import MonitoringAgent
from core.contracts import AgentMessage
from coordinator.coordinator_agent import CoordinatorAgent
from rules.rule_engine import rule_catalog
from core.registry import AGENT_CATALOG
from services.dl_service import DLPredictionService
from services.knowledge_service import KnowledgeRetrievalService
from services.neo4j_service import KnowledgeDatabaseError, Neo4jKnowledgeRepository

api_bp = Blueprint('api', __name__, url_prefix='/api')
_patient_data_agent = PatientDataAgent()
_dl_service = DLPredictionService()
_dl_agent = DLPredictionAgent(_dl_service)
_kg_repo = Neo4jKnowledgeRepository()
# Close lazy Neo4j driver before interpreter shutdown (important for tests).
atexit.register(_kg_repo.close)
_kg_service = KnowledgeRetrievalService(_kg_repo)
_kg_agent = KGRAGAgent(_kg_service)
_rule_agent = RuleBasedAgent()
_explanation_agent = ExplanationAgent()
_monitor_agent = MonitoringAgent()
_coordinator = CoordinatorAgent(_patient_data_agent, _dl_agent, _rule_agent, _kg_agent,
                                explanation_agent=_explanation_agent)

DISCLAIMER = (
    'Educational demonstration only. Prediction is a dataset label, not a diagnosis; '
    'KG evidence is informational and does not prescribe medication or treatment.'
)


@api_bp.get('/health')
def health():
    return jsonify({
        'status': 'ok', 'service': 'diabetes-multiagent-api', 'phase': '8-monitoring-evaluation',
        'integrations': {'patient_data': 'ready', 'deep_learning': _dl_service.readiness(), 'neo4j': _kg_service.readiness(), 'rule_based': 'ready', 'coordinator': 'ready', 'explanation': 'ready', 'monitoring': _monitor_agent.readiness()},
        'disclaimer': DISCLAIMER,
    }), 200


@api_bp.get('/agents/status')
def agents_status():
    dl_ready = _dl_service.readiness() == 'ready'
    kg_ready = _kg_service.readiness() == 'ready'
    agents = []
    for item in AGENT_CATALOG:
        status = 'not_implemented'
        if item['agent'] in ('patient_data', 'rule_based', 'coordinator', 'explanation'):
            status = 'ready'
        if item['agent'] == 'dl_prediction':
            status = 'ready' if dl_ready else 'model_missing'
        if item['agent'] == 'monitoring':
            status = _monitor_agent.readiness()
        if item['agent'] == 'kg_rag':
            status = 'ready' if kg_ready else 'neo4j_not_ready'
        agents.append({**item, 'status': status})
    return jsonify({'phase': '8-monitoring-evaluation', 'count': len(agents), 'agents': agents}), 200


@api_bp.post('/patient/validate')
def patient_validate():
    """Standalone Phase 3 endpoint. Does NOT run DL, rules, or diagnosis."""
    body = request.get_json(silent=True)
    # Feed non-object bodies to the agent so validation failures keep the same contract.
    features = body.get('features') if isinstance(body, dict) else None
    message = _patient_data_agent.run(request_id=str(uuid4()), features=features)
    response = {**message.to_dict(), 'disclaimer': DISCLAIMER}
    return jsonify(response), 200 if message.status == 'ok' else 400


@api_bp.post('/predict')
def predict_only():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({'status': 'error', 'error': 'Expected JSON object'}), 400
    message = _dl_agent.run(request_id=str(uuid4()), features=body.get('features'))
    response = {**message.to_dict(), 'disclaimer': DISCLAIMER}
    if message.status == 'ok':
        return jsonify(response), 200
    if message.payload.get('error_type') == 'invalid_features':
        return jsonify(response), 400
    return jsonify(response), 503


@api_bp.post('/knowledge/query')
def knowledge_query():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({'status': 'error', 'error': 'Expected JSON object'}), 400
    message = _kg_agent.run(request_id=str(uuid4()), question=body.get('question'))
    response = {**message.to_dict(), 'disclaimer': DISCLAIMER}
    if message.status == 'ok':
        return jsonify(response), 200
    if message.payload.get('error_type') == 'invalid_question':
        return jsonify(response), 400
    return jsonify(response), 503


@api_bp.get('/knowledge/topics')
def knowledge_topics():
    try:
        topics = _kg_repo.list_topics()
        return jsonify({'status': 'ok', 'count': len(topics), 'topics': topics}), 200
    except KnowledgeDatabaseError:
        return jsonify({'status': 'error', 'error': 'Neo4j is unavailable or not initialized'}), 503


@api_bp.get('/rules/catalog')
def rules_catalog():
    """Public static rule definitions; never reads patient information."""
    rules = rule_catalog()
    return jsonify({'status': 'ok', 'rule_set_version': _rule_agent.VERSION,
                    'count': len(rules), 'rules': rules, 'disclaimer': DISCLAIMER}), 200


@api_bp.post('/rules/evaluate')
def rules_evaluate():
    """Standalone rule evaluation: caller passes canonical features and DL payload.

    For Phase 4 demonstration only. This endpoint does not authenticate the
    supplied prediction; the Phase 5 Coordinator will provide a trusted result.
    """
    body = request.get_json(silent=True)
    features = body.get('features') if isinstance(body, dict) else None
    prediction = body.get('prediction') if isinstance(body, dict) else None
    message = _rule_agent.run(request_id=str(uuid4()), features=features, prediction=prediction)
    return jsonify({**message.to_dict(), 'disclaimer': DISCLAIMER}), 200 if message.status == 'ok' else 400


@api_bp.post('/workflow/run')
def run_coordinator_workflow():
    """Phase 5 only: orchestrate four agents, return separated structured outputs.

    Legacy workflow provides only 4-agent, non-persistent trace; use /assess for monitoring.
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({
            'status': 'error', 'error': 'Expected a JSON object',
            'error_type': 'invalid_request', 'disclaimer': DISCLAIMER,
        }), 400
    # Do not accept caller-injected predictions or rules: Coordinator obtains them
    # from trusted local agent instances and never trusts arbitrary client outputs.
    allowed = {'features', 'question'}
    if any(key not in allowed for key in body):
        return jsonify({
            'status': 'error', 'error': 'Only features and optional question are accepted',
            'error_type': 'invalid_request', 'disclaimer': DISCLAIMER,
        }), 400
    result = _coordinator.run(features=body.get('features'), question=body.get('question'),
                              question_provided='question' in body)
    response = {**result.to_dict(), 'disclaimer': DISCLAIMER}
    if result.status == 'ok':
        return jsonify(response), 200
    error = result.payload.get('error_type')
    if error in ('invalid_patient_data', 'invalid_question'):
        return jsonify(response), 400
    if error in ('model_unavailable', 'neo4j_unavailable'):
        return jsonify(response), 503
    return jsonify(response), 500


def _with_monitoring(result: AgentMessage, *, route_kind: str, append_step: bool) -> dict:
    """Write ONLY sanitized metadata; never pass request body or report to SQLite.

    Legacy /report/generate keeps its 5-step trace to preserve Phase 7 UI/tests.
    /assess is centrally orchestrated by Coordinator.run_full_with_monitoring().
    """
    note = _monitor_agent.run(request_id=result.request_id, workflow=result, route_kind=route_kind)
    payload = {**result.payload, 'monitoring_status': note.status,
               'audit_recorded': note.status == 'ok'}
    if append_step:
        payload['steps'] = [*result.payload.get('steps', []), {
            'agent': 'monitoring', 'status': note.status, 'version': note.version,
            'duration_ms': 0.0,
            'error_type': note.payload.get('error_type') if note.status == 'error' else None,
        }]
    response = {**result.to_dict(), 'payload': payload, 'disclaimer': DISCLAIMER}
    if note.status == 'error':
        # Honest failure visibility without inventing a successful audit.
        response['audit_error_type'] = note.payload.get('error_type', 'audit_storage_unavailable')
    return response


@api_bp.post('/assess')
def assess():
    """Full MAS: Patient Data -> DL -> Rules -> KG -> Explanation -> Monitoring.

    Audit failure returns HTTP 503, even if an educational report exists.
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or set(body) - {'features', 'question'}:
        return jsonify({'status': 'error', 'error_type': 'invalid_request',
                        'error': 'Only features and optional question are accepted',
                        'disclaimer': DISCLAIMER}), 400
    result = _coordinator.run_full_with_monitoring(
        features=body.get('features'), question=body.get('question'),
        question_provided='question' in body, monitoring_agent=_monitor_agent,
    )
    response = {**result.to_dict(), 'disclaimer': DISCLAIMER}
    if result.payload.get('monitoring_status') != 'ok':
        return jsonify(response), 503
    if result.status == 'ok':
        return jsonify(response), 200
    problem = result.payload.get('error_type')
    if problem in ('invalid_patient_data', 'invalid_question'):
        return jsonify(response), 400
    if problem in ('model_unavailable', 'neo4j_unavailable', 'explanation_unavailable'):
        return jsonify(response), 503
    return jsonify(response), 500


@api_bp.post('/report/generate')
def generate_explanation_report():
    """Run four trusted agents and then Explanation; do not accept injected evidence.

Explanation is deterministic and source-grounded; audit metadata is stored separately.
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({
            'status': 'error', 'error': 'Expected a JSON object',
            'error_type': 'invalid_request', 'disclaimer': DISCLAIMER,
        }), 400
    if set(body) - {'features', 'question'}:
        return jsonify({
            'status': 'error', 'error': 'Only features and optional question are accepted',
            'error_type': 'invalid_request', 'disclaimer': DISCLAIMER,
        }), 400
    result = _coordinator.run_with_explanation(
        features=body.get('features'), question=body.get('question'),
        question_provided='question' in body,
    )
    response = _with_monitoring(result, route_kind='report', append_step=False)
    if result.status == 'ok':
        return jsonify(response), 200
    problem = result.payload.get('error_type')
    if problem in ('invalid_patient_data', 'invalid_question'):
        return jsonify(response), 400
    if problem in ('model_unavailable', 'neo4j_unavailable', 'explanation_unavailable'):
        return jsonify(response), 503
    return jsonify(response), 500
