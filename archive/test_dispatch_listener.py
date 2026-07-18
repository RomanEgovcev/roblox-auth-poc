"""Deterministic approach: load api.js properly + trigger enforcement."""
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
    
    # Log key responses
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[:150]}", flush=True) if 'arkoselabs' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(1)
    
    # Try dispatchEvent click (with the response listener active)
    print("[1] dispatchEvent click...", flush=True)
    page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        btn.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter',bubbles:true}));
        btn.dispatchEvent(new MouseEvent('click', {bubbles:true,cancelable:true,view:window}));
    }""")
    
    # Wait for game-core
    print("[2] Waiting for game-core...", flush=True)
    gc = None
    for i in range(30):
        for f in page.frames:
            if 'game-core' in f.url:
                gc = f
                break
        if gc:
            print(f"  [+] Game-core at {i*0.5:.0f}s!", flush=True)
            break
        time.sleep(0.5)
    
    if not gc:
        print("  No game-core from dispatch. Trying 2nd dispatch...", flush=True)
        page.evaluate("""() => {
            const btn = document.getElementById('login-button');
            btn.dispatchEvent(new MouseEvent('click', {bubbles:true,cancelable:true,view:window}));
        }""")
        for i in range(30):
            for f in page.frames:
                if 'game-core' in f.url:
                    gc = f
                    break
            if gc:
                print(f"  [+] Game-core at {i*0.5:.0f}s!", flush=True)
                break
            time.sleep(0.5)
    
    if gc:
        time.sleep(3)
        state = gc.evaluate("""() => ({
            imgs: document.querySelectorAll('img').length,
            bodyLen: document.body?.innerHTML?.length || 0,
            bodyPreview: document.body?.innerHTML?.substring(0, 500) || '',
        })""")
        print(f"\n  GC: {json.dumps(state)[:600]}", flush=True)
    else:
        print("  No game-core. Loading api.js directly...", flush=True)
        # Load api.js with callback
        page.evaluate("""() => {
            return new Promise((resolve) => {
                window.__arkCB = function(api) {
                    window.__arkApi = api;
                    resolve(true);
                };
                const s = document.createElement('script');
                s.src = 'https://arkoselabs.roblox.com/v2/476068BF-9607-4799-B53D-966BE98E2B81/api.js';
                s.setAttribute('data-callback', '__arkCB');
                document.head.appendChild(s);
                setTimeout(() => resolve(false), 10000);
            });
        }""")
        time.sleep(2)
        
        has_api = page.evaluate("!!window.__arkApi")
        if has_api:
            print("  API loaded. Calling setConfig + run...", flush=True)
            page.evaluate("""async () => {
                try {
                    const api = window.__arkApi;
                    api.setConfig({publicKey: '476068BF-9607-4799-B53D-966BE98E2B81'});
                    // Wait then run
                    await new Promise(r => setTimeout(r, 3000));
                    api.run();
                } catch(e) {
                    console.error('Error:', e);
                }
            }""")
            
            for i in range(30):
                for f in page.frames:
                    if 'game-core' in f.url:
                        gc = f
                        break
                if gc:
                    print(f"  [+] Game-core at {i*0.5:.0f}s!", flush=True)
                    break
                time.sleep(0.5)
    
    if gc:
        time.sleep(3)
        state = gc.evaluate("""() => ({
            imgs: document.querySelectorAll('img').length,
            bodyLen: document.body?.innerHTML?.length || 0,
        })""")
        print(f"\n  GC final: {json.dumps(state)}", flush=True)
        
        # Submit form via React onClick
        btn = page.evaluate("""() => {
            const btn = document.getElementById('login-button');
            if (!btn) return 'no button';
            const pk = Object.keys(btn).find(k => k.startsWith('__reactProps'));
            if (!pk) return 'no props';
            btn[pk].onClick({});
            return 'clicked';
        }""")
        print(f"  Submit: {btn}", flush=True)
        
        # Wait for images
        for i in range(30):
            state = gc.evaluate("""() => ({
                imgs: document.querySelectorAll('img').length,
                bodyLen: document.body?.innerHTML?.length || 0,
            })""")
            if state['imgs'] > 0:
                print(f"  [+] {state['imgs']} images at {i*0.5:.0f}s!", flush=True)
                break
            time.sleep(0.5)
        print(f"  Final: {json.dumps(state)}", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    time.sleep(3)
    browser.close()
