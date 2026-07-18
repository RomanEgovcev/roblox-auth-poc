"""
End-to-end test: login → captcha → solve → login with token
"""
import asyncio, websockets, json, http.client, subprocess, time, shutil, os, threading, base64, glob, random
from http.server import HTTPServer, SimpleHTTPRequestHandler

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9243
HTML_PORT = 8096
FRESH_DIR = os.path.abspath(f"chrome_e2e_test_{random.randint(10000,99999)}")

async def main():
    # Clean up old Chrome dirs but ignore lock errors
    base = os.path.dirname(os.path.abspath(__file__))
    for d in glob.glob(os.path.join(base, "chrome_e2e_test_*")):
        try: shutil.rmtree(d)
        except: pass

    # HTTP server for solver
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    httpd = HTTPServer(("", HTML_PORT), SimpleHTTPRequestHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    proc = subprocess.Popen([
        CHROME, f"--user-data-dir={FRESH_DIR}",
        "--no-first-run", "--no-default-browser-check",
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-allow-origins=*",
        "--window-size=1200,900",
        "--new-window", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for i in range(30):
        try:
            conn = http.client.HTTPConnection("localhost", CDP_PORT, timeout=3)
            conn.request("GET", "/json")
            resp = conn.getresponse()
            tabs = json.loads(resp.read()); conn.close()
            for t in tabs:
                u = t.get("url", "")
                if u.startswith("about:") or u == "":
                    cdp_url = t["webSocketDebuggerUrl"]; break
            else:
                if tabs: cdp_url = tabs[0]["webSocketDebuggerUrl"]
                else: continue
            break
        except:
            time.sleep(1)
    else:
        print("FAIL"); proc.kill(); return

    cdp = await websockets.connect(cdp_url, max_size=None)
    msg_id = 0; pending = {}; event_handlers = {}

    async def cmd(method, params=None, timeout_s=20):
        nonlocal msg_id; msg_id += 1
        future = asyncio.get_event_loop().create_future()
        pending[msg_id] = future
        await cdp.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        try: return await asyncio.wait_for(future, timeout=timeout_s)
        except: pending.pop(msg_id, None); return None

    async def on_event(method, handler):
        event_handlers[method] = handler

    async def reader():
        async for raw in cdp:
            data = json.loads(raw)
            rid = data.get("id")
            if rid in pending:
                pending[rid].set_result(data.get("result", {}))
                del pending[rid]
            meth = data.get("method", "")
            if meth in event_handlers:
                asyncio.create_task(event_handlers[meth](data.get("params", {})))

    asyncio.create_task(reader())
    await cmd("Page.enable")
    await cmd("Network.enable")

    USER = "CheatingHitmanner"
    PASS = "LolKekZek228"
    captcha_blob = None
    captcha_token = None
    unified_captcha_id = None
    roblosecurity = None

    async def on_response(params):
        nonlocal captcha_blob, unified_captcha_id
        resp = params.get("response", {})
        url = resp.get("url", "")
        status = resp.get("status", 0)
        if "/challenge/v1/continue" in url and status == 200:
            req_id = params.get("requestId")
            print(f"  → Challenge reqId={req_id}, trying getResponseBody...")
            try:
                body_resp = await cmd("Network.getResponseBody", {"requestId": req_id})
                if body_resp:
                    body = body_resp.get("body", "")
                    if body:
                        j = json.loads(body)
                        if isinstance(j.get("unifiedCaptchaId"), str):
                            unified_captcha_id = j["unifiedCaptchaId"]
                        cm = j.get("challengeMetadata", "")
                        if isinstance(cm, str) and cm.startswith("{"):
                            try:
                                cm_data = json.loads(cm)
                                if not unified_captcha_id and isinstance(cm_data.get("unifiedCaptchaId"), str):
                                    unified_captcha_id = cm_data["unifiedCaptchaId"]
                            except:
                                pass
                        blob = None
                        if isinstance(j.get("dataExchangeBlob"), str):
                            blob = j["dataExchangeBlob"]
                        elif isinstance(j.get("challengeMetadata"), dict):
                            blob = j["challengeMetadata"].get("dataExchangeBlob", "")
                        elif isinstance(cm, str):
                            try:
                                cm_data = json.loads(cm)
                                blob = cm_data.get("dataExchangeBlob", "")
                            except:
                                blob = cm
                        if blob and len(blob) > 50:
                            captcha_blob = blob
                            print(f"  → BLOB: {len(blob)} chars ✓")
                            if unified_captcha_id:
                                print(f"  → unifiedCaptchaId: {unified_captcha_id}")
                        else:
                            print(f"  → No blob, keys={list(j.keys())}")
            except Exception as e:
                print(f"  → getResponseBody error: {type(e).__name__}: {e}")
    await on_event("Network.responseReceived", on_response)

    # STEP 1: Trigger captcha
    print("=== STEP 1: Trigger captcha ===")
    await cmd("Page.navigate", {"url": "https://www.roblox.com/login"})
    # Wait for page to fully render (VPN can take 15-20s)
    for i in range(15):
        await asyncio.sleep(2)
        ready = await cmd("Runtime.evaluate", {"expression": "!!document.querySelector('#login-button')"})
        if (ready or {}).get("result", {}).get("value"):
            print(f"  Page ready at ~{i*2}s")
            break
        url_r = await cmd("Runtime.evaluate", {"expression": "location.href"})
        url = (url_r or {}).get("result", {}).get("value", "")
        if i % 5 == 0:
            print(f"  Wait {i*2}s... url={url[:50]}")
    else:
        print("  Page didn't load fully")
    await cmd("Runtime.evaluate", {
        "expression": f"""(() => {{
            const u = document.querySelector('#login-username');
            const p = document.querySelector('#login-password');
            if (!u || !p) return 'no fields';
            Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(u, '{USER}');
            u.dispatchEvent(new Event('input', {{bubbles: true}}));
            Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(p, '{PASS}');
            p.dispatchEvent(new Event('input', {{bubbles: true}}));
            return 'filled';
        }})()"""
    })
    await asyncio.sleep(0.3)
    await cmd("Runtime.evaluate", {"expression": "document.querySelector('#login-button')?.click()"})

    for i in range(30):
        await asyncio.sleep(2)
        if captcha_blob:
            print(f"  Blob captured at ~{i*2}s")
            break
        # Check page-level blob capture
        blb_r = await cmd("Runtime.evaluate", {"expression": "window.__captchaBlob || ''"})
        blb = (blb_r or {}).get("result", {}).get("value", "")
        if blb and len(blb) > 50:
            captcha_blob = blb
            print(f"  Blob captured via page interception at ~{i*2}s ({len(blb)} chars)")
            break
        url_r = await cmd("Runtime.evaluate", {"expression": "location.href"})
        url = (url_r or {}).get("result", {}).get("value", "")
        if "home" in url:
            print(f"  → Already logged in (no captcha needed)")
            break
        err_r = await cmd("Runtime.evaluate", {"expression": "(document.querySelector('.login-error') || {}).textContent || ''"})
        err = (err_r or {}).get("result", {}).get("value", "")
        if i % 3 == 0:
            print(f"  [{i*2}s] url={url[:50]} err='{err[:30]}'")
    else:
        print("  No captcha after 60s")

    if not captcha_blob:
        print("No captcha blob, exiting")
        httpd.shutdown(); proc.kill(); await cdp.close()
        return

    # STEP 2: Solve captcha
    print("\n=== STEP 2: Solve captcha ===")
    print("  Solver HTML will open in the browser. Captcha solves automatically (suppressed).")
    
    solver_url = f"http://localhost:{HTML_PORT}/hundle/captcha_solver.html"
    print(f"  Navigating to solver: {solver_url}")
    await cmd("Page.navigate", {"url": solver_url})
    await asyncio.sleep(5)

    # Debug page state
    debug_r = await cmd("Runtime.evaluate", {
        "expression": """(() => {
            return JSON.stringify({
                status: (document.querySelector('#status') || {}).textContent || 'no-status',
                statusClass: (document.querySelector('#status') || {}).className || 'none',
                hasPi: typeof _pi !== 'undefined',
                hasBlobField: !!document.querySelector('#blob'),
                hasLoadBtn: !!document.querySelector('button'),
            });
        })()"""
    })
    print(f"  Solver state: {(debug_r or {}).get('result', {}).get('value', 'N/A')}")

    await cmd("Runtime.evaluate", {
        "expression": f"""(() => {{
            const ta = document.getElementById('blob');
            if (ta) {{
                Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set.call(ta, {json.dumps(captcha_blob)});
                ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }}
        }})()"""
    })
    await cmd("Runtime.evaluate", {"expression": "document.querySelector('button')?.click()"})

    # Debug status after click
    await asyncio.sleep(2)
    post_r = await cmd("Runtime.evaluate", {
        "expression": """(() => {
            return JSON.stringify({
                status: (document.querySelector('#status') || {}).textContent || 'none',
                statusClass: (document.querySelector('#status') || {}).className || 'none',
                captchaBoxHtml: (document.querySelector('#captcha-box') || {}).innerHTML?.substring(0, 100) || 'empty',
                hasToken: !!(document.querySelector('#token-field') || {}).textContent,
                blobValue: (document.querySelector('#blob') || {}).value?.substring(0, 30) || 'empty',
            });
        })()"""
    })
    print(f"  After click: {(post_r or {}).get('result', {}).get('value', 'N/A')}")
    # Print token directly
    tok_r = await cmd("Runtime.evaluate", {"expression": "(document.querySelector('#token-field') || {}).textContent || ''"})
    tok = (tok_r or {}).get("result", {}).get("value", "")
    print(f"  Token raw: '{tok[:80]}' (len={len(tok)})")

    # Wait for token (manual solve in browser)
    print("  ⏳ Solve captcha in the browser window now.")
    print("  After solving, the token will appear in the green field.")
    for i in range(120):
        await asyncio.sleep(1)
        token_r = await cmd("Runtime.evaluate", {"expression": "document.querySelector('#token-field')?.textContent || ''"})
        token = (token_r or {}).get("result", {}).get("value", "")
        if token:
            captcha_token = token
            print(f"  ✅ Token obtained at ~{i}s: {token[:80]}...")
            break
        if i % 10 == 0:
            status_r = await cmd("Runtime.evaluate", {"expression": "document.querySelector('#status')?.textContent || ''"})
            st = (status_r or {}).get("result", {}).get("value", "")
            print(f"  [{i}s] Status: {st[:60]}")
    else:
        print("  ⛔ No token after 120s")
        ss = await cmd("Page.captureScreenshot", {"format": "png"})
        if ss:
            with open("e2e_fail.png", "wb") as f:
                f.write(base64.b64decode(ss.get("data", "")))
        return

    # STEP 3: Login with captcha token
    print("\n=== STEP 3: Login with captcha token ===")
    if unified_captcha_id:
        print(f"  unifiedCaptchaId: {unified_captcha_id}")
    
    await cmd("Page.navigate", {"url": "https://www.roblox.com/login"})
    for i in range(10):
        await asyncio.sleep(1)
        ready = await cmd("Runtime.evaluate", {"expression": "!!document.querySelector('#login-username')"})
        if (ready or {}).get("result", {}).get("value"):
            print(f"  Page ready at ~{i}s")
            break
    
    # Test 1: token + unifiedCaptchaId + provider='Prove'
    print(f"\n  Test 1: token + unifiedCaptchaId")
    r = await cmd("Runtime.evaluate", {
        "awaitPromise": True,
        "expression": f"""(() => {{
            const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute('data-token') || '';
            const controller = new AbortController();
            const t = setTimeout(() => controller.abort(), 10000);
            return fetch('https://auth.roblox.com/v2/login', {{
                method: 'POST',
                credentials: 'include',
                signal: controller.signal,
                headers: {{'Content-Type': 'application/json', 'X-CSRF-TOKEN': csrf}},
                body: JSON.stringify({{
                    ctype: 'Username',
                    cvalue: '{USER}',
                    password: '{PASS}',
                    captchaToken: {json.dumps(captcha_token)},
                    captchaProvider: 'Prove',
                    unifiedCaptchaId: {json.dumps(unified_captcha_id or '')},
                }})
            }}).then(async r => {{
                clearTimeout(t);
                const body = await r.text();
                return JSON.stringify({{status: r.status, body: body.substring(0, 300)}});
            }}).catch(e => {{ clearTimeout(t); return 'error: ' + e.message; }});
        }})()"""
    })
    val = (r or {}).get("result", {}).get("value", "")
    print(f"    -> {val[:300]}")
    
    if '"status":200' not in val:
        # Test 2: POST to challenge/v1/continue with token first
        print(f"\n  Test 2: challenge/v1/continue with token")
        r = await cmd("Runtime.evaluate", {
            "awaitPromise": True,
            "expression": f"""(() => {{
                const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute('data-token') || '';
                const controller = new AbortController();
                const t = setTimeout(() => controller.abort(), 10000);
                return fetch('https://auth.roblox.com/v2/login', {{
                    method: 'POST',
                    credentials: 'include',
                    signal: controller.signal,
                    headers: {{'Content-Type': 'application/json', 'X-CSRF-TOKEN': csrf}},
                    body: JSON.stringify({{
                        ctype: 'Username',
                        cvalue: '{USER}',
                        password: '{PASS}',
                        captchaToken: {json.dumps(captcha_token)},
                        captchaProvider: 'Prove',
                    }})
                }}).then(async r => {{
                    clearTimeout(t);
                    const body = await r.text();
                    return JSON.stringify({{status: r.status, body: body.substring(0, 300)}});
                }}).catch(e => {{ clearTimeout(t); return 'error: ' + e.message; }});
            }})()"""
        })
        val = (r or {}).get("result", {}).get("value", "")
        print(f"    -> {val[:300]}")

    # Check cookies
    await asyncio.sleep(2)
    ck_r = await cmd("Network.getAllCookies")
    cookies_list = (ck_r or {}).get("cookies", [])
    roblosecurity_cookies = [c for c in cookies_list if c.get('name') == '.ROBLOSECURITY']
    if roblosecurity_cookies:
        tok = roblosecurity_cookies[0].get('value', '')
        print(f"\n✅ .ROBLOSECURITY obtained! {tok[:40]}...")
        with open("c2_credentials.txt", "a") as f:
            f.write(f"CheatingHitmanner:{PASS}:{tok}\n")
        print("  Saved to c2_credentials.txt")
    else:
        print("\n❌ No .ROBLOSECURITY cookie")

    await cdp.close()
    proc.kill()
    httpd.shutdown()

asyncio.run(main())
