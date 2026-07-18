"""Comprehensive: intercept PX callback OR create our own enforcement."""
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
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[40:160]}", flush=True) if 'arkoselabs' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(1)
    
    # Set up OUR callback AND a MutationObserver to catch PX's callback
    print("[1] Setting up callbacks...", flush=True)
    page.evaluate("""() => {
        // Our own Arkose API reference
        window.__myArkApi = null;
        
        // Create a promise to wait for any Arkose API
        window.__arkoseReadyPromise = new Promise((resolve) => {
            window.__resolveArkoseReady = resolve;
        });
        
        // Our own callback (in case PX uses it)
        window.__arkSR = function(api) {
            window.__myArkApi = api;
            window.__resolveArkoseReady('callback');
        };
        
        // Also monitor for PX's api.js script
        const observer = new MutationObserver((mutations) => {
            for (const m of mutations) {
                for (const node of m.addedNodes) {
                    if (node.tagName === 'SCRIPT' && node.src && node.src.includes('api.js')) {
                        const cb = node.getAttribute('data-callback');
                        if (cb && cb !== '__arkSR' && !window[cb + '_patched']) {
                            console.log('Found PX callback:', cb);
                            const origCb = window[cb];
                            window[cb + '_patched'] = true;
                            window[cb] = function(api) {
                                window.__myArkApi = api;
                                window.__resolveArkoseReady('px_' + cb);
                                if (origCb) origCb(api);
                            };
                        }
                    }
                }
            }
        });
        observer.observe(document.documentElement, {childList: true, subtree: true});
        
        // Also store observer ref
        window.__apiObserver = observer;
    }""")
    
    # Trigger PX
    print("[2] dispatchEvent click...", flush=True)
    page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        if (btn) {
            btn.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter',bubbles:true}));
            btn.dispatchEvent(new MouseEvent('click', {bubbles:true,cancelable:true,view:window}));
        }
    }""")
    
    # Wait for Arkose API to arrive (from PX or our own load)
    print("[3] Waiting for Arkose API (up to 30s)...", flush=True)
    
    # Try to get API from PX first (wait 10s)
    api_source = None
    for i in range(20):
        has_api = page.evaluate("!!window.__myArkApi")
        if has_api:
            api_source = page.evaluate("'from PX via observer'")
            print(f"  [+] API from PX at {i*0.5:.0f}s!", flush=True)
            break
        time.sleep(0.5)
    
    if not api_source:
        print("  No API from PX. Loading api.js ourselves...", flush=True)
        page.evaluate("""() => {
            const s = document.createElement('script');
            s.id = '__arkose_manual';
            s.src = 'https://arkoselabs.roblox.com/v2/476068BF-9607-4799-B53D-966BE98E2B81/api.js';
            s.setAttribute('data-callback', '__arkSR');
            document.head.appendChild(s);
        }""")
        
        for i in range(20):
            has_api = page.evaluate("!!window.__myArkApi")
            if has_api:
                api_source = "manual load"
                print(f"  [+] API from manual load at {i*0.5:.0f}s!", flush=True)
                break
            time.sleep(0.5)
    
    if not api_source:
        print("  API not available. Exiting.", flush=True)
        browser.close()
        exit()
    
    # Now use the API
    print(f"\n[4] API source: {api_source}", flush=True)
    api_info = page.evaluate("""() => {
        const api = window.__myArkApi;
        if (!api) return {error: 'no api'};
        return {
            keys: Object.keys(api).slice(0, 10),
            version: api.version,
            hasConfig: typeof api.getConfig === 'function',
            hasRun: typeof api.run === 'function',
        };
    }""")
    print(f"  API: {json.dumps(api_info, indent=2)[:400]}", flush=True)
    
    # Check if enforcement already created
    has_enf = any('enforcement.' in f.url for f in page.frames)
    if not has_enf:
        print("\n[5] Calling api.run()...", flush=True)
        page.evaluate("""() => {
            const api = window.__myArkApi;
            if (api && api.run) api.run();
        }""")
    
    # Wait for game-core
    print("[6] Waiting for game-core...", flush=True)
    gc = None
    for i in range(40):
        for f in page.frames:
            if 'game-core' in f.url:
                gc = f
                print(f"  [+] Game-core at {i*0.5:.0f}s!", flush=True)
                break
        if gc:
            break
        time.sleep(0.5)
    
    if gc:
        time.sleep(3)
        state = gc.evaluate("""() => ({
            imgs: document.querySelectorAll('img').length,
            bodyLen: document.body?.innerHTML?.length || 0,
        })""")
        print(f"  GC: {json.dumps(state)}", flush=True)
        
        # Submit form via React onClick
        print("\n[7] Submitting form...", flush=True)
        s = page.evaluate("""() => {
            const btn = document.getElementById('login-button');
            if (!btn) return 'no_btn';
            const pk = Object.keys(btn).find(k => k.startsWith('__reactProps'));
            if (pk && btn[pk]?.onClick) {
                btn[pk].onClick({});
                return 'clicked';
            }
            return 'no_handler';
        }""")
        print(f"  Submit: {s}", flush=True)
        
        for i in range(40):
            state = gc.evaluate("""() => ({
                imgs: document.querySelectorAll('img').length,
                bodyLen: document.body?.innerHTML?.length || 0,
            })""")
            if state['imgs'] > 0:
                print(f"  [+] {state['imgs']} images at {i*0.5:.0f}s!", flush=True)
                break
            if i % 10 == 0:
                print(f"  t={i*0.5:.0f}s: {json.dumps(state)}", flush=True)
            time.sleep(0.5)
        print(f"  Final: {json.dumps(state)}", flush=True)
    else:
        print("  No game-core.", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    time.sleep(3)
    browser.close()
