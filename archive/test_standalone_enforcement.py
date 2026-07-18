"""Load enforcement as standalone page and let it make its own API calls."""
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
    
    calls = []
    page.on("response", lambda r: calls.append(f"[{r.status}] {r.url[:200]}") 
             if 'api.funcaptcha.com' in r.url or 'arkoselabs' in r.url or 'funcaptcha' in r.url else None)
    
    logs = []
    page.on("console", lambda m: logs.append(f"[{m.type}] {m.text[:200]}") if m.type in ['error', 'warning', 'info', 'log'] else None)
    
    # Load enforcement as if it's in a top-level page (no parent context)
    print("[1] Loading enforcement as standalone page (with public_key only, no session)...", flush=True)
    try:
        page.goto(
            f'https://arkoselabs.roblox.com/v2/4.4.2/enforcement.162a14c47922edcced45ca4d9b28e5d5.html#{PUBLIC_KEY}&',
            wait_until='load', timeout=20000
        )
    except Exception as e:
        print(f"  Load exception: {e}", flush=True)
    
    time.sleep(10)
    
    print(f"\n=== API calls ({len(calls)}) ===", flush=True)
    for c in calls[-20:]:
        print(f"  {c}", flush=True)
    
    print(f"\n=== Console logs ({len(logs)}) ===", flush=True)
    for l in logs[-10:]:
        print(f"  {l}", flush=True)
    
    # Check page state
    state = page.evaluate("""() => ({
        url: location.href,
        appLen: document.getElementById('app')?.innerHTML?.length || 0,
        appHTML: document.getElementById('app')?.innerHTML?.substring(0, 500) || 'N/A',
        funCaptcha: !!window.funCaptcha,
        vt: document.getElementById('verification-token')?.value?.substring(0, 100) || 'N/A',
        scripts: Array.from(document.scripts).map(s => s.src.substring(0, 120) || s.id).join(', '),
    })""")
    print(f"\n=== Page state ===", flush=True)
    print(f"  {json.dumps(state)[:800]}", flush=True)
    
    page.screenshot(path="standalone_enforcement.png")
    
    # NOW let's try calling the enforcement's postMessage API to give it a session
    print("\n[2] Trying to interact with enforcement...", flush=True)
    
    # Check if funCaptcha exists and what methods are available
    api_check = page.evaluate("""() => {
        if (window.funCaptcha) {
            const methods = Object.getOwnPropertyNames(Object.getPrototypeOf(window.funCaptcha));
            const ownMethods = Object.getOwnPropertyNames(window.funCaptcha);
            return {prototypeMethods: methods, ownMethods: ownMethods};
        }
        const winKeys = Object.keys(window).filter(k => k.toLowerCase().includes('captcha') || k.toLowerCase().includes('funcap') || k.includes('Fun'));
        return {funCaptcha: !!window.funCaptcha, similarKeys: winKeys};
    }""")
    print(f"  API check: {json.dumps(api_check)[:400]}", flush=True)
    
    time.sleep(5)
    browser.close()
