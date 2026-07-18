"""Capture gt2 request body with route interception."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

gt2_info = {"body": None, "url": None, "headers": None}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    def handle_gt2(route):
        req = route.request
        if 'fc/gt2' in req.url:
            body = req.post_data
            print(f"\n=== GT2 REQUEST ===", flush=True)
            print(f"  URL: {req.url}", flush=True)
            print(f"  Method: {req.method}", flush=True)
            print(f"  Body ({len(body) if body else 0} bytes): {(body or 'N/A')[:1000]}", flush=True)
            gt2_info['url'] = req.url
            gt2_info['body'] = body
            gt2_info['headers'] = dict(req.headers)
        route.continue_()
    
    page.route("**/fc/gt2/**", handle_gt2)
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[40:160]}", flush=True))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
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
    
    if not loaded:
        browser.close()
        exit()
    
    page.evaluate("""() => {
        window.__arkApi.setConfig({publicKey: '476068BF-9607-4799-B53D-966BE98E2B81'});
    }""")
    
    time.sleep(3)
    
    page.evaluate("() => { window.__arkApi.run(); }")
    
    print("Waiting 20s for gt2...", flush=True)
    time.sleep(20)
    
    print(f"\n=== GT2 Info ===", flush=True)
    for k, v in gt2_info.items():
        val_str = str(v)
        if len(val_str) > 500:
            val_str = val_str[:500] + f"... ({len(val_str)} chars total)"
        print(f"  {k}: {val_str}", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for i, f in enumerate(page.frames):
        print(f"  [{i}] {f.url[:200]}", flush=True)
    
    time.sleep(2)
    browser.close()
