"""Call Roblox.Captcha.execute() to trigger captcha."""
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
    
    # Try Roblox.Captcha.execute()
    print(f"Calling Roblox.Captcha.execute()...", flush=True)
    r = page.evaluate("""() => {
        try {
            const result = Roblox.Captcha.execute();
            return {success: true, result: JSON.stringify(result), resultType: typeof result};
        } catch(e) {
            return {success: false, error: e.message, stack: e.stack?.substring(0, 300)};
        }
    }""")
    print(f"  Result: {json.dumps(r, indent=2)[:500]}", flush=True)
    time.sleep(5)
    
    print(f"\n--- Trying Roblox.Captcha.render() ---", flush=True)
    r2 = page.evaluate("""() => {
        try {
            const result = Roblox.Captcha.render();
            return {success: true, result: JSON.stringify(result), resultType: typeof result};
        } catch(e) {
            return {success: false, error: e.message, stack: e.stack?.substring(0, 300)};
        }
    }""")
    print(f"  Result: {json.dumps(r2, indent=2)[:500]}", flush=True)
    time.sleep(5)
    
    # Check for new frames
    print(f"\nFrames:", flush=True)
    for i, f in enumerate(page.frames):
        url = f.url
        if any(x in url for x in ['arkoselabs', 'enforcement', 'game-core', 'api.js']):
            print(f"  [{i}] {url[:200]}", flush=True)
    
    # Check if any enforcement elements appeared
    enf_check = page.evaluate("""() => {
        const iframes = Array.from(document.querySelectorAll('iframe')).map(f => f.src);
        const scripts = Array.from(document.querySelectorAll('script')).map(s => s.src);
        const arkose = scripts.filter(s => s.includes('arkoselabs') || s.includes('api.js'));
        const enf = iframes.filter(i => i.includes('arkoselabs') || i.includes('enforcement'));
        return {iframes, scripts_arkose: arkose, enf_iframes: enf};
    }""")
    print(f"\nPage elements:", flush=True)
    print(f"  Arkose scripts: {json.dumps(enf_check['scripts_arkose'])}", flush=True)
    print(f"  Enforcement iframes: {json.dumps(enf_check['enf_iframes'])}", flush=True)
    
    time.sleep(3)
    browser.close()
