"""
Test Fetch.intercept with pattern on real HTTP page.
"""
import asyncio, websockets, json, http.client, subprocess, os, time

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9227

async def test():
    user_dir = os.path.abspath("chrome_login_profile_test5")
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
        print(f"  FETCH: {url[:100]}")
        await cmd("Fetch.continueRequest", {"requestId": params["requestId"]})

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
                await event_handlers[meth](data.get("params", {}))

    reader_task = asyncio.create_task(reader())

    await cmd("Page.enable")
    
    # Test 1: Fetch.enable with wildcard pattern
    print("Test 1: Fetch.enable with pattern '*roblox*'")
    r = await cmd("Fetch.enable", {
        "patterns": [{"urlPattern": "*roblox*", "requestStage": "Request"}]
    })
    print(f"  Result: {r}")

    # Navigate
    print("  Navigating to roblox.com/login")
    r = await cmd("Page.navigate", {"url": "https://www.roblox.com/login"})
    print(f"  Navigate result keys: {list(r.keys()) if r else 'None'}")

    await asyncio.sleep(5)
    print(f"Intercepted {len(intercepted)} requests:")
    for u in intercepted[:15]:
        print(f"  {u[:120]}")

    # Test 2: Disable, re-enable with different pattern
    await cmd("Fetch.disable")
    await asyncio.sleep(0.5)

    print("\nTest 2: Fetch.enable with pattern '*arkoselabs*'")
    intercepted.clear()
    await cmd("Fetch.enable", {
        "patterns": [{"urlPattern": "*arkoselabs*", "requestStage": "Request"}]
    })

    await asyncio.sleep(5)
    print(f"Intercepted {len(intercepted)} requests:")
    for u in intercepted[:15]:
        print(f"  {u[:120]}")

    reader_task.cancel()
    await cdp.close()
    proc.kill()

asyncio.run(test())
