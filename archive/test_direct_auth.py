"""Bypass PX entirely: direct auth request from Python. Then inject enforcement."""
import os, time, json, requests, base64

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

# Step 0: We need Roblox session cookies first
# Browser with no-proxy
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(10)
    
    # Get CSRF token and cookies
    cookies = context.cookies()
    csrf_cookie = [c for c in cookies if c['name'] == '.ROBLOSECURITY']
    xcsrf = page.evaluate("""() => {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : null;
    }""")
    print(f"ROBLOSECURITY: {bool(csrf_cookie)}", flush=True)
    print(f"CSRF from meta: {xcsrf}", flush=True)
    
    # Get the x-csrf-token from response headers for auth.roblox.com
    # First send a GET to auth.roblox.com
    resp = page.evaluate("""async () => {
        try {
            const r = await fetch('https://auth.roblox.com/v2/login', {method: 'GET', credentials: 'include'});
            return {status: r.status, headers: [...r.headers.entries()].filter(h => h[0].includes('csrf')).map(h => h[0]+': '+h[1])};
        } catch(e) {return {error: e.message};}
    }""")
    print(f"Auth GET: {json.dumps(resp, indent=2)}", flush=True)
    
    # Get nonce
    nonce_resp = page.evaluate("""async () => {
        try {
            const r = await fetch('https://apis.roblox.com/hba-service/v1/getServerNonce?urlLocale=en_us', {credentials: 'include'});
            return {status: r.status, text: await r.text()};
        } catch(e) {return {error: e.message};}
    }""")
    print(f"Nonce: {json.dumps(nonce_resp, indent=2)}", flush=True)
    
    # Try POST to auth with proper body
    auth_resp = page.evaluate("""async () => {
        try {
            const r = await fetch('https://auth.roblox.com/v2/login', {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                    'x-csrf-token': 'fetch'
                },
                body: JSON.stringify({
                    ctype: 'Username',
                    cvalue: 'testuser123',
                    password: 'wrongpass123!'
                })
            });
            return {
                status: r.status,
                headers: [...r.headers.entries()].slice(0, 20),
                text: await r.text().then(t => t.substring(0, 500)).catch(e => 'err: '+e)
            };
        } catch(e) {
            return {error: e.message, name: e.name};
        }
    }""")
    print(f"\nAuth POST: {json.dumps(auth_resp, indent=2)[:1000]}", flush=True)
    
    # Try fetching from Python directly with cookies
    print("\n=== Python direct auth ===", flush=True)
    cookies_dict = {c['name']: c['value'] for c in cookies}
    print(f"Cookies: {list(cookies_dict.keys())}", flush=True)
    
    # First GET to get CSRF token
    s = requests.Session()
    # Don't use proxy
    r1 = s.get('https://auth.roblox.com/v2/login', cookies=cookies_dict)
    print(f"GET auth: {r1.status_code}", flush=True)
    csrf_token = r1.headers.get('x-csrf-token', 'no-token')
    print(f"CSRF token: {csrf_token}", flush=True)
    
    # POST with CSRF
    r2 = s.post('https://auth.roblox.com/v2/login',
        json={
            'ctype': 'Username',
            'cvalue': 'testuser123',
            'password': 'wrongpass123!'
        },
        headers={'x-csrf-token': csrf_token},
        cookies=cookies_dict
    )
    print(f"POST auth: {r2.status_code}", flush=True)
    print(f"Response: {r2.text[:500]}", flush=True)
    print(f"Headers: {dict(r2.headers)}", flush=True)
    
    input("Enter...")
    browser.close()
