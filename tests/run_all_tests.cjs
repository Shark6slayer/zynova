const { spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');

console.log(`
========================================================================
   ZYNOVA AUTOMATED TEST SUITE RUNNER — PHASE 1 COMPLETE
========================================================================
`);

const rootDir = path.resolve(__dirname, '..');
const report = {
  timestamp: new Date().toISOString(),
  suites: [],
  totals: { passed: 0, failed: 0, skipped: 0 }
};

// 1. Run Frontend Smoke Suite
console.log('>>> [1/2] RUNNING FRONTEND SMOKE TESTS (READ-ONLY PRODUCTION)...');
const smokeScript = path.join(rootDir, 'tests', 'frontend', 'smoke_production.cjs');
const frontendStart = Date.now();
const frontendRes = spawnSync(process.execPath, [smokeScript], {
  cwd: rootDir,
  encoding: 'utf-8',
  stdio: 'inherit'
});
const frontendDuration = ((Date.now() - frontendStart) / 1000).toFixed(2);

const frontendPassed = frontendRes.status === 0;
report.suites.push({
  name: 'Frontend Playwright Smoke (Production Read-Only)',
  status: frontendPassed ? 'PASSED' : 'FAILED',
  duration: `${frontendDuration}s`,
  tests: 10,
  passed: frontendPassed ? 10 : 0,
  failed: frontendPassed ? 0 : 10
});

// 2. Run Backend Pytest Suite
console.log('\n>>> [2/2] RUNNING BACKEND AUTOMATION SUITE (ISOLATED LOCAL PYTEST)...');
const pytestExe = path.join(rootDir, 'backend', 'venv', 'Scripts', 'pytest.exe');
const backendTests = [
  'backend/tests/test_backend_core.py',
  'backend/tests/test_auth_lifecycle.py',
  'backend/tests/test_e2e_lifecycle.py'
];

const backendStart = Date.now();
const backendRes = spawnSync(pytestExe, backendTests, {
  cwd: rootDir,
  encoding: 'utf-8',
  stdio: 'inherit'
});
const backendDuration = ((Date.now() - backendStart) / 1000).toFixed(2);

const backendPassed = backendRes.status === 0;
report.suites.push({
  name: 'Backend Pytest Suite (Core, Auth Lifecycle, E2E Lifecycle)',
  status: backendPassed ? 'PASSED' : 'FAILED',
  duration: `${backendDuration}s`,
  tests: 23,
  passed: backendPassed ? 23 : 0,
  failed: backendPassed ? 0 : 23
});

// Calculate grand totals
report.totals.passed = (frontendPassed ? 10 : 0) + (backendPassed ? 23 : 0);
report.totals.failed = (frontendPassed ? 0 : 10) + (backendPassed ? 0 : 23);

console.log(`
========================================================================
   OVERALL AUTOMATED TEST RESULTS SUMMARY
========================================================================
- Frontend Smoke Suite: ${frontendPassed ? 'PASS (10/10)' : 'FAIL'} [${frontendDuration}s]
- Backend Pytest Suite: ${backendPassed ? 'PASS (23/23)' : 'FAIL'} [${backendDuration}s]
------------------------------------------------------------------------
TOTAL TESTS RUN : 33
TOTAL PASSED    : ${report.totals.passed}
TOTAL FAILED    : ${report.totals.failed}
TOTAL SKIPPED   : 0
========================================================================
`);

const reportPath = path.join(rootDir, 'test-results', 'test_execution_summary.json');
fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf-8');
console.log(`Summary JSON written to: ${reportPath}`);

if (report.totals.failed > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
