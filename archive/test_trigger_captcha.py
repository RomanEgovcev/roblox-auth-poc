"""Explore and call triggerCaptcha."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[40:120]}", flush=True))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # Check triggerCaptcha source
    tc_src = page.evaluate("""() => {
        try {
            return triggerCaptcha.toString().substring(0, 2000);
        } catch(e) {
            return 'error: ' + e.message;
        }
    }""")
    print(f"triggerCaptcha source:", flush=True)
    print(tc_src, flush=True)
    
    print(f"\n---", flush=True)
    
    # Check what triggerCaptcha looks like
    tc_info = page.evaluate("""() => {
        const info = {};
        info.type = typeof triggerCaptcha;
        info.has_params = triggerCaptcha.length;
        
        // Check if it's a regular function or minified
        try {
            const fullSrc = triggerCaptcha.toString();
            info.length = fullSrc.length;
            info.startsWith = fullSrc.substring(0, 50);
        } catch(e) {
            info.error = e.message;
        }
        
        return info;
    }""")
    print(f"triggerCaptcha info:", flush=True)
    print(json.dumps(tc_info, indent=2), flush=True)
    
    print(f"\n--- Calling triggerCaptcha() ---", flush=True)
    
    r = page.evaluate("""() => {
        try {
            const result = triggerCaptcha();
            return {success: true, result: JSON.stringify(result), resultType: typeof result};
        } catch(e) {
            return {success: false, error: e.message, stack: e.stack?.substring(0, 300)};
        }
    }""")
    print(f"Result: {json.dumps(r, indent=2)[:500]}", flush=True)
    
    time.sleep(10)
    
    # Check frames after call
    print(f"\nFrames:", flush=True)
    for i, f in enumerate(page.frames):
        url = f.url
        if 'arkoselabs' in url or 'enforcement' in url or 'game-core' in url or 'about:blank' not in url:
            print(f"  [{i}] {url[:200]}", flush=True)
    
    time.sleep(3)
    browser.close()
