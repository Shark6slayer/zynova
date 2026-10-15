import { Capacitor } from '@capacitor/core';
import { Haptics, ImpactStyle } from '@capacitor/haptics';
import { StatusBar, Style } from '@capacitor/status-bar';

export type PlatformType = 'web' | 'android' | 'ios' | 'windows' | 'macos';

export interface DeviceInfo {
  platform: PlatformType;
  isNative: boolean;
  isMobile: boolean;
  hasTouch: boolean;
}

export class PlatformAdapter {
  /**
   * Identifies current platform and runtime environment.
   */
  static getDeviceInfo(): DeviceInfo {
    const capPlatform = Capacitor.getPlatform();
    const userAgent = typeof navigator !== 'undefined' ? navigator.userAgent.toLowerCase() : '';
    
    let platform: PlatformType = 'web';
    if (capPlatform === 'android') platform = 'android';
    else if (capPlatform === 'ios') platform = 'ios';
    else if (userAgent.includes('windows')) platform = 'windows';
    else if (userAgent.includes('macintosh')) platform = 'macos';

    const isNative = Capacitor.isNativePlatform();
    const hasTouch = typeof window !== 'undefined' && ('ontouchstart' in window || navigator.maxTouchPoints > 0);
    const isMobile = platform === 'android' || platform === 'ios' || hasTouch;

    return {
      platform,
      isNative,
      isMobile,
      hasTouch,
    };
  }

  /**
   * Triggers haptic feedback if running on a mobile native device or Web Haptics API.
   */
  static async triggerHaptic(style: 'light' | 'medium' | 'heavy' = 'light'): Promise<void> {
    try {
      if (Capacitor.isNativePlatform()) {
        const impact = 
          style === 'heavy' ? ImpactStyle.Heavy :
          style === 'medium' ? ImpactStyle.Medium : ImpactStyle.Light;
        await Haptics.impact({ style: impact });
      } else if (typeof navigator !== 'undefined' && 'vibrate' in navigator) {
        const duration = style === 'heavy' ? 40 : style === 'medium' ? 25 : 10;
        navigator.vibrate(duration);
      }
    } catch {
      // Haptics unavailable on platform
    }
  }

  /**
   * Adapts the native mobile status bar to match the theme aesthetic.
   */
  static async configureStatusBar(isDark: boolean, hexColor: string = '#090b10'): Promise<void> {
    try {
      if (Capacitor.isNativePlatform()) {
        await StatusBar.setStyle({ style: isDark ? Style.Dark : Style.Light });
        await StatusBar.setBackgroundColor({ color: hexColor });
      }
    } catch {
      // Status bar unavailable
    }
  }

  /**
   * Native file download or sharing trigger.
   */
  static async shareOrDownload(title: string, text: string, url?: string): Promise<boolean> {
    if (typeof navigator !== 'undefined' && navigator.share) {
      try {
        await navigator.share({ title, text, url });
        return true;
      } catch {
        return false;
      }
    }
    return false;
  }
}
