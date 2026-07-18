"""
Full test: captcha_solver.html via localhost, Fetch intercept rewriting Origin.
"""
import asyncio, websockets, json, http.client, subprocess, os, time, shutil, threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9230
HTML_PORT = 8090
FRESH_DIR = os.path.abspath("chrome_fetch_test2")

async def test():
    if os.path.exists(FRESH_DIR):
        shutil.rmtree(FRESH_DIR)

    # Start Chrome
    proc = subprocess.Popen([
        CHROME, f"--user-data-dir={FRESH_DIR}",
        "--no-first-run", "--no-default-browser-check",
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-allow-origins=*", "--window-size=900,700",
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
                if tabs:
                    cdp_url = tabs[0]["webSocketDebuggerUrl"]
                else:
                    continue
            break
        except:
            pass
        time.sleep(1)
    else:
        print("FAIL: Chrome not starting"); proc.kill(); return
    print(f"CDP: {cdp_url}")

    # Start HTTP server
    httpd = HTTPServer(("", HTML_PORT), SimpleHTTPRequestHandler)
    http_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    http_thread.start()
    print(f"HTTP server on :{HTML_PORT}")

    # Connect CDP
    cdp = await websockets.connect(cdp_url, max_size=None)
    msg_id = 0; pending = {}; event_handlers = {}

    async def cmd(method, params=None, timeout_s=20):
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

    intercept_count = 0

    async def on_fetch(params):
        nonlocal intercept_count
        try:
            req_id = params.get("requestId")
            req = params.get("request", {})
            url = req.get("url", "")
            headers = req.get("headers", [])
            if isinstance(headers, dict):
                headers = [{"name": k, "value": v} for k, v in headers.items()]

            # Rewrite Origin/Referer for Arkose API calls
            rewrite = "arkoselabs.com" in url and ("/fc/" in url or "/gt2/" in url or "/gc/" in url or "/gfct/" in url or "/ca/" in url)
            if rewrite:
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
                intercept_count += 1
                r = await cmd("Fetch.continueRequest", {"requestId": req_id, "headers": new_headers})
                if r is None:
                    print(f"  [TIMEOUT] continueRequest for {url[:60]}")
            else:
                r = await cmd("Fetch.continueRequest", {"requestId": req_id})
                if r is None:
                    print(f"  [TIMEOUT] continueRequest for {url[:60]}")
        except Exception as e:
            print(f"  [ERROR] on_fetch: {e}")

    await on_event("Fetch.requestPaused", on_fetch)

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

    # Enable domains
    await cmd("Page.enable")
    await cmd("Fetch.enable", {
        "patterns": [{"urlPattern": "*arkoselabs.com*", "requestStage": "Request"}]
    })
    print("Fetch interception active for *arkoselabs.com*")

    # Load blob
    blob_path = os.path.abspath("last_captcha_blob.txt")
    with open(blob_path, "r", encoding="utf-8") as f:
        blob = f.read().strip()
    print(f"Blob: {blob[:50]}... ({len(blob)} chars)")

    # Navigate to captcha_solver.html
    print("DEBUG: Page.navigate...")
    r = await cmd("Page.navigate", {"url": f"http://localhost:{HTML_PORT}/hundle/captcha_solver.html"})
    print(f"DEBUG: Navigate result: {json.dumps(r)[:100] if r else 'None'}")
    print("Waiting 3s for page to load...")
    await asyncio.sleep(3)

    # Check page state
    print("DEBUG: Runtime.evaluate for URL...")
    url_r = await cmd("Runtime.evaluate", {"expression": "window.location.href"})
    print(f"DEBUG: URL = {(url_r or {}).get('result', {}).get('value', 'N/A')[:80]}")

    print("DEBUG: Injecting blob...")
    eval_r = await cmd("Runtime.evaluate", {
        "expression": f"""(() => {{
            const ta = document.getElementById('blob');
            if (ta) {{
                const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                setter.call(ta, {json.dumps(blob)});
                ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }}
            return 'blob done';
        }})()"""
    })
    val = (eval_r or {}).get("result", {}).get("value", "")
    print(f"DEBUG: Inject result = {val}")

    print("DEBUG: Clicking button...")
    click_r = await cmd("Runtime.evaluate", {
        "expression": """(() => {
            const btn = document.querySelector('button');
            if (btn) { btn.click(); return 'clicked'; }
            return 'no button';
        })()"""
    })
    val2 = (click_r or {}).get("result", {}).get("value", "")
    print(f"DEBUG: Click result = {val2}")

    print("Waiting for captcha to load (30s)...")

    # Poll for status/token
    for i in range(60):  # 30 seconds
        await asyncio.sleep(0.5)

        status = await cmd("Runtime.evaluate", {
            "expression": "document.querySelector('#status') ? document.querySelector('#status').className : 'no-status'"
        })
        status_cls = (status or {}).get("result", {}).get("value", "")
        
        token = await cmd("Runtime.evaluate", {
            "expression": "document.querySelector('#token-field') ? document.querySelector('#token-field').textContent : ''"
        })
        token_text = (token or {}).get("result", {}).get("value", "")

        if token_text:
            print(f"\nTOKEN: {token_text[:100]}...")
            break

        if i % 10 == 0:
            print(f"  Status: {status_cls} ({i//2}s)")

    else:
        print("\nNo token after 30s - checking page state...")
        url = await cmd("Runtime.evaluate", {"expression": "window.location.href"})
        print(f"  URL: {(url or {}).get('result', {}).get('value', 'N/A')}")
        status = await cmd("Runtime.evaluate", {"expression": 
            "document.querySelector('#status') ? document.querySelector('#status').textContent : 'no element'"
        })
        print(f"  Status text: {(status or {}).get('result', {}).get('value', 'N/A')}")
        captcha_html = await cmd("Runtime.evaluate", {"expression":
            "document.querySelector('#captcha-box') ? document.querySelector('#captcha-box').innerHTML.substring(0, 200) : 'no element'"
        })
        print(f"  Captcha box: {(captcha_html or {}).get('result', {}).get('value', 'N/A')[:100]}")

    print(f"\nTotal intercepted: {intercept_count}")
    reader_task.cancel()
    await cdp.close()
    httpd.shutdown()
    proc.kill()

asyncio.run(test())
