import urllib.request
import ssl
import time
import sys

ctx = ssl.create_default_context()

endpoints = [
    ("Render /privacy", "https://zynova-backend-dgpe.onrender.com/privacy"),
    ("Render /terms", "https://zynova-backend-dgpe.onrender.com/terms"),
    ("Render /delete-account", "https://zynova-backend-dgpe.onrender.com/delete-account"),
    ("Render /api/v1/legal/privacy", "https://zynova-backend-dgpe.onrender.com/api/v1/legal/privacy"),
    ("Render /api/v1/legal/terms", "https://zynova-backend-dgpe.onrender.com/api/v1/legal/terms"),
    ("Custom Domain /privacy", "https://api.zenova.intellidev.in/privacy"),
    ("Custom Domain /terms", "https://api.zenova.intellidev.in/terms"),
    ("Custom Domain /delete-account", "https://api.zenova.intellidev.in/delete-account"),
]

print("Starting live deployment poller for Render legal endpoints...")
sys.stdout.flush()

max_attempts = 25  # ~8 minutes at 20s intervals
for attempt in range(1, max_attempts + 1):
    try:
        # Check /privacy first
        req = urllib.request.Request("https://zynova-backend-dgpe.onrender.com/privacy", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            if resp.status == 200:
                print(f"[Attempt {attempt}] Render /privacy is LIVE! HTTP 200 OK.")
                sys.stdout.flush()
                break
    except Exception as e:
        print(f"[Attempt {attempt}] Waiting for deployment... ({e})")
        sys.stdout.flush()
    time.sleep(20)

print("\n--- Performing Full Suite Verification ---")
results = {}
for name, url in endpoints:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            title_tag = ""
            if "<title>" in content:
                title_tag = content.split("<title>")[1].split("</title>")[0].strip()
            status_text = "PASS" if resp.status == 200 else f"FAIL ({resp.status})"
            print(f"[{status_text}] {name}: Status {resp.status}, Content-Length: {len(content)}, Title: '{title_tag}'")
            results[name] = {"status": resp.status, "length": len(content), "title": title_tag}
    except Exception as e:
        print(f"[FAIL] {name}: {e}")
        results[name] = {"status": "FAIL", "error": str(e)}

sys.stdout.flush()
