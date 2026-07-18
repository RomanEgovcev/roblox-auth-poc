"""Check login page structure"""
import asyncio, websockets, json, http.client, subprocess, time, shutil, os

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9233
FRESH_DIR = os.path.abspath("chrome_check_test")

async def test():
    if os.path.exists(FRESH_DIR):
        shutil.rmtree(FRESH_DIR)

    proc = subprocess.Popen([
        CHROME, f"--user-data-dir={FRESH_DIR}",
        "--no-first-run", "--no-default-browser-check",
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-allow-origins=*",
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
    async def cmd(method, params=None, timeout_s=10):
        nonlocal msg_id; msg_id += 1
        future = asyncio.get_event_loop().create_future()
        pending[msg_id] = future
        await cdp.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        return await asyncio.wait_for(future, timeout=timeout_s)

    async def reader():
        async for raw in cdp:
            data = json.loads(raw)
            rid = data.get("id")
            if rid in pending:
                pending[rid].set_result(data.get("result", {}))
                del pending[rid]

    asyncio.create_task(reader())
    await cmd("Page.enable", {})
    await cmd("Page.navigate", {"url": "https://www.roblox.com/login"})
    await asyncio.sleep(5)

    # Dump page structure
    res = await cmd("Runtime.evaluate", {
        "expression": """(() => {
            const inputs = document.querySelectorAll('input');
            const buttons = document.querySelectorAll('button');
            return JSON.stringify({
                url: location.href,
                inputs: Array.from(inputs).map(i => ({
                    id: i.id, name: i.name, type: i.type,
                    placeholder: i.placeholder || '',
                    class: i.className,
                    form: i.form ? i.form.id || 'has-form' : 'no-form'
                })),
                buttons: Array.from(buttons).map(b => ({
                    id: b.id, text: b.textContent.trim().substring(0, 30),
                    type: b.type, class: b.className
                })),
                forms: document.querySelectorAll('form').length
            });
        })()"""
    })
    val = (res or {}).get("result", {}).get("value", "{}")
    import json as j
    data = j.loads(val)
    print(f"URL: {data['url']}")
    print(f"Forms: {data['forms']}")
    print("Inputs:")
    for i in data['inputs']:
        print(f"  id={i['id']} name={i['name']} type={i['type']} placeholder={i['placeholder'][:30]} form={i['form']}")
    print("Buttons:")
    for b in data['buttons']:
        print(f"  id={b['id']} text='{b['text'][:40]}' type={b['type']}")
    print("\nCheck: is there a captcha iframe?")
    res2 = await cmd("Runtime.evaluate", {
        "expression": """(() => {
            const iframes = document.querySelectorAll('iframe');
            return JSON.stringify(iframes.length + ' iframes, srcs: ' + Array.from(iframes).map(f => f.src.substring(0,60)).join(', '));
        })()"""
    })
    print((res2 or {}).get("result", {}).get("value", "N/A"))

    await cdp.close()
    proc.kill()

asyncio.run(test())
