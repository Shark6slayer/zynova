export type ThemePreset = 'midnight-glass' | 'aurora-dark' | 'minimal-light' | 'monochrome' | 'indian-heritage' | 'cyber-violet';
export type AppearanceMode = 'system' | 'light' | 'dark';
export type AppLanguage = 
  | 'en'
  | 'as' | 'bn' | 'brx' | 'doi' | 'gu' | 'hi' | 'kn' | 'ks' 
  | 'kok' | 'mai' | 'ml' | 'mni' | 'mr' | 'ne' | 'or' | 'pa' 
  | 'sa' | 'sat' | 'sd' | 'ta' | 'te' | 'ur';

export type NavModuleId = 
  | 'home'
  | 'ai-assistant'
  | 'search'
  | 'chat'
  | 'social'
  | 'video'
  | 'shopping'
  | 'food'
  | 'payments'
  | 'cloud'
  | 'customization'
  | 'notifications'
  | 'settings';

export interface UserPreferences {
  theme: ThemePreset;
  appearanceMode?: AppearanceMode;
  language: AppLanguage;
  accentColor: string;
  reducedMotion: boolean;
  fontSize: 'compact' | 'normal' | 'comfortable';
  compactSidebar: boolean;
  currency: 'INR' | 'USD';
  aiMemoryEnabled: boolean;
  pinnedModules: NavModuleId[];
  hiddenModules: NavModuleId[];
  onboardingCompleted: boolean;
}

export interface NavItemConfig {
  id: NavModuleId;
  labelEn: string;
  labelTa: string;
  category: 'core' | 'connect' | 'lifestyle' | 'productivity' | 'system';
  badge?: string;
  isNew?: boolean;
}
