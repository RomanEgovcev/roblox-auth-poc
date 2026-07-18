"""Monitor-based: capture challenge ID + token, retry externally."""
import os, time, json
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
import httpx

captured = {
    "challenge_id": None,
    "challenge_type": None,
    "csrf": None,
    "token": None,
}

def on_resp(resp):
    url = resp.url
    status = resp.status
    
    if "/v2/login" in url and status == 403:
        h = resp.headers
        captured["challenge_id"] = h.get("rblx-challenge-id", "")
        captured["challenge_type"] = h.get("rblx-challenge-type", "")
        captured["csrf"] = h.get("x-csrf-token", "")
        print(f"[403] cid={captured['challenge_id']} type={captured['challenge_type']}", flush=True)
    
    if "pow-puzzle" in url and "POST" in resp.request.method and status == 200:
        try:
            body = resp.text()
            data = json.loads(body)
            if data.get("answerCorrect") and data.get("redemptionToken"):
                captured["token"] = data["redemptionToken"]
                print(f"[TOKEN] {captured['token'][:30]}...", flush=True)
        except:
            pass

for attempt in range(10):
    print(f"\n=== Attempt {attempt+1} ===", flush=True)
    captured["token"] = None
    captured["challenge_id"] = None
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        page = browser.new_page(bypass_csp=True)
        page.set_viewport_size({"width": 1280, "height": 900})
        page.on("response", on_resp)
        
        page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        
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
        
        start = time.time()
        while time.time() - start < 40:
            time.sleep(0.5)
            if captured["token"]:
                break
        
        has_cf = any(c["name"] == "__cf_bm" for c in page.context.cookies())
        print(f"  token={'yes' if captured['token'] else 'no'} cid={'yes' if captured['challenge_id'] else 'no'} CF={has_cf}", flush=True)
        
        if captured["token"] and captured["challenge_id"]:
            print(f"\n[RETRYING] cid={captured['challenge_id']}", flush=True)
            
            browser_cookies = {c["name"]: c["value"] for c in page.context.cookies()}
            h = httpx.Client(cookies=browser_cookies, verify=True, timeout=60)
            
            login_url = "https://auth.roblox.com/v2/login?urlLocale=en_us"
            body_data = {"ctype":"Username","username":"testuser123","password":"TestPassword123!"}
            
            hdrs = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Content-Type": "application/json;charset=UTF-8",
                "Origin": "https://www.roblox.com",
                "X-CSRF-TOKEN": captured["csrf"],
            }
            
            # Step 1: /challenge/v1/continue
            continue_body = {
                "challengeId": captured["challenge_id"],
                "redemptionToken": captured["token"],
                "challengeType": captured["challenge_type"],
            }
            r4 = h.post("https://apis.roblox.com/challenge/v1/continue?urlLocale=en_us", 
                       json=continue_body, headers=hdrs, timeout=30)
            print(f"[CONTINUE] {r4.status_code} {r4.text[:150]}", flush=True)
            
            # Step 2: Retry login with challenge headers
            retry_hdrs = {**hdrs,
                "rblx-challenge-id": captured["challenge_id"],
                "rblx-challenge-type": captured["challenge_type"],
                "rblx-challenge-redemption-token": captured["token"],
                "X-CSRF-TOKEN": captured["csrf"],
            }
            r5 = h.post(login_url, json=body_data, headers=retry_hdrs, follow_redirects=False)
            print(f"[RETRY] {r5.status_code} {r5.text[:300]}", flush=True)
            
            if r5.status_code == 200:
                set_cookie = r5.headers.get("set-cookie", "")
                print(f"[200] {r5.text[:200]}", flush=True)
                if ".ROBLOSECURITY" in set_cookie:
                    print(f"[SUCCESS!] ROBLOSECURITY: {set_cookie[:100]}...", flush=True)
                    break
            elif r5.status_code == 403:
                print(f"[403] Still challenged", flush=True)
                # Try without /challenge/v1/continue
                r6 = h.post(login_url, json=body_data, headers=retry_hdrs, follow_redirects=False)
                print(f"[RETRY NO CONTINUE] {r6.status_code} {r6.text[:300]}", flush=True)
            
            break
        
        browser.close()
    time.sleep(2)
