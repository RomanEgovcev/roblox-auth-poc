"""Test Fetch interception with fresh Chrome profile."""
import asyncio, websockets, json, http.client, subprocess, os, time, shutil

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9229
FRESH_DIR = os.path.abspath("chrome_fetch_test")

async def test():
    # Remove old profile
    if os.path.exists(FRESH_DIR):
        shutil.rmtree(FRESH_DIR)

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
            # Find the about:blank tab (not extensions)
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
        print("FAIL"); proc.kill(); return
    print(f"CDP: {cdp_url}")

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

    intercepted = []

    async def on_fetch(params):
        url = params.get("request", {}).get("url", "")
        intercepted.append(url)
        req_id = params["requestId"]
        print(f"  [Fetch] {url[:90]}")
        # VERY IMPORTANT: must continue or the request hangs forever
        r = await cmd("Fetch.continueRequest", {"requestId": req_id})
        if r is None:
            print(f"  [WARN] continueRequest TIMEOUT for {url[:50]}")

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

    await cmd("Page.enable")

    # Enable Fetch with pattern for ALL requests
    print("Enabling Fetch (all requests)...")
    r = await cmd("Fetch.enable", {
        "patterns": [{"urlPattern": "*", "requestStage": "Request"}]
    })
    print(f"  Fetch.enable result: {r}")
    await asyncio.sleep(1)

    # Navigate
    print("Navigating to https://example.com...")
    r = await cmd("Page.navigate", {"url": "https://example.com"})
    print(f"  Navigate result: {json.dumps(r, indent=2) if r else 'None'}")
    await asyncio.sleep(3)

    # Check URL
    url = await cmd("Runtime.evaluate", {"expression": "window.location.href"})
    print(f"  Current URL: {(url or {}).get('result', {}).get('value', 'N/A')}")
    print(f"\nTotal intercepted: {len(intercepted)}")
    for u in intercepted[:10]:
        print(f"  {u[:120]}")

    reader_task.cancel()
    await cdp.close()
    proc.kill()

asyncio.run(test())
