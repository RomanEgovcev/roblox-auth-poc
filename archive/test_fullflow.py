"""Full flow with response capture."""
import os, time, json
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    
    t0 = [None]
    request_bodies = {}
    response_bodies = {}
    
    def on_req(req):
        url = req.url
        if t0[0] is not None and any(x in url for x in ("/v2/login", "pow-puzzle", "challenge/v1", "continue")):
            dt = time.time() - t0[0]
            print(f"[{dt:5.2f}s] {req.method} {url[:120]}", flush=True)
            if req.post_data:
                request_bodies[url] = req.post_data
    
    def on_resp(resp):
        url = resp.url
        if t0[0] is not None and any(x in url for x in ("/v2/login", "pow-puzzle", "challenge/v1/continue")):
            dt = time.time() - t0[0]
            status = resp.status
            body_str = "<no body>"
            try:
                b = resp.body()
                body_str = b[:1000].decode('utf-8', errors='replace')
            except Exception as e:
                body_str = f"<err: {e}>"
                try:
                    t = resp.text()
                    body_str = t[:1000]
                except Exception as e2:
                    body_str = f"<err2: {e2}>"
            print(f"[RSP {dt:5.2f}s] {status} {url[:100]}", flush=True)
            print(f"  Body: {body_str}", flush=True)
            response_bodies[url] = body_str
    
    page.on("request", on_req)
    page.on("response", on_resp)
    
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
    t0[0] = time.time()
    print(f"[t=0] Submitted", flush=True)
    
    time.sleep(30)
    
    print(f"\nCaptured request bodies:")
    for url, body in request_bodies.items():
        if len(body) < 500:
            print(f"  {url[:80]}: {body}", flush=True)
    
    browser.close()
