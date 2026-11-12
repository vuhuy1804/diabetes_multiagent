"""Build a transparent educational report from a *trusted Coordinator result*.

Course architecture §3, §5, §6, §10: keep DL classification, explicit rules and
Neo4j evidence distinct; never create medical diagnoses or ungrounded facts.
No LLM, network calls, disk writes, treatment recommendations, or user-provided
claims are accepted by this builder.
"""
from __future__ import annotations

import math
from typing import Any

from core.contracts import AgentMessage


class ReportInputError(ValueError):
    """The orchestrated workflow is incomplete or violates the input contract."""


def _text(value: Any, field: str, limit: int = 1600) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ReportInputError(f'Invalid or missing {field}')
    return value.strip()


def _source(raw: Any, field: str, *, external: bool) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ReportInputError(f'Invalid source for {field}')
    title = _text(raw.get('title'), f'{field}.title', 220)
    publisher = _text(raw.get('publisher'), f'{field}.publisher', 160)
    url = raw.get('url')
    if external:
        if not isinstance(url, str) or not url.startswith('https://') or len(url) > 700:
            raise ReportInputError(f'Missing HTTPS source for {field}')
    elif url is not None and (not isinstance(url, str) or not url.startswith('https://')):
        raise ReportInputError(f'Invalid reference URL for {field}')
    return {'title': title, 'publisher': publisher, 'url': url}


def _validate_workflow(workflow: Any) -> tuple[dict, dict, dict | None, str, list[dict]]:
    if (not isinstance(workflow, AgentMessage) or workflow.agent != 'coordinator'
            or workflow.status != 'ok' or not workflow.request_id
            or not isinstance(workflow.payload, dict)):
        raise ReportInputError('Coordinator result must be successful')
    data = workflow.payload
    if data.get('workflow_status') != 'completed':
        raise ReportInputError('Coordinator workflow is incomplete')
    results = data.get('results')
    if not isinstance(results, dict):
        raise ReportInputError('Workflow results are missing')
    for name in ('patient_data', 'dl_prediction', 'rule_based'):
        if not isinstance(results.get(name), dict):
            raise ReportInputError(f'Missing {name} result')
    pred = results['dl_prediction']
    label = pred.get('prediction')
    if type(label) is not int or label not in (0, 1):
        raise ReportInputError('Invalid DL dataset label')
    score = pred.get('model_score_class_1')
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ReportInputError('Invalid DL model score')
    if not math.isfinite(score) or not 0 <= score <= 1:
        raise ReportInputError('DL model score out of range')
    if type(pred.get('score_is_calibrated')) is not bool:
        raise ReportInputError('DL score calibration status is missing')
    if pred.get('output_kind') != 'dataset_label_classification':
        raise ReportInputError('Unsupported prediction output kind')
    _text(pred.get('model_version'), 'model_version', 128)
    rules = results['rule_based']
    evaluated = rules.get('rules_evaluated')
    if type(evaluated) is not int or not (1 <= evaluated <= 100):
        raise ReportInputError('Invalid rules evaluated count')
    if not isinstance(rules.get('flags'), list) or len(rules['flags']) > evaluated:
        raise ReportInputError('Invalid rule flags')
    if type(rules.get('review_required')) is not bool:
        raise ReportInputError('Missing rule review status')
    if rules.get('triggered_rules_count') != len(rules['flags']):
        raise ReportInputError('Rule count does not match flags')
    kg_state = data.get('knowledge_status')
    if kg_state not in ('ok', 'skipped'):
        raise ReportInputError('Knowledge step must be ok or skipped')
    kg = results.get('kg_rag')
    if kg_state == 'ok' and not isinstance(kg, dict):
        raise ReportInputError('Knowledge output is missing')
    if kg_state == 'skipped' and kg is not None:
        raise ReportInputError('Skipped knowledge step has a result')
    if not isinstance(workflow.evidence, list):
        raise ReportInputError('Workflow evidence is malformed')
    return pred, rules, kg, kg_state, workflow.evidence


