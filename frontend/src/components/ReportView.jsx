import React, { useState } from 'react';
import Icon from './Icon.jsx';
import { AGENT_LABELS, fmtDuration, isSafeReferenceUrl } from '../lib/report.js';

const statusName = { ok: 'Hoàn thành', skipped: 'Bỏ qua', error: 'Lỗi' };

function FieldText({ value }) { return <span>{value == null ? '—' : String(value)}</span>; }

function Sources({ sources }) {
  if (!Array.isArray(sources) || sources.length === 0) return <p className="muted">Chưa có nguồn tham khảo trong lượt này.</p>;
  return <div className="sources-list">
    {sources.map((source, i) => <div className="source-entry" key={`${source.citation}-${i}`}>
      <span className="citation">{source.citation || `S${i + 1}`}</span>
      <div>
        <strong>{source.title || 'Nguồn tham khảo'}</strong>
        <small>{source.publisher || 'Nguồn nội bộ'} · {source.origin === 'kg_rag' ? 'Neo4j KG/RAG' : 'Rule-Based'}</small>
        {isSafeReferenceUrl(source.url) ? <a href={source.url} target="_blank" rel="noopener noreferrer">
          Mở tài liệu nguồn <Icon name="external" size={13}/>
        </a> : <span className="source-internal">Không có URL công khai</span>}
      </div>
    </div>)}
  </div>;
}

