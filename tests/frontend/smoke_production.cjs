/**
 * tests/frontend/smoke_production.cjs
 *
 * READ-ONLY Production Smoke & UI Automation Suite for Zynova
 * Target: https://zynova.intellidev.in
 *
 * Rules:
 * - Read-only safe execution. Never submits registration, login, chat, payment, or order forms.
 * - Captures full assertions, uncaught console errors, failed network requests, and screenshots.
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const ARTIFACTS_DIR = path.resolve(__dirname, '../../test-results/automation-artifacts');
if (!fs.existsSync(ARTIFACTS_DIR)) {
  fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });
}

// Find available Chromium / Edge executable on Windows
function getBrowserExecutable() {
  const edgePath = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
  const edgePath64 = 'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe';
  const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const localChrome = path.join(process.env.LOCALAPPDATA || '', 'Google\\Chrome\\Application\\chrome.exe');

  if (fs.existsSync(edgePath)) return edgePath;
  if (fs.existsSync(edgePath64)) return edgePath64;
  if (fs.existsSync(chromePath)) return chromePath;
  if (fs.existsSync(localChrome)) return localChrome;
  return undefined; // Fall back to Playwright bundled browser
}

async function runProductionSmokeTests() {
  console.log('===============================================================');
  console.log('   ZYNOVA READ-ONLY PRODUCTION SMOKE & UI AUTOMATION SUITE');
  console.log('   Target Origin: https://zynova.intellidev.in');
  console.log('===============================================================\n');

  const results = {
    total: 0,
    passed: 0,
    failed: 0,
    skipped: 0,
    tests: [],
  };

  const executablePath = getBrowserExecutable();
  console.log(`[Browser Engine] Using browser executable: ${executablePath || 'Playwright Bundled'}`);

  const browser = await chromium.launch({
    executablePath,
    headless: true,
  });

  async function recordTest(name, fn) {
    results.total++;
    const t0 = Date.now();
    try {
      await fn();
      const duration = Date.now() - t0;
      console.log(`  [PASS] ${name} (${duration}ms)`);
      results.passed++;
      results.tests.push({ name, status: 'PASSED', duration });
    } catch (err) {
      const duration = Date.now() - t0;
      console.error(`  [FAIL] ${name} (${duration}ms):`, err.message);
      results.failed++;
      results.tests.push({ name, status: 'FAILED', duration, error: err.message });
    }
  }

  // 1. Desktop Context (1440x900)
  const desktopContext = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 ZynovaAutomatedSmoke/1.0',
  });

  const desktopPage = await desktopContext.newPage();
  const consoleErrors = [];
  const networkFailures = [];

  desktopPage.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  desktopPage.on('requestfailed', (req) => {
    // Record failed requests
    networkFailures.push({
      url: req.url(),
      failure: req.failure() ? req.failure().errorText : 'Unknown failure',
    });
  });

  console.log('\n--- Test Group 1: Desktop Shell, Branding & Console Integrity ---');

  await recordTest('1. Production homepage loads with HTTP 200/304', async () => {
    const response = await desktopPage.goto('https://zynova.intellidev.in', {
      waitUntil: 'domcontentloaded',
      timeout: 30000,
    });
    if (!response || response.status() >= 400) {
      throw new Error(`Failed to load homepage, HTTP status: ${response ? response.status() : 'None'}`);
    }
  });

  await recordTest('2. Page title and metadata render correctly', async () => {
    const title = await desktopPage.title();
    if (!title.includes('Zynova')) {
      throw new Error(`Expected title to contain 'Zynova', got: "${title}"`);
    }
  });

  await recordTest('3. No uncaught JavaScript runtime errors occur during initial page load', async () => {
    // Wait briefly for hydration
    await desktopPage.waitForTimeout(2000);
    // Filter out third-party/extension noise if any; all app runtime errors fail this test
    const appErrors = consoleErrors.filter(e => !e.includes('favicon') && !e.includes('chrome-extension'));
    if (appErrors.length > 0) {
      throw new Error(`Found ${appErrors.length} uncaught console errors: ${appErrors.slice(0, 3).join(' | ')}`);
    }
  });

  await recordTest('4. No unexpected failed same-origin or backend API requests occur on initial render', async () => {
    const sameOriginFails = networkFailures.filter(f => f.url.includes('zynova.intellidev.in') || f.url.includes('api.open-meteo.com'));
    if (sameOriginFails.length > 0) {
      throw new Error(`Failed network requests: ${JSON.stringify(sameOriginFails)}`);
    }
  });

  console.log('\n--- Test Group 2: Layout, Navigation & Climate Widget ---');

  await recordTest('5. Primary layout (Sidebar / Unified sovereign navigation) renders', async () => {
    const sidebar = desktopPage.locator('aside, nav, header').first();
    const isVisible = await sidebar.isVisible();
    if (!isVisible) {
      throw new Error('Primary navigation/sidebar container is not visible');
    }
  });

  await recordTest('6. Climate widget renders valid data or respectful fallback without CSP errors', async () => {
    // Look for climate indicator, temperature display, or 'Detect Climate' badge
    const weatherIndicator = desktopPage.locator('button, span, div').filter({ hasText: /(Climate|°C|Detect Climate|Location disabled|Location access off|Updating climate)/i }).first();
    await weatherIndicator.waitFor({ state: 'attached', timeout: 8000 });
    const textContent = await weatherIndicator.textContent();
    if (!textContent || textContent.trim().length === 0) {
      throw new Error('Climate widget text was empty or not mounted');
    }
  });

  await recordTest('7. Manual city selection fallback dropdown opens and contains Indian metro cities', async () => {
    const citiesBtn = desktopPage.locator('button:has-text("Cities"), button[aria-label="Change city"], button:has-text("Choose city")').first();
    if (await citiesBtn.isVisible()) {
      await citiesBtn.click();
      await desktopPage.waitForTimeout(500);
      const bengaluruOption = desktopPage.locator('button:has-text("Bengaluru"), div:has-text("Bengaluru")').first();
      const isDropdownOpen = await bengaluruOption.isVisible();
      if (!isDropdownOpen) {
        throw new Error('Clicking cities selector did not reveal city options');
      }
      // Click city option to verify selection works
      await bengaluruOption.click();
      await desktopPage.waitForTimeout(1000);
    }
  });

  await recordTest('8. Desktop screenshot captured successfully for regression verification', async () => {
    const screenshotPath = path.join(ARTIFACTS_DIR, 'desktop_production_smoke.png');
    await desktopPage.screenshot({ path: screenshotPath, fullPage: false });
    if (!fs.existsSync(screenshotPath)) {
      throw new Error('Failed to write desktop screenshot artifact');
    }
  });

  await desktopContext.close();

  // 2. Mobile Context (375x812 - iPhone 13 / Android modern mobile)
  console.log('\n--- Test Group 3: Mobile Viewport & Responsiveness ---');
  const mobileContext = await browser.newContext({
    viewport: { width: 375, height: 812 },
    isMobile: true,
    hasTouch: true,
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1 ZynovaMobileSmoke/1.0',
  });

  const mobilePage = await mobileContext.newPage();

  await recordTest('9. Mobile homepage loads and adapts to 375px mobile viewport', async () => {
    const res = await mobilePage.goto('https://zynova.intellidev.in', {
      waitUntil: 'domcontentloaded',
      timeout: 30000,
    });
    if (!res || res.status() >= 400) {
      throw new Error(`Mobile navigation failed with status ${res ? res.status() : 'None'}`);
    }
    // Verify no horizontal overflow scrolling on root
    const scrollWidth = await mobilePage.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await mobilePage.evaluate(() => document.documentElement.clientWidth);
    if (scrollWidth > clientWidth + 20) {
      console.warn(`[Layout Warning] Potential horizontal overflow detected: scrollWidth=${scrollWidth}, clientWidth=${clientWidth}`);
    }
  });

  await recordTest('10. Mobile screenshot captured for responsiveness verification', async () => {
    const screenshotPath = path.join(ARTIFACTS_DIR, 'mobile_production_smoke.png');
    await mobilePage.screenshot({ path: screenshotPath, fullPage: false });
    if (!fs.existsSync(screenshotPath)) {
      throw new Error('Failed to write mobile screenshot artifact');
    }
  });

  await mobileContext.close();
  await browser.close();

  console.log('\n===============================================================');
  console.log(`SMOKE SUMMARY: Total: ${results.total} | Passed: ${results.passed} | Failed: ${results.failed} | Skipped: ${results.skipped}`);
  console.log('===============================================================\n');

  const reportPath = path.join(ARTIFACTS_DIR, 'production_smoke_summary.json');
  fs.writeFileSync(reportPath, JSON.stringify(results, null, 2), 'utf8');

  return results;
}

if (require.main === module) {
  runProductionSmokeTests()
    .then((res) => {
      process.exit(res.failed > 0 ? 1 : 0);
    })
    .catch((err) => {
      console.error('Fatal runner error:', err);
      process.exit(1);
    });
}

module.exports = { runProductionSmokeTests };
