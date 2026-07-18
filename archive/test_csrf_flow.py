"""Two-step auth: get CSRF, retry with it."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(10)
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Step 1: POST without CSRF to get token
    print("[*] Step 1: Get CSRF token...", flush=True)
    step1 = page.evaluate("""async () => {
        const r = await fetch('https://auth.roblox.com/v2/login', {
            method: 'POST',
            credentials: 'include',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ctype: 'Username', cvalue: 'testuser123', password: 'wrongpass123!'})
        });
        return {status: r.status, csrf: r.headers.get('x-csrf-token'), text: await r.text().then(t => t.substring(0, 300))};
    }""")
    print(f"  {json.dumps(step1, indent=2)}", flush=True)
    
    if step1.get('csrf'):
        csrf = step1['csrf']
        
        # Step 2: POST with CSRF
        print(f"\n[*] Step 2: POST with CSRF: {csrf}...", flush=True)
        step2 = page.evaluate("""async () => {
            const r = await fetch('https://auth.roblox.com/v2/login', {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                    'x-csrf-token': '""" + csrf + """'
                },
                body: JSON.stringify({ctype: 'Username', cvalue: 'testuser123', password: 'wrongpass123!'})
            });
            return {status: r.status, text: await r.text().then(t => t.substring(0, 1000)), headers: [...r.headers.entries()].filter(h => ['content-type','x-csrf-token'].includes(h[0]))};
        }""")
        print(f"  Status: {step2['status']}", flush=True)
        print(f"  Body preview: {step2['text'][:500]}", flush=True)
        print(f"  Key headers: {step2['headers']}", flush=True)
        
        if step2['status'] == 200:
            print("[++] LOGIN SUCCESS!", flush=True)
            print(f"  Full body: {step2['text']}", flush=True)
        elif step2['status'] == 403 and '<html' in step2['text'].lower():
            print("[++] PX CHALLENGE! HTML response", flush=True)
            # Extract enforcement URL
            enforce_url = page.evaluate("""(html) => {
                const m = html.match(/https:\\/\\/[^\"']*enforcement[^\"']*/);
                return m ? m[0] : 'no match';
            }""", step2['text'])
            print(f"  Enforcement URL: {enforce_url}", flush=True)
        elif step2['status'] == 403:
            print("[*] 403 but not HTML. JSON response.", flush=True)
        else:
            print(f"[?] Unexpected status: {step2['status']}", flush=True)
    
    # Also try with nonce
    print("\n[*] Try with nonce in body...", flush=True)
    step3 = page.evaluate("""async () => {
        const r = await fetch('https://auth.roblox.com/v2/login', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'x-csrf-token': '""" + csrf + """'
            },
            body: JSON.stringify({
                ctype: 'Username',
                cvalue: 'testuser123',
                password: 'wrongpass123!',
                secureAuthenticationIntent: {}
            })
        });
        return {status: r.status, text: await r.text().then(t => t.substring(0, 500))};
    }""")
    print(f"  Status: {step3['status']}", flush=True)
    print(f"  Body: {step3['text']}", flush=True)
    
    input("Enter...")
    browser.close()
