import React from 'react';
import Icon from './Icon.jsx';
import { isSafeReferenceUrl } from '../lib/report.js';
export default function KnowledgeView({ result }) {
  return <section className="panel knowledge-answer-panel" id="report-results" aria-live="polite">
    <div className="panel-head"><div className="panel-heading-group"><div className="section-icon result-icon"><Icon name="database" size={21}/></div><div>
      <div className="overline">TRI THỨC NEO4J</div><h2>Trả lời có nguồn tham khảo</h2><p>Chỉ truy xuất KG/RAG, không chạy Deep Learning</p>
    </div></div></div>
    <div className="report-body"><div className="knowledge-question-label">Câu hỏi</div><p className="knowledge-question-text">{result.question}</p>
      {result.kind === 'no_evidence' ? <div className="knowledge-no-evidence" role="status">
        <strong>Chưa có thông tin phù hợp</strong><p>{result.answer}</p>
        <p>Knowledge Graph hiện tại có phạm vi giới hạn. Bạn có thể thử câu hỏi về dinh dưỡng, loại bệnh, triệu chứng hoặc xét nghiệm.</p></div>
      : <><div className="knowledge-answer-text">{result.answer}</div>
        <h3 className="subsection-title">Nguồn dẫn chứng ({result.evidence.length})</h3>
        <div className="sources-list">{result.evidence.map((e,idx)=><div className="source-entry" key={`${e.fact_id}-${idx}`}>
          <span className="citation">{idx+1}</span><div><strong>{e.source?.title || 'Nguồn tham khảo'}</strong>
          <small>{e.source?.publisher || 'Không xác định'} · {e.topic_name}</small>
          {isSafeReferenceUrl(e.source?.url) && <a href={e.source.url} target="_blank" rel="noopener noreferrer">Mở tài liệu nguồn <Icon name="external" size={13}/></a>}</div>
        </div>)}</div></>}
      <p className="knowledge-disclaimer">Chỉ là thông tin sức khỏe tổng quát phục vụ bài tập cuối môn, không dùng để chẩn đoán hoặc thay đổi điều trị.</p>
    </div>
  </section>;
}
