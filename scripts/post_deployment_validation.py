"""
Post-deployment validation test suite for Zynova production backend.
Executes non-destructive read and authenticated checks against live endpoints.
"""
import urllib.request
import urllib.error
import json
import sys
import ssl

BASE_URL = "https://zynova-backend-dgpe.onrender.com/api/v1"
CUSTOM_DOMAIN_URL = "https://api.zynova.intellidev.in/api/v1"

ctx = ssl.create_default_context()

def check(title, condition, details=""):
    status = "✅ PASS" if condition else "❌ FAIL"
    print(f"{status} | {title} {details}")
    return condition

def run_tests():
    print("=" * 60)
    print("ZYNOVA PRODUCTION POST-DEPLOYMENT VALIDATION SUITE")
    print("=" * 60)
    results = []

    # 1. Health endpoint
    try:
        req = urllib.request.Request(f"{BASE_URL}/health")
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            results.append(check("Health Check (Render Direct)", resp.status == 200 and data.get("status") == "healthy"))
    except Exception as e:
        results.append(check("Health Check (Render Direct)", False, str(e)))

    # 2. Custom domain health
    try:
        req = urllib.request.Request(f"{CUSTOM_DOMAIN_URL}/health")
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            results.append(check("Health Check (Custom Domain)", resp.status == 200 and data.get("status") == "healthy"))
    except Exception as e:
        results.append(check("Health Check (Custom Domain)", False, str(e)))

    # 3. OpenAPI Schema route count
    try:
        req = urllib.request.Request("https://zynova-backend-dgpe.onrender.com/openapi.json")
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            paths = data.get("paths", {})
            count = len(paths)
            results.append(check(f"OpenAPI Contract (Expected: 158, Deployed: {count})", count == 158))
            
            # Check presence of specific required route groups
            has_stories = any("/social/stories" in p for p in paths)
            has_notes = "/api/v1/social/notes" in paths
            has_connect = any("/chat/communities" in p for p in paths)
            has_video = any("/videos/channels" in p for p in paths)
            has_ai = "/api/v1/ai/chat/stream" in paths

            results.append(check("Route Group: Social Stories", has_stories))
            results.append(check("Route Group: Social Notes", has_notes))
            results.append(check("Route Group: Connect Communities", has_connect))
            results.append(check("Route Group: Video Channels", has_video))
            results.append(check("Route Group: AI Chat Stream", has_ai))
    except Exception as e:
        results.append(check("OpenAPI Schema Validation", False, str(e)))

    # 4. CORS preflight tests
    origins_to_test = [
        "https://www.intellidev.in",
        "capacitor://localhost",
        "capacitor://"
    ]
    for orig in origins_to_test:
        try:
            req = urllib.request.Request(
                f"{BASE_URL}/auth/login",
                headers={
                    "Origin": orig,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "authorization,content-type"
                },
                method="OPTIONS"
            )
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                allow_orig = resp.headers.get("access-control-allow-origin")
                results.append(check(f"CORS Preflight Origin: {orig}", resp.status == 200 and allow_orig == orig))
        except Exception as e:
            results.append(check(f"CORS Preflight Origin: {orig}", False, str(e)))

    print("=" * 60)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"Summary: {passed}/{total} checks passed.")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()

