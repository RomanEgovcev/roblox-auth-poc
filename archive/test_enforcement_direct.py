"""Load enforcement in new browser context, track all API calls."""
import os, time, json, sys

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
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Track API calls more compactly
    calls = []
    page.on("response", lambda r: calls.append(f"[{r.status}] {r.url[:200]}") 
             if 'arkoselabs.roblox.com' in r.url or 'funcaptcha.com' in r.url else None)
    
    # Load enforcement directly in a tab
    print("[1] Loading enforcement directly...", flush=True)
    try:
        page.goto(f'https://arkoselabs.roblox.com/v2/4.4.2/enforcement.162a14c47922edcced45ca4d9b28e5d5.html#{PUBLIC_KEY}&',
                  wait_until='load', timeout=15000)
    except:
        pass
    time.sleep(8)
    
    print(f"\n=== API ({len(calls)}) ===", flush=True)
    for c in calls:
        print(f"  {c}", flush=True)
    
    # Check console errors
    logs = []
    page.on("console", lambda m: logs.append(f"[{m.type}] {m.text[:200]}") if m.type in ['error', 'warning'] else None)
    time.sleep(2)
    
    state = page.evaluate("""() => {
        const app = document.getElementById('app');
        return {
            url: location.href,
            appLen: app?.innerHTML?.length || 0,
            appHTML: app?.innerHTML?.substring(0, 300) || 'N/A',
        };
    }""")
    print(f"\n  State: {json.dumps(state)[:500]}", flush=True)
    
    # Also try with an iframe approach
    print("\n[2] Now trying iframe on Roblox login page...", flush=True)
    page2 = ctx.new_page()
    page2.set_viewport_size({"width": 1280, "height": 900})
    
    calls2 = []
    page2.on("response", lambda r: calls2.append(f"[{r.status}] {r.url[:200]}") 
             if 'arkoselabs.roblox.com' in r.url or 'funcaptcha.com' in r.url else None)
    
    page2.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=15000)
    time.sleep(5)
    
    # Inject enforcement iframe
    print("  Injecting enforcement iframe...", flush=True)
    page2.evaluate(f"""
    (() => {{
        const iframe = document.createElement('iframe');
        iframe.src = 'https://arkoselabs.roblox.com/v2/4.4.2/enforcement.162a14c47922edcced45ca4d9b28e5d5.html#{PUBLIC_KEY}&';
        iframe.style.cssText = 'width:400px;height:400px;border:1px solid red;position:fixed;top:100px;right:100px;z-index:999999';
        document.body.appendChild(iframe);
    }})();
    """)
    time.sleep(10)
    
    print(f"\n  API ({len(calls2)}) ===", flush=True)
    for c in calls2:
        print(f"  {c}", flush=True)
    
    print(f"\n  Frames:", flush=True)
    for fi, f in enumerate(page2.frames):
        print(f"    [{fi}] {f.url[:200]}", flush=True)
    
    time.sleep(5)
    browser.close()
