"""
Minimal test: open captcha_solver.html in Chrome with Fetch interception.
Uses the saved blob from last_captcha_blob.txt.
"""
import asyncio, websockets, json, http.client, subprocess, os, time, shutil, threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9232
HTML_PORT = 8092
FRESH_DIR = os.path.abspath("chrome_solver_test")

async def test():
    if os.path.exists(FRESH_DIR):
        shutil.rmtree(FRESH_DIR)

    # HTTP server for captcha_solver.html
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    httpd = HTTPServer(("", HTML_PORT), SimpleHTTPRequestHandler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    print(f"HTTP on :{HTML_PORT}")

    # Chrome
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
                u = t.get("url", "")
                if u.startswith("about:") or u == "":
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
        print("FAIL"); proc.kill(); httpd.shutdown(); return
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

    # Fetch interception
    intercepted = []
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
                intercepted.append(url)
                await cmd("Fetch.continueRequest", {"requestId": req_id, "headers": new_headers})
            else:
                await cmd("Fetch.continueRequest", {"requestId": req_id})
        except:
            try:
                await cmd("Fetch.continueRequest", {"requestId": params.get("requestId")})
            except:
                pass

    await on_event("Fetch.requestPaused", on_fetch)
    await cmd("Fetch.enable", {
        "patterns": [{"urlPattern": "*arkoselabs.com*", "requestStage": "Request"}]
    })
    print("Fetch interception active")

    # Read fresh blob — extract dataExchangeBlob if it's a JSON envelope
    blob_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fresh_captcha_blob.txt")
    if not os.path.exists(blob_path):
        blob_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_captcha_blob.txt")
    with open(blob_path, "r") as f:
        blob_raw = f.read().strip()
    # If it's JSON, extract dataExchangeBlob
    if blob_raw.startswith("{"):
        try:
            j = json.loads(blob_raw)
            blob = j.get("dataExchangeBlob", j.get("challengeMetadata", {}).get("dataExchangeBlob", blob_raw))
        except:
            blob = blob_raw
    else:
        blob = blob_raw
    print(f"Blob: {blob[:50]}... ({len(blob)} chars)")

    # Navigate to captcha_solver.html
    solver_url = f"http://localhost:{HTML_PORT}/hundle/captcha_solver.html"
    print(f"Opening: {solver_url}")
    await cmd("Page.navigate", {"url": solver_url})
    await asyncio.sleep(3)

    # Inject blob
    await cmd("Runtime.evaluate", {
        "expression": f"""(() => {{
            const ta = document.getElementById('blob');
            if (ta) {{
                Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set.call(ta, {json.dumps(blob)});
                ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }}
        }})()"""
    })
    print("Blob injected")

    # Click load button
    await cmd("Runtime.evaluate", {
        "expression": """(() => {
            const btn = document.querySelector('button');
            if (btn) { btn.click(); return 'clicked'; }
            return 'no button';
        })()"""
    })
    print("Load button clicked")

    # Wait for widget to init
    await asyncio.sleep(5)

    # Check status
    status = await cmd("Runtime.evaluate", {
        "expression": "document.querySelector('#status') ? document.querySelector('#status').textContent + ' | class: ' + document.querySelector('#status').className : 'no-status'"
    })
    print(f"Status: {(status or {}).get('result', {}).get('value', 'N/A')}")

    # Check captcha-box in detail
    for _ in range(10):
        await asyncio.sleep(2)
        box_detail = await cmd("Runtime.evaluate", {
            "expression": """(() => {
                const box = document.querySelector('#captcha-box');
                if (!box) return 'no captcha-box element';
                const iframes = box.querySelectorAll('iframe');
                const imgs = box.querySelectorAll('img');
                const children = box.children;
                const display = getComputedStyle(box).display;
                const visible = box.offsetParent !== null;
                return JSON.stringify({
                    display, visible,
                    className: box.className,
                    childCount: box.childElementCount,
                    iframes: Array.from(iframes).map(f => ({
                        src: f.src.substring(0, 100),
                        width: f.width,
                        height: f.height,
                    })),
                    images: Array.from(imgs).map(i => ({
                        src: i.src.substring(0, 100),
                    })),
                    html_len: box.innerHTML.length,
                    html_start: box.innerHTML.substring(0, 200)
                });
            })()"""
        })
        val = (box_detail or {}).get("result", {}).get("value", "{}")
        try:
            d = json.loads(val)
        except:
            print(f"  [wait] box detail parse error: {val[:100]}")
            continue
        has_content = d.get('childCount', 0) > 0 or d.get('html_len', 0) > 10
        print(f"  [{_*2}s] display={d.get('display','?')} visible={d.get('visible','?')} class={d.get('className','?')} children={d.get('childCount')} iframes={d.get('iframes',[])} html_len={d.get('html_len')}")
        if has_content:
            break

    # Take screenshot
    ss = await cmd("Page.captureScreenshot", {"format": "png"})
    if ss:
        import base64 as b64
        with open("test_solver.png", "wb") as f:
            f.write(b64.b64decode(ss.get("data", "")))
        print("Screenshot: test_solver.png")

    print(f"\nIntercepted requests ({len(intercepted)}):")
    for u in intercepted:
        print(f"  {u[:120]}")

    # Check for any other arkose requests (not intercepted but still made)
    arkose_entries = await cmd("Runtime.evaluate", {
        "expression": """(() => {
            const entries = performance.getEntriesByType('resource');
            return JSON.stringify(entries.filter(e => e.name.includes('arkoselabs')).map(e => ({
                url: e.name.substring(0, 120),
                type: e.initiatorType,
                duration: Math.round(e.duration)
            })));
        })()"""
    })
    ae = (arkose_entries or {}).get("result", {}).get("value", "[]")
    try:
        parsed = json.loads(ae)
        if parsed:
            print(f"All Arkose requests ({len(parsed)}):")
            for p in parsed:
                print(f"  {p['url']} ({p['type']}, {p['duration']}ms)")
    except:
        pass

    # Check if Pi object reports anything
    pi_info = await cmd("Runtime.evaluate", {
        "expression": """(() => {
            if (typeof _pi === 'undefined') return 'no _pi';
            return 'Pi keys: ' + Object.keys(_pi).join(', ');
        })()"""
    })
    print(f"Pi: {(pi_info or {}).get('result', {}).get('value', 'N/A')}")

    # Check token
    token = await cmd("Runtime.evaluate", {
        "expression": "document.querySelector('#token-field') ? document.querySelector('#token-field').textContent : ''"
    })
    t = (token or {}).get("result", {}).get("value", "")
    if t:
        print(f"\nTOKEN: {t[:80]}...")
    else:
        print("\nNo token — captcha not solved yet")

    print("\n✅ Done. Check test_solver.png to see the result.")

    reader_task.cancel()
    await cdp.close()
    proc.kill()
    httpd.shutdown()

asyncio.run(test())
