# SUPER_AI: Mobile Readiness & Target Architecture Documentation

This document records the mobile audit findings and production deployment standards for Android and iOS in SUPER_AI.

---

## 1. Network & API Base URL Architecture

Mobile applications running on devices or emulators cannot resolve `localhost` or `127.0.0.1` to the developer's computer. The following resolution strategy is implemented in `src/services/apiClient.ts`:

| Environment | Target API URL | Configuration & Resolution Mechanism |
| :--- | :--- | :--- |
| **Web Browser (Local)** | `http://127.0.0.1:8000/api/v1` | Default fallback when `Capacitor.isNativePlatform()` is false. |
| **Android Emulator** | `http://10.0.2.2:8000/api/v1` | Automated by `apiClient.ts` via `10.0.2.2` (the standard Android QEMU alias for the host loopback). |
| **Android Physical Device (Wi-Fi)** | `http://<HOST_LAN_IP>:8000/api/v1` | Set via `.env.production` or runtime `VITE_API_BASE_URL`. |
| **Android Physical Device (USB Reverse)** | `http://127.0.0.1:8000/api/v1` | Run `adb reverse tcp:8000 tcp:8000` via terminal. |
| **iOS Simulator** | `http://127.0.0.1:8000/api/v1` | Automated; macOS simulators share the host network interface. |
| **iOS Physical Device** | `http://<HOST_LAN_IP>:8000/api/v1` | Set via `VITE_API_BASE_URL` with trusted local certificate or tunneling. |
| **Production Cloud** | `https://api.superai.app/api/v1` | Hardened HTTPS endpoint enforced via `capacitor.config.ts`. Cleartext disabled. |

---

## 2. Secure Token Storage Strategy

### Current Web State:
- JWT Access and Refresh tokens are stored in `window.localStorage`.
- While acceptable for sandboxed desktop web browsers, `localStorage` on mobile devices is stored in cleartext SQLite/leveldb files inside the app's sandboxed data folder. On rooted or compromised devices, this exposes credentials to extraction.

### Native Production Strategy:
1. **Plugin**: `@aparajita/capacitor-secure-storage` or `@capacitor/preferences`.
2. **Android Backing**: Uses **Android Keystore Provider** with hardware-backed encryption keys (AES-256 GCM) protected by TEE (Trusted Execution Environment) or StrongBox.
3. **iOS Backing**: Uses the **iOS Keychain Services** with `kSecAttrAccessibleAfterFirstUnlock`.
4. **Data Classification**:
   - *Secure Storage*: JWT Access Token, JWT Refresh Token, Biometric Auth Flags.
   - *Standard Preferences*: App theme, language selection, notifications dismissed state, non-sensitive cache.
   - *Strictly Forbidden*: Never store bank PINs, card numbers, OTPs, or CVVs in any client storage.

---

## 3. Platform Capabilities & Native Permissions Matrix

| Feature | Plugin Required | Permissions Required | Notes |
| :--- | :--- | :--- | :--- |
| **QR Code Scanner** | `@capacitor-mlkit/barcode-scanning` | `android.permission.CAMERA` | Prompts user on first camera activation only. |
| **Media & Avatars** | `@capacitor/camera` | `android.permission.READ_MEDIA_IMAGES`<br>`android.permission.READ_MEDIA_VIDEO` | Granular media permission for Android 13+ (API 33+). |
| **Push Notifications**| `@capacitor/push-notifications` | `android.permission.POST_NOTIFICATIONS` | Required for Android 13+. Requires `google-services.json`. |
| **Haptic Feedback** | `@capacitor/haptics` (Installed) | `android.permission.VIBRATE` | Low-latency feedback for payment confirmations and taps. |
| **App Lifecycle** | `@capacitor/app` (Installed) | None | Handles hardware back button, backgrounding, and deep links. |
| **Keyboard Management**| `@capacitor/keyboard` (Installed)| None | Configured with `resize: 'body'` to prevent input clipping. |

---

## 4. Android Build Blockers & Exact Remediation

- **Root Cause**: Android Studio ships with a preview Java runtime (JBR OpenJDK 25, classfile version 69). Gradle 8.14.3 and Android Gradle Plugin 8.13.0 support up to Java 21/24. Attempting to run `gradlew assembleDebug` with JBR 25 triggers `BUG! Unsupported class file major version 69`.
- **Remediation**:
  1. Install standard JDK 17 or JDK 21 LTS:
     ```powershell
     winget install Microsoft.OpenJDK.17
     ```
  2. Configure environment variables in Windows:
     ```powershell
     $env:JAVA_HOME = "C:\Program Files\Microsoft\jdk-17..."
     $env:ANDROID_HOME = "C:\Users\karup\AppData\Local\Android\Sdk"
     ```
  3. Compile APK:
     ```powershell
     cd C:\super_ai\android
     .\gradlew.bat assembleDebug
     ```
  4. Launch Emulator & Run:
     ```powershell
     & "C:\Users\karup\AppData\Local\Android\Sdk\emulator\emulator.exe" -avd Medium_Phone_API_37.0
     & "C:\Users\karup\AppData\Local\Android\Sdk\platform-tools\adb.exe" install -r app\build\outputs\apk\debug\app-debug.apk
     ```

---

## 5. iOS Requirements & Project Initialization

- **Operating System Requirement**: macOS Sonoma or Sequoia with an Apple Silicon (M1/M2/M3/M4) or Intel Mac.
- **Tooling Requirement**: Xcode 15/16, Xcode Command Line Tools, CocoaPods (`gem install cocoapods`).
- **Initialization Steps**:
  ```bash
  npm run build
  npx cap add ios
  npx cap sync ios
  npx cap open ios
  ```
