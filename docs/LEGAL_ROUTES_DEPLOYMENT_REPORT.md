# ZENOVA — Public Legal Page Routing & Vercel Deployment Report

**Date:** November 26, 2026  
**Project:** `C:\super_ai`  
**Production Domain:** `https://www.intellidev.in`  
**Frontend Stack:** React 19 + TypeScript + Vite + Tailwind CSS  

---

## 1. Root Cause Analysis

1. **Stale Production Bundle on Vercel (`https://www.intellidev.in`):**
   - Live inspection of `https://www.intellidev.in/privacy-policy` showed HTTP 200 serving `/assets/index-BsVLKiLx.js`, which did **not** contain `/privacy-policy`, `/child-safety`, or `PrivacyPolicyView` (`False` for all three checks).
   - Because Vercel rewrites unknown paths to `/index.html`, the older deployed bundle fell through `AppShell.tsx`'s `switch (activeModule)` `default` case and rendered `HomeDashboardView`.

2. **Dashboard Shell & Onboarding Modal Blocking Public Routes (`src/components/layout/AppShell.tsx`):**
   - Legal routes were previously checked inside `AppShell.renderActiveModule()`, which mounted the full authenticated dashboard shell (`Sidebar`, `TopBar`, mobile bottom navigation, `CommandPalette`, and `OnboardingModal`).
   - For any first-time visitor or crawler (`preferences.onboardingCompleted === false`), `OnboardingModal` rendered on top of the legal page.
   - Unknown paths fell through to `HomeDashboardView` instead of rendering a 404 page.

3. **Static Asset Rewrite Pattern (`vercel.json`):**
   - The catch-all rewrite `/(.*)` -> `/index.html` did not explicitly exclude static asset paths (`/assets/*`, `/favicon.svg`, `/icons.svg`, `/robots.txt`, `/sitemap.xml`).

---

## 2. Files Created & Modified

### Created
- `src/features/public/LegalPageLayout.tsx` — Shared responsive dark-theme layout with dynamic SEO metadata (`document.title`, `<meta name="description">`, `<link rel="canonical">`), semantic `<header>` / `<main>` / `<footer>`, and 9-link legal footer navigation.
- `src/features/public/CommunityGuidelinesView.tsx` (`/community-guidelines`)
- `src/features/public/ContentModerationView.tsx` (`/content-moderation`)
- `src/features/public/DataRightsView.tsx` (`/data-rights`)
- `src/features/public/AccountDeletionView.tsx` (`/delete-account`, `/data-deletion`)
- `src/features/public/ContactSupportView.tsx` (`/contact`)
- `src/features/public/SafetyCenterView.tsx` (`/safety`)
- `src/features/public/NotFoundView.tsx` (404 page for unknown routes)
- `docs/LEGAL_ROUTES_DEPLOYMENT_REPORT.md` (this report)

### Modified
- `src/App.tsx` — Added top-level pathname routing (`PUBLIC_ROUTE_MAP`, `APP_SHELL_ROUTES`, `popstate` listener, and `NotFoundView` fallback) so public legal pages render standalone without `AppShell`, `AuthModal`, or `OnboardingModal`.
- `src/components/layout/AppShell.tsx` — Removed redundant inline public route checks from `renderActiveModule()`.
- `src/features/public/PrivacyPolicyView.tsx` — Migrated to `LegalPageLayout` with SEO metadata and legal footer links.
- `src/features/public/TermsOfServiceView.tsx` — Migrated to `LegalPageLayout` with SEO metadata and legal footer links.
- `src/features/public/ChildSafetyStandardsView.tsx` — Migrated to `LegalPageLayout` with SEO metadata and legal footer links.
- `vercel.json` — Updated SPA rewrite to `"/((?!assets/|favicon\\.svg$|icons\\.svg$|robots\\.txt$|sitemap\\.xml$).*)"` -> `"/index.html"`.

---

## 3. Routes Implemented & Verified Locally

| Route | Component | Local HTTP | `<h1>` Verified | Browser Reload | SEO Meta & Canonical | Auth Required |
|---|---|---|---|---|---|---|
| `/` | `AppShell` (`HomeDashboardView`) | 200 | Yes | Yes | Default | No |
| `/privacy-policy` | `PrivacyPolicyView` | 200 | `Privacy Policy` | Yes | Yes | No |
| `/terms` | `TermsOfServiceView` | 200 | `Terms of Service` | Yes | Yes | No |
| `/child-safety` | `ChildSafetyStandardsView` | 200 | `Child Safety Standards` | Yes | Yes | No |
| `/child-safety-standards` | `ChildSafetyStandardsView` | 200 | `Child Safety Standards` | Yes | Yes | No |
| `/community-guidelines` | `CommunityGuidelinesView` | 200 | `Community Guidelines` | Yes | Yes | No |
| `/content-moderation` | `ContentModerationView` | 200 | `Content Moderation` | Yes | Yes | No |
| `/data-rights` | `DataRightsView` | 200 | `Data Rights & Privacy Controls` | Yes | Yes | No |
| `/delete-account` | `AccountDeletionView` | 200 | `Account & Data Deletion` | Yes | Yes | No |
| `/data-deletion` | `AccountDeletionView` | 200 | `Account & Data Deletion` | Yes | Yes | No |
| `/contact` | `ContactSupportView` | 200 | `Contact & Support` | Yes | Yes | No |
| `/safety` | `SafetyCenterView` | 200 | `ZENOVA Safety Center` | Yes | Yes | No |
| `/unknown-route-404-check` | `NotFoundView` | 200 (SPA) | `404 — Page Not Found` | Yes | Yes | No |

*(Aliases `/privacy` and `/terms-of-service` are also preserved.)*

---

## 4. Build, Lint & Playwright Verification Results

- **Production Build (`npm run build:skip-val`):** `tsc -b && vite build` succeeded in `3.19s` (`1964 modules transformed`), generating dedicated chunks for every public legal view.
- **Linter (`npm run lint`):** `oxlint` finished in `180ms` with **0 errors** (232 pre-existing warnings).
- **Playwright Local E2E (`dist/` served with `vercel.json`-equivalent SPA rewrites):**
  - All **13/13** tested routes returned HTTP `200`, rendered the expected `<h1>`, preserved URL without redirecting to `/` or login, had `noOnboarding=true`, passed `page.reload()`, and rendered unique `<title>`, `<meta name="description">`, and `<link rel="canonical">`.
  - Footer navigation verified with all **9** legal/safety links.
  - Mobile responsiveness (`375x812`) on `/child-safety` passed with `horizontalOverflow=false`.
  - **0** `pageerror` exceptions and **0** console errors on all legal/safety/404 routes. (Homepage `/` logged 4 expected CORS console errors when fetching `https://api.zynova.intellidev.in` from `http://127.0.0.1:4179`.)

---

## 5. Production Deployment & Remaining Action Required

- **Current Live Status (`https://www.intellidev.in`):** Not yet updated. Vercel CLI (`npx vercel whoami`) returned `login_required` (`The saved login is not valid or has expired`).
- **Remaining Step to Go Live:**
  1. Authenticate Vercel CLI (`npx vercel login` or provide `VERCEL_TOKEN`) and run `npx vercel --prod`, **or** commit and push these changes to the branch connected to Vercel's GitHub integration.
  2. Re-verify `https://www.intellidev.in/privacy-policy`, `https://www.intellidev.in/terms`, `https://www.intellidev.in/child-safety`, and `https://www.intellidev.in/` after the Vercel deployment completes.
