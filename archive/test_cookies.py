"""Check what cookies are set by the challenge response."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    # Check all existing cookies before challenge
    cookies_before = page.context.cookies()
    print(f"Cookies before challenge ({len(cookies_before)}):")
    for c in cookies_before:
        print(f"  {c['name']}: {c['value'][:60]} (domain: {c['domain']})")
    print()
    
    # 1. Get CSRF
    csrf = page.evaluate("""() => {
        return fetch('https://auth.roblox.com/v2/login', {
            method: 'POST', credentials: 'include',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ctype:'Username', cvalue:'testuser123', password:'TestPassword123!'}),
        }).then(r => r.headers.get('x-csrf-token'));
    }""")
    print(f"CSRF: {csrf}")
    
    # 2. Trigger challenge
    result = page.evaluate("""async (csrf) => {
        const r = await fetch('https://auth.roblox.com/v2/login', {
            method: 'POST', credentials: 'include',
            headers: {'Content-Type': 'application/json', 'x-csrf-token': csrf},
            body: JSON.stringify({ctype:'Username', cvalue:'testuser123', password:'TestPassword123!'}),
        });
        const hdrs = {};
        r.headers.forEach((v,k) => { hdrs[k.toLowerCase()] = v; });
        const body = await r.text();
        return {status: r.status, headers: hdrs, body: body.substring(0, 500)};
    }""", csrf)
    
    print(f"\nChallenge response: {result['status']}")
    
    # Print all headers
    for k, v in sorted(result["headers"].items()):
        print(f"  header: {k}: {v}")
    
    # Print decoded metadata
    meta_b64 = result["headers"].get("rblx-challenge-metadata", "")
    if meta_b64:
        try:
            meta = json.loads(base64.b64decode(meta_b64))
            print(f"\nDecoded metadata:")
            print(json.dumps(meta, indent=2))
        except Exception as e:
            print(f"Failed to decode metadata: {e}")
    
    # Check all cookies after challenge
    cookies_after = page.context.cookies()
    print(f"\nCookies AFTER challenge ({len(cookies_after)}):")
    for c in cookies_after:
        print(f"  {c['name']}: {c['value'][:60]} (domain: {c['domain']})")
    
    # Find new cookies
    before_names = {c["name"] for c in cookies_before}
    print(f"\nNEW cookies:")
    for c in cookies_after:
        if c["name"] not in before_names:
            print(f"  NEW: {c['name']}: {c['value'][:60]} (domain: {c['domain']})")
        elif c["value"] != next((cb["value"] for cb in cookies_before if cb["name"] == c["name"]), None):
            print(f"  CHANGED: {c['name']}: {c['value'][:60]} (was different)")
    
    time.sleep(2)
    browser.close()
