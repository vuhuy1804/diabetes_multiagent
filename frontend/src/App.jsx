import React, { useCallback, useEffect, useRef, useState } from 'react';
import FeatureForm from './components/FeatureForm.jsx';
import KnowledgeForm from './components/KnowledgeForm.jsx';
import KnowledgeView from './components/KnowledgeView.jsx';
import ReportView from './components/ReportView.jsx';
import Icon from './components/Icon.jsx';
import { DEMO_FORM, DEMO_QUESTION, EMPTY_FORM, validatePatientForm } from './lib/patient.js';
import { ApiError, fetchHealth, generateReport, queryKnowledge } from './lib/api.js';
import { validateKnowledgeQuestion, extractKnowledgeResult } from './lib/knowledge.js';
import { AGENT_LABELS, extractReport, getFieldIssues, getProblems, integrationCount } from './lib/report.js';

const AGENTS = [
  ['patient_data', 'Patient Data'], ['deep_learning', 'Deep Learning'],
  ['rule_based', 'Rule-Based'], ['neo4j', 'Neo4j KG/RAG'],
  ['coordinator', 'Coordinator'], ['explanation', 'Explanation'], ['monitoring', 'Monitoring'],
];

function EmptyReport({ mode }) {
  return <section className="panel empty-report" aria-live="polite" id="report-results">
    <div className="empty-icon"><Icon name="file" size={30}/></div>
    <span className="eyebrow">BƯỚC 02 · KẾT QUẢ</span>
    <h2>{mode === 'knowledge' ? 'Câu trả lời sẽ xuất hiện tại đây' : 'Báo cáo của bạn sẽ xuất hiện tại đây'}</h2>
    <p>{mode === 'knowledge' ? 'Nhập câu hỏi và nhấn Hỏi KG/RAG. Bạn không cần nhập 8 đặc trưng bệnh nhân.' : 'Điền dữ liệu và chọn Tạo báo cáo. Coordinator sẽ điều phối các Agent.'}</p>
    {mode === 'report' && <div className="empty-steps">
      {['Kiểm tra dữ liệu', 'Deep Learning', 'Đối chiếu luật', 'Truy xuất tri thức', 'Tạo báo cáo'].map((step,i)=><span key={step}><b>{i+1}</b>{step}</span>)}
    </div>}
    <div className="empty-hint"><Icon name="info" size={16}/> Dữ liệu mẫu chỉ phục vụ mô phỏng học phần.</div>
  </section>;
}

function RequestError({ error, mode }) {
  const problems = getProblems(error);
  return <section className="panel error-panel" role="alert" id="request-error">
    <div className="error-head"><Icon name="alert" size={22}/><div><h3>{mode === 'knowledge' ? 'Chưa thể tra cứu tri thức' : 'Chưa thể tạo báo cáo'}</h3><p>{error?.message || 'Đã xảy ra lỗi.'}</p></div></div>
    {problems.length > 0 && <div className="problem-list">{problems.map((problem, i)=><div key={i}>
      <strong>{AGENT_LABELS[problem.agent] || problem.agent}</strong>: {problem.error_type || 'Lỗi xử lý'}
      {Array.isArray(problem.issues) && problem.issues.length > 0 && <ul>{problem.issues.map((issue,j)=><li key={j}>{issue.field}: {issue.message}</li>)}</ul>}
    </div>)}</div>}
    <p className="retry-note">Kiểm tra dữ liệu và trạng thái Backend, sau đó thử lại. Không có báo cáo thay thế nào được tạo khi Agent lỗi.</p>
  </section>;
}

