"""Create enforcement manually: load enforcement HTML, then call gt2 API from within."""
import os, time, json, sys, re

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

PUBLIC_KEY = "476068BF-9607-4799-B53D-966BE98E2B81"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    ctx = browser.new_context()
    page = ctx.new_page()
    page.set_viewport_size({"width": 800, "height": 600})
    
    # Load enforcement HTML as standalone page
    print("[1] Loading enforcement HTML...", flush=True)
    page.goto(
        f'https://arkoselabs.roblox.com/v2/4.4.2/enforcement.162a14c47922edcced45ca4d9b28e5d5.html#{PUBLIC_KEY}&',
        wait_until='load', timeout=15000
    )
    time.sleep(5)
    
    # Now call gt2 API from within this page's context
    print("[2] Calling gt2 API from enforcement page context...", flush=True)
    
    result = page.evaluate("""async () => {
        const pk = '476068BF-9607-4799-B53D-966BE98E2B81';
        const callbackName = 'setupEnforcement0';
        
        try {
            // Try JSONP approach first (create script tag)
            const resp = await fetch('/fc/gt2/public_key/' + pk + '?' + new URLSearchParams({
                callback: callbackName,
                public_key: pk,
                userbrowser: navigator.userAgent,
                simulate: 'mouse',
                lang: 'en'
            }));
            
            return {
                status: resp.status,
                statusText: resp.statusText,
                text: (await resp.text()).substring(0, 500),
                headers: Array.from(resp.headers.entries()).slice(0, 15)
            };
        } catch(e) {
            return {error: e.message, stack: e.stack?.substring(0, 300)};
        }
    }""")
    
    print(f"  Result: {json.dumps(result)[:600]}", flush=True)
    
    # Try POST
    print("\n[3] Trying POST to gt2...", flush=True)
    result2 = page.evaluate("""async () => {
        const pk = '476068BF-9607-4799-B53D-966BE98E2B81';
        try {
            const resp = await fetch('/fc/gt2/public_key/' + pk, {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({
                    callback: 'setupEnforcement0',
                    public_key: pk,
                    userbrowser: navigator.userAgent,
                    simulate: 'mouse',
                    lang: 'en'
                })
            });
            return {
                status: resp.status,
                text: (await resp.text()).substring(0, 500),
            };
        } catch(e) {
            return {error: e.message};
        }
    }""")
    
    print(f"  POST result: {json.dumps(result2)[:600]}", flush=True)
    
    # Try XMLHttpRequest
    print("\n[4] Trying XMLHttpRequest to gt2...", flush=True)
    result3 = page.evaluate("""async () => {
        const pk = '476068BF-9607-4799-B53D-966BE98E2B81';
        return new Promise((resolve) => {
            try {
                const xhr = new XMLHttpRequest();
                xhr.open('GET', '/fc/gt2/public_key/' + pk + '?' + new URLSearchParams({
                    callback: 'setupEnforcement0',
                    public_key: pk,
                    userbrowser: navigator.userAgent,
                    simulate: 'mouse',
                }));
                xhr.onload = () => resolve({
                    status: xhr.status,
                    text: xhr.responseText.substring(0, 500),
                });
                xhr.onerror = () => resolve({error: 'XHR error'});
                xhr.send();
            } catch(e) {
                resolve({error: e.message});
            }
        });
    }""")
    
    print(f"  XHR result: {json.dumps(result3)[:600]}", flush=True)
    
    # Check current cookies
    cookies = page.evaluate("""() => document.cookie""")
    print(f"\n  Cookies: {cookies[:200]}", flush=True)
    
    browser.close()
