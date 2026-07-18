"""Debug page state with VPN"""
import asyncio, websockets, json, http.client, subprocess, time, shutil, os

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9237
FRESH_DIR = os.path.abspath("chrome_vpn_test")

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

    # Capture ALL responses
    responses = []
    async def on_response(params):
        resp = params.get("response", {})
        url = resp.get("url", "")
        status = resp.get("status", 0)
        if status >= 300 or "auth" in url or "challenge" in url or "captcha" in url:
            responses.append({"url": url[:120], "status": status, "headers": dict(list(resp.get("headers", {}).items())[:5])})
    # Can't hook events easily here, let's just dump page state

    await cmd("Page.navigate", {"url": "https://www.roblox.com/login"})
    await asyncio.sleep(12)

    # Dump full page details
    dump = await cmd("Runtime.evaluate", {
        "expression": """(() => {
            const r = {};
            r.url = location.href;
            r.title = document.title;
            r.forms = document.querySelectorAll('form').length;
            r.has_login_btn = !!document.querySelector('#login-button');
            r.login_btn_type = document.querySelector('#login-button')?.type || 'N/A';
            
            // Check if page shows any error/alerts
            const alerts = document.querySelectorAll('.alert, .alert-container, .error-message, [class*=error]');
            r.alerts = Array.from(alerts).map(a => ({
                text: a.textContent.trim().substring(0, 100),
                display: a.offsetParent !== null ? 'visible' : 'hidden'
            }));
            
            // Check for iframes
            r.iframes = Array.from(document.querySelectorAll('iframe')).map(f => ({
                src: f.src.substring(0, 80),
                display: f.style.display || (f.offsetParent !== null ? 'visible' : 'hidden'),
                id: f.id
            }));
            
            // Check for turnstile / cloudflare
            r.has_turnstile = !!document.querySelector('[class*=turnstile], [id*=turnstile]');
            r.has_cf = document.body?.textContent?.includes('cloudflare') || document.body?.textContent?.includes('Cloudflare');
            
            // Page HTML snippet (first 2000 chars)
            r.body_html_start = document.body?.innerHTML?.substring(0, 500) || 'no body';
            
            // Check input fields
            r.username = document.querySelector('#login-username') ? 'found' : 'missing';
            r.password = document.querySelector('#login-password') ? 'found' : 'missing';
            
            return JSON.stringify(r);
        })()"""
    })
    val = (dump or {}).get("result", {}).get("value", "{}")
    try:
        d = json.loads(val)
        print(f"URL: {d.get('url')}")
        print(f"Title: {d.get('title')}")
        print(f"Login button: {d.get('has_login_btn')} type={d.get('login_btn_type')}")
        print(f"Forms: {d.get('forms')}")
        print(f"Alert count: {len(d.get('alerts', []))}")
        for a in d.get('alerts', [])[:3]:
            print(f"  Alert: {a}")
        print(f"Iframes: {len(d.get('iframes', []))}")
        for f in d.get('iframes', [])[:3]:
            print(f"  iframe: {f}")
        print(f"Turnstile: {d.get('has_turnstile')}")
        print(f"CF: {d.get('has_cf')}")
        print(f"Fields: user={d.get('username')} pass={d.get('password')}")
        print(f"\n--- HTML start (500 chars) ---")
        print(d.get('body_html_start', '')[:500])
    except Exception as e:
        print(f"Parse error: {e}")
        print(f"Raw: {val[:500]}")

    await cdp.close()
    proc.kill()

asyncio.run(test())
