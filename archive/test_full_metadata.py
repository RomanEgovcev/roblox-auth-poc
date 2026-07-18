"""Extract full challenge metadata with puzzle parameters."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    csrf = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    print(f"CSRF: {csrf}", flush=True)
    
    # Capture full response
    result = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json', 'x-csrf-token': '{csrf}'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(async r => {{
            const headers = {{}};
            r.headers.forEach((v, k) => {{ headers[k] = v; }});
            const body = await r.text();
            return {{status: r.status, headers, body: body.substring(0, 2000)}};
        }});
    }}""")
    print(f"\nStatus: {result['status']}", flush=True)
    
    h = result['headers']
    chall_meta_b64 = h.get('rblx-challenge-metadata', '')
    chall_id = h.get('rblx-challenge-id', '')
    chall_type = h.get('rblx-challenge-type', '')
    
    print(f"Challenge: {chall_id} ({chall_type})", flush=True)
    print(f"Body: {result.get('body', '')[:300]}", flush=True)
    
    if chall_meta_b64:
        print(f"\nMetadata base64 length: {len(chall_meta_b64)}", flush=True)
        try:
            decoded = base64.b64decode(chall_meta_b64)
            print(f"Raw decoded: {decoded}", flush=True)
            print(f"\nFull decoded JSON:", flush=True)
            meta = json.loads(decoded)
            print(json.dumps(meta, indent=2), flush=True)
        except Exception as e:
            print(f"Decode error: {e}", flush=True)
            # Try with padding
            padded = chall_meta_b64 + '=' * (4 - len(chall_meta_b64) % 4) if len(chall_meta_b64) % 4 else chall_meta_b64
            try:
                decoded = base64.b64decode(padded)
                print(f"With padding: {decoded}", flush=True)
            except Exception as e2:
                print(f"With padding error: {e2}", flush=True)
    
    # Print ALL response headers  
    print(f"\nAll response headers:", flush=True)
    for k, v in sorted(h.items()):
        print(f"  {k}: {v[:200]}", flush=True)
    
    time.sleep(2)
    browser.close()