export default function ReportView({ response, report, onClear }) {
  const [expanded, setExpanded] = useState('report');
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const sections = report.sections || {};
  const prediction = sections.prediction || {};
  const rules = sections.rule_assessment || {};
  const knowledge = sections.knowledge || {};
  const limitations = sections.limitations || {};
  const flags = Array.isArray(rules.flags) ? rules.flags : [];
  const facts = Array.isArray(knowledge.facts) ? knowledge.facts : [];
  const steps = Array.isArray(response?.payload?.steps) ? response.payload.steps : [];

  async function handleCopy() {
    if (!report.text || !navigator.clipboard?.writeText) {
      setCopyError(true);
      return;
    }
    try { await navigator.clipboard.writeText(report.text); setCopied(true); setCopyError(false); }
    catch { setCopyError(true); }
  }

  return <div className="report-stack" id="report-results">
    <section className="panel report-panel">
      <div className="panel-head panel-head-result">
        <div className="panel-heading-group">
          <div className="section-icon result-icon"><Icon name="file" size={21}/></div>
          <div>
            <div className="overline">BƯỚC 02 · KẾT QUẢ</div>
            <h2>Báo cáo tham khảo</h2>
            <p>Được tạo từ 5 Agent và dữ liệu nguồn</p>
          </div>
        </div>
        <span className="status-pill success"><span className="status-dot"/> Hoàn thành</span>
      </div>
      <div className="report-body">
        <div className="report-meta"><span>Request ID: <code title={response.request_id}>{response.request_id?.slice(0, 14) || '—'}…</code></span><span>Phương pháp: Template-based</span></div>
        <div className="prediction-card">
          <div className="prediction-top"><Icon name="activity" size={18}/> MÔ HÌNH DEEP LEARNING</div>
          <div className="prediction-main">
            <div><span className="prediction-label">Nhãn dự đoán dataset</span><strong className="prediction-value"><FieldText value={prediction.dataset_label}/></strong></div>
            <div><span className="prediction-label">Điểm kỹ thuật lớp 1</span><strong className="prediction-value"><FieldText value={prediction.model_score_class_1}/></strong></div>
          </div>
          <p>{prediction.text || 'Không có mô tả từ backend.'}</p>
          <small>Model: {prediction.model_version || '—'} · Không diễn giải nhãn hoặc score như chẩn đoán hay xác suất mắc bệnh.</small>
        </div>
        <div className="subsection-title"><Icon name="shield" size={18}/> Đối chiếu Rule-Based</div>
        <p className="report-description">{rules.text || 'Chưa có thông tin luật.'}</p>
        {flags.length ? <div className="flags-list">{flags.map((flag, i) => <div className="flag" key={`${flag.rule_id}-${i}`}>
          <span className={`flag-severity ${flag.severity === 'review' ? 'review' : 'informational'}`}>{flag.severity === 'review' ? 'Cần xem xét' : 'Thông tin'}</span>
          <div><strong>{flag.title || flag.rule_id}</strong><p>{flag.message}</p><small>{flag.rule_id} · [{flag.citation}]</small></div>
        </div>)}</div> : <p className="muted" >Không có cờ luật nào được kích hoạt. Điều này không khẳng định người dùng không mắc bệnh.</p>}
        <div className="subsection-title"><Icon name="database" size={18}/> Tri thức từ Neo4j</div>
        <p className="report-description">{knowledge.text || 'Chưa có thông tin tri thức.'}</p>
        {facts.length ? <div className="knowledge-list">{facts.map((fact, i) => <div key={`${fact.fact_id}-${i}`} className="knowledge-item">
          <span className="citation">{fact.citation || `K${i + 1}`}</span><p>{fact.text}</p>
        </div>)}</div> : <div className="empty-evidence">{knowledge.knowledge_status === 'skipped' ? 'KG/RAG được bỏ qua vì không có câu hỏi.' : 'Không có bằng chứng phù hợp trong lượt này.'}</div>}
        <div className="subsection-title"><Icon name="info" size={18}/> Giới hạn và lưu ý</div>
        <ul className="limitations-list">{(limitations.items || []).map((item, i) => <li key={i}>{item}</li>)}</ul>
        <div className="report-cta">
          <button type="button" className="button-secondary" onClick={handleCopy}><Icon name="copy" size={16}/> {copied ? 'Đã sao chép' : 'Sao chép báo cáo'}</button>
          <button type="button" className="link-button" onClick={onClear}>Tạo lượt mới <Icon name="arrow" size={16}/></button>
        </div>
        {copyError && <div className="inline-alert">Trình duyệt không cho phép sao chép tự động. Bạn có thể mở phần văn bản bên dưới để sao chép thủ công.</div>}
        <details className="details-panel" open={expanded === 'report'} onToggle={(event) => { if(event.currentTarget.open) setExpanded('report'); }}>
          <summary>Văn bản báo cáo đầy đủ</summary><pre>{report.text || ''}</pre>
        </details>
      </div>
    </section>
    <section className="panel" id="agent-trace">
      <div className="secondary-panel-heading"><div><h3>Nhật ký thực thi trong lượt</h3><p>{response?.payload?.audit_recorded === true
        ? 'Audit đã ghi metadata vào SQLite; không lưu chỉ số đầu vào, câu hỏi hoặc báo cáo'
        : 'Audit chưa ghi thành công. Kiểm tra trạng thái Monitoring và Backend'}</p></div><span className="count-chip">{steps.length} bước</span></div>
      <div className="trace-list">{steps.map((step, i) => <div className="trace-row" key={`${step.agent}-${i}`}>
        <span className={`trace-index ${step.status === 'ok' ? 'active' : ''}`}>{i + 1}</span>
        <div><strong>{AGENT_LABELS[step.agent] || step.agent}</strong><small>{step.version || '—'}</small></div>
        <span className={`trace-status ${step.status}`}>{statusName[step.status] || step.status}</span>
        <time>{fmtDuration(step.duration_ms)}</time>
      </div>)}</div>
    </section>
    <section className="panel" id="reference-sources"><div className="secondary-panel-heading"><div><h3>Tài liệu tham khảo</h3><p>Trích dẫn từ Rule-Based và Neo4j</p></div><span className="count-chip">{report.sources?.length || 0} nguồn</span></div><Sources sources={report.sources}/></section>
    <details className="raw-json"><summary>Dữ liệu JSON phản hồi (dành cho kiểm thử)</summary><pre>{JSON.stringify(response, null, 2)}</pre></details>
  </div>;
}
