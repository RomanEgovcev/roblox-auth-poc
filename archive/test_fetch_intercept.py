"""
Test: CDP Fetch interception with proper event handling.
Navigate to data: URL with captcha_solver.html content,
intercept Arkose requests, rewrite Origin.
"""
import asyncio, websockets, json, http.client, subprocess, os, time
import urllib.parse

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9223  # different port to avoid conflict

async def test():
    # 1. Start Chrome
    user_dir = os.path.abspath("chrome_login_profile_test2")
    proc = subprocess.Popen([
        CHROME,
        f"--user-data-dir={user_dir}",
        "--no-first-run", "--no-default-browser-check",
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-allow-origins=*",
        "--window-size=900,700",
        "--disable-extensions", "--disable-sync",
        "--disable-background-networking", "--mute-audio",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 2. Wait for CDP
    for i in range(30):
        try:
            conn = http.client.HTTPConnection("localhost", CDP_PORT, timeout=3)
            conn.request("GET", "/json")
            resp = conn.getresponse()
            tabs = json.loads(resp.read())
            conn.close()
            if tabs:
                cdp_url = tabs[0]["webSocketDebuggerUrl"]
                break
        except:
            pass
        time.sleep(1)
    else:
        print("FAIL: Could not connect to Chrome CDP")
        proc.kill()
        return

    print(f"CDP: {cdp_url}")

    # 3. Connect to CDP
    cdp = await websockets.connect(cdp_url, max_size=None)
    msg_id = 0
    pending = {}
    event_handlers = {}

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
                await event_handlers[meth](data.get("params", {}))

    reader_task = asyncio.create_task(reader())

    # 4. Enable Page and Fetch
    await cmd("Page.enable")

    intercept_count = 0

    async def on_fetch(params):
        nonlocal intercept_count
        req_id = params.get("requestId")
        req = params.get("request", {})
        url = req.get("url", "")
        headers = req.get("headers", [])

        # Only rewrite for Arkose API calls (not static assets)
        if "/fc/" in url or "/gt2/" in url or "/gfct/" in url or "/ca/" in url or "/gc/" in url:
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
            print(f"[{intercept_count}] Intercepted: {url[:80]}")

            await cmd("Fetch.continueRequest", {
                "requestId": req_id,
                "headers": new_headers,
            })
        else:
            await cmd("Fetch.continueRequest", {"requestId": req_id})

    await on_event("Fetch.requestPaused", on_fetch)

    # 5. Enable Fetch with pattern
    await cmd("Fetch.enable", {
        "patterns": [{
            "urlPattern": "*arkoselabs.com*",
            "requestStage": "Request"
        }]
    })
    print("Fetch interception enabled")

    # 6. Load captcha_solver.html via HTTP server
    import threading
    from http.server import HTTPServer, SimpleHTTPRequestHandler

    HTML_PORT = 8089
    httpd = HTTPServer(("", HTML_PORT), SimpleHTTPRequestHandler)
    http_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    http_thread.start()

    # Inject blob into the page via JS evaluation after navigation
    blob_path = os.path.abspath("last_captcha_blob.txt")
    with open(blob_path, "r", encoding="utf-8") as f:
        blob = f.read().strip()
    print(f"Blob: {blob[:50]}...")

    await cmd("Page.navigate", {"url": f"http://localhost:{HTML_PORT}/hundle/captcha_solver.html"})
    print(f"Navigated to http://localhost:{HTML_PORT}/hundle/captcha_solver.html")

    # Wait for page load
    await asyncio.sleep(3)

    # Inject blob and click load
    await cmd("Runtime.evaluate", {
        "expression": f"""(() => {{
            const ta = document.getElementById('blob');
            if (ta) {{
                const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                setter.call(ta, {json.dumps(blob)});
                ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }}
            const btn = document.getElementById('load-btn') || document.querySelector('button');
            if (btn) btn.click();
        }})()"""
    })
    print("Blob injected and button clicked")

    # 7. Wait for captcha interactions
    await asyncio.sleep(10)

    # Check page state
    status = await cmd("Runtime.evaluate", {
        "expression": "document.querySelector('#status') ? document.querySelector('#status').textContent : 'no status'"
    })
    status_text = (status or {}).get("result", {}).get("value", "")
    print(f"Page status: {status_text}")

    token = await cmd("Runtime.evaluate", {
        "expression": "document.querySelector('#token-field') ? document.querySelector('#token-field').textContent : ''"
    })
    token_text = (token or {}).get("result", {}).get("value", "")
    if token_text:
        print(f"TOKEN: {token_text[:80]}...")
    else:
        print("No token yet")

    print(f"\nTotal intercepted: {intercept_count}")

    reader_task.cancel()
    await cdp.close()
    proc.kill()
    print("Done")

asyncio.run(test())
