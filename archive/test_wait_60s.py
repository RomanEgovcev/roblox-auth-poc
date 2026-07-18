"""Wait longer for enforcement after React onClick, check proper form."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    all_req = []
    all_resp = []
    page.on("request", lambda r: all_req.append({
        't': time.time(), 'u': r.url[:250], 'm': r.method, 'h': dict(r.headers)[:5]
    }) if 'auth.roblox.com/v2/login' in r.url or 'arkoselabs' in r.url else None)
    page.on("response", lambda r: all_resp.append({
        't': time.time(), 's': r.status, 'u': r.url[:250]
    }) if 'auth.roblox.com/v2/login' in r.url or 'arkoselabs' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Get ALL forms
    forms = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('form')).map((f, i) => ({
            idx: i, id: f.id, action: f.action, method: f.method,
            inputs: Array.from(f.querySelectorAll('input')).map(i => ({
                name: i.name, id: i.id, type: i.type, value: i.value.substring(0, 20)
            }))
        }));
    }""")
    print(f"Forms: {json.dumps(forms, indent=2)[:800]}", flush=True)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(1)
    
    print("\n[1] Calling React onClick to trigger login flow...", flush=True)
    page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        const propsKey = Object.keys(btn).find(k => k.startsWith('__reactProps'));
        btn[propsKey].onClick({});
    }""")
    time.sleep(3)
    
    print(f"[2] Requests made:", flush=True)
    for r in all_req[-5:]:
        print(f"  [{r['m']}] {r['u'][:200]}", flush=True)
    
    # Wait 60s for enforcement
    print("\n[3] Waiting 60s for enforcement...", flush=True)
    enf = None
    for i in range(120):
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf = f
                break
        if enf:
            print(f"  [+] Enforcement at {i*0.5:.0f}s!", flush=True)
            break
        if i > 0 and i % 20 == 0:
            # Check auth responses
            for ri in range(-3, 0 if len(all_resp) > 3 else -len(all_resp)):
                if abs(ri) <= len(all_resp):
                    r = all_resp[ri]
                    print(f"  [t={r['t']-time.time():.0f}s {r['s']}] {r['u'][:120]}", flush=True)
        time.sleep(0.5)
    
    if enf:
        print(f"  URL: {enf.url[:120]}", flush=True)
    else:
        print("  No enforcement in 60s.", flush=True)
    
    print(f"\n=== All auth responses ===", flush=True)
    for r in all_resp:
        print(f"  [t={r['t']-time.time():.0f}s {r['s']}] {r['u'][:200]}", flush=True)
    
    time.sleep(3)
    browser.close()
