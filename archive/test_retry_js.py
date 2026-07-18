"""Let challenge complete, then call PX retry via JS."""
import os, time, json
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    
    t0 = [None]
    events = []
    
    def on_req(req):
        if t0[0] is not None:
            events.append((time.time(), "REQ", req.method, req.url[:120]))
    page.on("request", on_req)
    
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
    
    t0[0] = time.time()
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
    print(f"[t=0] Submitted", flush=True)
    
    # Wait for challenge to appear (either captcha visible or complete)
    for i in range(70):
        time.sleep(1)
        
        # Check page state
        state = page.evaluate("""() => {
            const c = document.querySelector('.challenge-container, #arkose-iframe, [class*="captcha"], iframe[src*="arkoselabs"]');
            return {
                challengeVisible: c !== null,
                challengeHTML: c ? c.outerHTML.substring(0, 200) : null,
                url: window.location.href,
                // Check for PX
                pxKeys: Object.keys(window).filter(k => k.toLowerCase().includes('px') || k.toLowerCase().includes('perimeter')),
                // Check window._pxpjs
                pxpjs: window._pxpjs ? typeof window._pxpjs : null,
            };
        }""")
        
        if state.get("challengeVisible"):
            print(f"[t={i+1}] Challenge UI visible!", flush=True)
            print(f"  HTML: {state['challengeHTML']}", flush=True)
            print(f"  PX keys: {state.get('pxKeys', [])}", flush=True)
            time.sleep(10)  # Wait a bit
            break
            
        if i % 10 == 9:
            print(f"[t={i+1}] waiting, challenge={state.get('challengeVisible')}, px_keys={state.get('pxKeys', [])}", flush=True)
    
    # Now try to call PX retry or find retry function
    print(f"\n=== Looking for PX retry function ===", flush=True)
    
    # Search in window and PX objects
    retry_info = page.evaluate("""() => {
        const results = {};
        
        // Check window._pxpjs
        if (window._pxpjs) {
            results._pxpjs_keys = Object.keys(window._pxpjs).filter(k => !k.startsWith('_'));
        }
        
        // Check for retry functions globally
        const retryCandidates = [];
        for (const k in window) {
            try {
                const v = window[k];
                if (typeof v === 'function') {
                    const s = v.toString();
                    if (s.includes('retry') || s.includes('challenge') || s.includes('token') || 
                        s.includes('/v2/login') || s.includes('rblx-challenge'))
                        retryCandidates.push(k + ': ' + s.substring(0, 100));
                }
            } catch(e) {}
        }
        results.retryCandidates = retryCandidates;
        
        // Look for Nn function
        if (typeof Nn === 'function') {
            results.Nn = Nn.toString().substring(0, 200);
        }
        
        return results;
    }""")
    
    print(f"PX retry search:", flush=True)
    for k, v in retry_info.items():
        print(f"  {k}: {json.dumps(v)[:300]}", flush=True)
    
    # Try to trigger login retry from JS
    print(f"\n=== Trying to retry login from JS ===", flush=True)
    
    # Method 1: Look for login button and click
    retry_result = page.evaluate("""() => {
        const results = {};
        
        // Method 1: Find any retry/login button in challenge UI
        const buttons = document.querySelectorAll('button');
        const challengeButtons = [];
        buttons.forEach(b => {
            if (b.textContent.toLowerCase().includes('retry') || 
                b.textContent.toLowerCase().includes('try again') ||
                b.textContent.toLowerCase().includes('continue'))
                challengeButtons.push(b.textContent);
        });
        results.challengeButtons = Array.from(challengeButtons);
        
        // Method 2: Find and call Nn directly
        // Nn might be in React fiber
        const root = document.querySelector('#login-base') || document.body;
        const key = Object.keys(root).find(k => k.startsWith('__reactFiber'));
        let nnFound = false;
        if (key) {
            function walk(f, d) {
                if (!f || d > 20) return;
                // Look for stateNode or memoizedProps that contains login logic
                if (f.stateNode && typeof f.stateNode.handleSubmit === 'function') {
                    results.handleSubmit = 'found';
                }
                walk(f.child, d+1);
                walk(f.sibling, d);
            }
            walk(root[key], 0);
        }
        
        return results;
    }""")
    print(f"Retry result: {retry_result}", flush=True)
    
    # Print events
    print(f"\n=== Timeline ===", flush=True)
    events.sort(key=lambda x: x[0])
    for ts, tp, method, url in events:
        dt = ts - t0[0]
        if any(x in url for x in ("/v2/login", "pow-puzzle", "challenge/v1", "worker-resources")):
            print(f"[{dt:6.1f}s] {tp} {method} {url[:110]}", flush=True)
    
    cookies = ctx.cookies()
    rs = [c for c in cookies if ".ROBLOSECURITY" in c["name"]]
    print(f"\nROBLOSECURITY: {len(rs)}", flush=True)
    
    browser.close()
