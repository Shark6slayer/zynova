/**
 * Comprehensive Automated Tests for India's 22-Language Experience (Phase 5)
 */
import { 
  LANGUAGE_REGISTRY, 
  SUPPORTED_LOCALES_LIST, 
  getLanguageMetadata, 
  isRtlLanguage, 
  t, 
  formatCurrencyPaise,
  getTranslationStatusReport,
  TRANSLATIONS 
} from '../src/i18n';
import type { AppLanguage } from '../src/types';

function runPhase5LocalizationTests() {
  console.log('--- STARTING PHASE 5 LOCALIZATION TESTS ---');
  let passed = 0;
  let failed = 0;

  function assert(condition: boolean, desc: string) {
    if (condition) {
      console.log(`✓ PASS: ${desc}`);
      passed++;
    } else {
      console.error(`✗ FAIL: ${desc}`);
      failed++;
    }
  }

  // 1. All 22 Eighth Schedule languages + English are present
  const required22 = [
    'as', 'bn', 'brx', 'doi', 'gu', 'hi', 'kn', 'ks',
    'kok', 'mai', 'ml', 'mni', 'mr', 'ne', 'or', 'pa',
    'sa', 'sat', 'sd', 'ta', 'te', 'ur'
  ];
  
  assert(SUPPORTED_LOCALES_LIST.length === 23, 'Supported locales count is exactly 23 (22 Eighth Schedule + English)');
  
  required22.forEach((code) => {
    const meta = (LANGUAGE_REGISTRY as any)[code];
    assert(!!meta, `Language ${code} exists in registry`);
    assert(meta && meta.name.length > 0, `Language ${code} has English name: ${meta?.name}`);
    assert(meta && meta.nativeName.length > 0, `Language ${code} has native display name: ${meta?.nativeName}`);
    assert(meta && meta.script.length > 0, `Language ${code} specifies script: ${meta?.script}`);
  });

  // 2. RTL direction validation
  assert(isRtlLanguage('ur') === true, 'Urdu (ur) is flagged as RTL');
  assert(isRtlLanguage('ks') === true, 'Kashmiri (ks) is flagged as RTL');
  assert(isRtlLanguage('sd') === true, 'Sindhi (sd) is flagged as RTL');
  assert(isRtlLanguage('ta') === false, 'Tamil (ta) is flagged as LTR');
  assert(isRtlLanguage('hi') === false, 'Hindi (hi) is flagged as LTR');
  assert(isRtlLanguage('en') === false, 'English (en) is flagged as LTR');

  // 3. Translation engine & fallback
  const testKey = 'nav.home';
  assert(t(testKey, 'ta') === 'முகப்பு', 'Tamil translation for nav.home matches');
  assert(t(testKey, 'hi') === 'होम', 'Hindi translation for nav.home matches');
  assert(t(testKey, 'ur') === 'ہوم', 'Urdu translation for nav.home matches');
  assert(t(testKey, 'en') === 'Home', 'English translation for nav.home matches');

  // 4. Missing key graceful fallback to English (never empty or key itself if English has it)
  const nonExistentKey = 'non.existent.random.key.xyz';
  assert(t(nonExistentKey, 'ta') === nonExistentKey, 'Completely missing key returns raw key without crash');

  // 5. Parameter interpolation
  const interpolated = t('home.greeting_morning', 'ta', { name: 'அனன்யா' });
  assert(interpolated.includes('அனன்யா'), `Interpolation worked: "${interpolated}"`);

  const countInterpolated = t('shopping.cart_items', 'hi', { count: 5 });
  assert(countInterpolated.includes('5'), `Plural/count interpolation worked: "${countInterpolated}"`);

  // 6. Currency Paise formatting without altering values
  const formattedPaiseEn = formatCurrencyPaise(125000, 'en');
  const formattedPaiseHi = formatCurrencyPaise(125000, 'hi');
  assert(formattedPaiseEn.includes('1,250'), `Paise 125000 formatted correctly as Rupees: ${formattedPaiseEn}`);
  assert(formattedPaiseHi.includes('1,250') || formattedPaiseHi.includes('१,२५०'), `Paise 125000 in Hindi formatted correctly: ${formattedPaiseHi}`);

  // 7. Status report verification
  const report = getTranslationStatusReport();
  assert(report['en'].completenessPercent === 100, 'English completeness is 100%');
  assert(report['ta'].translated > 0, `Tamil has ${report['ta'].translated} translated keys`);
  assert(report['hi'].translated > 0, `Hindi has ${report['hi'].translated} translated keys`);
  assert(report['ur'].translated > 0, `Urdu has ${report['ur'].translated} translated keys`);

  console.log(`\n========================================`);
  console.log(`TOTAL TESTS: ${passed + failed} | PASSED: ${passed} | FAILED: ${failed}`);
  console.log(`========================================\n`);

  if (failed > 0) {
    process.exit(1);
  }
}

runPhase5LocalizationTests();
