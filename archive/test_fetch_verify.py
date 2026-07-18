"""Solve puzzle via Python with proper error handling and logging."""
import os, time, json, re
os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

def solve_pow(N_str, A, T):
    N = int(N_str)
    val = A % N
    for i in range(T):
        val = (val * val) % N
    return val

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    puzzle_data = [None]
    session_id = [None]
    challenge_data = {"id": None, "type": None, "csrf": None}
    
    def on_resp(resp):
        url = resp.url
        if "/v2/login" in url and resp.status == 403:
            h = resp.headers
            challenge_data["id"] = h.get("rblx-challenge-id", "")
            challenge_data["type"] = h.get("rblx-challenge-type", "")
            challenge_data["csrf"] = h.get("x-csrf-token", "")
            print(f"[CHALLENGE] {challenge_data['id']}", flush=True)
    page.on("response", on_resp)
    def on_puzzle_resp(resp):
        url = resp.url
        if "pow-puzzle" not in url or resp.request.method != "GET":
            return
        if "/verify" in url:
            return
        
        m = re.search(r'sessionID=([^&]+)', url)
        if m:
            session_id[0] = m.group(1)
        
        try:
            data = resp.json()
            puzzle_data[0] = data
            artifacts = json.loads(data.get("artifacts", "{}"))
            print(f"[PUZZLE OK] T={artifacts.get('T')} N={str(artifacts.get('N','?'))[:30]}...", flush=True)
        except Exception as e:
            print(f"[PUZZLE PARSE ERR] {e}", flush=True)
            # Try text instead
            try:
                text = resp.text()[:200]
                print(f"[PUZZLE TEXT] {text}", flush=True)
            except Exception as e2:
                print(f"[PUZZLE TEXT ERR] {e2}", flush=True)
    
    page.on("response", on_puzzle_resp)
    
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
    while time.time() - start < 90:
        time.sleep(2)
        if puzzle_data[0] and session_id[0]:
            print(f"[GOT DATA at {time.time()-start:.0f}s]", flush=True)
            break
        if time.time() - start > 20:
            print(f"  [{time.time()-start:.0f}s] puzzle={'yes' if puzzle_data[0] else 'no'} sid={'yes' if session_id[0] else 'no'} cid={'yes' if challenge_data['id'] else 'no'}", flush=True)
    
    elapsed = time.time() - start
    print(f"[WAIT] {elapsed:.0f}s puzzle={'yes' if puzzle_data[0] else 'no'} sid={'yes' if session_id[0] else 'no'} cid={'yes' if challenge_data['id'] else 'no'}", flush=True)
    
    if not puzzle_data[0]:
        print("Abort: no puzzle data", flush=True)
        browser.close()
        exit()
    
    artifacts = json.loads(puzzle_data[0].get("artifacts", "{}"))
    answer = solve_pow(artifacts["N"], artifacts["A"], artifacts["T"])
    print(f"[SOLVED] answer={str(answer)[:20]}...", flush=True)
    
    # Verify via browser fetch
    verify_code = f"""
    (async () => {{
        try {{
            const r = await fetch('https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle/{session_id[0]}/verify', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{"answer": "{answer}"}})
            }});
            const text = await r.text();
            return JSON.parse(text);
        }} catch(e) {{
            return {{error: e.message}};
        }}
    }})()
    """
    verify_result = page.evaluate(verify_code)
    print(f"[VERIFY] {json.dumps(verify_result)[:200]}", flush=True)
    
    token = None
    if isinstance(verify_result, dict) and verify_result.get("answerCorrect") and verify_result.get("redemptionToken"):
        token = verify_result["redemptionToken"]
        print(f"[TOKEN] {token[:30]}...", flush=True)
    elif isinstance(verify_result, dict) and verify_result.get("error"):
        print(f"[VERIFY ERROR] {verify_result['error']}", flush=True)
    
    if not token:
        print("No token", flush=True)
        browser.close()
        exit()
    
    # Try /challenge/v1/continue
    body_data = {"ctype":"Username","username":"testuser123","password":"TestPassword123!"}
    
    continue_code = f"""
    (async () => {{
        try {{
            const r = await fetch('https://apis.roblox.com/challenge/v1/continue?urlLocale=en_us', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{
                    challengeId: '{challenge_data["id"]}',
                    redemptionToken: '{token}',
                    challengeType: '{challenge_data["type"]}'
                }})
            }});
            return {{status: r.status, text: await r.text()}};
        }} catch(e) {{
            return {{error: e.message}};
        }}
    }})()
    """
    continue_result = page.evaluate(continue_code)
    print(f"[CONTINUE] {json.dumps(continue_result)[:200]}", flush=True)
    
    # Retry login via browser fetch with challenge headers
    retry_code = f"""
    (async () => {{
        try {{
            const r = await fetch('https://auth.roblox.com/v2/login?urlLocale=en_us', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json;charset=UTF-8',
                    'X-CSRF-TOKEN': '{challenge_data["csrf"]}',
                    'rblx-challenge-id': '{challenge_data["id"]}',
                    'rblx-challenge-type': '{challenge_data["type"]}',
                    'rblx-challenge-redemption-token': '{token}',
                    'Origin': 'https://www.roblox.com'
                }},
                body: JSON.stringify({json.dumps(body_data)})
            }});
            return {{
                status: r.status,
                text: await r.text(),
                headers: Object.fromEntries([...r.headers])
            }};
        }} catch(e) {{
            return {{error: e.message}};
        }}
    }})()
    """
    retry_result = page.evaluate(retry_code)
    print(f"[RETRY] {retry_result.get('status', '?')} {retry_result.get('text', '')[:300]}", flush=True)
    
    headers = retry_result.get("headers", {})
    set_cookie = headers.get("set-cookie", "") or headers.get("Set-Cookie", "")
    if ".ROBLOSECURITY" in set_cookie:
        print(f"[SUCCESS!] {set_cookie[:100]}...", flush=True)
    
    print("\n=== FINAL COOKIES ===", flush=True)
    cookies = ctx.cookies()
    rs = [c for c in cookies if c["name"] == ".ROBLOSECURITY"]
    print(f"ROBLOSECURITY: {len(rs)}", flush=True)
    
    browser.close()
