"""Bypass WebAuthn passkey check that causes 60s delay."""
import os, time
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    
    # Disable WebAuthn/passkey by overriding credentials API
    page.add_init_script("""
    (() => {
        // Disable WebAuthn to prevent 60s passkey timeout
        navigator.credentials.get = () => Promise.reject(new Error('WebAuthn disabled'));
        navigator.credentials.create = () => Promise.reject(new Error('WebAuthn disabled'));
        navigator.credentials.store = () => Promise.reject(new Error('WebAuthn disabled'));
        
        // Also override the public key credential creation
        if (window.PublicKeyCredential) {
            window.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable = () => Promise.resolve(false);
            window.PublicKeyCredential.isConditionalMediationAvailable = () => Promise.resolve(false);
        }
    })();
    """)
    
    t0 = [None]
    
    def on_req(req):
        if t0[0] is None:
            return
        dt = time.time() - t0[0]
        url = req.url
        if any(x in url for x in ("/v2/login", "pow-puzzle", "challenge/v1", "px-cloud", "main.min")):
            print(f"[{dt:5.1f}s] {req.method} {url[:140]}", flush=True)
        if "/v2/login" in url and req.method == "POST":
            h = dict(req.headers)
            print(f"[LOGIN POST at {dt:.1f}s] csrf={h.get('x-csrf-token','-')[:20]}", flush=True)
    
    page.on("request", on_req)
    
    def on_resp(resp):
        if t0[0] is None:
            return
        dt = time.time() - t0[0]
        url = resp.url
        if "/v2/login" in url:
            print(f"[LOGIN RESP at {dt:.1f}s] {resp.status} challenge={resp.headers.get('rblx-challenge-id','-')[:30]}", flush=True)
        elif "pow-puzzle" in url:
            print(f"[PUZZLE at {dt:.1f}s] {url[:100]}", flush=True)
        elif "challenge/v1/continue" in url:
            print(f"[CONTINUE at {dt:.1f}s] {resp.status}", flush=True)
    
    page.on("response", on_resp)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    print("Page loaded", flush=True)
    time.sleep(5)
    
    page.fill('input[name="username"]', 'testuser123')
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    
    page.evaluate("""() => {
        const root = document.querySelector('#login-base') || document.body;
        const key = Object.keys(root).find(k => k.startsWith('__reactFiber'));
        if (!key) return 'no_fiber';
        function walk(f, d) {
            if (!f || d > 20) return null;
            if (f.memoizedProps && typeof f.memoizedProps.onFormSubmit === 'function') {
                console.log('FOUND_onFormSubmit at depth', d);
                f.memoizedProps.onFormSubmit();
                return 'ok depth ' + d;
            }
            return walk(f.child, d+1) || walk(f.sibling, d);
        }
        return walk(root[key], 0);
    }""")
    t0[0] = time.time()
    print(f"[t=0] Form submitted", flush=True)
    
    time.sleep(45)
    print(f"[t=45] Done waiting", flush=True)
    browser.close()
