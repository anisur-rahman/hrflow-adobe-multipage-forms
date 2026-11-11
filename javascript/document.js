/*
 * Document-level JavaScript for the HRFlow onboarding form.
 *
 * Acrobat runs an older JavaScript engine, so this file sticks to ES5:
 * var instead of let/const, and no arrow functions or template strings.
 * Page numbers are zero-based, matching Acrobat's doc.pageNum.
 */

var PAGE_COUNT = 5;
var SUBMIT_URL = 'http://127.0.0.1:8000/submit';
var MAX_SALARY = 9999999999.99; // NUMERIC(12,2) in the database

// Fields that must be filled before leaving each page.
var REQUIRED_FIELDS = [
  ['first_name', 'last_name', 'email', 'phone'],
  ['department', 'job_title', 'start_date', 'employment_type', 'annual_salary', 'remote_employee'],
  ['health_plan', 'retirement_percent'],
  ['emergency_name', 'emergency_relationship', 'emergency_phone'],
  ['employee_name']
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fieldValue(doc, name) {
  return String(doc.getField(name).valueAsString).replace(/^\s+|\s+$/g, '');
}

function isBlank(value) {
  // Dropdowns start on a "Select" placeholder, which counts as empty.
  return value === '' || value === 'Select';
}

function showError(doc, name, message) {
  app.alert(message);
  doc.getField(name).setFocus();
  return false;
}

function isValidIsoDate(text) {
  var parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
  if (!parts) {
    return false;
  }
  var year = Number(parts[1]);
  var month = Number(parts[2]) - 1;
  var day = Number(parts[3]);
  var date = new Date(year, month, day);
  // new Date() rolls invalid dates over (Feb 30 -> Mar 2), so compare back.
  return date.getFullYear() === year && date.getMonth() === month && date.getDate() === day;
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

function validatePage(doc, page) {
  var required = REQUIRED_FIELDS[page];
  for (var i = 0; i < required.length; i++) {
    if (isBlank(fieldValue(doc, required[i]))) {
      return showError(doc, required[i], 'Complete ' + required[i]);
    }
  }

  if (page === 0 && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(fieldValue(doc, 'email'))) {
    return showError(doc, 'email', 'Enter a valid email.');
  }

  if (page === 1) {
    var salary = Number(fieldValue(doc, 'annual_salary'));
    if (!isFinite(salary) || salary <= 0 || salary > MAX_SALARY) {
      return showError(doc, 'annual_salary', 'Enter a positive salary within 10 digits.');
    }
    if (!isValidIsoDate(fieldValue(doc, 'start_date'))) {
      return showError(doc, 'start_date', 'Use a valid YYYY-MM-DD date.');
    }
    if (fieldValue(doc, 'remote_employee') === 'Yes' && !fieldValue(doc, 'remote_location')) {
      return showError(doc, 'remote_location', 'Enter remote location.');
    }
  }

  if (page === 2) {
    var percent = Number(fieldValue(doc, 'retirement_percent'));
    if (!isFinite(percent) || percent < 0 || percent > 100) {
      return showError(doc, 'retirement_percent', 'Enter 0 to 100.');
    }
  }

  if (page === 4 && fieldValue(doc, 'acknowledged') !== 'Yes') {
    return showError(doc, 'acknowledged', 'Confirm acknowledgment.');
  }

  return true;
}

// ---------------------------------------------------------------------------
// Calculations (also used by the calculated fields' own scripts)
// ---------------------------------------------------------------------------

function monthlySalary(doc) {
  var annual = Number(fieldValue(doc, 'annual_salary'));
  return annual > 0 ? (annual / 12).toFixed(2) : '';
}

function monthlyRetirement(doc) {
  var annual = Number(fieldValue(doc, 'annual_salary'));
  var percent = Number(fieldValue(doc, 'retirement_percent'));
  if (!(annual > 0) || !(percent >= 0 && percent <= 100)) {
    return '';
  }
  return (annual / 12 * percent / 100).toFixed(2);
}

function reviewName(doc) {
  return fieldValue(doc, 'first_name') + ' ' + fieldValue(doc, 'last_name');
}

function updateCalculatedFields(doc) {
  doc.getField('monthly_salary').value = monthlySalary(doc);
  doc.getField('retirement_monthly').value = monthlyRetirement(doc);
  doc.getField('review_name').value = reviewName(doc);
  doc.getField('review_email').value = fieldValue(doc, 'email');
  doc.getField('review_department').value = fieldValue(doc, 'department');
  doc.getField('review_salary').value = fieldValue(doc, 'annual_salary');
}

// ---------------------------------------------------------------------------
// Conditional field: remote location is only shown and required for "Yes"
// ---------------------------------------------------------------------------

function toggleRemoteLocation(doc, answer) {
  var location = doc.getField('remote_location');
  var isRemote = answer === 'Yes';
  location.display = isRemote ? display.visible : display.hidden;
  location.required = isRemote;
  if (!isRemote) {
    location.value = '';
  }
}

// ---------------------------------------------------------------------------
// Button actions
// ---------------------------------------------------------------------------

function nextPage(doc, page) {
  if (validatePage(doc, page)) {
    updateCalculatedFields(doc);
    doc.pageNum = page + 1;
  }
}

function submitAll(doc) {
  // Check every page, not just the last one: the viewer's own page controls
  // let people skip ahead without pressing Next.
  for (var page = 0; page < PAGE_COUNT; page++) {
    doc.pageNum = page;
    if (!validatePage(doc, page)) {
      return;
    }
  }
  updateCalculatedFields(doc);
  doc.submitForm({ cURL: SUBMIT_URL, cSubmitAs: 'HTML', bEmpty: true });
}

function resetAll(doc) {
  doc.resetForm();
  toggleRemoteLocation(doc, 'No');
  updateCalculatedFields(doc);
  doc.pageNum = 0;
}