export default function App() {
  const [mode, setMode] = useState('knowledge');
  const [values, setValues] = useState({ ...EMPTY_FORM });
  const [question, setQuestion] = useState('');
  const [includeQuestion, setIncludeQuestion] = useState(true);
  const [errors, setErrors] = useState({});
  const [knowledgeError, setKnowledgeError] = useState('');
  const [health, setHealth] = useState(null);
  const [healthError, setHealthError] = useState(false);
  const [checkingHealth, setCheckingHealth] = useState(true);
  const [busy, setBusy] = useState(false);
  const [response, setResponse] = useState(null);
  const [requestError, setRequestError] = useState(null);
  const [attempts, setAttempts] = useState(0);
  const mounted = useRef(true);

  const refreshHealth = useCallback(async () => {
    setCheckingHealth(true);
    try {
      const data = await fetchHealth();
      if (mounted.current) { setHealth(data); setHealthError(false); }
    } catch {
      if (mounted.current) { setHealth(null); setHealthError(true); }
    } finally {
      if (mounted.current) setCheckingHealth(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    refreshHealth();
    return () => { mounted.current = false; };
  }, [refreshHealth]);

  function setValue(name, value) {
    setValues((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => { const next = { ...prev }; delete next[name]; return next; });
  }

  function loadSample() {
    setValues({ ...DEMO_FORM });
    setQuestion(DEMO_QUESTION);
    setIncludeQuestion(true);
    setErrors({});
    setKnowledgeError('');
    setResponse(null);
    setRequestError(null);
  }

  function clearAll() {
    setValues({ ...EMPTY_FORM });
    setQuestion('');
    setIncludeQuestion(true);
    setResponse(null);
    setErrors({});
    setKnowledgeError('');
    setRequestError(null);
    document.getElementById('patient-input')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function changeMode(next) {
    if (busy || !['knowledge','report'].includes(next)) return;
    setMode(next); setResponse(null); setRequestError(null); setErrors({}); setKnowledgeError('');
  }

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    if (mode === 'knowledge') {
      const validation = validateKnowledgeQuestion(question);
      setKnowledgeError(validation.error);
      if (!validation.valid) return;
      setBusy(true); setResponse(null); setRequestError(null); setAttempts(n => n + 1);
      try {
        const data = await queryKnowledge(validation.question);
        if (!extractKnowledgeResult(data)) throw new ApiError('Phản hồi KG/RAG không đúng hợp đồng.', {kind:'contract',data});
        setResponse(data);
      } catch (error) { setRequestError(error); }
      finally { setBusy(false); refreshHealth(); }
      return;
    }
    const validation = validatePatientForm(values, { includeQuestion, question });
    setErrors(validation.errors);
    if (!validation.valid) { document.getElementById('patient-input')?.scrollIntoView({behavior:'smooth'}); return; }
    setBusy(true);
    setResponse(null);
    setRequestError(null);
    setAttempts((n) => n + 1);
    try {
      const data = await generateReport(validation.request);
      if (!extractReport(data)) {
        setRequestError(new ApiError('Phản hồi chưa có báo cáo hoàn chỉnh. Kiểm tra Coordinator và Explanation Agent.', { kind: 'contract', data }));
      } else {
        setResponse(data);
      }
    } catch (error) {
      setRequestError(error);
      const fieldIssues = getFieldIssues(error);
      if (Object.keys(fieldIssues).length) setErrors(fieldIssues);
    } finally {
      setBusy(false);
      // Fresh readiness after each request, but not continuous monitoring.
      refreshHealth();
    }
  }

  const report = mode === 'report' && response ? extractReport(response) : null;
  const knowledgeResult = mode === 'knowledge' && response ? extractKnowledgeResult(response) : null;
  const count = integrationCount(health?.integrations) + (health?.integrations?.monitoring === 'ready' ? 1 : 0);
  const backendOnline = !checkingHealth && !healthError && health?.status === 'ok';
  const fullyReady = backendOnline && count === 7;
  const reportVisible = report !== null;

  function navigate(id) { document.getElementById(id)?.scrollIntoView({behavior:'smooth', block:'start'}); }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Icon name="pulse" size={25}/></div><div><strong>GlycoMAS</strong><small>Multi-Agent Studio</small></div></div>
      <div className="nav-label">KHÔNG GIAN LÀM VIỆC</div>
      <nav aria-label="Điều hướng trang">
        <button type="button" onClick={() => navigate('overview')} className="nav-item active"><Icon name="grid" size={19}/> Tổng quan</button>
        <button type="button" onClick={() => navigate('patient-input')} className="nav-item"><Icon name="sliders" size={19}/> Hỏi đáp / phân tích</button>
        <button type="button" onClick={() => navigate('report-results')} className="nav-item"><Icon name="file" size={19}/> Báo cáo</button>
        <button type="button" onClick={() => navigate('system-status')} className="nav-item"><Icon name="users" size={19}/> Trạng thái Agent</button>
      </nav>
      <div className="sidebar-spacer" />
      <div className="sidebar-insight"><div className="insight-top"><Icon name="spark" size={18}/> KIẾN TRÚC 6 TẦNG</div><strong>Hybrid Multi-Agent</strong><p>Deep Learning · Rule-Based · Neo4j KG/RAG · Explanation</p></div>
      <div className="sidebar-footer"><span className="sidebar-indicator"/> Bài tập cuối môn PTHTTM<br/>PTIT · Giai đoạn 8</div>
    </aside>
    <main className="workspace" id="overview">
      <div className="workspace-inner">
        <div className="topbar"><div className="breadcrumb">PTIT <span>/</span> Phát triển hệ thống thông minh <span>/</span> Demo</div><span className="topbar-tag">PHASE 08 · MULTI-AGENT</span></div>
        <header className="page-heading"><div><span className="eyebrow"><Icon name="spark" size={14}/> HỆ THỐNG HỖ TRỢ RA QUYẾT ĐỊNH</span><h1>Hệ đa Agent cho <span>bệnh tiểu đường</span></h1><p>Khám phá luồng xử lý đa tác nhân và báo cáo tham khảo dựa trên dữ liệu có nguồn.</p></div>
          <button type="button" className="refresh-button" onClick={refreshHealth} disabled={checkingHealth} title="Kiểm tra lại kết nối Backend"><Icon name="refresh" size={17}/> {checkingHealth ? 'Đang kiểm tra' : 'Kiểm tra kết nối'}</button>
        </header>
        <div className="headline-cards">
          <div className="headline-card"><span className="headline-icon blue"><Icon name="users" size={21}/></span><div><strong>7</strong><small>Agent cốt lõi đã xây dựng</small></div></div>
          <div className="headline-card"><span className="headline-icon green"><Icon name="pulse" size={21}/></span><div><strong>{checkingHealth ? '…' : `${count}/7`}</strong><small>Integration đang sẵn sàng</small></div></div>
          <div className="headline-card"><span className="headline-icon violet"><Icon name="file" size={21}/></span><div><strong>{attempts}</strong><small>Lượt gửi trong phiên này</small></div></div>
        </div>
        <section className={`connection-banner ${fullyReady ? 'is-ready' : 'not-ready'}`} id="system-status">
          <span className="connection-symbol"><Icon name={fullyReady ? 'check' : 'info'} size={18}/></span>
          <div><strong>{checkingHealth ? 'Đang kiểm tra hệ thống…' : fullyReady ? 'Backend sẵn sàng để chạy demo' : backendOnline ? 'Backend hoạt động, một số thành phần chưa ready' : 'Không kết nối được Flask API'}</strong>
            <p>{backendOnline ? `Flask ${health.phase || ''} · ${count}/7 thành phần sẵn sàng` : 'Hãy khởi động Flask tại http://127.0.0.1:5000 và bấm Kiểm tra kết nối.'}</p></div>
          <span className={`connection-chip ${fullyReady ? 'online' : 'offline'}`}>{fullyReady ? 'READY' : checkingHealth ? 'CHECKING' : 'CHECK'}</span>
        </section>
        {backendOnline && <div className="integrations-row" aria-label="Trạng thái thành phần">
          {AGENTS.map(([key, label])=><span key={key} className={`integration-badge ${health.integrations[key] === 'ready' ? 'good' : 'pending'}`}><span className="integration-dot"/>{label}</span>)}
        </div>}
        <div className="mode-switch" role="group" aria-label="Chế độ sử dụng">
          <button type="button" aria-pressed={mode === 'knowledge'} className={mode === 'knowledge' ? 'mode-tab selected' : 'mode-tab'} onClick={() => changeMode('knowledge')} disabled={busy}><Icon name="database" size={17}/> Hỏi kiến thức (không cần chỉ số)</button>
          <button type="button" aria-pressed={mode === 'report'} className={mode === 'report' ? 'mode-tab selected' : 'mode-tab'} onClick={() => changeMode('report')} disabled={busy}><Icon name="activity" size={17}/> Phân tích dữ liệu & báo cáo</button>
        </div>
        <div className="content-columns">
          <div className="left-column">{mode === 'knowledge'
            ? <KnowledgeForm question={question} onChange={(q)=>{setQuestion(q);setKnowledgeError('');}} error={knowledgeError} onSubmit={submit} busy={busy}/>
            : <FeatureForm values={values} onChange={setValue} onSample={loadSample} onClear={clearAll} includeQuestion={includeQuestion} setIncludeQuestion={(v) => {setIncludeQuestion(v); setErrors((p)=>({...p,question:undefined}));}} question={question} setQuestion={(v)=>{setQuestion(v);setErrors((p)=>({...p,question:undefined}));}} errors={errors} onSubmit={submit} busy={busy}/>}</div>
          <div className="right-column">{busy ? <section className="panel busy-panel" role="status" aria-live="polite"><span className="large-spinner"/><h2>{mode === 'knowledge' ? 'Đang tra cứu Neo4j...' : 'Coordinator đang xử lý...'}</h2><p>{mode === 'knowledge' ? 'Đang tìm các dữ kiện phù hợp trong Knowledge Graph.' : 'Đang gọi các Agent theo thứ tự và chuẩn bị báo cáo có nguồn.'}</p></section> : knowledgeResult ? <KnowledgeView result={knowledgeResult}/> : reportVisible ? <ReportView key={response?.request_id || attempts} response={response} report={report} onClear={clearAll}/> : requestError ? <RequestError error={requestError}/> : <EmptyReport mode={mode}/>}</div>
        </div>
        <footer className="page-footer"><Icon name="shield" size={17}/> <span>Bản demo học phần — không được sử dụng để chẩn đoán, kê đơn hoặc quyết định điều trị.</span><span>GlycoMAS · PTIT</span></footer>
      </div>
    </main>
  </div>;
}
