import type { AppLanguage } from '../types';

export interface LanguageMetadata {
  code: AppLanguage;
  name: string;
  nativeName: string;
  script: string;
  direction: 'ltr' | 'rtl';
  completeness: number; // percentage 0-100
  reviewStatus: 'reviewed' | 'provisional_catalog' | 'fallback_baseline';
}

export const LANGUAGE_REGISTRY: Record<AppLanguage, LanguageMetadata> = {
  en: {
    code: 'en',
    name: 'English',
    nativeName: 'English',
    script: 'Latin',
    direction: 'ltr',
    completeness: 100,
    reviewStatus: 'reviewed',
  },
  as: {
    code: 'as',
    name: 'Assamese',
    nativeName: 'অসমীয়া',
    script: 'Bengali-Assamese',
    direction: 'ltr',
    completeness: 85,
    reviewStatus: 'reviewed',
  },
  bn: {
    code: 'bn',
    name: 'Bengali',
    nativeName: 'বাংলা',
    script: 'Bengali',
    direction: 'ltr',
    completeness: 92,
    reviewStatus: 'reviewed',
  },
  brx: {
    code: 'brx',
    name: 'Bodo',
    nativeName: 'बड़ो',
    script: 'Devanagari',
    direction: 'ltr',
    completeness: 80,
    reviewStatus: 'reviewed',
  },
  doi: {
    code: 'doi',
    name: 'Dogri',
    nativeName: 'डोगरी',
    script: 'Devanagari',
    direction: 'ltr',
    completeness: 80,
    reviewStatus: 'reviewed',
  },
  gu: {
    code: 'gu',
    name: 'Gujarati',
    nativeName: 'ગુજરાતી',
    script: 'Gujarati',
    direction: 'ltr',
    completeness: 90,
    reviewStatus: 'reviewed',
  },
  hi: {
    code: 'hi',
    name: 'Hindi',
    nativeName: 'हिन्दी',
    script: 'Devanagari',
    direction: 'ltr',
    completeness: 100,
    reviewStatus: 'reviewed',
  },
  kn: {
    code: 'kn',
    name: 'Kannada',
    nativeName: 'ಕನ್ನಡ',
    script: 'Kannada',
    direction: 'ltr',
    completeness: 92,
    reviewStatus: 'reviewed',
  },
  ks: {
    code: 'ks',
    name: 'Kashmiri',
    nativeName: 'کٲشُر',
    script: 'Perso-Arabic',
    direction: 'rtl',
    completeness: 82,
    reviewStatus: 'reviewed',
  },
  kok: {
    code: 'kok',
    name: 'Konkani',
    nativeName: 'कोंकणी',
    script: 'Devanagari',
    direction: 'ltr',
    completeness: 82,
    reviewStatus: 'reviewed',
  },
  mai: {
    code: 'mai',
    name: 'Maithili',
    nativeName: 'मैथिली',
    script: 'Devanagari',
    direction: 'ltr',
    completeness: 82,
    reviewStatus: 'reviewed',
  },
  ml: {
    code: 'ml',
    name: 'Malayalam',
    nativeName: 'മലയാളം',
    script: 'Malayalam',
    direction: 'ltr',
    completeness: 92,
    reviewStatus: 'reviewed',
  },
  mni: {
    code: 'mni',
    name: 'Manipuri (Meitei)',
    nativeName: 'মেইতেই / মৈতৈলোন্',
    script: 'Bengali / Meetei Mayek',
    direction: 'ltr',
    completeness: 80,
    reviewStatus: 'reviewed',
  },
  mr: {
    code: 'mr',
    name: 'Marathi',
    nativeName: 'मराठी',
    script: 'Devanagari',
    direction: 'ltr',
    completeness: 92,
    reviewStatus: 'reviewed',
  },
  ne: {
    code: 'ne',
    name: 'Nepali',
    nativeName: 'नेपाली',
    script: 'Devanagari',
    direction: 'ltr',
    completeness: 86,
    reviewStatus: 'reviewed',
  },
  or: {
    code: 'or',
    name: 'Odia',
    nativeName: 'ଓଡ଼ିଆ',
    script: 'Odia',
    direction: 'ltr',
    completeness: 88,
    reviewStatus: 'reviewed',
  },
  pa: {
    code: 'pa',
    name: 'Punjabi',
    nativeName: 'ਪੰਜਾਬੀ',
    script: 'Gurmukhi',
    direction: 'ltr',
    completeness: 90,
    reviewStatus: 'reviewed',
  },
  sa: {
    code: 'sa',
    name: 'Sanskrit',
    nativeName: 'संस्कृतम्',
    script: 'Devanagari',
    direction: 'ltr',
    completeness: 88,
    reviewStatus: 'reviewed',
  },
  sat: {
    code: 'sat',
    name: 'Santali',
    nativeName: 'ᱥᱟᱱᱛᱟᱲᱤ',
    script: 'Ol Chiki',
    direction: 'ltr',
    completeness: 80,
    reviewStatus: 'reviewed',
  },
  sd: {
    code: 'sd',
    name: 'Sindhi',
    nativeName: 'سنڌي',
    script: 'Perso-Arabic',
    direction: 'rtl',
    completeness: 82,
    reviewStatus: 'reviewed',
  },
  ta: {
    code: 'ta',
    name: 'Tamil',
    nativeName: 'தமிழ்',
    script: 'Tamil',
    direction: 'ltr',
    completeness: 100,
    reviewStatus: 'reviewed',
  },
  te: {
    code: 'te',
    name: 'Telugu',
    nativeName: 'తెలుగు',
    script: 'Telugu',
    direction: 'ltr',
    completeness: 92,
    reviewStatus: 'reviewed',
  },
  ur: {
    code: 'ur',
    name: 'Urdu',
    nativeName: 'اردو',
    script: 'Perso-Arabic',
    direction: 'rtl',
    completeness: 95,
    reviewStatus: 'reviewed',
  },
};

export const SUPPORTED_LOCALES_LIST: LanguageMetadata[] = Object.values(LANGUAGE_REGISTRY);

export function getLanguageMetadata(code: string): LanguageMetadata {
  return (LANGUAGE_REGISTRY as any)[code] || LANGUAGE_REGISTRY['en'];
}

export function isRtlLanguage(code: string): boolean {
  return getLanguageMetadata(code).direction === 'rtl';
}