def build_report(workflow: AgentMessage) -> dict[str, Any]:
    """Return a predictable four-section report and linked reference list.

    Facts from KG are copied verbatim from Neo4j evidence, never summarized into
    new medical claims. Rule descriptions come from Phase 4's explicit rules.
    This function fails closed if any KG fact lacks an HTTPS source.
    """
    pred, rules, kg, kg_state, raw_evidence = _validate_workflow(workflow)
    label = pred['prediction']
    score = round(float(pred['model_score_class_1']), 4)
    model_version = _text(pred['model_version'], 'model_version', 128)
    calibrated = pred['score_is_calibrated']

    prediction_sentence = (
        f'Mô hình Deep Learning (phiên bản {model_version}) trả nhãn {label} '
        f'theo bộ dữ liệu huấn luyện. Điểm kỹ thuật của lớp 1: {score:.4f}. '
        'Nhãn này không phải kết luận chẩn đoán bệnh tiểu đường.'
    )
    if not calibrated:
        prediction_sentence += ' Điểm mô hình chưa được hiệu chuẩn thành xác suất mắc bệnh.'
    else:
        prediction_sentence += ' Điểm mô hình vẫn cần đánh giá độc lập trước khi diễn giải lâm sàng.'

    refs: list[dict[str, Any]] = []
    rule_flags: list[dict[str, Any]] = []
    cited_evidence: list[dict[str, Any]] = []
    for index, raw in enumerate(rules['flags'], start=1):
        if not isinstance(raw, dict):
            raise ReportInputError('Invalid flag entry')
        rule_id = _text(raw.get('rule_id'), 'rule_id', 50)
        title = _text(raw.get('title'), 'rule title', 260)
        message = _text(raw.get('message'), 'rule message', 900)
        if raw.get('severity') not in ('info', 'review'):
            raise ReportInputError('Invalid rule severity')
        source = _source(raw.get('source'), rule_id, external=False)
        citation = f'R{index}'
        rule_flags.append({'rule_id': rule_id, 'title': title, 'message': message,
                           'severity': raw['severity'], 'citation': citation})
        refs.append({'citation': citation, 'origin': 'rule_based', 'reference_id': rule_id, **source})
        cited_evidence.append({'citation': citation, 'agent': 'rule_based', 'rule_id': rule_id,
                               'source': source})
    flagged = len(rule_flags)
    if flagged:
        rule_sentence = (f'Đã kiểm tra {rules["rules_evaluated"]} luật demo; có {flagged} cờ cần chú ý. '
                         'Các cờ là điều kiện tham khảo, không phải chẩn đoán.')
    else:
        rule_sentence = (f'Đã kiểm tra {rules["rules_evaluated"]} luật demo và không có cờ nào được kích hoạt. '
                         'Điều này không có nghĩa người dùng không mắc bệnh.')
    review_required = bool(rules['review_required'])
    if review_required != any(f['severity'] == 'review' for f in rule_flags):
        raise ReportInputError('Rule review flag is inconsistent')

    facts: list[dict[str, Any]] = []
    kg_knowledge_state = 'skipped'
    knowledge_sentence = 'Người dùng không gửi câu hỏi tri thức; bước Neo4j KG/RAG được bỏ qua rõ ràng.'
    if kg_state == 'ok':
        if kg.get('response_kind') not in ('grounded_extractive', 'no_evidence'):
            raise ReportInputError('Unknown knowledge response kind')
        fact_count = kg.get('retrieved_fact_count')
        if type(fact_count) is not int or not (0 <= fact_count <= 6):
            raise ReportInputError('Invalid knowledge fact count')
        evidence = [record for record in raw_evidence if isinstance(record, dict) and record.get('agent') == 'kg_rag']
        if len(evidence) != fact_count:
            raise ReportInputError('Knowledge evidence count mismatch')
        if fact_count == 0 and kg['response_kind'] != 'no_evidence':
            raise ReportInputError('Knowledge response missing evidence')
        if fact_count > 0 and kg['response_kind'] != 'grounded_extractive':
            raise ReportInputError('Knowledge response kind/evidence mismatch')
        if fact_count == 0:
            kg_knowledge_state = 'no_evidence'
            knowledge_sentence = 'Không tìm thấy tri thức có nguồn phù hợp trong Knowledge Graph hiện tại.'
        else:
            kg_knowledge_state = 'grounded'
            knowledge_sentence = f'Tìm thấy {fact_count} đoạn tri thức có nguồn từ Neo4j Knowledge Graph.'
            for index, raw in enumerate(evidence, start=1):
                excerpt = _text(raw.get('excerpt'), 'knowledge excerpt', 1600)
                fact_id = _text(raw.get('fact_id'), 'fact_id', 80)
                source = _source(raw.get('source'), fact_id, external=True)
                citation = f'K{index}'
                facts.append({'fact_id': fact_id, 'text': excerpt, 'citation': citation})
                refs.append({'citation': citation, 'origin': 'kg_rag', 'reference_id': fact_id, **source})
                cited_evidence.append({'citation': citation, 'agent': 'kg_rag', 'fact_id': fact_id,
                                       'excerpt': excerpt, 'source': source})

    limitations = [
        'Đây là bản demo học phần; không dùng để chẩn đoán, xác nhận bệnh hay quyết định điều trị.',
        'Nhãn Deep Learning là nhãn phân loại dataset; điểm kỹ thuật không mặc nhiên là xác suất mắc bệnh.',
        'Bảy luật là luật tham khảo cho bài học, chưa thay thế việc đánh giá y tế chuyên môn.',
        'Thông tin KG/RAG giới hạn ở các tài liệu đã nạp và nguồn được hiển thị; không tự suy ra tri thức ngoài bằng chứng.',
        'Không có chỉ định thuốc, liều dùng hay thay đổi phác đồ điều trị trong báo cáo này.',
    ]
    if kg_knowledge_state in ('skipped', 'no_evidence'):
        limitations.append('Chưa có bằng chứng Neo4j phù hợp cho câu hỏi trong lượt xử lý này.')

    sections = {
        'prediction': {'title': 'Kết quả mô hình Deep Learning', 'text': prediction_sentence,
                       'dataset_label': label, 'model_score_class_1': score,
                       'score_is_calibrated': calibrated, 'model_version': model_version},
        'rule_assessment': {'title': 'Các luật được kích hoạt', 'text': rule_sentence,
                            'rules_evaluated': rules['rules_evaluated'], 'review_required': review_required,
                            'flags': rule_flags},
        'knowledge': {'title': 'Tri thức và nguồn tham khảo', 'text': knowledge_sentence,
                      'knowledge_status': kg_knowledge_state, 'facts': facts},
        'limitations': {'title': 'Giới hạn và lưu ý an toàn', 'items': limitations},
    }
    lines = [
        'BÁO CÁO THAM KHẢO — HỆ ĐA AGENT CHO BỆNH TIỂU ĐƯỜNG',
        '', '1. KẾT QUẢ MÔ HÌNH', prediction_sentence,
        '', '2. ĐỐI CHIẾU LUẬT', rule_sentence,
    ]
    for flag in rule_flags:
        lines.append(f'- {flag["title"]}: {flag["message"]} [{flag["citation"]}]')
    lines.extend(['', '3. TRI THỨC CÓ NGUỒN', knowledge_sentence])
    for fact in facts:
        lines.append(f'- {fact["text"]} [{fact["citation"]}]')
    lines.extend(['', '4. GIỚI HẠN'])
    lines.extend(f'- {item}' for item in limitations)
    if refs:
        lines.extend(['', 'TÀI LIỆU THAM KHẢO'])
        for ref in refs:
            link = ref['url'] or 'Nguồn nội bộ của project (không có URL)'
            lines.append(f'[{ref["citation"]}] {ref["publisher"]} — {ref["title"]}: {link}')

    return {'title': 'Báo cáo tham khảo hệ đa Agent cho bệnh tiểu đường',
            'report_kind': 'educational_evidence_grounded_not_diagnosis',
            'generation_method': 'deterministic_template',
            'section_order': list(sections), 'sections': sections, 'sources': refs,
            'text': '\n'.join(lines), 'evidence': cited_evidence}
