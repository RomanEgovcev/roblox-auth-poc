"""Create enforcement iframe manually to see if it auto-generates session."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[:200]}", flush=True) if 'arkoselabs' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Create enforcement iframe without session token
    print("[1] Creating enforcement iframe...", flush=True)
    page.evaluate("""() => {
        const iframe = document.createElement('iframe');
        iframe.src = 'https://arkoselabs.roblox.com/v2/4.4.2/enforcement.162a14c47922edcced45ca4d9b28e5d5.html#476068BF-9607-4799-B53D-966BE98E2B81&';
        iframe.id = 'arkose-enforcement';
        iframe.style.display = 'none';
        document.body.appendChild(iframe);
    }""")
    
    time.sleep(5)
    
    # Check frames
    print("\n[2] Checking frames...", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    # Check if enforcement frame loaded and created game-core
    enf = None
    for f in page.frames:
        if 'enforcement.' in f.url:
            enf = f
            break
    
    if enf:
        print(f"\n[3] Enforcement frame found!", flush=True)
        # Check enforcement state
        enf_state = enf.evaluate("""() => ({
            url: window.location.href,
            iframes: document.querySelectorAll('iframe').length,
            iframeSrcs: Array.from(document.querySelectorAll('iframe')).map(f => f.src.substring(0, 150)),
        })""", timeout=5000)
        print(f"  Enforcement state: {json.dumps(enf_state, indent=2)[:500]}", flush=True)
        
        # Wait for game-core
        print("\n  Waiting 10s for game-core...", flush=True)
        time.sleep(10)
        gc = None
        for f in page.frames:
            if 'game-core' in f.url:
                gc = f
                break
        
        if gc:
            print(f"  [+] Game-core: {gc.url[:120]}", flush=True)
            state = gc.evaluate("""() => ({
                imgs: document.querySelectorAll('img').length,
                bodyLen: document.body?.innerHTML?.length || 0,
            })""", timeout=5000)
            print(f"  GC: {json.dumps(state)}", flush=True)
        else:
            print("  No game-core found.", flush=True)
    
    time.sleep(5)
    browser.close()
