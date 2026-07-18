"""Full flow with retry loop for non-determinism."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

for attempt in range(5):
    print(f"\n{'='*60}", flush=True)
    print(f"Attempt {attempt+1}", flush=True)
    print('='*60, flush=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 900})
        
        page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
        time.sleep(3)
        
        page.fill("input[name='username']", USER)
        page.fill("input[name='password']", PASS)
        time.sleep(1)
        
        # Trigger PX multiple times
        print(f"  dispatchEvent click...", flush=True)
        page.evaluate("""() => {
            const btn = document.getElementById('login-button');
            if (!btn) return;
            for (let i = 0; i < 5; i++) {
                btn.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter',bubbles:true}));
                btn.dispatchEvent(new MouseEvent('click', {bubbles:true,cancelable:true,view:window}));
            }
        }""")
        
        # Wait for enforcement/game-core
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
            time.sleep(5)
            
            # Check game-core state
            state = gc.evaluate("""() => ({
                imgs: document.querySelectorAll('img').length,
                bodyLen: document.body?.innerHTML?.length || 0,
                bodyPreview: document.body?.innerHTML?.substring(0, 500) || '',
            })""")
            print(f"  GC: imgs={state['imgs']}, bodyLen={state['bodyLen']}", flush=True)
            print(f"  Body: {state['bodyPreview'][:200]}", flush=True)
            
            # Submit via React onClick
            btn = page.evaluate("""() => {
                const btn = document.getElementById('login-button');
                if (btn) {
                    const pk = Object.keys(btn).find(k => k.startsWith('__reactProps'));
                    if (pk && btn[pk]?.onClick) {
                        btn[pk].onClick({});
                        return 'clicked';
                    }
                    return 'no onClick';
                }
                return 'no button';
            }""")
            print(f"  Submit: {btn}", flush=True)
            
            # Wait for images
            for i in range(40):
                state = gc.evaluate("""() => ({
                    imgs: document.querySelectorAll('img').length,
                    bodyLen: document.body?.innerHTML?.length || 0,
                })""")
                if state['imgs'] > 0:
                    print(f"  [+] {state['imgs']} images at {i*0.5:.0f}s!", flush=True)
                    urls = gc.evaluate("""() => 
                        Array.from(document.querySelectorAll('img')).map(i => i.src).filter(s => s)
                    """)
                    print(f"  URLs: {json.dumps(urls)[:600]}", flush=True)
                    break
                if i % 10 == 0:
                    print(f"  t={i*0.5:.0f}s: {json.dumps(state)}", flush=True)
                time.sleep(0.5)
            
            print(f"\n=== Frames ===", flush=True)
            for fi, f in enumerate(page.frames):
                print(f"  [{fi}] {f.url[:200]}", flush=True)
            
            if state['imgs'] > 0:
                print("\n*** SUCCESS! Challenge images found! ***", flush=True)
            
            time.sleep(3)
            browser.close()
            break
        
        print(f"  No game-core on attempt {attempt+1}", flush=True)
        browser.close()
