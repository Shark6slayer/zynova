# SUPER_AI — Cross-Platform Deployment Guide

This guide details how to build, run, and package the unified SUPER_AI application across **Web**, **Android**, **iOS**, and **Windows Desktop**.

---

## 1. Shared Web Architecture
The application is built on **React 19 + TypeScript + Vite 8 + Tailwind CSS 4**, bundled into the static distribution directory `dist/`.

### Local Development
- **Frontend**: `http://127.0.0.1:5173/` (`npm run dev`)
- **FastAPI Backend**: `http://127.0.0.1:8000/` (`.\backend\venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000`)
- **MongoDB**: `127.0.0.1:27017`

---

## 2. Android Packaging (Capacitor)

### Architecture
Uses **Capacitor 8** to wrap the responsive React web application inside an Android WebView container with native bridging for status bar theming, touch haptics, and soft-keyboard management via `PlatformAdapter`.

### Prerequisites for Compiling Android APK / App Bundle
1. **Java Development Kit (JDK 21 or JDK 17)**:
   - Download from Oracle or Adoptium Temurin.
   - Set environment variable `JAVA_HOME`.
2. **Android Studio & SDK**:
   - Install Android Studio, Android SDK Platform-Tools, and Android Build-Tools.
   - Set `ANDROID_HOME` in environment variables.

### Build and Sync Commands
```powershell
# 1. Install Android native platform template (first time)
npm install @capacitor/android
npx cap add android

# 2. Build production web bundle and sync assets into Android project
npm run cap:build

# 3. Open in Android Studio to build APK or run on an emulator
npm run cap:android
```

---

## 3. iOS Packaging (Capacitor)

### Architecture
Uses **Capacitor 8** targeting iOS 15+ devices with native safe area insets and status bar style adaptation.

### Prerequisites (Mandatory macOS & Xcode)
- Building native iOS apps requires a machine running **macOS** with **Xcode 16+** and CocoaPods installed (`sudo gem install cocoapods`).
- iOS apps cannot be compiled natively on a Windows host.

### Build and Sync Commands (Run on macOS)
```bash
# 1. Install iOS native platform template
npm install @capacitor/ios
npx cap add ios

# 2. Build production web bundle and sync assets into iOS project
npm run cap:build

# 3. Open Xcode project for simulation and archiving
npm run cap:ios
```

---

## 4. Windows Desktop Packaging (Tauri)

### Architecture
Uses **Tauri 2** with a Rust-based native backend container hosting Microsoft Edge WebView2, delivering a lightweight (<15MB) native desktop `.exe` installer.

### Prerequisites for Compiling Windows Desktop App
1. **Microsoft Visual Studio 2022 C++ Build Tools**:
   - Install "Desktop development with C++" from the Visual Studio Installer.
2. **Rust Toolchain**:
   - Download and run `rustup-init.exe` from [rustup.rs](https://rustup.rs).
   - Verify: `rustc --version` and `cargo --version`.
3. **Microsoft Edge WebView2**:
   - Pre-installed on Windows 10/11.

### Initialization & Desktop Build Commands
```powershell
# 1. Install Tauri CLI as a dev dependency
npm install -D @tauri-apps/cli

# 2. Initialize Tauri configuration
npx tauri init

# 3. Run desktop app in development mode
npx tauri dev

# 4. Compile standalone Windows release installer (.msi / .exe)
npx tauri build
```

---

## 5. Platform-Specific UX & Adaptive Bridge

All platform-specific APIs are encapsulated inside [src/services/platformAdapter.ts](file:///c:/super_ai/src/services/platformAdapter.ts):
- `PlatformAdapter.getDeviceInfo()`: Resolves whether current user is on `web`, `android`, `ios`, or `windows`.
- `PlatformAdapter.triggerHaptic(style)`: Executes native device vibrations on Android/iOS and Web Haptics API on touch screens.
- `PlatformAdapter.configureStatusBar(isDark, hexColor)`: Dynamically syncs the mobile status bar with active SUPER_AI themes.
- `PlatformAdapter.shareOrDownload()`: Invokes native OS share sheets on mobile and fallback file downloads on desktop browsers.
