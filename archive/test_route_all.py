"""Test with ALL route interception (matching the successful test)."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Intercept ALL requests (key: this was in the successful test)
    page.route("**/*", lambda route: route.continue_())
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[40:160]}", flush=True))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Load api.js manually
    loaded = page.evaluate("""() => {
        return new Promise((resolve) => {
            window.__arkCB = function(api) {
                window.__arkApi = api;
                resolve(true);
            };
            const s = document.createElement('script');
            s.src = 'https://arkoselabs.roblox.com/v2/476068BF-9607-4799-B53D-966BE98E2B81/api.js';
            s.setAttribute('data-callback', '__arkCB');
            document.head.appendChild(s);
            setTimeout(() => resolve(false), 15000);
        });
    }""")
    print(f"API loaded: {loaded}", flush=True)
    
    if loaded:
        page.evaluate("""() => {
            window.__arkApi.setConfig({publicKey: '476068BF-9607-4799-B53D-966BE98E2B81'});
        }""")
        time.sleep(5)
        page.evaluate("() => { window.__arkApi.run(); }")
    
    print("Waiting 15s...", flush=True)
    time.sleep(15)
    
    print(f"\n=== Frames ===", flush=True)
    for i, f in enumerate(page.frames):
        print(f"  [{i}] {f.url[:200]}", flush=True)
    
    time.sleep(2)
    browser.close()
