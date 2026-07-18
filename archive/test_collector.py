"""Intercept PX collector to see its format."""
import os, time

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    collector_data = []
    
    def handle_collector(route):
        req = route.request
        if 'collector' in req.url:
            data = {
                'url': req.url,
                'method': req.method,
                'headers': dict(req.headers),
                'body': req.post_data[:1000] if req.post_data else None,
            }
            print(f"\n[collector] {req.method} {req.url[40:160]}", flush=True)
            if data['body']:
                print(f"  Body: {data['body'][:300]}", flush=True)
            collector_data.append(data)
        route.continue_()
    
    page.route("**/collector**", handle_collector)
    page.route("**/api/v2**", handle_collector)
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[40:120]}", flush=True))
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "TestPassword123!")
    time.sleep(1)
    
    page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        if (btn) {
            btn.dispatchEvent(new MouseEvent('click', {bubbles:true,cancelable:true,view:window}));
        }
    }""")
    
    time.sleep(10)
    
    print(f"\n=== Collector data ({len(collector_data)} requests) ===", flush=True)
    for d in collector_data:
        print(f"  {d['method']} {d['url'][:150]}", flush=True)
        print(f"    Body: {(d['body'] or 'None')[:300]}", flush=True)
    
    browser.close()
