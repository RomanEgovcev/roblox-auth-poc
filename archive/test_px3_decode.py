"""Decode _px3 cookie and try to use it with PX.setChallenge."""
import os, time, json, base64, urllib.parse

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(10)
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Trigger PX challenge
    csrf = page.evaluate("""async () => {
        const r = await fetch('https://auth.roblox.com/v2/login', {
            method: 'POST', credentials: 'include',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ctype: 'Username', cvalue: 'testuser123', password: 'wrongpass123!'})
        });
        return r.headers.get('x-csrf-token');
    }""")
    
    result = page.evaluate("""async (csrf) => {
        const r = await fetch('https://auth.roblox.com/v2/login', {
            method: 'POST', credentials: 'include',
            headers: {'Content-Type': 'application/json', 'x-csrf-token': csrf},
            body: JSON.stringify({ctype: 'Username', cvalue: 'testuser123', password: 'wrongpass123!'})
        });
        // Get ALL response data including body, headers, cookies
        return {
            status: r.status,
            body: await r.text(),
            headers: Object.fromEntries([...r.headers.entries()])
        };
    }""", csrf)
    print(f"Status: {result['status']}", flush=True)
    print(f"Body: {result['body']}", flush=True)
    print(f"Headers: {json.dumps(result['headers'], indent=2)}", flush=True)
    
    # Get PX cookies
    cookies = context.cookies()
    for c in cookies:
        if '_px' in c['name']:
            print(f"\n{c['name']}: {c['value'][:100]}")
            # Try to decode
            try:
                decoded = base64.b64decode(c['value'].split(':')[0] if ':' in c['value'] else c['value'])
                print(f"  Decoded (hex): {decoded[:80].hex()}")
            except:
                print(f"  (not base64)")
    
    # Also capture the raw auth.xhr response using route
    # Actually, let's try calling PX.setChallenge with challenge data from the _px3 cookie
    print("\n[*] Trying PX.setChallenge with px3 data...", flush=True)
    px3 = next((c['value'] for c in cookies if c['name'] == '_px3'), None)
    
    if px3:
        # The px3 format is: hash:encrypted_data:timestamp:random
        parts = px3.split(':')
        if len(parts) >= 2:
            challenge_data = parts[1]  # might contain challenge data
            print(f"  Challenge data from px3: {challenge_data[:100]}", flush=True)
        
        # Try calling setChallenge with various data formats
        for i, data in enumerate([
            {"type": "captcha", "appId": "PXbf8PROpW"},
            {"appId": "PXbf8PROpW", "type": "captcha", "cookie": px3},
            {"type": "v2", "appId": "PXbf8PROpW"},
            {}  # empty
        ]):
            print(f"  Iteration {i}: calling setChallenge({json.dumps(data)[:100]})", flush=True)
            try:
                page.evaluate("""(data) => {
                    window.PX.setChallenge(data);
                }""", data)
            except Exception as e:
                print(f"    Error: {e}", flush=True)
        
        time.sleep(3)
        
        # Check for frames
        print(f"\n  Frames: {[f.url[:100] for f in page.frames]}", flush=True)
        
        # Also check PX's internal state
        px_state = page.evaluate("""() => {
            const px = window.PX;
            const result = {};
            Object.keys(px).forEach(k => {
                if (typeof px[k] !== 'function') {
                    try { result[k] = JSON.stringify(px[k]).substring(0, 200); } catch(e) { result[k] = 'error'; }
                }
            });
            return result;
        }""")
        print(f"  PX state: {px_state}", flush=True)
    
    input("Enter...")
    browser.close()
