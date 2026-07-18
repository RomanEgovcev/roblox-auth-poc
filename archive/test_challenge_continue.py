"""CSP bypass: intercept /challenge/v1/continue to see its response."""
import os, time, json
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

continue_resp_data = None

def on_resp(resp):
    global continue_resp_data
    url = resp.url
    if "/challenge/v1/continue" in url:
        try:
            body = resp.text()[:500]
            continue_resp_data = f"[CONTINUE RESP {resp.status}] {body}"
            print(continue_resp_data, flush=True)
        except:
            pass
    if any(x in url for x in ["/v2/login", "pow-puzzle", "worker", "verify"]):
        print(f"[RESP {resp.status}] {resp.request.method} {url}", flush=True)
    if "pow-puzzle" in url and resp.request.method == "POST":
        try:
            body = resp.text()[:300]
            print(f"[VERIFY] {body}", flush=True)
        except:
            pass

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page(bypass_csp=True)
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.on("response", on_resp)
    page.on("console", lambda m: print(f"[CONSOLE] {m.text[:300]}", flush=True) if any(x in m.text.lower() for x in ["evalerror", "worker", "challenge", "error", "captcha", "funcaptcha"]) else None)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    print("Page loaded", flush=True)
    
    page.fill('input[name="username"]', 'testuser123')
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(1)
    
    page.evaluate("""() => {
        const root = document.querySelector('#login-base') || document.body;
        const key = Object.keys(root).find(k => k.startsWith('__reactFiber'));
        if (!key) return;
        function walk(f, d) {
            if (!f || d > 20) return;
            if (f.memoizedProps && typeof f.memoizedProps.onFormSubmit === 'function') {
                f.memoizedProps.onFormSubmit();
                return;
            }
            if (f.child) walk(f.child, d+1);
            if (f.sibling) walk(f.sibling, d);
        }
        walk(root[key], 0);
    }""")
    print("Login triggered", flush=True)
    
    time.sleep(20)
    
    print(f"\n{'='*50}", flush=True)
    if continue_resp_data:
        print(continue_resp_data)
    else:
        print("No /challenge/v1/continue response captured")
    print(f"{'='*50}", flush=True)
    
    cookies = page.context.cookies()
    rs = [c for c in cookies if c["name"] == ".ROBLOSECURITY"]
    print(f"ROBLOSECURITY: {len(rs)}", flush=True)
    if not rs:
        names = [c["name"] + "=" + c["value"][:20] for c in cookies]
        print(f"Cookies: {names}", flush=True)
    
    browser.close()
