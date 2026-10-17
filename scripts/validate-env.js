#!/usr/bin/env node
/**
 * validate-env.js — Pre-build API Configuration Validation
 *
 * Enforces production build safety:
 * 1. Rejects missing VITE_API_BASE_URL when building for production.
 * 2. Rejects localhost / 127.0.0.1 loopback URLs in production builds.
 * 3. Enforces HTTPS for remote production backend URLs.
 * 4. Rejects placeholder URLs (e.g. YOUR-BACKEND-DOMAIN).
 */

const mode = process.env.NODE_ENV || 'production';
const DEFAULT_PRODUCTION_API = 'https://zynova-backend-dgpe.onrender.com/api/v1';
const apiUrl = process.env.VITE_API_BASE_URL || DEFAULT_PRODUCTION_API;

console.log(`[Zynova Build Check] Validating environment for mode: ${mode}...`);

// Only run strict checks when in production build mode
if (mode === 'production') {

  if (apiUrl.includes('YOUR-BACKEND-DOMAIN') || apiUrl.includes('<verified-production-api-host>')) {
    console.error('\n❌ BUILD FAILED: VITE_API_BASE_URL contains an unconfigured placeholder.');
    console.error(`Current value: ${apiUrl}`);
    console.error('Please provide a real, deployed backend endpoint.\n');
    process.exit(1);
  }

  if (apiUrl.includes('127.0.0.1') || apiUrl.includes('localhost') || apiUrl.includes('10.0.2.2')) {
    console.error('\n❌ BUILD FAILED: Production build cannot point to a local loopback interface.');
    console.error(`Current value: ${apiUrl}`);
    console.error('Deploy your backend to a public server with HTTPS before building production bundles.\n');
    process.exit(1);
  }

  if (!apiUrl.startsWith('https://') && !apiUrl.startsWith('/')) {
    console.error('\n❌ BUILD FAILED: Production API URL must use secure HTTPS protocol or relative path (/api/v1).');
    console.error(`Current value: ${apiUrl}\n`);
    process.exit(1);
  }

  console.log(`✅ [Zynova Build Check] Validated production API URL: ${apiUrl}`);
} else {
  console.log('ℹ️ Non-production build mode; skipping strict remote HTTPS checks.');
}

process.exit(0);
