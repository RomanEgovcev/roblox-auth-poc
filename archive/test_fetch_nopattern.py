"""
Test if Fetch.enable with pattern is intercepting ALL requests.
"""
import asyncio, websockets, json, http.client, subprocess, os, time

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9226

async def test():
    user_dir = os.path.abspath("chrome_login_profile_test4")
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
    msg_id = 0
    pending = {}
    event_handlers = {}

    async def cmd(method, params=None, timeout_s=10):
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
            return {"TIMEOUT": method}

    async def on_event(method, handler):
        event_handlers[method] = handler

    intercepted = []

    async def on_fetch(params):
        url = params.get("request", {}).get("url", "")
        intercepted.append(url)
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

    # Test with NO pattern (intercept ALL)
    await cmd("Page.enable")
    print("Enabling Fetch with NO pattern (all requests)")
    await cmd("Fetch.enable")  # No patterns = intercept all
    await asyncio.sleep(0.5)

    print("Navigating to about:blank")
    await cmd("Page.navigate", {"url": "about:blank"})
    await asyncio.sleep(2)

    print(f"Intercepted {len(intercepted)} requests:")
    for u in intercepted[:10]:
        print(f"  {u[:120]}")
    if len(intercepted) > 10:
        print(f"  ... and {len(intercepted) - 10} more")

    reader_task.cancel()
    await cdp.close()
    proc.kill()

asyncio.run(test())
