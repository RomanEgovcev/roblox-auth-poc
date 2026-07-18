"""Capture puzzle and continue responses properly."""
import os, time, json
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)
    
    # Mouse interaction
    page.evaluate("""() => {
        for (let i = 0; i < 30; i++)
            document.dispatchEvent(new MouseEvent('mousemove', {clientX: 100+i*20, clientY: 200+i*5, bubbles: true}));
        const u = document.querySelector('input[name="username"]');
        if (u) { u.focus(); u.dispatchEvent(new FocusEvent('focus', {bubbles: true})); }
    }""")
    time.sleep(0.5)
    page.fill('input[name="username"]', 'testuser123')
    time.sleep(0.3)
    page.fill('input[name="password"]', 'TestPassword123!')
    time.sleep(0.5)
    page.evaluate("""() => {
        for (let i = 0; i < 15; i++)
            document.dispatchEvent(new MouseEvent('mousemove', {clientX: 400+i*15, clientY: 350+i*3, bubbles: true}));
    }""")
    time.sleep(0.3)
    
    t0 = time.time()
    
    # Step 1: Wait for puzzle GET
    print(f"Waiting for puzzle GET...", flush=True)
    with page.expect_response(
        lambda r: "pow-puzzle" in r.url and r.request.method == "GET" and "/verify" not in r.url,
        timeout=30000
    ) as p_info:
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
        
        puzzle_resp = p_info.value
    
    dt1 = time.time() - t0
    print(f"[t={dt1:.1f}s] Puzzle GET status={puzzle_resp.status}", flush=True)
    
    try:
        pj = puzzle_resp.json()
        session_id = pj.get("sessionID", "")
        artifacts = json.loads(pj.get("artifacts", "{}"))
        print(f"  sessionID={session_id[:30]}", flush=True)
        print(f"  T={artifacts.get('T')} N={str(artifacts.get('N',''))[:40]}", flush=True)
    except Exception as e:
        print(f"  Puzzle parse error: {e}", flush=True)
        try:
            body = puzzle_resp.body()
            print(f"  Raw body: {body[:300]}", flush=True)
        except:
            print(f"  Raw body also failed", flush=True)
    
    # Step 2: Wait for /challenge/v1/continue
    print(f"Waiting for /challenge/v1/continue...", flush=True)
    try:
        with page.expect_response(
            lambda r: "/challenge/v1/continue" in r.url and r.request.method == "POST",
            timeout=30000
        ) as c_info:
            pass
        
        continue_resp = c_info.value
        dt2 = time.time() - t0
        print(f"[t={dt2:.1f}s] /challenge/v1/continue status={continue_resp.status}", flush=True)
        try:
            cbody = continue_resp.body()
            print(f"  Body: {cbody[:600].decode('utf-8','replace')}", flush=True)
        except Exception as e:
            print(f"  Body error: {e}", flush=True)
    except Exception as e:
        print(f"  Continue wait error: {e}", flush=True)
    
    # Step 3: Wait for login retry (if it happens)
    print(f"Waiting for login retry...", flush=True)
    try:
        with page.expect_response(
            lambda r: "/v2/login" in r.url and r.request.method == "POST",
            timeout=20000
        ) as l_info:
            pass
        login_resp = l_info.value
        dt3 = time.time() - t0
        print(f"[t={dt3:.1f}s] Login retry! status={login_resp.status}", flush=True)
        try:
            lbody = login_resp.body()
            print(f"  Body: {lbody[:500].decode('utf-8','replace')}", flush=True)
        except:
            pass
    except Exception as e:
        print(f"  No login retry: {e}", flush=True)
    
    print(f"\nDone {time.time()-t0:.0f}s", flush=True)
    browser.close()
