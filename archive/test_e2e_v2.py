"""
E2E: stay on login page, open solver in NEW TAB, solve, come back, login.
"""
import asyncio, websockets, json, http.client, subprocess, time, shutil, os, threading, base64, glob, random
from http.server import HTTPServer, SimpleHTTPRequestHandler

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9252
HTML_PORT = 8098
FRESH_DIR = os.path.abspath(f"chrome_e2e_v2_{random.randint(10000,99999)}")
USER = "CheatingHitmanner"
PASS = "LolKekZek228"

async def main():
    for d in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_e2e_v2_*")):
        try: shutil.rmtree(d)
        except: pass

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    httpd = HTTPServer(("", HTML_PORT), SimpleHTTPRequestHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print(f"HTTP server on :{HTML_PORT}")

    proc = subprocess.Popen([
        CHROME, f"--user-data-dir={FRESH_DIR}",
        "--no-first-run", "--no-default-browser-check",
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-allow-origins=*",
        "--window-size=1400,1000",
        "--new-window", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Connect to first tab
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
    captcha_blob = None; captcha_token = None

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

    # ---------- STEP 1: Trigger captcha on login page ----------
    print("=== STEP 1: Trigger captcha ===")
    await cmd("Page.navigate", {"url": "https://www.roblox.com/login"})
    for i in range(60):
        await asyncio.sleep(1)
        ready = await cmd("Runtime.evaluate", {"expression": "!!document.querySelector('#login-button')"})
        if (ready or {}).get("result", {}).get("value"):
            print(f"  Page ready at ~{i}s"); break
    else:
        print("  Page didn't load after 60s"); return

    # Fill and click login
    await cmd("Runtime.evaluate", {
        "expression": f"""(() => {{
            const u = document.querySelector('#login-username');
            const p = document.querySelector('#login-password');
            if (!u || !p) return;
            Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(u, '{USER}');
            u.dispatchEvent(new Event('input', {{bubbles: true}}));
            Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(p, '{PASS}');
            p.dispatchEvent(new Event('input', {{bubbles: true}}));
        }})()"""
    })
    await asyncio.sleep(0.3)
    await cmd("Runtime.evaluate", {"expression": "document.querySelector('#login-button')?.click()"})

    # Capture blob from challenge/v1/continue and v2/login 403
    async def on_response(params):
        nonlocal captcha_blob
        resp = params.get("response", {})
        url = resp.get("url", "")
        if "v2/login" in url and resp.get("status") == 403:
            req_id = params.get("requestId")
            # Log headers that might contain challenge data
            headers = resp.get("headers", {})
            for k, v in headers.items():
                if "challenge" in k.lower() or "captcha" in k.lower() or "rblx" in k.lower():
                    # Decode base64 metadata
                    if "metadata" in k.lower():
                        try:
                            padded = v + "=" * (4 - len(v) % 4) if len(v) % 4 else v
                            decoded = base64.b64decode(padded).decode("utf-8")
                            print(f"  → {k}: {json.dumps(json.loads(decoded), indent=6)}")
                        except:
                            print(f"  → {k}: {v[:200]}")
                    else:
                        print(f"  → {k}: {v[:200]}")
            try:
                body_resp = await cmd("Network.getResponseBody", {"requestId": req_id})
                if body_resp:
                    body = body_resp.get("body", "")
                    if body:
                        print(f"  → body: {body[:300]}")
            except Exception as e:
                print(f"  → body error: {e}")
        if "/challenge/v1/continue" in url and resp.get("status") == 200:
            req_id = params.get("requestId")
            try:
                body_resp = await cmd("Network.getResponseBody", {"requestId": req_id})
                if body_resp:
                    body = body_resp.get("body", "")
                    if body:
                        j = json.loads(body)
                        blob = j.get("dataExchangeBlob", "")
                        if not blob or len(blob) < 50:
                            cm = j.get("challengeMetadata", "")
                            if isinstance(cm, str) and cm.startswith("{"):
                                blob = json.loads(cm).get("dataExchangeBlob", "")
                            elif isinstance(cm, dict):
                                blob = cm.get("dataExchangeBlob", "")
                        if len(blob) > 50:
                            captcha_blob = blob
                            print(f"  → BLOB: {len(blob)} chars ✓")
            except Exception as e:
                print(f"  → getResponseBody error: {e}")
    await on_event("Network.responseReceived", on_response)

    for i in range(60):
        await asyncio.sleep(1)
        if captcha_blob:
            print(f"  Blob captured at ~{i}s"); break
    else:
        print("  No captcha"); await cmd("Page.captureScreenshot", {"format": "png"}); return

    # Wait for captcha token and PoW
    print("\n=== STEP 2: Inject token and let page retry ===")
    
    # Create new tab for solver (still needed for suppressed solve)
    target_result = await cmd("Target.createTarget", {
        "url": f"http://localhost:{HTML_PORT}/hundle/captcha_solver.html",
        "newWindow": False
    })
    solver_target_id = (target_result or {}).get("targetId", "")
    print(f"  Solver tab: {solver_target_id}")
    
    # Connect to solver tab
    for i in range(10):
        try:
            conn2 = http.client.HTTPConnection("localhost", CDP_PORT, timeout=3)
            conn2.request("GET", "/json")
            tabs2 = json.loads(conn2.getresponse().read()); conn2.close()
            for t in tabs2:
                if t.get("id") == solver_target_id:
                    solver_ws = t["webSocketDebuggerUrl"]
                    break
            if solver_ws: break
        except:
            pass
        await asyncio.sleep(1)
    
    if not solver_ws:
        print("  Could not connect to solver tab"); return
    
    print(f"  Connected to solver tab")
    
    # We can't easily switch CDP sessions. Instead, use Target.attachToTarget
    # to get a new session and use it for Runtime.evaluate in the solver tab
    
    # Actually, easier: just use the same session but navigate the solver tab
    # via a second websocket connection
    
    solver_cdp = await websockets.connect(solver_ws, max_size=None)
    solver_msg_id = 0; solver_pending = {}
    
    async def solver_cmd(method, params=None, timeout_s=20):
        nonlocal solver_msg_id; solver_msg_id += 1
        future = asyncio.get_event_loop().create_future()
        solver_pending[solver_msg_id] = future
        await solver_cdp.send(json.dumps({"id": solver_msg_id, "method": method, "params": params or {}}))
        try: return await asyncio.wait_for(future, timeout=timeout_s)
        except: solver_pending.pop(solver_msg_id, None); return None
    
    async def solver_reader():
        async for raw in solver_cdp:
            data = json.loads(raw)
            rid = data.get("id")
            if rid in solver_pending:
                solver_pending[rid].set_result(data.get("result", {}))
                del solver_pending[rid]
    asyncio.create_task(solver_reader())
    
    await solver_cmd("Page.enable")
    await solver_cmd("Runtime.enable")
    
    # Wait for SDK to be ready
    for i in range(15):
        await asyncio.sleep(1)
        pi_check = await solver_cmd("Runtime.evaluate", {"expression": "typeof _pi !== 'undefined' && _pi !== null"})
        pi_ready = (pi_check or {}).get("result", {}).get("value", False)
        if pi_ready:
            print(f"  SDK ready at ~{i}s")
            break
    else:
        print("  SDK not loaded, continuing anyway...")
    
    # Inject blob into solver and click load
    await solver_cmd("Runtime.evaluate", {
        "expression": f"""(() => {{
            const ta = document.getElementById('blob');
            if (ta) {{
                Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set.call(ta, {json.dumps(captcha_blob)});
                ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }}
        }})()"""
    })
    await asyncio.sleep(0.5)
    
    # Click load (no API calls needed - suppressed mode)
    await solver_cmd("Runtime.evaluate", {"expression": "document.querySelector('button')?.click()"})
    await asyncio.sleep(1)
    
    # Check status after click
    status_r = await solver_cmd("Runtime.evaluate", {"expression": "document.querySelector('#status')?.textContent || ''"})
    st = (status_r or {}).get("result", {}).get("value", "")
    print(f"  Solver status: {st[:120]}")
    
    tok_r = await solver_cmd("Runtime.evaluate", {"expression": "document.querySelector('#token-field')?.textContent || ''"})
    tok = (tok_r or {}).get("result", {}).get("value", "")
    if tok:
        print(f"  Token: {tok[:80]}...")
        captcha_token = tok
    else:
        for i in range(30):
            await asyncio.sleep(1)
            token_r = await solver_cmd("Runtime.evaluate", {"expression": "document.querySelector('#token-field')?.textContent || ''"})
            token = (token_r or {}).get("result", {}).get("value", "")
            if token:
                captcha_token = token
                print(f"  ✅ Token at ~{i}s: {token[:80]}...")
                break
            if i % 5 == 0:
                s2 = await solver_cmd("Runtime.evaluate", {"expression": "document.querySelector('#status')?.textContent || ''"})
                st2 = (s2 or {}).get("result", {}).get("value", "")
                print(f"  [{i}s] {st2[:80]}")
        else:
            print("  No token after 30s")
    
    if not captcha_token:
        print("  No token obtained"); return
    
    # Close solver connection and tab
    await solver_cdp.close()
    await cmd("Target.closeTarget", {"targetId": solver_target_id})
    
    # ---------- STEP 3: Click login again on original page ----------
    print("\n=== STEP 3: Click login button (page retries with PoW) ===")
    
    # Activate original tab
    tabs_r = await cmd("Target.getTargets")
    if tabs_r:
        for t in tabs_r.get("targetInfos", []):
            if t.get("type") == "page" and t.get("targetId") != solver_target_id:
                await cmd("Target.activateTarget", {"targetId": t["targetId"]})
                break
    await asyncio.sleep(1)
    
    url_r = await cmd("Runtime.evaluate", {"expression": "location.href"})
    print(f"  URL: {(url_r or {}).get('result',{}).get('value','')[:60]}")
    
    # Click login button
    btn_r = await cmd("Runtime.evaluate", {"expression": "!!document.querySelector('#login-button')"})
    has_btn = (btn_r or {}).get("result", {}).get("value", False)
    print(f"  Login button: {has_btn}")
    
    if has_btn:
        await cmd("Runtime.evaluate", {"expression": "document.querySelector('#login-button')?.click()"})
        print("  Clicked login")
        for i in range(30):
            await asyncio.sleep(1)
            url_r2 = await cmd("Runtime.evaluate", {"expression": "location.href"})
            url2 = (url_r2 or {}).get("result", {}).get("value", "")
            if "home" in url2.lower():
                print(f"  ✅ Home at ~{i}s!")
                break
            err_r = await cmd("Runtime.evaluate", {"expression": "(document.querySelector('.login-error')||{}).textContent||''"})
            err = (err_r or {}).get("result", {}).get("value", "")
            if i % 5 == 0:
                print(f"  [{i}s] url={url2[:50]} err='{err[:30]}'")
    ck_r = await cmd("Network.getAllCookies")
    rob_cookies = [c for c in (ck_r or {}).get("cookies", []) if c.get('name') == '.ROBLOSECURITY']
    if rob_cookies:
        tok = rob_cookies[0].get('value', '')
        print(f"\n✅ .ROBLOSECURITY obtained! {tok[:40]}...")
    else:
        print("\n❌ No .ROBLOSECURITY")
    
    await cdp.close()
    proc.kill()
    httpd.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
