"""dispatchEvent click, wait long for enforcement, then call React handler."""
import os, time, json, sys, re

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    all_responses = []
    page.on("response", lambda r: all_responses.append({
        't': time.time(), 's': r.status, 'u': r.url[:200]
    }) if '/v2/login' in r.url or 'arkoselabs' in r.url or 'funcaptcha' in r.url else None)
    
    enf_frames = []
    def track_frames(frame):
        if 'arkoselabs.roblox.com' in frame.url and 'enforcement.' in frame.url:
            enf_frames.append(frame)
            print(f"  [+] Enforcement ({len(enf_frames)}): {frame.url[:200]}", flush=True)
    page.on("frameattached", track_frames)
    page.on("framenavigated", track_frames)
    
    # Long blocking wait for enforcement
    def wait_for_enforcement(page, timeout=60):
        start = time.time()
        while time.time() - start < timeout:
            for f in page.frames:
                if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                    return f
            time.sleep(0.5)
        return None
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(8)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    
    # Phase 1: dispatchEvent click
    print("[1] dispatchEvent click...", flush=True)
    click1_time = time.time()
    page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        if (btn) btn.dispatchEvent(
            new MouseEvent('click', {bubbles: true, cancelable: true, view: window})
        );
    }""")
    
    # Wait for enforcement (up to 60s)
    print("  Waiting up to 60s for enforcement...", flush=True)
    enf = wait_for_enforcement(page, 60)
    
    if not enf:
        print("  No enforcement found. Exiting.", flush=True)
        browser.close()
        exit()
    
    print(f"  Enforcement found at t={int(time.time()-click1_time)}s!", flush=True)
    print(f"  URL: {enf.url[:250]}", flush=True)
    
    st = re.search(r'&([0-9a-f\-]{36})$', enf.url)
    if st:
        print(f"  Session: {st.group(1)}", flush=True)
    
    # Wait a bit for enforcement to settle
    time.sleep(5)
    
    # Phase 2: Call React onClick handler directly (not dispatchEvent)
    print("\n[2] Calling React onClick handler directly...", flush=True)
    click2_time = time.time()
    
    handler_result = page.evaluate("""() => {
        try {
            const btn = document.getElementById('login-button');
            if (!btn) return {error: 'btn null'};
            
            // Get React props
            const propsKey = Object.keys(btn).find(k => k.startsWith('__reactProps'));
            if (!propsKey) return {error: 'no reactProps'};
            
            const props = btn[propsKey];
            if (!props?.onClick) return {error: 'no onClick'};
            
            const handler = props.onClick;
            // handler is function(e){return f()}
            const result = handler({});
            
            return {
                ok: true,
                handlerType: typeof handler,
                handlerStr: handler.toString().substring(0, 100),
                resultType: typeof result,
            };
        } catch(e) {
            return {error: e.message, stack: e.stack?.substring(0, 200)};
        }
    }""")
    print(f"  Handler result: {json.dumps(handler_result)[:400]}", flush=True)
    
    # Monitor for auth + game-core (30s)
    print("  Monitoring 30s for auth/game-core...", flush=True)
    auth_found = False
    gc_found = False
    nav_found = False
    
    start = time.time()
    while time.time() - start < 30:
        elapsed = int(time.time() - start)
        
        # Check auth
        for r in all_responses:
            if r['s'] == 403 and '/v2/login' in r['u'] and not auth_found:
                auth_found = True
                print(f"  [+] Auth 403 at t={elapsed}s!", flush=True)
        
        # Check game-core
        if not gc_found:
            for f in page.frames:
                if 'game-core' in f.url or 'game_core' in f.url:
                    gc_found = True
                    print(f"  [+] Game-core at t={elapsed}s!", flush=True)
        
        # Check enforcement iframes
        if not gc_found:
            try:
                iframes = enf.evaluate("document.querySelectorAll('iframe').length")
                if iframes > 0:
                    gc_found = True
                    print(f"  [+] Enforcement has {iframes} iframe(s) at t={elapsed}s!", flush=True)
            except:
                pass
        
        if gc_found:
            break
        time.sleep(0.5)
    
    total_elapsed = int(time.time() - start)
    print(f"\n[3] Results (t={total_elapsed}s)...", flush=True)
    print(f"  Auth 403: {auth_found}", flush=True)
    print(f"  Game-core: {gc_found}", flush=True)
    print(f"  Page URL: {page.url[:200]}", flush=True)
    
    print(f"\n=== All frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    print(f"\n=== Key responses ===", flush=True)
    for r in all_responses[-15:]:
        d1 = r['t'] - click1_time
        d2 = r['t'] - click2_time
        print(f"  [t1={d1:.0f}s t2={d2:.0f}s {r['s']}] {r['u']}", flush=True)
    
    page.screenshot(path="react_handler.png")
    time.sleep(5)
    browser.close()
