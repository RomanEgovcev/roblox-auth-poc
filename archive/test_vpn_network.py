"""Check what network requests fail with VPN"""
import asyncio, websockets, json, http.client, subprocess, time, shutil, os

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9238
FRESH_DIR = os.path.abspath("chrome_net_test")

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
    msg_id = 0; pending = {}
    async def cmd(method, params=None, timeout_s=15):
        nonlocal msg_id; msg_id += 1
        future = asyncio.get_event_loop().create_future()
        pending[msg_id] = future
        await cdp.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        try: return await asyncio.wait_for(future, timeout=timeout_s)
        except: pending.pop(msg_id, None); return None

    async def reader():
        async for raw in cdp:
            data = json.loads(raw)
            rid = data.get("id")
            if rid in pending:
                pending[rid].set_result(data.get("result", {}))
                del pending[rid]
    asyncio.create_task(reader())
    await cmd("Page.enable")
    await cmd("Network.enable")

    failed_requests = []
    loaded_requests = []

    async def on_request_will(params):
        req = params.get("request", {})
        url = req.get("url", "")
        if "rbxcdn" in url or "arkoselabs" in url or "roblox.com" in url:
            loaded_requests.append({"url": url[:100], "type": params.get("type", "?")})

    async def on_loading_failed(params):
        url = params.get("url", "")
        typ = params.get("type", "?")
        err = params.get("errorText", params.get("blockedReason", "unknown"))
        if "rbxcdn" in url or "roblox" in url:
            failed_requests.append({"url": url[:100], "type": typ, "error": err})
            print(f"  FAILED: {url[:100]} ({typ}) → {err}")

    await cmd("Network.enable")

    # Listen using the CDP event system
    # We need to add event handlers via addEventListener-like pattern
    # But actually we already have the Network.enable call above

    # Navigate
    await cmd("Page.navigate", {"url": "https://www.roblox.com/login"})
    await asyncio.sleep(3)

    # Get all failed requests by checking console
    await cmd("Runtime.evaluate", {
        "expression": """(() => {
            const orig = window.fetch;
            window.fetch = function(url, opts) {
                return orig.apply(this, arguments).catch(e => {
                    console.log('FETCH_FAILED:', url, e.message);
                    throw e;
                });
            };
        })()"""
    })

    await asyncio.sleep(5)

    # Get performance entries
    perf = await cmd("Runtime.evaluate", {
        "expression": """(() => {
            const entries = performance.getEntriesByType('resource');
            return JSON.stringify(entries.map(e => ({
                name: e.name.substring(0, 80),
                duration: Math.round(e.duration),
                type: e.initiatorType,
                status: e.transferSize > 0 ? 'ok' : 'cached-or-fail'
            })));
        })()"""
    })
    val = (perf or {}).get("result", {}).get("value", "[]")
    try:
        entries = json.loads(val)
        print(f"Resource entries: {len(entries)}")
        # group by domain
        domains = {}
        for e in entries:
            domain = e['name'].split('/')[2] if '//' in e['name'] else 'other'
            domains.setdefault(domain, []).append(e)
        for domain, items in sorted(domains.items()):
            failed = [i for i in items if i['status'] != 'ok']
            print(f"  {domain}: {len(items)} req, {len(failed)} failed")
            if failed:
                for f in failed[:3]:
                    print(f"    FAIL: {f['name'][:60]}")
    except:
        print(f"Perf parse error: {val[:200]}")

    # Check page state now
    state = await cmd("Runtime.evaluate", {
        "expression": """(() => {
            return JSON.stringify({
                url: location.href,
                body_len: document.body?.innerHTML?.length || 0,
                has_login: !!document.querySelector('#login-button'),
                html_start: document.body?.innerHTML?.substring(0, 300) || ''
            });
        })()"""
    })
    s = (state or {}).get("result", {}).get("value", "{}")
    print(f"\nPage state: {s[:300]}")

    # Check for console errors
    console_r = await cmd("Runtime.evaluate", {
        "expression": "Array.from(document.querySelectorAll('script')).map(s => s.src).join('\\n')"
    })
    scripts = (console_r or {}).get("result", {}).get("value", "")
    print(f"\nScripts loaded ({scripts.count(chr(10))}):")
    for s in scripts.split('\n')[:10]:
        print(f"  {s[:100]}")

    await cdp.close()
    proc.kill()

asyncio.run(test())
