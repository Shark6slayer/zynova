import urllib.request
import re

urls = [
    'https://zynova.intellidev.in',
    'https://intellidev.in',
    'https://zynovaapp-git-deployment-atlas-vercel-karuppusamy2.vercel.app'
]

for url in urls:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        res = urllib.request.urlopen(req, timeout=10)
        body = res.read().decode('utf-8', errors='ignore')
        print(f"=== {url} ===")
        print("Status:", res.status)
        for h, v in res.getheaders():
            if any(k in h.lower() for k in ['server', 'vercel', 'cache', 'etag', 'last-modified', 'content-type']):
                print(f"  {h}: {v}")
        title = re.search(r'<title>(.*?)</title>', body, re.I)
        print("  Title:", title.group(1) if title else "None")
        scripts = re.findall(r'<script[^>]+src=[\'"]([^\'"]+)[\'"]', body, re.I)
        print("  Scripts:", scripts)
        links = re.findall(r'<link[^>]+href=[\'"]([^\'"]+)[\'"]', body, re.I)
        print("  Links:", [l for l in links if 'assets/' in l or '.css' in l or '.js' in l])
    except Exception as e:
        print(f"=== {url} === ERROR: {e}")
