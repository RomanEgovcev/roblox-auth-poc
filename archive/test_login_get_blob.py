"""Submit login form + intercept captcha blob in real-time.
Opens roblox.com/login, fills random creds, submits form, catches captcha blob."""
import asyncio, websockets, json, http.client, subprocess, time, shutil, os, threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9234
FRESH_DIR = os.path.abspath("chrome_login_test")

async def test():
    if os.path.exists(FRESH_DIR):
        shutil.rmtree(FRESH_DIR)

    proc = subprocess.Popen([
        CHROME, f"--user-data-dir={FRESH_DIR}",
        "--no-first-run", "--no-default-browser-check",
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-allow-origins=*",
        "--window-size=1000,900",
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
    print(f"CDP connected")

    cdp = await websockets.connect(cdp_url, max_size=None)
    msg_id = 0; pending = {}; event_handlers = {}

    async def cmd(method, params=None, timeout_s=15):
        nonlocal msg_id; msg_id += 1
        future = asyncio.get_event_loop().create_future()
        pending[msg_id] = future
        await cdp.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
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

    asyncio.create_task(reader())

    await cmd("Page.enable")

    # Enable Network to capture responses
    await cmd("Network.enable")

    captured_blob = None
    captured_headers = None

    async def on_response(params):
        nonlocal captured_blob, captured_headers
        resp = params.get("response", {})
        url = resp.get("url", "")
        status = resp.get("status", 0)
        headers = resp.get("headers", {})
        ct = (headers.get("content-type", headers.get("Content-Type", "")))
        
        # Capture challenge response
        if "challenge/v1/continue" in url and status == 200:
            print(f"\n=== CAPTCHA RESPONSE: {url} (status {status})")
            captured_headers = dict(headers)
            # Try to get body
            req_id = params.get("requestId")
            if req_id:
                body_resp = await cmd("Network.getResponseBody", {"requestId": req_id})
                if body_resp:
                    body = body_resp.get("body", "")
                    try:
                        j = json.loads(body)
                        blob = j.get("challengeMetadata", j.get("dataExchangeBlob", ""))
                        if isinstance(blob, str) and len(blob) > 100:
                            captured_blob = blob
                            print(f"  BLOB: {blob[:60]}... ({len(blob)} chars)")
                            with open("fresh_captcha_blob.txt", "w") as f:
                                f.write(blob)
                            print("  SAVED to fresh_captcha_blob.txt")
                        else:
                            print(f"  Body keys: {list(j.keys())}")
                    except:
                        print(f"  Raw body: {body[:200]}")
        
        # Track auth responses
        if "auth.roblox.com" in url:
            print(f"\n  AUTH: {url} -> {status}")
            for k, v in list(headers.items())[:5]:
                print(f"    {k}: {v[:80] if isinstance(v,str) else v}")

    await on_event("Network.responseReceived", on_response)

    # Navigate to login
    print("Navigating to roblox.com/login...")
    await cmd("Page.navigate", {"url": "https://www.roblox.com/login"})
    await asyncio.sleep(4)

    # Fill credentials
    print("Filling random credentials...")
    await cmd("Runtime.evaluate", {
        "expression": """(() => {
            const u = document.querySelector('#login-username');
            const p = document.querySelector('#login-password');
            if (!u || !p) return 'fields not found';
            
            Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(u, 'testuser_aksjdh');
            u.dispatchEvent(new Event('input', {bubbles: true}));
            u.dispatchEvent(new Event('change', {bubbles: true}));
            
            Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(p, 'wrongpass_12345');
            p.dispatchEvent(new Event('input', {bubbles: true}));
            p.dispatchEvent(new Event('change', {bubbles: true}));
            
            return 'ok';
        })()"""
    })

    await asyncio.sleep(0.5)

    # Submit form via login-button click (CDP mouse)
    print("Clicking login-button...")
    
    # Get button position
    btn_pos = await cmd("Runtime.evaluate", {
        "expression": """(() => {
            const btn = document.querySelector('#login-button');
            if (!btn) return null;
            const r = btn.getBoundingClientRect();
            return JSON.stringify({x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)});
        })()"""
    })
    pos = json.loads((btn_pos or {}).get("result", {}).get("value", "null"))
    if pos:
        print(f"  Position: ({pos['x']}, {pos['y']})")
        await cmd("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": pos["x"], "y": pos["y"],
            "button": "left", "clickCount": 1
        })
        await asyncio.sleep(0.03)
        await cmd("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": pos["x"], "y": pos["y"],
            "button": "left", "clickCount": 1
        })
        print("  Mouse click dispatched")
    else:
        # Fallback: JS click
        print("  Button not found, trying JS click")
        await cmd("Runtime.evaluate", {
            "expression": "document.querySelector('#login-button')?.click()"
        })

    # Wait for captcha or timeout
    print("Waiting for response...")
    for i in range(30):
        await asyncio.sleep(2)
        if captured_blob:
            print(f"\n✅ Captcha blob captured at ~{i*2}s!")
            break
        # Check URL
        url_r = await cmd("Runtime.evaluate", {
            "expression": "location.href"
        })
        url = (url_r or {}).get("result", {}).get("value", "")
        # Check for error text
        err_r = await cmd("Runtime.evaluate", {
            "expression": """(() => {
                const err = document.querySelector('.error, .alert, [class*="error"], [class*="alert"]');
                return err ? err.textContent.trim().substring(0, 100) : '';
            })()"""
        })
        err = (err_r or {}).get("result", {}).get("value", "")
        if i % 5 == 0:
            print(f"  Wait {i*2}s... url={url[:60]} err='{err[:40]}'")
    else:
        print("\n❌ No captcha blob after 60s")
        # Take screenshot
        ss = await cmd("Page.captureScreenshot", {"format": "png"})
        if ss:
            import base64 as b64
            with open("login_error.png", "wb") as f:
                f.write(b64.b64decode(ss.get("data", "")))
            print("Screenshot: login_error.png")
        
        # Dump page text
        text_r = await cmd("Runtime.evaluate", {
            "expression": "document.body ? document.body.textContent.trim().substring(0, 500) : 'no body'"
        })
        print(f"Page text: {(text_r or {}).get('result', {}).get('value', '')[:300]}")

    await cdp.close()
    proc.kill()
    print(f"\nDone. Blob captured: {captured_blob is not None}")

asyncio.run(test())
