"""Use RobloxCaptcha to render the captcha directly."""
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
    
    # Explore RobloxCaptcha methods
    captcha_info = page.evaluate("""() => {
        const info = {};
        const rc = RobloxCaptcha;
        
        for (const k of Object.keys(rc)) {
            try {
                const v = rc[k];
                if (typeof v === 'function') {
                    info[k] = {
                        type: 'function',
                        params: v.length,
                        src: v.toString().substring(0, 300),
                    };
                } else {
                    info[k] = {
                        type: typeof v,
                        value: String(v).substring(0, 200),
                    };
                }
            } catch(e) {
                info[k] = {error: e.message};
            }
        }
        return info;
    }""")
    print(f"RobloxCaptcha methods:", flush=True)
    print(json.dumps(captcha_info, indent=2)[:3000], flush=True)
    
    # Try render
    print(f"\n--- Calling RobloxCaptcha.execute() ---", flush=True)
    r1 = page.evaluate("""() => {
        try {
            const result = RobloxCaptcha.execute();
            return {success: true, result: JSON.stringify(result)};
        } catch(e) {
            return {success: false, error: e.message, stack: e.stack?.substring(0, 300)};
        }
    }""")
    print(f"  execute: {json.dumps(r1)[:500]}", flush=True)
    time.sleep(5)
    
    print(f"\n--- Calling RobloxCaptcha.render() ---", flush=True)
    r2 = page.evaluate("""() => {
        try {
            const result = RobloxCaptcha.render();
            return {success: true, result: JSON.stringify(result)};
        } catch(e) {
            return {success: false, error: e.message, stack: e.stack?.substring(0, 300)};
        }
    }""")
    print(f"  render: {json.dumps(r2)[:500]}", flush=True)
    time.sleep(5)
    
    print(f"\nFrames:", flush=True)
    for i, f in enumerate(page.frames):
        url = f.url
        if any(x in url for x in ['arkoselabs', 'enforcement', 'game-core']):
            print(f"  [{i}] {url[:200]}", flush=True)
    
    time.sleep(3)
    browser.close()
