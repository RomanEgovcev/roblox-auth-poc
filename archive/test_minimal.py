"""
Minimal test: just check if Page.navigate with Fetch.enable works.
"""
import asyncio, websockets, json, http.client, subprocess, os, time

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9228

async def test():
    user_dir = os.path.abspath("chrome_login_profile_test6")
    proc = subprocess.Popen([
        CHROME, f"--user-data-dir={user_dir}",
        "--no-first-run", "--no-default-browser-check",
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-allow-origins=*", "--window-size=900,700",
        "--disable-extensions", "--disable-sync",
        "--mute-audio",
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

    # Just navigate without Fetch
    print("Test: Navigate without Fetch")
    r = await cmd("Page.navigate", {"url": "https://www.roblox.com/login"})
    print(f"  Full result: {json.dumps(r, indent=2) if r else 'None'}")
    await asyncio.sleep(3)

    # Check URL
    url = await cmd("Runtime.evaluate", {"expression": "window.location.href"})
    print(f"  Current URL: {(url or {}).get('result', {}).get('value', 'N/A')}")

    reader_task.cancel()
    await cdp.close()
    proc.kill()

asyncio.run(test())
