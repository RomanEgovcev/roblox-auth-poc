"""Debug: what happens after login button click - look for captcha elements"""
import asyncio, websockets, json, http.client, subprocess, time, shutil, os

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9235
FRESH_DIR = os.path.abspath("chrome_debug_test")

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
        try:
            return await asyncio.wait_for(future, timeout=timeout_s)
        except:
            pending.pop(msg_id, None)
            return None

    async def reader():
        async for raw in cdp:
            data = json.loads(raw)
            rid = data.get("id")
            if rid in pending:
                pending[rid].set_result(data.get("result", {}))
                del pending[rid]
    asyncio.create_task(reader())

    await cmd("Page.enable")

    # Navigate
    await cmd("Page.navigate", {"url": "https://www.roblox.com/login"})
    await asyncio.sleep(5)

    # Fill
    await cmd("Runtime.evaluate", {
        "expression": """(() => {
            const u = document.querySelector('#login-username');
            const p = document.querySelector('#login-password');
            if (!u || !p) return 'no fields';
            Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(u, 'testuser_aksjdh');
            u.dispatchEvent(new Event('input', {bubbles: true}));
            u.dispatchEvent(new Event('change', {bubbles: true}));
            Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(p, 'wrongpass_12345');
            p.dispatchEvent(new Event('input', {bubbles: true}));
            p.dispatchEvent(new Event('change', {bubbles: true}));
            return 'filled';
        })()"""
    })
    await asyncio.sleep(0.5)

    # Click using JS element.click()
    print("Clicking login-button via JS...")
    click_r = await cmd("Runtime.evaluate", {
        "expression": """(() => {
            const btn = document.querySelector('#login-button');
            if (!btn) return 'no button found';
            // Try multiple dispatch approaches
            btn.click();  // JS click
            return 'click() called on ' + btn.id;
        })()"""
    })
    print(f"  {(click_r or {}).get('result', {}).get('value', 'N/A')}")

    await asyncio.sleep(3)

    # Check what happened
    for i in range(15):
        await asyncio.sleep(2)
        diag = await cmd("Runtime.evaluate", {
            "expression": """(() => {
                const r = {};
                
                // Check URL
                r.url = location.href;
                
                // Check if login button is still visible
                const btn = document.querySelector('#login-button');
                r.btn_visible = btn ? btn.offsetParent !== null : 'no button';
                
                // Check for error message
                const errorEls = document.querySelectorAll('.error-message, .alert, [class*="error"], [class*="alert"], .captcha, .challenge');
                r.errors = Array.from(errorEls).map(e => ({
                    text: e.textContent.trim().substring(0, 80),
                    cls: e.className,
                    display: e.offsetParent !== null ? 'visible' : 'hidden'
                }));
                
                // Check for iframes (captcha usually in iframe)
                const iframes = document.querySelectorAll('iframe');
                r.iframes = Array.from(iframes).map(f => ({
                    src: f.src.substring(0, 100),
                    display: f.offsetParent !== null ? 'visible' : 'hidden',
                    id: f.id
                }));
                
                // Check for arkose/captcha divs
                const allDivs = document.querySelectorAll('div');
                r.funcaptcha_divs = Array.from(allDivs)
                    .filter(d => d.id.toLowerCase().includes('funcaptcha') || 
                           d.className.toLowerCase().includes('funcaptcha') ||
                           d.id.toLowerCase().includes('captcha') ||
                           d.className.toLowerCase().includes('captcha') ||
                           d.id.toLowerCase().includes('challenge') ||
                           d.className.toLowerCase().includes('challenge'))
                    .map(d => ({
                        id: d.id.substring(0, 40),
                        cls: d.className.substring(0, 40),
                        display: d.offsetParent !== null ? 'visible' : 'hidden',
                        html: d.innerHTML.substring(0, 100)
                    }));
                
                // Check body content near submit
                const body = document.body ? document.body.textContent : '';
                r.body_snippets = [
                    body.includes('challenge') ? 'has_challenge' : '',
                    body.includes('captcha') ? 'has_captcha' : '',
                    body.includes('DENIED') ? 'has_DENIED' : '',
                    body.includes('verify') ? 'has_verify' : '',
                ].filter(Boolean);
                
                return JSON.stringify(r);
            })()"""
        })
        val = (diag or {}).get("result", {}).get("value", "{}")
        try:
            d = json.loads(val)
        except:
            print(f"  Raw: {val[:200]}")
            continue
        
        if d.get('iframes') and len(d['iframes']) > 0:
            print(f"  [{i*2}s] iframes: {d['iframes']}")
        if d.get('funcaptcha_divs') and len(d['funcaptcha_divs']) > 0:
            print(f"  [{i*2}s] captcha divs: {d['funcaptcha_divs']}")
        
        has_challenge = any('challenge' in str(s) for s in d.get('body_snippets', []))
        has_captcha = any('captcha' in str(s) for s in d.get('body_snippets', []))
        
        print(f"  [{i*2}s] url={d.get('url','')[:60]} errors={d.get('errors',[])} snippets={d.get('body_snippets',[])}")
        
        if has_challenge or has_captcha:
            print("  → Captcha/challenge detected!")
            break

    # Take screenshot
    ss = await cmd("Page.captureScreenshot", {"format": "png"})
    if ss:
        import base64 as b64
        with open("login_debug.png", "wb") as f:
            f.write(b64.b64decode(ss.get("data", "")))
        print("Screenshot saved: login_debug.png")

    await cdp.close()
    proc.kill()

asyncio.run(test())
