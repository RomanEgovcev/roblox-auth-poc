"""
Monitor the FULL flow after clicking login (no interference).
Wait for PoW → captcha iframe → auto-solve → login success.
"""
import asyncio, websockets, json, http.client, subprocess, time, shutil, os, base64, glob, random

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9270
FRESH_DIR = os.path.abspath(f"chrome_monitor_{random.randint(10000,99999)}")
USER = "CheatingHitmanner"
PASS = "LolKekZek228"

async def main():
    for d in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_monitor_*")):
        try: shutil.rmtree(d)
        except: pass

    proc = subprocess.Popen([
        CHROME, f"--user-data-dir={FRESH_DIR}",
        "--no-first-run", "--no-default-browser-check",
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-allow-origins=*", "--window-size=1400,1000",
        "--new-window", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for i in range(30):
        try:
            conn = http.client.HTTPConnection("localhost", CDP_PORT, timeout=3)
            conn.request("GET", "/json")
            resp = conn.getresponse()
            tabs = json.loads(resp.read()); conn.close()
            for t in tabs:
                if t.get("url", "").startswith("about:") or t.get("url", "") == "":
                    cdp_url = t["webSocketDebuggerUrl"]; break
            else:
                if tabs: cdp_url = tabs[0]["webSocketDebuggerUrl"]
                else: continue
            break
        except:
            time.sleep(1)
    else:
        print("FAIL"); return

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

    # Monitor all network requests
    requests_log = []
    async def on_request(params):
        url = params.get("request", {}).get("url", "")
        if any(x in url for x in ["v2/login", "challenge/v1/continue", "proof-of-work", "arkoselabs"]):
            requests_log.append({"t": time.time(), "event": "req", "url": url[:150], "method": params.get("request", {}).get("method", "")})

    async def on_response(params):
        resp = params.get("response", {})
        url = resp.get("url", "")
        status = resp.get("status")
        if any(x in url for x in ["v2/login", "challenge/v1/continue", "proof-of-work", "arkoselabs"]):
            hdrs = resp.get("headers", {})
            chall_type = hdrs.get("rblx-challenge-type", "")
            requests_log.append({"t": time.time(), "event": f"resp {status}", "url": url[:150], "chall_type": chall_type})

    await on_event("Network.requestWillBeSent", on_request)
    await on_event("Network.responseReceived", on_response)

    await cmd("Page.navigate", {"url": "https://www.roblox.com/login"})
    print("Waiting for page load...")
    for i in range(60):
        await asyncio.sleep(1)
        ready = await cmd("Runtime.evaluate", {"expression": "!!document.querySelector('#login-button')"})
        if (ready or {}).get("result", {}).get("value"):
            print(f"  Page ready at ~{i}s"); break
    else:
        print("  Page didn't load"); return

    # Inject message listener to capture postMessage from captcha iframe
    await cmd("Runtime.evaluate", {"expression": """
        window.__capturedMessages = [];
        window.addEventListener('message', function(e) {
            window.__capturedMessages.push({
                origin: e.origin,
                data: JSON.stringify(e.data).substring(0, 500),
                time: Date.now()
            });
        });
    """})

    # Fill credentials
    await cmd("Runtime.evaluate", {
        "expression": f"""(() => {{
            const u = document.querySelector('#login-username');
            const p = document.querySelector('#login-password');
            if (!u || !p) return;
            Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(u, '{USER}');
            u.dispatchEvent(new Event('input', {{bubbles: true}}));
            Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(p, '{PASS}');
            p.dispatchEvent(new Event('input', {{bubbles: true}}));
        }})()"""
    })
    await asyncio.sleep(0.3)

    # Click login and monitor for up to 120s
    print("\n=== Clicking login ===")
    await cmd("Runtime.evaluate", {"expression": "document.querySelector('#login-button')?.click()"})
    
    start = time.time()
    last_log_t = 0
    captured_iframes = set()
    pow_seen = False
    captcha_seen = False

    for i in range(240):  # 120 seconds
        await asyncio.sleep(0.5)
        elapsed = time.time() - start

        # Check for PoW container
        pow_check = await cmd("Runtime.evaluate", {"expression": "!!document.querySelector('#generic-challenge-container-proofofwork')"})
        has_pow = (pow_check or {}).get("result", {}).get("value", False)
        if has_pow and not pow_seen:
            pow_seen = True
            print(f"\n  [{elapsed:.0f}s] PoW container appeared")

        # Check if PoW container is gone (PoW solved)
        if pow_seen and not has_pow and not captcha_seen:
            print(f"  [{elapsed:.0f}s] PoW container GONE (solved by page)")

        # Check for captcha iframes
        iframe_check = await cmd("Runtime.evaluate", {"expression": """(() => {
            const iframes = document.querySelectorAll('iframe');
            return Array.from(iframes).map(f => f.src.substring(0, 120)).filter(s => s.includes('arkose') || s.includes('funcaptcha'));
        })()"""})
        iframes = (iframe_check or {}).get("result", {}).get("value", [])
        for src in iframes:
            if src not in captured_iframes:
                captured_iframes.add(src)
                print(f"  [{elapsed:.0f}s] Captcha iframe: {src}")

        # Check .ROBLOSECURITY
        ck_resp = await cmd("Network.getAllCookies")
        for c in (ck_resp or {}).get("cookies", []):
            if c["name"] == ".ROBLOSECURITY":
                print(f"\n  [OK] [{elapsed:.0f}s] .ROBLOSECURITY = {c['value'][:40]}...")
                msg_r = await cmd("Runtime.evaluate", {"expression": "JSON.stringify(window.__capturedMessages)"})
                msgs = (msg_r or {}).get("result", {}).get("value", "[]")
                print(f"  Captured postMessages: {msgs[:500]}")
                # Check current URL
                url_r = await cmd("Runtime.evaluate", {"expression": "location.href"})
                url = (url_r or {}).get("result", {}).get("value", "")
                print(f"  URL: {url}")
                
                ss = await cmd("Page.captureScreenshot", {"format": "png"})
                if ss:
                    with open("flow_success.png", "wb") as f:
                        f.write(base64.b64decode(ss.get("data", "")))
                    print("  Screenshot: flow_success.png")
                
                await cdp.close()
                proc.kill()
                return

        # Log network events
        while requests_log and requests_log[0]["t"] < start + elapsed:
            ev = requests_log.pop(0)
            ct = ev.get("chall_type", "")
            ct_str = f" type={ct}" if ct else ""
            print(f"  [{ev['t']-start:.0f}s] {ev['event']}: {ev['url'][:100]}{ct_str}")

        # Log every 5s
        if elapsed - last_log_t >= 5:
            last_log_t = elapsed
            pow_s = "pow" if has_pow else "no-pow"
            iframe_s = f"iframes={len(captured_iframes)}" if captured_iframes else "no-iframes"
            print(f"  [{elapsed:.0f}s] {pow_s}, {iframe_s}")

    # Timeout - dump state
    print(f"\n  [FAIL] No .ROBLOSECURITY after 120s")
    
    # Check if page is still on login
    url_r = await cmd("Runtime.evaluate", {"expression": "location.href"})
    url = (url_r or {}).get("result", {}).get("value", "")
    print(f"  URL: {url}")
    
    # Dump iframes
    iframe_r = await cmd("Runtime.evaluate", {"expression": "Array.from(document.querySelectorAll('iframe')).map(f => f.src)"})
    iframes = (iframe_r or {}).get("result", {}).get("value", [])
    print(f"  All iframes ({len(iframes)}):")
    for s in iframes:
        print(f"    {s[:120]}")
    
    # Dump postMessages
    msg_r = await cmd("Runtime.evaluate", {"expression": "JSON.stringify(window.__capturedMessages)"})
    msgs = (msg_r or {}).get("result", {}).get("value", "[]")
    print(f"  Captured postMessages: {msgs[:1000]}")
    
    # Dump remaining network events
    for ev in requests_log:
        ct = ev.get("chall_type", "")
        ct_str = f" type={ct}" if ct else ""
        print(f"  [{ev['t']-start:.0f}s] {ev['event']}: {ev['url'][:100]}{ct_str}")

    ss = await cmd("Page.captureScreenshot", {"format": "png"})
    if ss:
        with open("flow_timeout.png", "wb") as f:
            f.write(base64.b64decode(ss.get("data", "")))
        print("  Screenshot: flow_timeout.png")

    await cdp.close()
    proc.kill()

if __name__ == "__main__":
    asyncio.run(main())
