"""Monitor ALL requests to find where PX retry goes (or doesn't go)."""
import os, time
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

all_urls = set()
all_login = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page(bypass_csp=True)
    page.set_viewport_size({"width": 1280, "height": 900})
    
    def on_req(req):
        url = req.url
        all_urls.add(url)
        if "/v2/login" in url:
            all_login.append(("REQ", time.time(), url, req.headers))
            print(f"[REQ] {url}", flush=True)
    
    def on_resp(resp):
        url = resp.url
        if "/v2/login" in url:
            all_login.append(("RESP", time.time(), resp.status, url, dict(resp.headers)))
            print(f"[RESP {resp.status}] {url}", flush=True)
        if "pow-puzzle" in url and "verify" not in url:
            body = resp.text()[:500]
            if "answerCorrect" in body:
                print(f"[VERIFIED] {body[:200]}", flush=True)
    
    def on_console(msg):
        t = msg.text.lower()
        if any(x in t for x in ["error", "exception", "fail", "worker", "challenge", "resolve", "retry", "try"]):
            print(f"[CONSOLE] {msg.text[:250]}", flush=True)
    
    page.on("request", on_req)
    page.on("response", on_resp)
    page.on("console", on_console)
    page.on("pageerror", lambda e: print(f"[PAGE_ERR] {e}", flush=True))
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
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
    
    time.sleep(60)  # Wait 60s for retry
    
    # Check for px-cloud URLs
    px_urls = [u for u in all_urls if "px-cloud" in u or "px-cdn" in u or "perimeterx" in u]
    print(f"\n=== PX URLs ({len(px_urls)}) ===", flush=True)
    for u in px_urls:
        print(f"  {u}", flush=True)
    
    print(f"\n=== All /v2/login events ({len(all_login)}) ===", flush=True)
    for ev in all_login:
        print(f"  {ev}", flush=True)
    
    print(f"\n=== ALL UNIQUE urls ({len(all_urls)}) ===", flush=True)
    for u in sorted(all_urls):
        print(f"  {u}", flush=True)
    
    cookies = page.context.cookies()
    rs = [c for c in cookies if c["name"] == ".ROBLOSECURITY"]
    print(f"\n.ROBLOSECURITY: {len(rs)}", flush=True)
    if rs:
        print(f"VALUE: {rs[0]['value'][:50]}...", flush=True)
    
    browser.close()
