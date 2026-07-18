"""Add continuous monitoring to change timing for PX trigger."""
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
    
    # Active response listener (creates async callbacks in event loop)
    arkose_calls = []
    def track(r):
        if 'arkoselabs' in r.url:
            arkose_calls.append({'s': r.status, 'u': r.url[:120]})
            print(f"  [{r.status}] {r.url[40:160]}", flush=True)
    page.on("response", track)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(1)
    
    # Continuous monitoring in page (via setInterval) to create async activity
    print("[1] Starting page monitoring...", flush=True)
    page.evaluate("""() => {
        window.__monitorInterval = setInterval(() => {
            // Read something from the page to keep event loop active
            const _ = document.title;
        }, 10);
    }""")
    
    # Now do dispatchEvent click
    print("[2] dispatchEvent click...", flush=True)
    page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        if (btn) {
            btn.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter',bubbles:true}));
            btn.dispatchEvent(new MouseEvent('click', {bubbles:true,cancelable:true,view:window}));
        }
    }""")
    
    # Wait for game-core with active monitoring
    print("[3] Waiting for game-core...", flush=True)
    gc = None
    t0 = time.time()
    for i in range(60):
        for f in page.frames:
            if 'game-core' in f.url:
                gc = f
                t = time.time() - t0
                print(f"  [+] Game-core at {t:.0f}s!", flush=True)
                break
        if gc:
            break
        time.sleep(0.5)
    
    if gc:
        time.sleep(5)
        state = gc.evaluate("""() => ({
            imgs: document.querySelectorAll('img').length,
            bodyLen: document.body?.innerHTML?.length || 0,
        })""")
        print(f"  GC initial: {json.dumps(state)}", flush=True)
        
        # Submit via React onClick if button exists
        submit_result = page.evaluate("""() => {
            const btn = document.getElementById('login-button');
            if (!btn) return 'no button';
            const pk = Object.keys(btn).find(k => k.startsWith('__reactProps'));
            if (!pk || !btn[pk]?.onClick) return 'no handler';
            btn[pk].onClick({});
            return 'submitted';
        }""")
        print(f"  Submit: {submit_result}", flush=True)
        
        # Wait for images
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
        
        if state['imgs'] > 0:
            urls = gc.evaluate("""() => 
                Array.from(document.querySelectorAll('img')).map(i => i.src).filter(s => s)
            """)
            print(f"  Image URLs: {json.dumps(urls)[:800]}", flush=True)
    else:
        t = time.time() - t0
        print(f"  No game-core in {t:.0f}s. Arkose calls:", flush=True)
        for c in arkose_calls:
            print(f"    [{c['s']}] {c['u']}", flush=True)
    
    # Cleanup interval
    page.evaluate("clearInterval(window.__monitorInterval)")
    
    time.sleep(3)
    browser.close()
