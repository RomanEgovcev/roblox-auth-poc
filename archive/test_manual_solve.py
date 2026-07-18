import asyncio, json, base64, sys
sys.path.insert(0, r"C:\Users\regov\Desktop\lua")
from cdp_connect import OpenCDP

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
USER = "CheatingHitmanner"
PASS = ""

with open("last_captcha_blob.txt") as f:
    RAW_BLOB = f.read().strip()

async def cmd(ws, method, params=None):
    import json, uuid
    msg = json.dumps({"id": str(uuid.uuid4()), "method": method, "params": params or {}})
    ws.send(msg)
    resp = json.loads(ws.recv())
    while resp.get("method"):
        resp = json.loads(ws.recv())
    return resp

async def main():
    cdp = OpenCDP(CHROME_PATH)
    ws_url = cdp.get_ws_url()
    if not ws_url:
        print("No WS URL")
        return
    import websockets
    async with websockets.connect(ws_url) as ws:
        await cmd(ws, "Page.enable")
        await cmd(ws, "Network.enable")
        
        print(f"Navigating to solver...")
        await cmd(ws, "Page.navigate", {"url": "http://localhost:8096/hundle/captcha_solver.html"})
        await asyncio.sleep(3)
        
        # — Inject modified blob with shouldAnalyze REMOVED —
        # Parse blob, remove shouldAnalyze
        import base64 as b64mod
        try:
            decoded = b64mod.b64decode(RAW_BLOB + "==").decode("utf-8")
            blob_data = json.loads(decoded)
            if "sharedParameters" in blob_data:
                blob_data["sharedParameters"]["shouldAnalyze"] = True  # enable real solving
            modified_blob = b64mod.b64encode(json.dumps(blob_data).encode()).decode()
            print(f"  Modified blob: shouldAnalyze set to TRUE")
        except Exception as e:
            print(f"  Could not modify blob: {e}, using raw")
            modified_blob = RAW_BLOB
        
        # Inject blob
        await cmd(ws, "Runtime.evaluate", {"expression": f"""
            document.getElementById('blob').value = {json.dumps(modified_blob)};
        """})
        await asyncio.sleep(0.5)
        
        # Click load
        await cmd(ws, "Runtime.evaluate", {"expression": "document.getElementById('load-btn').click()"})
        print("  Waiting for widget to load (20s)...")
        
        for i in range(20):
            await asyncio.sleep(1)
            state = await cmd(ws, "Runtime.evaluate", {"expression": "JSON.stringify({status: (document.getElementById('status')||{}).textContent, className: (document.getElementById('status')||{}).className})"})
            val = (state or {}).get("result", {}).get("value", "")
            print(f"  [{i}s] {val[:120]}")
            if "success" in val or "Токен" in val:
                token_el = await cmd(ws, "Runtime.evaluate", {"expression": "document.getElementById('token-field').textContent"})
                token_val = (token_el or {}).get("result", {}).get("value", "")
                print(f"\n  ✅ TOKEN: {token_val[:80]}...")
                with open("real_solved_token.txt", "w") as f:
                    f.write(token_val)
                break
            # Take screenshot to see visual state
            if i == 5:
                ss = await cmd(ws, "Page.captureScreenshot", {"format": "png"})
                if ss:
                    import base64 as b64mod2
                    with open("manual_solve_state.png", "wb") as f:
                        f.write(b64mod2.b64decode(ss.get("data", "")))
                    print("  Screenshot saved: manual_solve_state.png")
        
        await asyncio.sleep(60)  # keep browser open for manual solving
        await cmd(ws, "Browser.close")

asyncio.run(main())
