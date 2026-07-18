"""
Quick test: open Chrome, login to Roblox with captcha Fetch interception.
If captcha appears, opens captcha_solver.html and takes a screenshot.
"""
import asyncio, websockets, json, http.client, subprocess, os, time, shutil, threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9231
HTML_PORT = 8091
FRESH_DIR = os.path.abspath("chrome_captcha_test")
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

async def test():
    # Clean profile
    if os.path.exists(FRESH_DIR):
        shutil.rmtree(FRESH_DIR)

    # Start HTTP server
    os.chdir(PROJECT_DIR)
    httpd = HTTPServer(("", HTML_PORT), SimpleHTTPRequestHandler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    print(f"HTTP server on :{HTML_PORT}")

    # Start Chrome
    proc = subprocess.Popen([
        CHROME, f"--user-data-dir={FRESH_DIR}",
        "--no-first-run", "--no-default-browser-check",
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-allow-origins=*",
        "--window-size=1200,800",
        "--disable-extensions", "--disable-sync",
        "--disable-background-networking", "--mute-audio",
        "--new-window", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for i in range(30):
        try:
            conn = http.client.HTTPConnection("localhost", CDP_PORT, timeout=3)
            conn.request("GET", "/json")
            resp = conn.getresponse()
            tabs = json.loads(resp.read())
            conn.close()
            for t in tabs:
                if t.get("url", "").startswith("about:") or t.get("url", "") == "":
                    cdp_url = t["webSocketDebuggerUrl"]
                    break
            else:
                if tabs: cdp_url = tabs[0]["webSocketDebuggerUrl"]
                else: continue
            break
        except:
            pass
        time.sleep(1)
    else:
        print("FAIL: Chrome not starting"); proc.kill(); httpd.shutdown(); return
    print(f"CDP connected")

    cdp = await websockets.connect(cdp_url, max_size=None)
    msg_id = 0; pending = {}; event_handlers = {}

    async def cmd(method, params=None, timeout_s=15):
        nonlocal msg_id
        msg_id += 1
        future = asyncio.get_event_loop().create_future()
        msg = {"id": msg_id, "method": method, "params": params or {}}
        pending[msg_id] = future
        await cdp.send(json.dumps(msg))
        try:
            return await asyncio.wait_for(future, timeout=timeout_s)
        except asyncio.TimeoutError:
            pending.pop(msg_id, None)
            return None

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

    reader_task = asyncio.create_task(reader())

    await cmd("Page.enable")
    await cmd("Network.enable")

    # Fetch interception
    await cmd("Fetch.enable", {
        "patterns": [{"urlPattern": "*arkoselabs.com*", "requestStage": "Request"}]
    })
    print("Fetch interception active")

    async def on_fetch(params):
        try:
            req_id = params.get("requestId")
            req = params.get("request", {})
            url = req.get("url", "")
            headers = req.get("headers", [])
            if isinstance(headers, dict):
                headers = [{"name": k, "value": v} for k, v in headers.items()]

            if "arkoselabs.com" in url and ("/fc/" in url or "/gt2/" in url or "/gc/" in url or "/gfct/" in url or "/ca/" in url):
                new_headers = []
                for h in headers:
                    name = h.get("name", "").lower()
                    if name == "origin":
                        new_headers.append({"name": "Origin", "value": "https://www.roblox.com"})
                    elif name == "referer":
                        new_headers.append({"name": "Referer", "value": "https://www.roblox.com/login"})
                    else:
                        new_headers.append(h)
                has_origin = any(h.get("name", "").lower() == "origin" for h in new_headers)
                has_referer = any(h.get("name", "").lower() == "referer" for h in new_headers)
                if not has_origin:
                    new_headers.append({"name": "Origin", "value": "https://www.roblox.com"})
                if not has_referer:
                    new_headers.append({"name": "Referer", "value": "https://www.roblox.com/login"})
                await cmd("Fetch.continueRequest", {"requestId": req_id, "headers": new_headers})
            else:
                await cmd("Fetch.continueRequest", {"requestId": req_id})
        except:
            try:
                await cmd("Fetch.continueRequest", {"requestId": params.get("requestId")})
            except:
                pass

    await on_event("Fetch.requestPaused", on_fetch)

    # Navigate to Roblox login
    print("Navigating to roblox.com/login...")
    await cmd("Page.navigate", {"url": "https://www.roblox.com/login"})
    await asyncio.sleep(4)

    # Fill credentials
    print("Filling credentials...")
    creds = {"username": "CheatingHitmanner", "password": "LolKekZek228"}
    for field, val in [("username", creds["username"]), ("password", creds["password"])]:
        await cmd("Runtime.evaluate", {
            "expression": f"""(() => {{
                const el = document.querySelector('input[name="{field}"]');
                if (!el) return;
                el.focus(); el.select();
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(el, '');
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                setter.call(el, {json.dumps(val)});
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }})()"""
        })
        await asyncio.sleep(0.2)

    # Monitor auth API responses
    auth_responses = []

    async def on_auth_response(params):
        resp = params.get("response", {})
        url = resp.get("url", "")
        if "auth.roblox.com" in url or "apis.roblox.com/challenge" in url:
            auth_responses.append({
                "url": url,
                "status": resp.get("status"),
                "headers": dict(resp.get("headers", {})),
            })

    await on_event("Network.responseReceived", on_auth_response)

    # Click login using proper selector
    print("Clicking login...")
    btn = await cmd("Runtime.evaluate", {
        "expression": """(() => {
            const sels = ['#login-button', 'button[type="submit"]', '.login-button', 'form button', '[data-testid="login-button"]'];
            for (const sel of sels) {
                const b = document.querySelector(sel);
                if (b) {
                    const r = b.getBoundingClientRect();
                    return JSON.stringify({x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2), sel});
                }
            }
            return 'none';
        })()"""
    })
    btn_val = (btn or {}).get("result", {}).get("value", "")
    if btn_val and btn_val != "none":
        pos = json.loads(btn_val)
        print(f"  Clicking at ({pos['x']}, {pos['y']}) using {pos.get('sel','?')}")
        await cmd("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": pos["x"], "y": pos["y"], "button": "left", "clickCount": 1
        })
        await asyncio.sleep(0.05)
        await cmd("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": pos["x"], "y": pos["y"], "button": "left", "clickCount": 1
        })
    else:
        print("  No button found, using JS click")
        await cmd("Runtime.evaluate", {
            "expression": """(() => {
                const sels = ['#login-button', 'button[type="submit"]', '.login-button', 'form button'];
                for (const s of sels) {
                    const b = document.querySelector(s);
                    if (b) { b.click(); return 'clicked'; }
                }
                return 'no button';
            })()"""
        })

    # Wait for captcha or redirect
    captcha_detected = False
    blob_saved = None
    for i in range(120):  # 60 seconds
        await asyncio.sleep(0.5)

        # Check if captcha appeared
        captcha_elem = await cmd("Runtime.evaluate", {
            "expression": "!!document.querySelector('iframe[src*=arkose], iframe[src*=funcaptcha]') ? 'yes' : 'no'"
        })
        has_captcha = (captcha_elem or {}).get("result", {}).get("value", "") == "yes"

        url_r = await cmd("Runtime.evaluate", {"expression": "window.location.href"})
        url = (url_r or {}).get("result", {}).get("value", "") or ""

        # Check for cookie (login success)
        ck_resp = await cmd("Network.getAllCookies")
        for c in (ck_resp or {}).get("cookies", []):
            if c["name"] == ".ROBLOSECURITY":
                print(f"\n✅ LOGIN SUCCESS! Cookie: {c['value'][:50]}...")
                # Screenshot
                ss = await cmd("Page.captureScreenshot", {"format": "png"})
                if ss:
                    import base64 as b64
                    with open("test_success.png", "wb") as f:
                        f.write(b64.b64decode(ss.get("data", "")))
                    print("Screenshot: test_success.png")
                reader_task.cancel(); await cdp.close(); proc.kill(); httpd.shutdown()
                return

        if has_captcha and not captcha_detected:
            captcha_detected = True
            print("\n🔵 CAPTCHA DETECTED!")
            # Take screenshot of login page with captcha
            ss = await cmd("Page.captureScreenshot", {"format": "png"})
            if ss:
                import base64 as b64
                with open("test_captcha_page.png", "wb") as f:
                    f.write(b64.b64decode(ss.get("data", "")))
                print("Screenshot: test_captcha_page.png (login page with captcha iframe)")

            # Now open captcha_solver.html in same tab
            solver_url = f"http://localhost:{HTML_PORT}/hundle/captcha_solver.html"
            print(f"Opening captcha solver: {solver_url}")
            await cmd("Page.navigate", {"url": solver_url})
            await asyncio.sleep(3)

            # Inject blob (read from a test blob if available)
            blob_path = os.path.join(PROJECT_DIR, "last_captcha_blob.txt")
            if os.path.exists(blob_path):
                with open(blob_path, "r") as f:
                    blob = f.read().strip()
                await cmd("Runtime.evaluate", {
                    "expression": f"""(() => {{
                        const ta = document.getElementById('blob');
                        if (ta) {{
                            Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set.call(ta, {json.dumps(blob)});
                            ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }}
                    }})()"""
                })
                print("Blob injected into solver page")

            # Click load button
            await cmd("Runtime.evaluate", {
                "expression": """document.querySelector('button') && document.querySelector('button').click()"""
            })
            await asyncio.sleep(4)

            # Screenshot of solver
            ss2 = await cmd("Page.captureScreenshot", {"format": "png"})
            if ss2:
                import base64 as b64
                with open("test_captcha_solver.png", "wb") as f:
                    f.write(b64.b64decode(ss2.get("data", "")))
                print("Screenshot: test_captcha_solver.png (solver page)")
            
            # Check status
            status = await cmd("Runtime.evaluate", {
                "expression": "document.querySelector('#status') ? document.querySelector('#status').textContent : 'no status'"
            })
            st = (status or {}).get("result", {}).get("value", "")
            print(f"Solver status: {st}")

            # Check captcha-box HTML
            box = await cmd("Runtime.evaluate", {
                "expression": "document.querySelector('#captcha-box') ? document.querySelector('#captcha-box').innerHTML.substring(0, 500) : ''"
            })
            bx = (box or {}).get("result", {}).get("value", "")
            if bx:
                print(f"Captcha box has content: {bx[:100]}...")
            else:
                print("Captcha box empty — widget loaded but no challenge rendered")

            print("\n✅ HTML loads, captcha widget is ready.")
            print("Open test_captcha_solver.png to see the result.")
            break

        if i % 20 == 0:
            print(f"  Waiting... ({i//2}s)")

    else:
        print("No captcha detected in 60s")
        # Debug: check current state
        url_r = await cmd("Runtime.evaluate", {"expression": "window.location.href"})
        print(f"  URL: {(url_r or {}).get('result', {}).get('value', 'N/A')}")
        body_r = await cmd("Runtime.evaluate", {"expression": "document.body ? document.body.innerText.substring(0, 500) : 'no body'"})
        print(f"  Page text: {(body_r or {}).get('result', {}).get('value', 'N/A')[:200]}")
        ck_r = await cmd("Network.getAllCookies")
        cookies_list = (ck_r or {}).get('cookies', [])
        cookies = [c for c in cookies_list if c.get('name') == '.ROBLOSECURITY']
        print(f"  .ROBLOSECURITY cookie: {cookies[0].get('value','')[:40] if cookies else 'not found'}")
        ss = await cmd("Page.captureScreenshot", {"format": "png"})
        if ss:
            import base64 as b64
            with open("test_no_captcha.png", "wb") as f:
                f.write(b64.b64decode(ss.get("data", "")))
            print("  Screenshot: test_no_captcha.png")

    reader_task.cancel()
    await cdp.close()
    proc.kill()
    httpd.shutdown()

asyncio.run(test())
