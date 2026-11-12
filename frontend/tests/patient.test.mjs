import test from 'node:test';
import assert from 'node:assert/strict';
import { FIELDS, EMPTY_FORM, DEMO_FORM, DEMO_QUESTION, validatePatientForm } from '../src/lib/patient.js';

const check = (data, options) => validatePatientForm(data, options);

test('1. contract contains exact 8 backend features', () => {
  assert.deepEqual(FIELDS.map((field) => field.name), ['gender','age','hypertension','heart_disease','smoking_history','bmi','HbA1c_level','blood_glucose_level']);
});
test('2. empty form lacks all required fields', () => {
  const output = check(EMPTY_FORM);
  assert.equal(output.valid, false);
  assert.equal(Object.keys(output.errors).length, 8);
});
test('3. demo sample produces canonical backend types', () => {
  const output = check(DEMO_FORM);
  assert.equal(output.valid, true);
  assert.deepEqual(output.request.features, {gender:'Female',age:44,hypertension:0,heart_disease:0,smoking_history:'never',bmi:27.32,HbA1c_level:5.7,blood_glucose_level:140});
});
test('4. all numeric outputs are JS numbers', () => {
  const features = check(DEMO_FORM).request.features;
  for (const name of ['age','bmi','HbA1c_level','blood_glucose_level','hypertension','heart_disease']) assert.equal(typeof features[name], 'number');
});
test('5. rejects comma decimal separators to match backend', () => {
  const output = check({ ...DEMO_FORM, bmi: '27,32' });
  assert.equal(output.valid,false);
  assert.ok(output.errors.bmi);
});
test('6. rejects non-numeric values', () => {
  assert.ok(check({ ...DEMO_FORM, age:'no' }).errors.age);
  assert.ok(check({ ...DEMO_FORM, age:'NaN' }).errors.age);
});
test('7. rejects negative numbers', () => assert.ok(check({ ...DEMO_FORM, age:'-1' }).errors.age));
test('8. rejects engineering-bound violations', () => {
  assert.ok(check({ ...DEMO_FORM, HbA1c_level:'30.1' }).errors.HbA1c_level);
  assert.ok(check({ ...DEMO_FORM, blood_glucose_level:'1001' }).errors.blood_glucose_level);
});
test('9. allows backend engineering boundary values', () => {
  const output = check({ ...DEMO_FORM, age:'0', bmi:'150', HbA1c_level:'30', blood_glucose_level:'1000' });
  assert.equal(output.valid,true);
});
test('10. rejects unknown categories', () => assert.ok(check({ ...DEMO_FORM, gender:'Unknown' }).errors.gender));
test('11. rejects invalid binary flags', () => assert.ok(check({ ...DEMO_FORM, hypertension:'2' }).errors.hypertension));
test('12. optional question omitted entirely when disabled', () => {
  const output = check(DEMO_FORM, {includeQuestion:false, question:'123'});
  assert.equal(output.valid,true);
  assert.deepEqual(Object.keys(output.request),['features']);
});
test('13. question included when enabled', () => {
  const output = check(DEMO_FORM, {includeQuestion:true, question:` ${DEMO_QUESTION} `});
  assert.equal(output.valid,true);
  assert.equal(output.request.question,DEMO_QUESTION);
});
test('14. enabled empty question fails', () => assert.ok(check(DEMO_FORM,{includeQuestion:true,question:''}).errors.question));
test('15. overlong question fails', () => assert.ok(check(DEMO_FORM,{includeQuestion:true,question:'a'.repeat(501)}).errors.question));
test('16. punct-only question fails', () => assert.ok(check(DEMO_FORM,{includeQuestion:true,question:'???'}).errors.question));
test('17. extra form key is never forwarded to server', () => {
  const out = check({...DEMO_FORM, injection:'malicious'});
  assert.equal(out.valid,true);
  assert.equal('injection' in out.request.features,false);
});
