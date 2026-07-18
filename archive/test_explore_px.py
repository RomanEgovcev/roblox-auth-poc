"""Explore PX object and try to bypass captcha from JS."""
import os, time, json
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    
    def on_req(req):
        if any(x in req.url for x in ("/v2/login", "pow-puzzle", "challenge/v1", "account-security")):
            print(f"[REQ] {req.method} {req.url[:110]}", flush=True)
        if "/v2/login" in req.url:
            h = dict(req.headers)
            if any("rblx-challenge" in k for k in h):
                print(f"  ** HAS CHALLENGE HEADERS **", flush=True)
    page.on("request", on_req)
    
    def on_resp(resp):
        if "/v2/login" in resp.url:
            try:
                b = resp.body()[:300]
                print(f"[RESP] /v2/login {resp.status} {b}", flush=True)
            except:
                print(f"[RESP] /v2/login {resp.status}", flush=True)
        elif "/challenge/v1/continue" in resp.url:
            try:
                b = resp.body()[:400]
                print(f"[RESP] continue {resp.status} {b}", flush=True)
            except:
                pass
    page.on("response", on_resp)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    page.evaluate("""() => {
        for (let i = 0; i < 30; i++)
            document.dispatchEvent(new MouseEvent('mousemove', {clientX: 100+i*20, clientY: 200+i*5, bubbles: true}));
        document.querySelector('input[name="username"]')?.focus();
    }""")
    time.sleep(1)
    page.fill('input[name="username"]', 'testuser123')
    time.sleep(0.5)
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    page.evaluate("""() => {
        for (let i = 0; i < 15; i++)
            document.dispatchEvent(new MouseEvent('mousemove', {clientX: 500+i*20, clientY: 300+i*5, bubbles: true}));
    }""")
    time.sleep(0.5)
    
    page.evaluate("""() => {
        const root = document.querySelector('#login-base') || document.body;
        const key = Object.keys(root).find(k => k.startsWith('__reactFiber'));
        function walk(f, d) {
            if (!f || d > 20) return null;
            if (f.memoizedProps && typeof f.memoizedProps.onFormSubmit === 'function') {
                f.memoizedProps.onFormSubmit();
                return 'ok';
            }
            return walk(f.child, d+1) || walk(f.sibling, d);
        }
        return walk(root[key], 0);
    }""")
    print(f"Submitted", flush=True)
    
    # Wait for challenge UI
    for i in range(30):
        time.sleep(1)
        challenge_visible = page.evaluate("() => document.querySelector('.challenge-captcha-body') !== null")
        if challenge_visible:
            print(f"[t={i+1}] Challenge UI visible", flush=True)
            time.sleep(2)
            
            # Explore PX object
            px_info = page.evaluate("""() => {
                const results = {};
                
                // Get PX object
                const px = window.PXbf8PROpW;
                if (!px) return {error: 'no PXbf8PROpW'};
                
                results.pxType = typeof px;
                results.pxKeys = Object.getOwnPropertyNames(px).filter(k => !k.startsWith('_')).slice(0, 30);
                
                // Try to find methods
                const methods = [];
                for (const k in px) {
                    if (typeof px[k] === 'function') {
                        const s = px[k].toString().substring(0, 150);
                        methods.push({name: k, sig: s});
                    }
                }
                results.methods = methods.slice(0, 15);
                
                // Look for enforcement state
                if (px._enforcement) {
                    results.enforcementKeys = Object.keys(px._enforcement).slice(0, 20);
                }
                
                // Look for challenge data
                if (px._challengeData) {
                    results.challengeData = JSON.stringify(px._challengeData).substring(0, 300);
                }
                
                return results;
            }""")
            print(f"PX object:", flush=True)
            for k, v in px_info.items():
                if isinstance(v, list):
                    print(f"  {k}:", flush=True)
                    for item in v[:10]:
                        print(f"    {item}", flush=True)
                else:
                    print(f"  {k}: {str(v)[:200]}", flush=True)
            
            # Try to find a way to retry login
            retry_info = page.evaluate("""() => {
                const px = window.PXbf8PROpW;
                const results = {};
                
                // Look for submit/resolve challenge
                if (typeof px.submitChallenge === 'function')
                    results.submitChallenge = px.submitChallenge.toString().substring(0, 100);
                
                if (typeof px.resolveChallenge === 'function')
                    results.resolveChallenge = px.resolveChallenge.toString().substring(0, 100);
                
                if (typeof px.submitCaptcha === 'function')
                    results.submitCaptcha = px.submitCaptcha.toString().substring(0, 100);
                
                // Look for enforcement that handles captcha
                if (px._enforcement) {
                    const e = px._enforcement;
                    const enMethods = [];
                    for (const k in e) {
                        if (typeof e[k] === 'function')
                            enMethods.push(k);
                    }
                    results.enforcementMethods = enMethods.slice(0, 20);
                }
                
                // Try to call setupEnforcement to see what we get
                if (px.setupEnforcement) {
                    const se = px.setupEnforcement;
                    results.setupEnforcementType = typeof se;
                }
                
                return results;
            }""")
            print(f"\nRetry methods:", flush=True)
            for k, v in retry_info.items():
                print(f"  {k}: {str(v)[:200]}", flush=True)
            
            break
        if i % 5 == 4:
            print(f"[t={i+1}] waiting for challenge...", flush=True)
    
    # If we found retry methods, try calling them
    print(f"\n=== Attempting retry bypass ===", flush=True)
    
    # Try to submit empty captcha token
    bypass_result = page.evaluate("""() => {
        const px = window.PXbf8PROpW;
        const results = {};
        
        // Try to access _enforcement
        if (px._enforcement) {
            const e = px._enforcement;
            // Look for a way to bypass
            if (e.bypassChallenge && typeof e.bypassChallenge === 'function') {
                results.bypassCalled = true;
                try { e.bypassChallenge(); } catch(ex) { results.bypassError = ex.message; }
            }
            
            // Try to access challenge data
            if (e._challengeData) {
                results.challengeData = JSON.stringify(e._challengeData).substring(0, 300);
            }
            
            // Try accessing risk or session
            for (const k of Object.keys(e)) {
                if (k.includes('challenge') || k.includes('token') || k.includes('risk') || k.includes('session'))
                    results['enforcement_' + k] = typeof e[k] === 'object' ? JSON.stringify(e[k]).substring(0, 100) : String(e[k]).substring(0, 100);
            }
        }
        
        return results;
    }""")
    print(f"Bypass result: {json.dumps(bypass_result, indent=2)[:500]}", flush=True)
    
    # Check cookies
    cookies = ctx.cookies()
    rs = [c for c in cookies if ".ROBLOSECURITY" in c["name"]]
    print(f"\nROBLOSECURITY: {len(rs)}", flush=True)
    
    time.sleep(3)
    browser.close()
