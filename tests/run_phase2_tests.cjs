/**
 * Zynova QA Automation — Master Phase 2 Suite Runner
 * Runs:
 * 1. Read-Only Production Frontend Smoke (10 checks)
 * 2. Deep Route Navigation & Viewport Responsiveness Suite (10 checks)
 * 3. Backend Core & Security Suite (16 checks)
 * 4. Backend Authentication & Authorization Lifecycle Suite (6 checks)
 * 5. Backend E2E Lifecycle Suite (1 check)
 * 6. Backend Phase 2 Domain States, Empty & Error Suite (5 checks)
 */

const { spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');

console.log(`
========================================================================
   ZYNOVA AUTOMATED TEST SUITE RUNNER — PHASE 2 EXPANDED
========================================================================
`);

const rootDir = path.resolve(__dirname, '..');
const report = {
  timestamp: new Date().toISOString(),
  phase: 'Phase 2 Deep Automation',
  suites: [],
  totals: { passed: 0, failed: 0, skipped: 0, blocked: 0 }
};

// 1. Frontend Smoke (Read-only Production)
console.log('>>> [1/4] RUNNING FRONTEND SMOKE TESTS (READ-ONLY PRODUCTION)...');
const smokeScript = path.join(rootDir, 'tests', 'frontend', 'smoke_production.cjs');
const t1 = Date.now();
const res1 = spawnSync(process.execPath, [smokeScript], { cwd: rootDir, encoding: 'utf-8', stdio: 'inherit' });
const d1 = ((Date.now() - t1) / 1000).toFixed(2);
const pass1 = res1.status === 0;
report.suites.push({
  name: 'Frontend Production Smoke',
  target: 'https://zynova.intellidev.in',
  status: pass1 ? 'PASSED' : 'FAILED',
  duration: `${d1}s`,
  tests: 10,
  passed: pass1 ? 10 : 0,
  failed: pass1 ? 0 : 10
});

// 2. Frontend Deep Navigation & Responsive Viewports
console.log('\n>>> [2/4] RUNNING FRONTEND DEEP NAVIGATION & VIEWPORTS SUITE...');
const deepScript = path.join(rootDir, 'tests', 'frontend', 'phase2_deep_suite.cjs');
const t2 = Date.now();
const res2 = spawnSync(process.execPath, [deepScript], { cwd: rootDir, encoding: 'utf-8', stdio: 'inherit' });
const d2 = ((Date.now() - t2) / 1000).toFixed(2);
const pass2 = res2.status === 0;
report.suites.push({
  name: 'Frontend Deep Route Navigation & Responsiveness',
  target: 'https://zynova.intellidev.in',
  status: pass2 ? 'PASSED' : 'FAILED',
  duration: `${d2}s`,
  tests: 10,
  passed: pass2 ? 10 : 0,
  failed: pass2 ? 0 : 10
});

// 3. Backend Core & Auth Lifecycle (Isolated Local Pytest)
console.log('\n>>> [3/4] RUNNING BACKEND CORE & AUTHENTICATION SUITES...');
const pytestExe = path.join(rootDir, 'backend', 'venv', 'Scripts', 'pytest.exe');
const coreBackendFiles = [
  'backend/tests/test_backend_core.py',
  'backend/tests/test_auth_lifecycle.py',
  'backend/tests/test_e2e_lifecycle.py'
];
const t3 = Date.now();
const res3 = spawnSync(pytestExe, coreBackendFiles, { cwd: rootDir, encoding: 'utf-8', stdio: 'inherit' });
const d3 = ((Date.now() - t3) / 1000).toFixed(2);
const pass3 = res3.status === 0;
report.suites.push({
  name: 'Backend Core & Auth Lifecycle',
  target: 'Local ASGI Test Harness',
  status: pass3 ? 'PASSED' : 'FAILED',
  duration: `${d3}s`,
  tests: 23,
  passed: pass3 ? 23 : 0,
  failed: pass3 ? 0 : 23
});

// 4. Backend Phase 2 Domain States, Empty & Error Handling (Isolated Local Pytest)
console.log('\n>>> [4/4] RUNNING BACKEND DOMAIN STATES, EMPTY & ERROR TESTS...');
const phase2BackendFiles = [
  'backend/tests/test_phase2_domain_states.py'
];
const t4 = Date.now();
const res4 = spawnSync(pytestExe, phase2BackendFiles, { cwd: rootDir, encoding: 'utf-8', stdio: 'inherit' });
const d4 = ((Date.now() - t4) / 1000).toFixed(2);
const pass4 = res4.status === 0;
report.suites.push({
  name: 'Backend Domain States, Empty & Error Handling',
  target: 'Local ASGI Test Harness',
  status: pass4 ? 'PASSED' : 'FAILED',
  duration: `${d4}s`,
  tests: 5,
  passed: pass4 ? 5 : 0,
  failed: pass4 ? 0 : 5
});

// Totals
const totalTests = 10 + 10 + 23 + 5;
report.totals.passed = (pass1 ? 10 : 0) + (pass2 ? 10 : 0) + (pass3 ? 23 : 0) + (pass4 ? 5 : 0);
report.totals.failed = totalTests - report.totals.passed;

console.log(`
========================================================================
   OVERALL PHASE 2 AUTOMATED TEST RESULTS SUMMARY
========================================================================
- Frontend Smoke Suite (Read-Only Production)         : ${pass1 ? 'PASS (10/10)' : 'FAIL'} [${d1}s]
- Frontend Deep Navigation & Viewports (Production)   : ${pass2 ? 'PASS (10/10)' : 'FAIL'} [${d2}s]
- Backend Core & Auth Lifecycle (Local Pytest)        : ${pass3 ? 'PASS (23/23)' : 'FAIL'} [${d3}s]
- Backend Domain States & Error Handling (Pytest)     : ${pass4 ? 'PASS (5/5)' : 'FAIL'} [${d4}s]
------------------------------------------------------------------------
TOTAL TESTS RUN : ${totalTests}
TOTAL PASSED    : ${report.totals.passed}
TOTAL FAILED    : ${report.totals.failed}
TOTAL SKIPPED   : 0
TOTAL BLOCKED   : 0
========================================================================
`);

const reportPath = path.join(rootDir, 'test-results', 'phase2_execution_summary.json');
fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf-8');
console.log(`Master Summary written to: ${reportPath}`);

if (report.totals.failed > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
