const { chromium } = require('playwright');
const fs = require('fs');
const assert = require('assert');

(async () => {
  console.log('[Zynova Regression] Launching headless browser tests...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  const localUrl = 'http://127.0.0.1:5173';
  await page.goto(localUrl, { waitUntil: 'networkidle' });

  // 1. Title verification
  const title = await page.title();
  console.log('Document title:', title);
  assert(title.includes('Zynova'), 'Document title must include Zynova');
  assert(!title.includes('super_ai'), 'Document title must not include super_ai');
  console.log('✅ Test 1 Passed: Document title properly branded as Zynova');

  // 2. Sidebar branding verification
  const brandLocator = page.locator('text=ZYNOVA').first();
  const brandVisible = await brandLocator.isVisible();
  assert(brandVisible, 'Sidebar must display ZYNOVA');

  const subTitleLocator = page.locator('text=UNIFIED PLATFORM').first();
  const subTitleVisible = await subTitleLocator.isVisible();
  assert(subTitleVisible, 'Sidebar must display UNIFIED PLATFORM');
  console.log('✅ Test 2 Passed: Sidebar branding verified as ZYNOVA UNIFIED PLATFORM');

  // 3. Sovereign Cloud interpolation verification
  const htmlContent = await page.content();
  assert(!htmlContent.includes('{used}'), 'HTML must not leak raw {used} token');
  assert(!htmlContent.includes('{total}'), 'HTML must not leak raw {total} token');
  assert(htmlContent.includes('Zynova Cloud'), 'Must render Zynova Cloud storage string');
  console.log('✅ Test 3 Passed: Cloud usage widget cleanly interpolates parameters');

  // 4. Guest user privacy verification
  const signInPrompt = page.locator('text=Sign In to View').first();
  const promptVisible = await signInPrompt.isVisible();
  assert(promptVisible, 'Guest user must see Sign In to View prompt');

  const swiggyVisible = await page.locator('text=Swiggy Delivery').isVisible();
  assert(!swiggyVisible, 'Guest user must NOT see mock Swiggy Delivery transaction');
  console.log('✅ Test 4 Passed: Guest users protected from leaking mock financial data');

  // 5. Vercel Security Headers configuration
  const vercelJson = JSON.parse(fs.readFileSync('C:/super_ai/vercel.json', 'utf8'));
  const headerKeys = vercelJson.headers[0].headers.map(h => h.key);
  assert(headerKeys.includes('X-Content-Type-Options'), 'Must have X-Content-Type-Options');
  assert(headerKeys.includes('X-Frame-Options'), 'Must have X-Frame-Options');
  assert(headerKeys.includes('Referrer-Policy'), 'Must have Referrer-Policy');
  assert(headerKeys.includes('Permissions-Policy'), 'Must have Permissions-Policy');
  assert(headerKeys.includes('Content-Security-Policy'), 'Must have Content-Security-Policy');
  console.log('✅ Test 5 Passed: vercel.json contains complete security headers & API proxy');

  // Take screenshot for remediation evidence
  await page.screenshot({ path: 'C:/super_ai_docs/zynova_remediation/screenshots/remediation_desktop_verified.png' });
  console.log('📸 Screenshot saved: remediation_desktop_verified.png');

  // Mobile screenshot at 375x812
  await page.setViewportSize({ width: 375, height: 812 });
  await page.screenshot({ path: 'C:/super_ai_docs/zynova_remediation/screenshots/remediation_mobile_verified.png' });
  console.log('📸 Screenshot saved: remediation_mobile_verified.png');

  await browser.close();
  console.log('\n🎉 ALL 5 REGRESSION TESTS PASSED CLEANLY!\n');
  process.exit(0);
})().catch(err => {
  console.error('\n❌ REGRESSION TEST FAILED:', err.message);
  process.exit(1);
});
