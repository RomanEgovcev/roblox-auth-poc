"""Submit via React onClick to get proper PX challenge response."""
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
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[:200]}", flush=True) if 'auth.roblox.com' in r.url or 'arkoselabs' in r.url or '/fc/' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(1)
    
    # Check for ctoken and other hidden fields
    print("[1] Checking form fields...", flush=True)
    fields = page.evaluate("""() => {
        const form = document.querySelector('form');
        if (!form) return {error: 'no form'};
        const inputs = form.querySelectorAll('input');
        return Array.from(inputs).map(i => ({
            name: i.name,
            id: i.id,
            type: i.type,
            value: i.value.substring(0, 20),
        }));
    }""")
    print(f"  Fields: {json.dumps(fields, indent=2)[:600]}", flush=True)
    
    # Call React onClick with ctoken included
    print("\n[2] Calling React onClick handler...", flush=True)
    result = page.evaluate("""async () => {
        try {
            const btn = document.getElementById('login-button');
            if (!btn) return {error: 'button not found'};
            
            // Find React props
            const propsKey = Object.keys(btn).find(k => k.startsWith('__reactProps'));
            if (!propsKey) return {error: 'no reactProps'};
            
            const onClick = btn[propsKey].onClick;
            if (!onClick) return {error: 'no onClick'};
            
            console.log('onClick handler:', onClick.toString());
            
            // Call the handler
            const result = onClick({});
            console.log('onClick returned:', result);
            
            // If result is a promise, await it
            if (result && typeof result.then === 'function') {
                const resolved = await result;
                console.log('onClick resolved:', resolved);
                return {resolved: true};
            }
            
            return {called: true, resultType: typeof result};
        } catch(e) {
            return {error: e.message, stack: e.stack.substring(0, 300)};
        }
    }""")
    print(f"  {json.dumps(result)[:400]}", flush=True)
    
    # Wait for enforcement
    print("[3] Waiting 15s for enforcement...", flush=True)
    enf = None
    for i in range(30):
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf = f
                break
        if enf:
            print(f"  [+] Enforcement at {i*0.5:.0f}s!", flush=True)
            break
        time.sleep(0.5)
    
    if enf:
        print(f"      {enf.url[:120]}", flush=True)
        time.sleep(5)
        
        # Check for images
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
        
        if gc:
            time.sleep(2)
            state = gc.evaluate("""() => ({
                imgs: document.querySelectorAll('img').length,
                bodyLen: document.body?.innerHTML?.length || 0,
            })""")
            print(f"  GC: {json.dumps(state)}", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    time.sleep(5)
    browser.close()
