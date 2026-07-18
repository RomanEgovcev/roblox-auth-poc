"""Capture gt2 request payload and check response."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

gt2_details = {}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    def log_req(r):
        if 'fc/gt2' in r.url:
            print(f"  >> GT2 req: {r.url}", flush=True)
            print(f"  >> GT2 method: {r.method}", flush=True)
            print(f"  >> GT2 headers: {dict(r.headers)}", flush=True)
            gt2_details['body'] = r.post_data
            gt2_details['url'] = r.url
    
    page.on("request", log_req)
    
    def log_resp(r):
        if 'fc/gt2' in r.url:
            print(f"  << GT2 resp: [{r.status}] {r.url[40:200]}", flush=True)
            try:
                body = r.body()
                print(f"  << GT2 body: {body[:500]}", flush=True)
                gt2_details['response'] = body[:1000].decode()
            except:
                print(f"  << GT2 body: (error reading)", flush=True)
        elif 'settings' in r.url:
            print(f"  [{r.status}] settings", flush=True)
        elif 'enforcement' in r.url or 'game-core' in r.url:
            print(f"  [{r.status}] {r.url[40:200]}", flush=True)
    
    page.on("response", log_resp)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Load api.js with callback
    print("\n[1] Loading api.js...", flush=True)
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
    print(f"  Loaded: {loaded}", flush=True)
    
    if not loaded:
        browser.close()
        exit()
    
    # setConfig
    print("\n[2] setConfig...", flush=True)
    page.evaluate("""() => {
        window.__arkApi.setConfig({
            publicKey: '476068BF-9607-4799-B53D-966BE98E2B81',
        });
    }""")
    
    time.sleep(5)
    
    # run
    print("\n[3] run()...", flush=True)
    page.evaluate("() => { window.__arkApi.run(); }")
    
    time.sleep(5)
    
    print(f"\n=== GT2 details ===", flush=True)
    print(f"  URL: {gt2_details.get('url', 'N/A')}", flush=True)
    print(f"  Body: {gt2_details.get('body', 'N/A')[:500]}", flush=True)
    print(f"  Response status: unknown (captured via response listener)", flush=True)
    
    time.sleep(2)
    browser.close()
