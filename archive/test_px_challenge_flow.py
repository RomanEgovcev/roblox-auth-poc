"""Check if PX processes 403 challenge and triggers Challenge.js."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Listen for requests
    requests_made = []
    page.on("request", lambda req: requests_made.append({
        'url': req.url,
        'method': req.method,
        'headers': dict(req.headers),
    }))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    print("Making login POST via page.evaluate...", flush=True)
    
    # Make the login POST
    result = page.evaluate(f"""async () => {{
        const r = await fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }});
        return {{
            status: r.status,
            headers: Object.fromEntries(r.headers.entries()),
        }};
    }}""")
    
    print(f"Response: {result['status']}", flush=True)
    for k, v in result['headers'].items():
        if 'chall' in k.lower() or 'csrf' in k.lower() or 'token' in k.lower():
            print(f"  {k}: {v[:80]}...", flush=True)
    
    # Now check if Challenge.js has been triggered
    time.sleep(2)
    
    domCheck = page.evaluate("""() => {
        // Check for challenge-related DOM elements
        return {
            newElements: Array.from(document.querySelectorAll('[id*="challenge" i], [class*="challenge" i], [data-challenge]')).map(e => ({
                id: e.id,
                className: e.className?.substring(0, 100),
                innerHTML: e.innerHTML?.substring(0, 200),
                tag: e.tagName,
            })),
            bodyInnerHTML: document.body.innerHTML?.substring(0, 1000),
            url: window.location.href,
        };
    }""")
    
    print(f"\nDOM after fetch:", flush=True)
    for k, v in domCheck.items():
        if isinstance(v, list):
            for item in v:
                print(f"  {item}", flush=True)
        elif isinstance(v, str):
            print(f"  {k}: {v[:300]}", flush=True)
        else:
            print(f"  {k}: {v}", flush=True)
    
    # Also check requests that happened
    print(f"\nRequests ({len(requests_made)}):", flush=True)
    for req in requests_made[-10:]:
        if 'auth' in req['url'] or 'px' in req['url'] or 'challenge' in req['url']:
            print(f"  {req['method']} {req['url']}", flush=True)
    
    time.sleep(3)
    browser.close()
