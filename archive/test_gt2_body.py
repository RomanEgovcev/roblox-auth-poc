"""Capture gt2 400 response body properly."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

gt2_body = {}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Use route interception to capture gt2 body
    def handle_gt2(route):
        req = route.request
        if 'fc/gt2' in req.url:
            body = req.post_data
            print(f"\n=== GT2 Request ===", flush=True)
            print(f"  URL: {req.url}", flush=True)
            print(f"  Body ({len(body)} bytes): {body[:2000]}", flush=True)
            gt2_body['req_body'] = body
            
            # Continue and capture response
            response = route.fetch()
            gt2_body['resp_status'] = response.status
            gt2_body['resp_body'] = response.body()[:2000]
            print(f"\n=== GT2 Response [{response.status}] ===", flush=True)
            print(f"  Body: {response.body()[:1000]}")
            route.fulfill(response=response)
        else:
            route.continue_()
    
    page.route("**/fc/gt2/**", handle_gt2)
    
    page.on("response", lambda r: print(f"  [{r.status}] settings" if 'settings' in r.url else "", flush=True))
    
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
    
    if loaded:
        page.evaluate("""() => {
            window.__arkApi.setConfig({publicKey: '476068BF-9607-4799-B53D-966BE98E2B81'});
        }""")
        time.sleep(5)
        page.evaluate("() => { window.__arkApi.run(); }")
    
    time.sleep(10)
    
    print(f"\n=== GT2 Details ===", flush=True)
    for k, v in gt2_body.items():
        val = v
        if isinstance(val, bytes):
            val = val.decode('utf-8', errors='replace')
        print(f"  {k}: {str(val)[:500]}", flush=True)
    
    time.sleep(2)
    browser.close()
