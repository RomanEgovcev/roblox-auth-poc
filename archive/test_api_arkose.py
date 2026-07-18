"""
Debug Arkose API call from solver.html with CDP Fetch interception.
Opens http://localhost:8096/hundle/captcha_solver.html, rewrites Origin/Referer.
"""
import asyncio, websockets, json, http.client, subprocess, time, shutil, os, random, base64, glob, threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9251
HTML_PORT = 8097
FRESH_DIR = os.path.abspath(f"chrome_arkose_debug_{random.randint(10000,99999)}")

async def main():
    for d in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_arkose_debug_*")):
        try: shutil.rmtree(d)
        except: pass

    # HTTP server
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    httpd = HTTPServer(("", HTML_PORT), SimpleHTTPRequestHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print(f"HTTP server on :{HTML_PORT}")

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

    async def command(method, params=None, timeout_s=20):
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
    await command("Page.enable")
    await command("Network.enable")

    # Fetch interception for Arkose API calls
    await command("Fetch.enable", {"patterns": [
        {"urlPattern": "*arkoselabs.com/fc/*", "requestStage": "Request"},
        {"urlPattern": "*funcaptcha.com/fc/*", "requestStage": "Request"},
    ]})
    print("Fetch interception active for Arkose API")

    async def on_fetch(params):
        req_id = params.get("requestId")
        raw_headers = params.get("request", {}).get("headers", [])
        new_headers = []
        for h in raw_headers:
            if isinstance(h, dict):
                new_headers.append({"name": h.get("name", ""), "value": h.get("value", "")})
            elif isinstance(h, str) and ":" in h:
                name, _, val = h.partition(":")
                new_headers.append({"name": name.strip(), "value": val.strip()})
        for h in new_headers:
            if h["name"].lower() == "origin":
                h["value"] = "https://www.roblox.com"
            if h["name"].lower() == "referer":
                h["value"] = "https://www.roblox.com/"
        if not any(h["name"].lower() == "origin" for h in new_headers):
            new_headers.append({"name": "Origin", "value": "https://www.roblox.com"})
        if not any(h["name"].lower() == "referer" for h in new_headers):
            new_headers.append({"name": "Referer", "value": "https://www.roblox.com/"})
        await command("Fetch.continueRequest", {"requestId": req_id, "headers": new_headers})
    await on_event("Fetch.requestPaused", on_fetch)

    # Navigate to solver
    solver_url = f"http://localhost:{HTML_PORT}/hundle/captcha_solver.html"
    print(f"Navigating to: {solver_url}")
    await command("Page.navigate", {"url": solver_url})
    await asyncio.sleep(3)

    # Click load without blob (fresh challenge)
    await command("Runtime.evaluate", {"expression": "document.getElementById('load-btn').click()"})
    print("Waiting for captcha (Origin=roblox.com, no blob)...")

    captcha_token = None
    for i in range(120):
        await asyncio.sleep(1)
        state = await command("Runtime.evaluate", {"expression": "JSON.stringify({status:(document.getElementById('status')||{}).textContent, className:(document.getElementById('status')||{}).className})"})
        val = (state or {}).get("result", {}).get("value", "")
        if i % 5 == 0 or "ошибк" in val.lower() or "success" in val or "Токен" in val or "Реши" in val:
            print(f"[{i}s] {val[:180]}")
        if "Реши капчу" in val:
            print("  👆 CAPTCHA VISIBLE! Solve manually in the browser window.")
            # Also try taking screenshot
        if "Токен" in val or "success" in val:
            token_el = await command("Runtime.evaluate", {"expression": "document.getElementById('token-field').textContent"})
            captcha_token = (token_el or {}).get("result", {}).get("value", "")
            print(f"\n✅ TOKEN: {captcha_token[:80]}...")
            break
        if i == 15:
            ss = await command("Page.captureScreenshot", {"format": "png"})
            if ss:
                with open("arkose_debug.png", "wb") as f:
                    f.write(base64.b64decode(ss.get("data", "")))
                print("  Screenshot: arkose_debug.png")
    
    if captcha_token:
        print(f"\nFinal token: {captcha_token[:100]}...")
        with open("visual_solved_token.txt", "w") as f:
            f.write(captcha_token)
    
    print("\nBrowser stays open for 120s for manual solving.")
    await asyncio.sleep(120)
    proc.kill()
    httpd.shutdown()
    await cdp.close()

if __name__ == "__main__":
    asyncio.run(main())
