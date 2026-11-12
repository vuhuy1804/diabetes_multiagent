import React from 'react';
import Icon from './Icon.jsx';
const EXAMPLES = ['Bệnh tiểu đường nên ăn gì?', 'Tiểu đường có những triệu chứng nào?', 'Có mấy loại bệnh tiểu đường?'];
export default function KnowledgeForm({ question, onChange, error, onSubmit, busy }) {
  return <section id="patient-input" className="panel input-panel knowledge-form" aria-labelledby="knowledge-heading">
    <div className="panel-head"><div className="panel-heading-group"><div className="section-icon"><Icon name="database" size={21}/></div><div>
      <div className="overline">CHẾ ĐỘ HỎI ĐÁP</div><h2 id="knowledge-heading">Hỏi kiến thức bệnh tiểu đường</h2>
      <p>Không cần nhập dữ liệu bệnh nhân</p>
    </div></div></div>
    <form noValidate onSubmit={onSubmit}>
      <div className="field question-field"><label htmlFor="knowledge-question">Câu hỏi của bạn</label>
        <textarea id="knowledge-question" rows={5} maxLength={500} disabled={busy} value={question}
          placeholder="Ví dụ: Bệnh tiểu đường nên ăn gì?" aria-invalid={Boolean(error)}
          onChange={e => onChange(e.target.value)}/>
        {error && <div className="input-error" role="alert">{error}</div>}
        <p className="field-help">Câu trả lời được trích từ tri thức hiện có trong Neo4j, kèm nguồn tham khảo.</p>
      </div>
      <div className="example-questions"><strong>Câu hỏi gợi ý</strong>{EXAMPLES.map(x =>
        <button type="button" className="example-chip" key={x} disabled={busy} onClick={() => onChange(x)}>{x}</button>)}</div>
      <div className="form-actions"><button type="button" className="button-muted" onClick={() => onChange('')} disabled={busy}>Xóa câu hỏi</button>
        <button type="submit" className="button-primary" disabled={busy}>{busy ? 'Đang tra cứu...' : 'Hỏi KG/RAG'} <Icon name="arrow" size={16}/></button>
      </div><p className="privacy-note"><Icon name="shield" size={15}/> Nội dung giáo dục, không thay thế lời khuyên của nhân viên y tế.</p>
    </form>
  </section>;
}
