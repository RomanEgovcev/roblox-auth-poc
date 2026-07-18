"""Configure and trigger Roblox Captcha."""
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
    
    # Check current captcha config
    config = page.evaluate("""() => {
        const c = Roblox.Captcha;
        return {
            currentEndpoint: c.getEndpoint ? c.getEndpoint() : 'no getEndpoint',
            isInvisible: c.getInvisibleMode ? c.getInvisibleMode() : 'no getInvisibleMode',
            ids: c.ids || [],
            types: c.types || [],
        };
    }""")
    print(f"Current config:", flush=True)
    print(json.dumps(config, indent=2)[:500], flush=True)
    
    # Check if we can see the Captcha.js source for how it's configured
    captcha_render_src = page.evaluate("""() => {
        try {
            return Roblox.Captcha.render.toString().substring(0, 1000);
        } catch(e) { return e.message; }
    }""")
    print(f"\nCaptcha.render source:", flush=True)
    print(captcha_render_src[:1000], flush=True)
    
    # Check setSiteKey
    set_sitekey_src = page.evaluate("""() => {
        try {
            return Roblox.Captcha.setSiteKey.toString().substring(0, 500);
        } catch(e) { return e.message; }
    }""")
    print(f"\nCaptcha.setSiteKey source:", flush=True)
    print(set_sitekey_src[:500], flush=True)
    
    # Check verify
    verify_src = page.evaluate("""() => {
        try {
            return Roblox.Captcha.verify.toString().substring(0, 500);
        } catch(e) { return e.message; }
    }""")
    print(f"\nCaptcha.verify source:", flush=True)
    print(verify_src[:500], flush=True)
    
    time.sleep(3)
    browser.close()
