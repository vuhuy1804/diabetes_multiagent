"""Coordinator Agent — Phase 5 of the PTIT hybrid diabetes MAS.

Order (§5 of instructor's PDF): Patient Data -> DL -> Rules -> KG/RAG -> aggregate.
Explanation and Monitoring agents do not exist yet.  A response contains a
request-scoped, non-persistent *execution trace*, not a clinical report.

Never silently substitute failed medical components or fabricate predictions.
No user-provided features/question are stored to disk or printed to logs.
"""
from __future__ import annotations

from time import perf_counter
from typing import Any
from uuid import uuid4

from core.contracts import AgentMessage
from services.knowledge_service import KnowledgeQueryError, validate_question


class CoordinatorAgent:
    VERSION = 'coordinator-v1'
    ORDER = ('patient_data', 'dl_prediction', 'rule_based', 'kg_rag')

    def __init__(self, data_agent: Any, dl_agent: Any, rule_agent: Any, kg_agent: Any,
                 explanation_agent: Any = None):
        self.explanation_agent = explanation_agent
        self.agents = {
            'patient_data': data_agent,
            'dl_prediction': dl_agent,
            'rule_based': rule_agent,
            'kg_rag': kg_agent,
        }

    @staticmethod
    def _summary(message: AgentMessage, duration_ms: float) -> dict[str, Any]:
        """Trace metadata, NOT raw patient features, question or source excerpts."""
        return {
            'agent': message.agent,
            'status': message.status,
            'version': message.version,
            'duration_ms': round(duration_ms, 3),
            'error_type': message.payload.get('error_type') if message.status == 'error' else None,
        }

    def _invoke(self, name: str, request_id: str, **kwargs: Any) -> tuple[AgentMessage, dict[str, Any]]:
        start = perf_counter()
        try:
            agent_result = self.agents[name].run(request_id=request_id, **kwargs)
            if (not isinstance(agent_result, AgentMessage)
                or agent_result.request_id != request_id
                or agent_result.agent != name
                or agent_result.status not in ('ok', 'error', 'skipped')
                or not isinstance(agent_result.payload, dict)
                or not isinstance(agent_result.evidence, list)
                or any(not isinstance(item, dict) for item in agent_result.evidence)
                or (name == 'patient_data' and agent_result.status == 'ok'
                    and (agent_result.payload.get('valid') is not True
                         or not isinstance(agent_result.payload.get('features'), dict)))):
                raise ValueError('Agent contract mismatch')
            msg = agent_result
        except Exception:  # fail closed; never leak user values or internal exception details
            msg = AgentMessage(
                request_id=request_id, agent=name, status='error', version='phase5',
                payload={'error_type': 'agent_execution_error'},
                error='Agent execution failed or returned an invalid contract.',
            )
        return msg, self._summary(msg, (perf_counter() - start) * 1000.0)

    @staticmethod
    def _skipped(request_id: str, name: str, reason: str) -> tuple[AgentMessage, dict[str, Any]]:
        msg = AgentMessage(
            request_id=request_id, agent=name, status='skipped',
            payload={'reason': reason}, version='phase5',
        )
        return msg, CoordinatorAgent._summary(msg, 0.0)

    def run(self, *, features: Any, question: Any = None,
            question_provided: bool = False, request_id: str | None = None) -> AgentMessage:
        """Run a single sequential request without persistent side effects.

        Question is optional. If absent, KG/RAG is explicitly marked skipped;
        the other 3 agents still run. If present, it must be a valid question.
        If KG fails after DL/rules succeeded, return error with partial results.
        """
        rid = request_id or str(uuid4())
        outcomes: dict[str, AgentMessage] = {}
        trace: list[dict[str, Any]] = []
        evidence: list[dict[str, Any]] = []

        def add(name: str, message: AgentMessage, stage_trace: dict[str, Any]):
            outcomes[name] = message
            trace.append(stage_trace)
            if message.status == 'ok':
                for item in message.evidence:
                    # No mutation of each agent's own evidence.
                    evidence.append({**item, 'agent': name})

        def skip_rest(reason: str):
            for name in self.ORDER:
                if name not in outcomes:
                    add(name, *self._skipped(rid, name, reason))

        def finish(status: str, workflow_status: str, error_type: str | None = None):
            # Keep the four outputs independent: never merge rule flags with model labels.
            results = {name: (outcomes[name].payload if outcomes[name].status == 'ok' else None)
                       for name in self.ORDER}
            steps = [{**t} for t in trace]
            problems = [{ 'agent': name,
                          'error_type': outcomes[name].payload.get('error_type', 'unknown'),
                          'message': outcomes[name].error,
                          'issues': outcomes[name].payload.get('issues', [])}
                        for name in self.ORDER if outcomes[name].status == 'error']
            return AgentMessage(
                request_id=rid, agent='coordinator', status=status, version=self.VERSION,
                payload={
                    'workflow_status': workflow_status,
                    'results': results,
                    'steps': steps,
                    'problems': problems,
                    'error_type': error_type,
                    'question_provided': bool(question_provided),
                    'knowledge_status': outcomes['kg_rag'].status,
                    'explanation_status': 'not_implemented',
                    'monitoring_status': 'not_implemented',
                    'report_ready': False,
                    'limitations': [
                        'This is a course prototype, not a medical diagnosis.',
                        'The DL score is not a calibrated disease probability.',
                        'Rule flags are educational references, not treatment advice.',
                        'An evidence-grounded report and persistent audit require later phases.',
                    ],
                },
                evidence=evidence,
                error='One or more required agents failed.' if status == 'error' else None,
            )

        # Input validation must precede all intelligent operations.
        add('patient_data', *self._invoke('patient_data', rid, features=features))
        if outcomes['patient_data'].status != 'ok':
            skip_rest('patient_data_failed')
            problem = outcomes['patient_data'].payload.get('error_type', 'agent_execution_error')
            return finish('error', 'failed', problem)

        # Prevent expensive inference for malformed optional knowledge questions.
        if question_provided:
            try:
                question = validate_question(question)
            except KnowledgeQueryError:
                # No KG query executed; record the validation error without echoing text.
                invalid = AgentMessage(rid, 'kg_rag', 'error',
                                       payload={'error_type': 'invalid_question'},
                                       version='phase5', error='Question is invalid (3..500 searchable characters required).')
                add('dl_prediction', *self._skipped(rid, 'dl_prediction', 'invalid_question'))
                add('rule_based', *self._skipped(rid, 'rule_based', 'invalid_question'))
                add('kg_rag', invalid, self._summary(invalid, 0.0))
                return finish('error', 'failed', 'invalid_question')

        add('dl_prediction', *self._invoke('dl_prediction', rid,
                                          features=outcomes['patient_data'].payload['features']))
        if outcomes['dl_prediction'].status != 'ok':
            skip_rest('dl_prediction_failed')
            return finish('error', 'failed', outcomes['dl_prediction'].payload.get('error_type', 'agent_execution_error'))

        add('rule_based', *self._invoke('rule_based', rid,
                                      features=outcomes['patient_data'].payload['features'],
                                      prediction=outcomes['dl_prediction'].payload))
        if outcomes['rule_based'].status != 'ok':
            skip_rest('rule_based_failed')
            return finish('error', 'failed', outcomes['rule_based'].payload.get('error_type', 'agent_execution_error'))

        if question_provided:
            add('kg_rag', *self._invoke('kg_rag', rid, question=question))
            if outcomes['kg_rag'].status != 'ok':
                return finish('error', 'partial', outcomes['kg_rag'].payload.get('error_type', 'agent_execution_error'))
        else:
            add('kg_rag', *self._skipped(rid, 'kg_rag', 'question_not_provided'))
        return finish('ok', 'completed')

    def run_with_explanation(self, *, features: Any, question: Any = None,
                             question_provided: bool = False,
                             request_id: str | None = None) -> AgentMessage:
        """Phase 6: Coordinator invokes the existing four agents, THEN Explanation.

        /api/workflow/run deliberately retains its Phase 5 contract; this method
        powers /api/report/generate. Never generate a report from partial or
        failed workflows. Reporting does not write patient data or audit records.
        """
        base = self.run(features=features, question=question,
                        question_provided=question_provided, request_id=request_id)
        rid = base.request_id
        result_payload = dict(base.payload)
        steps = [dict(stage) for stage in result_payload['steps']]
        results = dict(result_payload['results'])
        problems = [dict(problem) for problem in result_payload['problems']]
        explanation = None
        if base.status != 'ok':
            explanation, trace = self._skipped(rid, 'explanation', 'incomplete_upstream_workflow')
        elif self.explanation_agent is None:
            explanation = AgentMessage(
                request_id=rid, agent='explanation', status='error',
                payload={'error_type': 'explanation_unavailable'},
                version='phase6', error='Explanation Agent is not configured.',
            )
            trace = self._summary(explanation, 0.0)
        else:
            start = perf_counter()
            try:
                reply = self.explanation_agent.run(request_id=rid, workflow=base)
                if (not isinstance(reply, AgentMessage) or reply.request_id != rid
                    or reply.agent != 'explanation' or reply.status not in ('ok', 'error')
                    or not isinstance(reply.payload, dict)
                    or not isinstance(reply.evidence, list)
                    or (reply.status == 'ok' and
                        (not isinstance(reply.payload.get('report'), dict)
                         or reply.payload['report'].get('report_kind') != 'educational_evidence_grounded_not_diagnosis'))):
                    raise ValueError('Explanation Agent message contract mismatch')
                explanation = reply
            except Exception:
                explanation = AgentMessage(
                    request_id=rid, agent='explanation', status='error',
                    payload={'error_type': 'explanation_execution_error'}, version='phase6',
                    error='Explanation Agent failed or returned an invalid contract.',
                )
            trace = self._summary(explanation, (perf_counter() - start) * 1000.0)

        steps.append(trace)
        results['explanation'] = explanation.payload if explanation.status == 'ok' else None
        success = base.status == 'ok' and explanation.status == 'ok'
        if explanation.status == 'error':
            problems.append({'agent': 'explanation',
                             'error_type': explanation.payload.get('error_type', 'unknown'),
                             'message': explanation.error, 'issues': []})
        result_payload.update({
            'results': results, 'steps': steps, 'problems': problems,
            'explanation_status': explanation.status,
            'report_ready': success,
            'report': explanation.payload['report'] if success else None,
        })
        if success:
            result_payload['workflow_status'] = 'completed'
            result_payload['error_type'] = None
        elif base.status == 'ok':
            result_payload['workflow_status'] = 'partial'
            result_payload['error_type'] = explanation.payload.get('error_type', 'explanation_execution_error')
        # If upstream already failed, preserve its status/error/partial results.
        return AgentMessage(
            request_id=rid, agent='coordinator',
            status='ok' if success else 'error', version=self.VERSION,
            payload=result_payload,
            evidence=list(base.evidence),  # Original agent provenance, no duplication
            error=None if success else (
                base.error if base.status == 'error' else 'Explanation report generation failed.'
            ),
        )

    def run_full_with_monitoring(self, *, features: Any, question: Any = None,
                                 question_provided: bool = False,
                                 monitoring_agent: Any,
                                 request_id: str | None = None) -> AgentMessage:
        """Phase 8 full MAS: Coordinate patient -> DL -> rules -> KG -> Explanation -> Monitoring.

        Monitoring is intentionally invoked even if an earlier agent fails,
        so failures appear in metadata-only SQLite audit records.
        """
        base = self.run_with_explanation(
            features=features, question=question,
            question_provided=question_provided, request_id=request_id)
        monitor_started = perf_counter()
        try:
            monitor = monitoring_agent.run(request_id=base.request_id,
                                           workflow=base, route_kind='assess')
            if (not isinstance(monitor, AgentMessage)
                or monitor.request_id != base.request_id or monitor.agent != 'monitoring'
                or monitor.status not in ('ok', 'error')
                or not isinstance(monitor.payload, dict)):
                raise ValueError('Monitoring Agent contract mismatch')
        except Exception:
            monitor = AgentMessage(base.request_id, 'monitoring', 'error',
                                   payload={'error_type': 'audit_storage_unavailable'},
                                   version='monitoring-phase8', error='Monitoring execution failed.')
        payload = {**base.payload,
                   'steps': [*base.payload.get('steps', []),
                             self._summary(monitor, (perf_counter() - monitor_started) * 1000.0)],
                   'monitoring_status': monitor.status,
                   'audit_recorded': monitor.status == 'ok'}
        success = base.status == 'ok' and monitor.status == 'ok'
        if monitor.status == 'error':
            payload['error_type'] = 'audit_storage_unavailable'
            if base.status == 'ok':
                payload['workflow_status'] = 'partial'
        return AgentMessage(
            request_id=base.request_id, agent='coordinator', version=self.VERSION,
            status='ok' if success else 'error', payload=payload,
            evidence=list(base.evidence),
            error=None if success else (
                'Monitoring audit storage is unavailable.' if monitor.status == 'error' else base.error),
        )
