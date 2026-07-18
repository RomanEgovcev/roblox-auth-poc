"""Capture complete challenge flow with response bodies."""
import os, time, json
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    
    events = []
    
    def on_req(req):
        events.append((time.time(), "REQ", req.method, req.url[:150], req.post_data[:200] if req.post_data else ""))
    page.on("request", on_req)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    # Mouse interaction
    page.evaluate("""() => {
        for (let i = 0; i < 30; i++) {
            document.dispatchEvent(new MouseEvent('mousemove', {
                clientX: 100 + i * 20, clientY: 200 + i * 5, bubbles: true
            }));
        }
        const u = document.querySelector('input[name="username"]');
        if (u) { u.focus(); u.dispatchEvent(new FocusEvent('focus', {bubbles: true})); }
    }""")
    time.sleep(0.5)
    page.fill('input[name="username"]', 'testuser123')
    time.sleep(0.3)
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(0.5)
    
    page.evaluate("""() => {
        for (let i = 0; i < 15; i++) {
            document.dispatchEvent(new MouseEvent('mousemove', {
                clientX: 400 + i * 15, clientY: 350 + i * 3, bubbles: true
            }));
        }
    }""")
    time.sleep(0.3)
    
    page.evaluate("""() => {
        const root = document.querySelector('#login-base') || document.body;
        const key = Object.keys(root).find(k => k.startsWith('__reactFiber'));
        function walk(f, d) {
            if (!f || d > 20) return null;
            if (f.memoizedProps && typeof f.memoizedProps.onFormSubmit === 'function') {
                f.memoizedProps.onFormSubmit();
                return 'ok';
            }
            return walk(f.child, d+1) || walk(f.sibling, d);
        }
        return walk(root[key], 0);
    }""")
    t0 = time.time()
    print(f"[t=0] Submitted", flush=True)
    
    # Poll main thread to flush background prints
    while time.time() - t0 < 20:
        time.sleep(0.5)
        # Background thread prints are flushed when main thread prints
    
    print(f"\n=== Timeline ({len(events)} events) ===", flush=True)
    key_urls = ("/v2/login", "pow-puzzle", "challenge/v1", "continue", "px-cloud", "worker-resources", "account-security", "main.min")
    for ts, tp, method, url, body in events:
        dt = ts - t0
        if any(x in url for x in key_urls):
            print(f"[{dt:6.2f}s] {tp} {method} {url[:130]}", flush=True)
            if body:
                print(f"  body: {body[:150]}", flush=True)
    
    # Also capture response bodies for key URLs
    print(f"\n=== Response Capture ===", flush=True)
    resp_bodies = {}
    def on_resp_capture(resp):
        url = resp.url
        if any(x in url for x in ("pow-puzzle", "challenge/v1/continue")):
            dt = time.time() - t0
            try:
                b = resp.body()
                text = b[:2000].decode('utf-8', errors='replace')
                resp_bodies[url] = text
                print(f"[{dt:6.2f}s] RESP {resp.status} {url[:100]}", flush=True)
                print(f"  body: {text[:300]}", flush=True)
            except Exception as e:
                resp_bodies[url] = f"<err: {e}>"
                try:
                    t = resp.text()
                    resp_bodies[url] = t[:2000]
                    print(f"[{dt:6.2f}s] RESP (text) {resp.status} {url[:100]}", flush=True)
                    print(f"  body: {t[:300]}", flush=True)
                except Exception as e2:
                    print(f"[{dt:6.2f}s] RESP (err2) {resp.status} {url[:100]}: {e2}", flush=True)
    
    ctx.on("response", on_resp_capture)
    # Re-register since we missed the first responses
    time.sleep(15)
    
    print(f"\n=== Captured Response Bodies ===", flush=True)
    for url, body in resp_bodies.items():
        print(f"{url[:100]}: {body[:300]}", flush=True)
    
    browser.close()
