"""
Open login page, trigger captcha, then dump page JS variables and DOM
to find where captcha token is stored.
"""
import asyncio, websockets, json, http.client, subprocess, time, shutil, os, random, base64, glob

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9260
FRESH_DIR = os.path.abspath(f"chrome_debug_{random.randint(10000,99999)}")
USER = "CheatingHitmanner"
PASS = "LolKekZek228"

async def main():
    for d in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_debug_*")):
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

    # Navigate to login
    await cmd("Page.navigate", {"url": "https://www.roblox.com/login"})
    for i in range(30):
        await asyncio.sleep(1)
        ready = await cmd("Runtime.evaluate", {"expression": "!!document.querySelector('#login-button')"})
        if (ready or {}).get("result", {}).get("value"):
            print(f"Page ready at ~{i}s"); break
    else:
        print("Page didn't load"); return

    # Fill credentials and click login
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
    await cmd("Runtime.evaluate", {"expression": "document.querySelector('#login-button')?.click()"})

    # Wait for captcha to appear
    print("Waiting for captcha (15s)...")
    await asyncio.sleep(15)

    # Dump page state
    print("\n=== Page state after captcha trigger ===")

    # Look for captcha-related globals
    for var_name in ["__captchaToken", "captchaToken", "_captchaToken", "__captcha", "g_captchaToken", "captchaData",
                     "challengeData", "_challengeData", "__challenge", "recaptchaToken", "g_recaptcha"]:
        r = await cmd("Runtime.evaluate", {"expression": f"typeof window.{var_name} !== 'undefined' ? JSON.stringify(window.{var_name}).substring(0,200) : 'undefined'"})
        val = (r or {}).get("result", {}).get("value", "")
        if val != "undefined" and val:
            print(f"  {var_name}: {val[:200]}")

    # Check all iframes
    r = await cmd("Runtime.evaluate", {"expression": "document.querySelectorAll('iframe').length"})
    iframe_count = (r or {}).get("result", {}).get("value", 0)
    print(f"\n  Iframes on page: {iframe_count}")
    
    for i in range(iframe_count):
        r = await cmd("Runtime.evaluate", {"expression": f"document.querySelectorAll('iframe')[{i}].src || 'no-src'"})
        src = (r or {}).get("result", {}).get("value", "")
        print(f"  iframe[{i}]: {src[:120]}")

    # Check login form
    r = await cmd("Runtime.evaluate", {"expression": f"""(() => {{
        const f = document.querySelector('form');
        if (!f) return 'no form';
        const inputs = Array.from(f.querySelectorAll('input')).map(i => i.name + '=' + i.value.substring(0,20));
        return 'form inputs: ' + inputs.join(', ');
    }})()"""})
    print(f"\n  Form: {(r or {}).get('result',{}).get('value','')[:200]}")

    # Check for captcha-related elements
    r = await cmd("Runtime.evaluate", {"expression": f"""(() => {{
        const all = document.querySelectorAll('*');
        const results = [];
        for (const el of all) {{
            if (el.id && (el.id.toLowerCase().includes('captcha') || el.id.toLowerCase().includes('challenge')))
                results.push('#' + el.id + ' (' + el.tagName + ')');
            if (el.className && typeof el.className === 'string' && 
                (el.className.toLowerCase().includes('captcha') || el.className.toLowerCase().includes('challenge')))
                results.push('.' + el.className.substring(0,30) + ' (' + el.tagName + ')');
        }}
        return results.slice(0,20).join(', ');
    }})()"""})
    print(f"\n  Captcha elements: {(r or {}).get('result',{}).get('value','none')[:300]}")

    # Check Arkose/Prove related window properties
    for prop in ["Pi", "ARKOSE", "arkose", "_px", "px", "Prove"]:
        r = await cmd("Runtime.evaluate", {"expression": f"typeof window.{prop} !== 'undefined' ? 'defined' : 'undefined'"})
        print(f"  window.{prop}: {(r or {}).get('result',{}).get('value','?')}")

    # Check if any script added captcha token handler
    r = await cmd("Runtime.evaluate", {"expression": f"""(() => {{
        const scripts = document.querySelectorAll('script');
        for (const s of scripts) {{
            const t = s.textContent || '';
            if (t.includes('captchaToken') || t.includes('captchaProvider'))
                return t.substring(0, 500);
        }}
        return 'not found';
    }})()"""})
    print(f"\n  Script with captchaToken:\n    {(r or {}).get('result',{}).get('value','')[:500]}")

    # Take a screenshot
    ss = await cmd("Page.captureScreenshot", {"format": "png"})
    if ss:
        with open("debug_captcha_page.png", "wb") as f:
            f.write(base64.b64decode(ss.get("data", "")))
        print("\nScreenshot saved: debug_captcha_page.png")

    print("\nBrowser open for 60s - inspect manually.")
    await asyncio.sleep(60)
    proc.kill()
    await cdp.close()

if __name__ == "__main__":
    asyncio.run(main())
