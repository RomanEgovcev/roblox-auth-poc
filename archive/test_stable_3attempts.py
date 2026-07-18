"""Stable test with error-resistant handlers + retry login after challenge."""
import os, time, json
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    page = browser.new_page(bypass_csp=True)
    page.set_viewport_size({"width": 1280, "height": 900})
    
    challenge_data = {"attempts": 0, "verify_ok": False, "challenge_id": None}
    
    def on_resp(resp):
        try:
            url = resp.url
            if "/v2/login" in url:
                challenge_data["attempts"] += 1
                print(f"[LOGIN {resp.status}] #{challenge_data['attempts']}", flush=True)
                if resp.status == 403:
                    cid = resp.headers.get("rblx-challenge-id", "")
                    if cid:
                        challenge_data["challenge_id"] = cid
                        print(f"  CID={cid[:35]}...", flush=True)
        except: pass
    
    def on_req(req):
        try:
            url = req.url
            if "Challenge.js" in url or "Challenge.css" in url:
                print(f"[CHALLENGE_LOAD] {req.method} {url}", flush=True)
        except: pass
    
    page.on("response", on_resp)
    page.on("request", on_req)
    page.on("pageerror", lambda e: print(f"[PAGE_ERR] {e}", flush=True))
    
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
    print("Login trigger #1", flush=True)
    
    # Wait with checks every 5s
    start = time.time()
    for i in range(0, 8):  # 40 seconds
        time.sleep(5)
        print(f"  [{time.time()-start:.0f}s] attempts={challenge_data['attempts']} verify={challenge_data['verify_ok']} url={page.url.split('/')[-1]}", flush=True)
        
        # Check cookies
        cookies = page.context.cookies()
        rs = [c for c in cookies if c["name"] == ".ROBLOSECURITY"]
        if rs:
            print(f"\n[SUCCESS] After attempt #{challenge_data['attempts']}!", flush=True)
            print(f".ROBLOSECURITY={rs[0]['value'][:50]}...", flush=True)
            break
        
        # Check if we can see challenge-specific cookies changing
        px3 = [c for c in cookies if c["name"] == "_px3"]
        if px3:
            # _px3 changed since last check?
            pass
    
    # Second attempt - same page, same session
    print("\n--- Login trigger #2 ---", flush=True)
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
    
    time.sleep(15)
    
    # Third attempt if needed
    if not [c for c in page.context.cookies() if c["name"] == ".ROBLOSECURITY"]:
        print("\n--- Login trigger #3 ---", flush=True)
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
        time.sleep(15)
    
    print(f"\n{'='*50}", flush=True)
    cookies = page.context.cookies()
    rs = [c for c in cookies if c["name"] == ".ROBLOSECURITY"]
    px3 = [c for c in cookies if c["name"] == "_px3"]
    print(f"Attempts: {challenge_data['attempts']}", flush=True)
    print(f"ROBLOSECURITY: {len(rs)}", flush=True)
    print(f"_px3: {px3[0]['value'][:40] if px3 else 'missing'}...", flush=True)
    print(f"URL: {page.url}", flush=True)
    
    if rs:
        val = rs[0]["value"]
        print(f"COOKIE: {val[:50]}...", flush=True)
        import httpx
        r = httpx.Client(cookies={".ROBLOSECURITY": val})
        auth = r.get("https://users.roblox.com/v1/users/authenticated")
        print(f"AUTH: {auth.status_code} {auth.text[:200]}", flush=True)
    
    print(f"{'='*50}", flush=True)
    browser.close()
