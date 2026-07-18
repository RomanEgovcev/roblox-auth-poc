"""Two-step CSRF flow, capture full PX challenge response."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    # Track the full response
    px_response = {}
    def on_resp(r):
        if 'auth.roblox' in r.url and r.status == 403:
            r.body().then(lambda b: px_response.update({'body': b[:5000], 'headers': r.headers_array, 'url': r.url}))
    page.on("response", on_resp)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(10)
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Step 1: Get CSRF
    print("[*] Step 1: Getting CSRF...", flush=True)
    step1 = page.evaluate("""async () => {
        const r = await fetch('https://auth.roblox.com/v2/login', {
            method: 'POST', credentials: 'include',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ctype: 'Username', cvalue: 'testuser123', password: 'wrongpass123!'})
        });
        return {status: r.status, csrf: r.headers.get('x-csrf-token')};
    }""")
    print(f"  CSRF: {step1.get('csrf')}", flush=True)
    
    if step1.get('csrf'):
        csrf = step1['csrf']
        # Step 2: POST with proper CSRF
        print(f"[*] Step 2: POST with CSRF...", flush=True)
        step2 = page.evaluate("""async (csrf) => {
            const r = await fetch('https://auth.roblox.com/v2/login', {
                method: 'POST', credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                    'x-csrf-token': csrf
                },
                body: JSON.stringify({ctype: 'Username', cvalue: 'testuser123', password: 'wrongpass123!'})
            });
            return {
                status: r.status,
                body: await r.text(),
                headers: Object.fromEntries([...r.headers.entries()])
            };
        }""", csrf)
        print(f"  Status: {step2['status']}", flush=True)
        print(f"  Body: {step2['body']}", flush=True)
        print(f"  Content-Type: {step2['headers'].get('content-type')}", flush=True)
        
        # Check for enforcement URL
        if 'challenge' in step2['body'].lower():
            # Try to extract challenge URL
            import re
            m = re.search(r'"url"\s*:\s*"([^"]+)"', step2['body'])
            if m: print(f"\n[+] Enforcement URL from body: {m.group(1)}", flush=True)
            
            # Check if there's a redirect URL
            m2 = re.search(r'"redirect"\s*:\s*"([^"]+)"', step2['body'])
            if m2: print(f"[+] Redirect URL: {m2.group(1)}", flush=True)
            
            # Check all PX cookies
            cookies = context.cookies()
            px_cookies = [c for c in cookies if '_px' in c['name']]
            cookie_str = "; ".join([f"{c['name']}={c['value'][:50]}..." for c in px_cookies])
            print(f"\nPX cookies: {cookie_str}", flush=True)
            
            # Try to navigate to the enforcement URL
            # The enforcement is typically at: https://client.px-cloud.net/PXbf8PROpW/enforcement/main
            # or similar
            print("\n[*] Checking if enforcement page loads...", flush=True)
            try:
                # Open enforcement in new page
                enf_page = context.new_page()
                enf_page.goto("https://client.px-cloud.net/PXbf8PROpW/enforcement/main", wait_until="domcontentloaded", timeout=15000)
                time.sleep(3)
                print(f"  Enforcement page URL: {enf_page.url[:200]}", flush=True)
                print(f"  Frames: {[f.url[:100] for f in enf_page.frames]}", flush=True)
                
                # Check for canvas
                for f in enf_page.frames:
                    c = f.evaluate("""() => {
                        const el = document.querySelector('canvas');
                        if (!el) return null;
                        return {w: el.width, h: el.height};
                    }""")
                    if c: print(f"  Canvas in frame {f.url[:50]}: {c}", flush=True)
                
                enf_page.close()
            except Exception as e:
                print(f"  Failed to load: {e}", flush=True)
    
    input("Enter...")
    browser.close()
