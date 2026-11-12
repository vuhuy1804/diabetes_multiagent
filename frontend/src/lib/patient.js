// Mirrors backend/core/features.py (8 features). The server remains authoritative.
// Ranges are engineering input bounds, NOT medical reference ranges.
export const FIELDS = Object.freeze([
  { name: 'gender', label: 'Giới tính trong dataset', type: 'select', options: [
    { value: 'Female', label: 'Female — Nữ' },
    { value: 'Male', label: 'Male — Nam' },
    { value: 'Other', label: 'Other — Khác' },
  ] },
  { name: 'age', label: 'Tuổi', type: 'number', suffix: 'năm', min: 0, max: 120, placeholder: 'Ví dụ: 44' },
  { name: 'hypertension', label: 'Tăng huyết áp (nhãn dữ liệu)', type: 'select', options: [
    { value: '0', label: '0 — Không' }, { value: '1', label: '1 — Có' },
  ] },
  { name: 'heart_disease', label: 'Bệnh tim (nhãn dữ liệu)', type: 'select', options: [
    { value: '0', label: '0 — Không' }, { value: '1', label: '1 — Có' },
  ] },
  { name: 'smoking_history', label: 'Lịch sử hút thuốc trong dataset', type: 'select', options: [
    { value: 'No Info', label: 'No Info — Không có thông tin' },
    { value: 'never', label: 'never — Chưa từng' },
    { value: 'former', label: 'former — Trước đây' },
    { value: 'current', label: 'current — Hiện tại' },
    { value: 'ever', label: 'ever — Đã từng' },
    { value: 'not current', label: 'not current — Không hiện tại' },
  ] },
  { name: 'bmi', label: 'BMI', type: 'number', suffix: 'kg/m²', min: 0, max: 150, placeholder: 'Ví dụ: 27.32' },
  { name: 'HbA1c_level', label: 'HbA1c', type: 'number', suffix: '%', min: 0, max: 30, placeholder: 'Ví dụ: 5.7' },
  { name: 'blood_glucose_level', label: 'Glucose máu', type: 'number', suffix: 'mg/dL', min: 0, max: 1000, placeholder: 'Ví dụ: 140' },
]);

export const EMPTY_FORM = Object.freeze(Object.fromEntries(FIELDS.map((field) => [field.name, ''])));
export const DEMO_FORM = Object.freeze({
  gender: 'Female', age: '44', hypertension: '0', heart_disease: '0',
  smoking_history: 'never', bmi: '27.32', HbA1c_level: '5.7', blood_glucose_level: '140',
});
export const DEMO_QUESTION = 'Bệnh tiểu đường có mấy loại chính?';
const DECIMAL_PATTERN = /^(?:\d+)(?:\.\d+)?$/;
const BINARY_FIELDS = new Set(['hypertension', 'heart_disease']);

export function validatePatientForm(values, { includeQuestion = false, question = '' } = {}) {
  const errors = {};
  const features = {};
  for (const field of FIELDS) {
    const raw = values?.[field.name];
    const value = typeof raw === 'string' ? raw.trim() : String(raw ?? '').trim();
    if (!value) {
      errors[field.name] = 'Vui lòng nhập trường này.';
      continue;
    }
    if (field.type === 'select') {
      const allowed = field.options.some((option) => option.value === value);
      if (!allowed) {
        errors[field.name] = 'Lựa chọn không hợp lệ.';
        continue;
      }
      features[field.name] = BINARY_FIELDS.has(field.name) ? Number(value) : value;
      continue;
    }
    if (!DECIMAL_PATTERN.test(value)) {
      errors[field.name] = 'Nhập số với dấu chấm thập phân, ví dụ 5.7.';
      continue;
    }
    const number = Number(value);
    if (!Number.isFinite(number) || number < field.min || number > field.max) {
      errors[field.name] = `Khoảng dữ liệu hỗ trợ: ${field.min}–${field.max}.`;
      continue;
    }
    features[field.name] = number;
  }
  let cleanQuestion;
  if (includeQuestion) {
    cleanQuestion = typeof question === 'string' ? question.trim() : '';
    if (cleanQuestion.length < 3 || cleanQuestion.length > 500 || !/[\p{L}\p{N}]/u.test(cleanQuestion)) {
      errors.question = 'Câu hỏi cần từ 3–500 ký tự và có nội dung tìm kiếm.';
    }
  }
  return {
    valid: Object.keys(errors).length === 0,
    errors,
    // Never send caller-provided keys other than the documented 8 features and optional question.
    request: includeQuestion ? { features, question: cleanQuestion } : { features },
  };
}
