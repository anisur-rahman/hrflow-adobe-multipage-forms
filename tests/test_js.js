// Tests for javascript/document.js using a small mock of Acrobat's objects.
// This checks the logic only; it is not the real Acrobat runtime.
// Run from the project root:  node tests/test_js.js

const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const vm = require('node:vm');

const VALID_VALUES = {
  first_name: 'John',
  last_name: 'Smith',
  email: 'john@example.com',
  phone: '202-555-0100',
  department: 'IT',
  job_title: 'Engineer',
  start_date: '2026-12-01',
  employment_type: 'Full-time',
  annual_salary: '120000',
  remote_employee: 'Yes',
  remote_location: 'NJ',
  health_plan: 'Individual',
  retirement_percent: '5',
  emergency_name: 'Jane',
  emergency_relationship: 'Spouse',
  emergency_phone: '202-555-0101',
  employee_name: 'John Smith',
  acknowledged: 'Yes',
};

// Load document.js into a sandbox that provides Acrobat's app and display globals.
function loadScript() {
  const alerts = [];
  const sandbox = {
    app: { alert: (message) => alerts.push(message) },
    display: { visible: 0, hidden: 1 },
  };
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync('javascript/document.js', 'utf8'), sandbox);
  return { acrobat: sandbox, alerts };
}

// A fake Acrobat Doc whose fields start with the given values.
function makeDoc(overrides = {}) {
  const values = { ...VALID_VALUES, ...overrides };
  const fields = {};
  return {
    pageNum: 0,
    submitted: null,
    getField(name) {
      if (!fields[name]) {
        fields[name] = {
          value: values[name] ?? '',
          get valueAsString() { return String(this.value); },
          setFocus() { this.focused = true; },
        };
      }
      return fields[name];
    },
    submitForm(options) { this.submitted = options; },
    resetForm() {},
  };
}

test('every page passes with valid data', () => {
  const { acrobat } = loadScript();
  const doc = makeDoc();
  for (let page = 0; page < 5; page++) {
    assert.ok(acrobat.validatePage(doc, page), `page ${page + 1} should be valid`);
  }
});

test('Next validates and moves to the following page', () => {
  const { acrobat } = loadScript();
  const doc = makeDoc();
  acrobat.nextPage(doc, 0);
  assert.equal(doc.pageNum, 1);
});

test('Next stays put and focuses the missing field', () => {
  const { acrobat, alerts } = loadScript();
  const doc = makeDoc({ last_name: '' });
  acrobat.nextPage(doc, 0);
  assert.equal(doc.pageNum, 0);
  assert.ok(doc.getField('last_name').focused);
  assert.equal(alerts.length, 1);
});

test('calculated fields show monthly salary and retirement', () => {
  const { acrobat } = loadScript();
  const doc = makeDoc();
  acrobat.updateCalculatedFields(doc);
  assert.equal(doc.getField('monthly_salary').value, '10000.00');
  assert.equal(doc.getField('retirement_monthly').value, '500.00');
  assert.equal(doc.getField('review_name').value, 'John Smith');
});

test('remote location is hidden, cleared and not required for office staff', () => {
  const { acrobat } = loadScript();
  const doc = makeDoc();
  acrobat.toggleRemoteLocation(doc, 'No');
  const location = doc.getField('remote_location');
  assert.equal(location.display, acrobat.display.hidden);
  assert.equal(location.required, false);
  assert.equal(location.value, '');
});

test('remote employees must give a location', () => {
  const { acrobat } = loadScript();
  assert.equal(acrobat.validatePage(makeDoc({ remote_location: '' }), 1), false);
});

test('impossible dates are rejected', () => {
  const { acrobat } = loadScript();
  assert.equal(acrobat.validatePage(makeDoc({ start_date: '2026-02-30' }), 1), false);
});

test('Submit sends the form as HTML to the local API', () => {
  const { acrobat } = loadScript();
  const doc = makeDoc();
  acrobat.submitAll(doc);
  assert.equal(doc.submitted.cSubmitAs, 'HTML');
  assert.equal(doc.submitted.cURL, 'http://127.0.0.1:8000/submit');
});

test('Submit stops on the first invalid page', () => {
  const { acrobat } = loadScript();
  const doc = makeDoc({ health_plan: 'Select' });
  acrobat.submitAll(doc);
  assert.equal(doc.submitted, null);
  assert.equal(doc.pageNum, 2);
});
