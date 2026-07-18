"""
Test fetch login with captcha token in browser context.
No Fetch interception, no solver — just test the API call.
"""
import asyncio, websockets, json, http.client, subprocess, time, shutil, os

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9245
FRESH_DIR = os.path.abspath(f"chrome_fetch_test_{int(time.time())}")

async def main():
    for d in glob.glob("chrome_fetch_test_*"):
        try: shutil.rmtree(d)
        except: pass

    proc = subprocess.Popen([
        CHROME, f"--user-data-dir={FRESH_DIR}",
        "--no-first-run", "--no-default-browser-check",
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-allow-origins=*",
        "--window-size=1000,800",
        "--new-window", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for i in range(30):
        try:
            conn = http.client.HTTPConnection("localhost", CDP_PORT, timeout=3)
            conn.request("GET", "/json"); resp = conn.getresponse()
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
    asyncio.create_task(reader())
    await cmd("Page.enable")
    await cmd("Network.enable")

    # Get a valid token from the last run
    token = "27518c31b7a5b7915.8352373805|r=eu-west-1|meta=3|metabgclr=transparent|metaiconclr=|meta_1=1|meta_2=1|meta_3=1|guitextcolor=%23000000|metabgclr=%23FFFFFF|meta_4=1|meta_5=1|meta_6=1|pk=476068BF-9607-4799-B53D-966BE98E2B81|at=40|sup=1|rid=3|ag=101|cdn_url=https%3A%2F%2Froblox-api.arkoselabs.com%2Fcdn%2Fjpzb3qph%2F|surl=https%3A%2F%2Froblox-api.arkoselabs.com%2F|sm=2|dp=0|lpurl=https%3A%2F%2Froblox-api.arkoselabs.com%2F|lt=0|pba=15|emb=0"

    await cmd("Page.navigate", {"url": "https://www.roblox.com/login"})
    await asyncio.sleep(5)

    # Wait for login page
    for i in range(10):
        await asyncio.sleep(1)
        ready = await cmd("Runtime.evaluate", {"expression": "!!document.querySelector('#login-username')"})
        if (ready or {}).get("result", {}).get("value"):
            print(f"  Login page ready"); break
    else:
        print("Page not ready"); return

    # Test 1: Simple GET to test fetch
    print("\nTest 1: Simple fetch GET")
    r1 = await cmd("Runtime.evaluate", {
        "expression": "fetch('https://www.roblox.com/login').then(r => 'status: ' + r.status).catch(e => 'error: ' + e.message)"
    })
    print(f"  Result: {(r1 or {}).get('result', {}).get('value', 'N/A')}")

    # Test 2: Fetch v2/login with random creds (should get 401 or 403)
    print("\nTest 2: Fetch v2/login (no captcha)")
    r2 = await cmd("Runtime.evaluate", {
        "expression": """(() => {
            const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute('data-token') || '';
            return fetch('https://auth.roblox.com/v2/login', {
                method: 'POST',
                credentials: 'include',
                headers: {'Content-Type': 'application/json', 'X-CSRF-TOKEN': csrf},
                body: JSON.stringify({ctype: 'Username', cvalue: 'wrong', password: 'wrong'})
            }).then(async r => {
                const body = await r.text();
                return JSON.stringify({status: r.status, body: body.substring(0, 200)});
            }).catch(e => 'error: ' + e.message);
        })()"""
    })
    print(f"  Result: {(r2 or {}).get('result', {}).get('value', 'N/A')[:300]}")

    # Test 3: Fetch v2/login WITH token
    print("\nTest 3: Fetch v2/login WITH captcha token")
    r3 = await cmd("Runtime.evaluate", {
        "expression": f"""(() => {{
            const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute('data-token') || '';
            const controller = new AbortController();
            const t = setTimeout(() => controller.abort(), 10000);
            return fetch('https://auth.roblox.com/v2/login', {{
                method: 'POST',
                credentials: 'include',
                signal: controller.signal,
                headers: {{'Content-Type': 'application/json', 'X-CSRF-TOKEN': csrf}},
                body: JSON.stringify({{ctype: 'Username', cvalue: 'CheatingHitmanner', password: 'LolKekZek228', captchaToken: {json.dumps(token)}, captchaProvider: 'Prove'}})
            }}).then(async r => {{
                clearTimeout(t);
                const body = await r.text();
                return JSON.stringify({{status: r.status, body: body.substring(0, 300)}});
            }}).catch(e => {{ clearTimeout(t); return 'error: ' + e.message; }});
        }})()"""
    })
    print(f"  Result: {(r3 or {}).get('result', {}).get('value', 'N/A')[:400]}")

    await cdp.close(); proc.kill()

import glob
asyncio.run(main())
