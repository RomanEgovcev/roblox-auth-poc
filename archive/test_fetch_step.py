"""
Test CDP Fetch interception step by step to find where it hangs.
"""
import asyncio, websockets, json, http.client, subprocess, os, time, threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9225

async def test():
    user_dir = os.path.abspath("chrome_login_profile_test3")
    proc = subprocess.Popen([
        CHROME, f"--user-data-dir={user_dir}",
        "--no-first-run", "--no-default-browser-check",
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-allow-origins=*", "--window-size=900,700",
        "--disable-extensions", "--disable-sync",
        "--disable-background-networking", "--mute-audio",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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
        print("FAIL: Chrome not starting"); proc.kill(); return

    print(f"CDP: {cdp_url}")

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
            print(f"  TIMEOUT: {method}")
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

    # Step 1: Page.enable
    print("Step 1: Page.enable")
    r = await cmd("Page.enable")
    print(f"  Result: {r}")

    # Step 2: Navigate to about:blank
    print("Step 2: Navigate to about:blank")
    r = await cmd("Page.navigate", {"url": "about:blank"})
    print(f"  Result: {r}")
    await asyncio.sleep(1)

    # Step 3: Enable Fetch
    print("Step 3: Fetch.enable")
    
    async def on_fetch(params):
        req_id = params.get("requestId")
        url = params.get("request", {}).get("url", "")
        print(f"  Fetch intercepted: {url[:80]}")
        await cmd("Fetch.continueRequest", {"requestId": req_id})

    await on_event("Fetch.requestPaused", on_fetch)
    
    r = await cmd("Fetch.enable", {
        "patterns": [{"urlPattern": "*arkoselabs.com*", "requestStage": "Request"}]
    })
    print(f"  Result: {r}")
    await asyncio.sleep(1)

    # Step 4: Navigate to google (safe test)
    print("Step 4: Navigate to example.com")
    r = await cmd("Page.navigate", {"url": "http://example.com"})
    print(f"  Result: {r}")
    await asyncio.sleep(3)

    print("\nDone - checking page...")
    url = await cmd("Runtime.evaluate", {"expression": "window.location.href"})
    print(f"Current URL: {url}")

    reader_task.cancel()
    await cdp.close()
    proc.kill()

asyncio.run(test())
