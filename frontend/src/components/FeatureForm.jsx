import React from 'react';
import { FIELDS } from '../lib/patient.js';
import Icon from './Icon.jsx';

export default function FeatureForm({ values, onChange, onSample, onClear, includeQuestion, setIncludeQuestion,
                                      question, setQuestion, errors, onSubmit, busy }) {
  return <section id="patient-input" className="panel input-panel" aria-labelledby="input-heading">
    <div className="panel-head">
      <div className="panel-heading-group">
        <div className="section-icon"><Icon name="sliders" size={21} /></div>
        <div>
          <div className="overline">BƯỚC 01 · DỮ LIỆU</div>
          <h2 id="input-heading">Thông tin đầu vào</h2>
          <p>8 đặc trưng theo mô hình Deep Learning</p>
        </div>
      </div>
      <button type="button" className="link-button" onClick={onSample} disabled={busy}>
        <Icon name="spark" size={16} /> Nạp mẫu
      </button>
    </div>
    <form noValidate onSubmit={onSubmit}>
      <div className="fields-grid">
        {FIELDS.map((field) => <div className="field" key={field.name}>
          <label htmlFor={`field-${field.name}`}>{field.label}</label>
          <div className={`input-shell ${errors[field.name] ? 'invalid' : ''}`}>
            {field.type === 'select' ? <select id={`field-${field.name}`}
              value={values[field.name] ?? ''} disabled={busy}
              aria-invalid={Boolean(errors[field.name])}
              aria-describedby={errors[field.name] ? `error-${field.name}` : undefined}
              onChange={(event) => onChange(field.name, event.target.value)}>
              <option value="">Chọn giá trị</option>
              {field.options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select> : <>
              <input id={`field-${field.name}`} type="text" inputMode="decimal" autoComplete="off"
                placeholder={field.placeholder} disabled={busy} value={values[field.name] ?? ''}
                aria-invalid={Boolean(errors[field.name])}
                aria-describedby={errors[field.name] ? `error-${field.name}` : undefined}
                onChange={(event) => onChange(field.name, event.target.value)} />
              <span className="unit">{field.suffix}</span>
            </>}
          </div>
          {errors[field.name] && <div id={`error-${field.name}`} className="input-error" role="alert">{errors[field.name]}</div>}
        </div>)}
      </div>
      <div className="form-divider" />
      <div className="question-header">
        <label className="toggle-label" htmlFor="include-question">
          <input id="include-question" type="checkbox" checked={includeQuestion}
            disabled={busy} onChange={(event) => setIncludeQuestion(event.target.checked)}/>
          <span className="toggle-switch" aria-hidden="true" />
          <span><strong>Tra cứu Knowledge Graph</strong><small>Gửi câu hỏi đến Neo4j KG/RAG (tùy chọn)</small></span>
        </label>
      </div>
      {includeQuestion && <div className="field question-field">
        <label htmlFor="knowledge-question">Câu hỏi về tiểu đường</label>
        <textarea id="knowledge-question" rows={3} maxLength={500} value={question}
          disabled={busy} aria-invalid={Boolean(errors.question)}
          aria-describedby={errors.question ? 'error-question' : 'question-help'}
          placeholder="Ví dụ: Bệnh tiểu đường có mấy loại chính?"
          onChange={(event) => setQuestion(event.target.value)} />
        <div className="field-help" id="question-help">Câu trả lời được trích xuất từ các nguồn hiện có trong Neo4j.</div>
        {errors.question && <div id="error-question" className="input-error" role="alert">{errors.question}</div>}
      </div>}
      <div className="form-actions">
        <button type="button" className="button-muted" disabled={busy} onClick={onClear}>
          <Icon name="refresh" size={16}/> Xóa biểu mẫu
        </button>
        <button type="submit" className="button-primary" disabled={busy}>
          {busy ? <span className="spinner" aria-hidden="true"/> : <Icon name="spark" size={17}/>}
          {busy ? 'Đang xử lý...' : 'Tạo báo cáo'}
          {!busy && <Icon name="arrow" size={17}/>}
        </button>
      </div>
      <p className="privacy-note"><Icon name="shield" size={15}/> Chỉ sử dụng dữ liệu giả lập hoặc dữ liệu được phép xử lý. Form không tự lưu lịch sử trên trình duyệt.</p>
    </form>
  </section>;
}
