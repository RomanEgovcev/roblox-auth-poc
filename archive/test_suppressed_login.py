"""
Test suppressed captcha: does Roblox auto-solve on the login page?
"""
import asyncio, websockets, json, http.client, subprocess, time, shutil, os

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9244
FRESH_DIR = os.path.abspath(f"chrome_suppressed_test_{int(time.time())}")

async def main():
    for d in glob.glob("chrome_suppressed_test_*"):
        try: shutil.rmtree(d)
        except: pass

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
            conn.request("GET", "/json"); resp = conn.getresponse()
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
    auto_logged_in = False
    roblosecurity = None
    network_events = []

    async def on_response(params):
        nonlocal auto_logged_in, roblosecurity
        resp = params.get("response", {})
        url = resp.get("url", "")
        status = resp.get("status", 0)
        headers = resp.get("headers", {})
        short = url.split('?')[0]
        
        if "v2/login" in short:
            network_events.append(f"v2/login -> {status}")
            print(f"  AUTH: v2/login -> {status}")
        
        if status == 200 and "challenge/v1/continue" in url:
            network_events.append(f"challenge -> 200")
            print(f"  CHALLENGE: challenge/v1/continue -> 200")
        
        # Check set-cookie for .ROBLOSECURITY
        sh = headers.get("set-cookie", headers.get("Set-Cookie", ""))
        if ".ROBLOSECURITY" in str(sh):
            roblosecurity = str(sh)
            auto_logged_in = True
            print(f"  ✅ .ROBLOSECURITY in response!")
    await on_event("Network.responseReceived", on_response)

    # Navigate and fill
    await cmd("Page.navigate", {"url": "https://www.roblox.com/login"})
    for i in range(15):
        await asyncio.sleep(2)
        ready = await cmd("Runtime.evaluate", {"expression": "!!document.querySelector('#login-button')"})
        if (ready or {}).get("result", {}).get("value"):
            print(f"  Page ready at ~{i*2}s"); break
    else:
        print("  Page not ready")

    # Fill and click login
    await cmd("Runtime.evaluate", {
        "expression": f"""(() => {{
            const u = document.querySelector('#login-username');
            const p = document.querySelector('#login-password');
            Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(u, '{USER}');
            u.dispatchEvent(new Event('input', {{bubbles: true}}));
            Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(p, '{PASS}');
            p.dispatchEvent(new Event('input', {{bubbles: true}}));
        }})()"""
    })
    await asyncio.sleep(0.3)
    await cmd("Runtime.evaluate", {"expression": "document.querySelector('#login-button')?.click()"})
    print("Login clicked, waiting for auto-solve...")

    # Wait for auto-login
    for i in range(30):
        await asyncio.sleep(2)
        url_r = await cmd("Runtime.evaluate", {"expression": "location.href"})
        url = (url_r or {}).get("result", {}).get("value", "")
        
        if "home" in url or "home" in str(url_r):
            print(f"  ✅ Redirected to home at ~{i*2}s!")
            auto_logged_in = True
            break
        
        if roblosecurity:
            print(f"  ✅ .ROBLOSECURITY at ~{i*2}s!")
            break
        
        if i % 3 == 0:
            err_r = await cmd("Runtime.evaluate", {"expression": "(document.querySelector('.login-error') || {}).textContent || ''"})
            err = (err_r or {}).get("result", {}).get("value", "")
            print(f"  [{i*2}s] url={url[:50]} err='{err[:40]}'")

    print(f"\nAuto-login: {'✅ SUCCESS' if auto_logged_in else '❌ FAILED'}")
    print(f"Network events: {network_events}")
    if roblosecurity:
        print(f".ROBLOSECURITY: {roblosecurity[:60]}...")

    await cdp.close(); proc.kill()

import glob
asyncio.run(main())
