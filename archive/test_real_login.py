"""Try real credentials to trigger captcha or get .ROBLOSECURITY"""
import asyncio, websockets, json, http.client, subprocess, time, shutil, os

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9236
FRESH_DIR = os.path.abspath("chrome_real_test")

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

    cdp = await websockets.connect(cdp_url, max_size=None)
    msg_id = 0; pending = {}; event_handlers = {}
    async def cmd(method, params=None, timeout_s=15):
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

    captured_blob = None
    redirected = False
    roblosecurity = None

    async def on_response(params):
        nonlocal captured_blob, redirected, roblosecurity
        resp = params.get("response", {})
        url = resp.get("url", "")
        status = resp.get("status", 0)
        headers = resp.get("headers", {})

        if "auth.roblox.com" in url:
            print(f"\n  AUTH {status}: {url.split('?')[0]}")
        
        # Challenge response
        if "challenge/v1/continue" in url and status == 200:
            print(f"\n  === CAPTCHA CHALLENGE ===")
            req_id = params.get("requestId")
            if req_id:
                body_resp = await cmd("Network.getResponseBody", {"requestId": req_id})
                if body_resp:
                    body = body_resp.get("body", "")
                    with open("fresh_blob_response.json", "w") as f:
                        f.write(body[:2000])
                    try:
                        j = json.loads(body)
                        blob = j.get("challengeMetadata", j.get("dataExchangeBlob", ""))
                        if isinstance(blob, str) and len(blob) > 50:
                            captured_blob = blob
                            with open("fresh_captcha_blob.txt", "w") as f:
                                f.write(blob)
                            print(f"  BLOB saved ({len(blob)} chars)")
                    except:
                        print(f"  Body: {body[:200]}")

    async def on_headers(params):
        nonlocal roblosecurity
        headers = params.get("response", {}).get("headers", [])
        if isinstance(headers, dict):
            headers = [{"name": k, "value": v} for k, v in headers.items()]
        for h in headers:
            if h.get("name", "").lower() == "set-cookie" and ".ROBLOSECURITY" in str(h.get("value", "")):
                roblosecurity = str(h.get("value", ""))
                print(f"\n  === .ROBLOSECURITY COOKIE! {roblosecurity[:50]}...")

    await on_event("Network.responseReceived", on_response)
    await on_event("Network.responseReceivedExtraInfo", on_headers)

    await cmd("Page.navigate", {"url": "https://www.roblox.com/login"})
    print("Waiting for page to fully load...")
    for i in range(15):
        await asyncio.sleep(2)
        ready = await cmd("Runtime.evaluate", {"expression": "!!document.querySelector('#login-button')"})
        if (ready or {}).get("result", {}).get("value"):
            print(f"  Login button found at ~{i*2}s")
            break
        url_r = await cmd("Runtime.evaluate", {"expression": "location.href"})
        url = (url_r or {}).get("result", {}).get("value", "")
        if i % 5 == 0:
            print(f"  Wait {i*2}s... url={url[:50]}")
    else:
        print("  Login button not found after 30s, continuing anyway")

    # Use real credentials from user's known valid account
    USER = "CheatingHitmanner"
    PASS = "LolKekZek228"

    await cmd("Runtime.evaluate", {
        "expression": f"""(() => {{
            const u = document.querySelector('#login-username');
            const p = document.querySelector('#login-password');
            if (!u || !p) return 'no fields';
            Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(u, '{USER}');
            u.dispatchEvent(new Event('input', {{bubbles: true}}));
            u.dispatchEvent(new Event('change', {{bubbles: true}}));
            Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(p, '{PASS}');
            p.dispatchEvent(new Event('input', {{bubbles: true}}));
            p.dispatchEvent(new Event('change', {{bubbles: true}}));
            return 'filled';
        }})()"""
    })
    await asyncio.sleep(0.3)

    # Click login
    print("Clicking login...")
    await cmd("Runtime.evaluate", {
        "expression": "document.querySelector('#login-button')?.click()"
    })

    for i in range(30):
        await asyncio.sleep(2)
        
        url_r = await cmd("Runtime.evaluate", {"expression": "location.href"})
        url = (url_r or {}).get("result", {}).get("value", "")
        
        if captured_blob:
            print(f"\n✅ Captcha blob at ~{i*2}s!")
            break
        if roblosecurity:
            print(f"\n✅ LOGGED IN! .ROBLOSECURITY obtained!")
            break
        if "home" in url:
            print(f"\n✅ Redirected to home! Logged in.")
            break
        
        if i % 3 == 0:
            err_r = await cmd("Runtime.evaluate", {"expression": """
                (() => {
                    const e = document.querySelector('.login-error');
                    return e ? e.textContent.trim() : '';
                })()
            """})
            err = (err_r or {}).get("result", {}).get("value", "")
            print(f"  [{i*2}s] url={url.split('?')[0][:50]} err='{err[:50]}'")

    else:
        print("\n❌ No captcha, no redirect")
    
    # Check auth responses
    print(f"\nCaptcha: {'yes' if captured_blob else 'no'}")
    print(f"Logged in: {'yes' if roblosecurity else 'no'}")

    await cdp.close()
    proc.kill()

asyncio.run(test())
