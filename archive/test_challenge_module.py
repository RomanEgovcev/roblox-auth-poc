"""Explore Roblox.Challenge and challenge flow."""
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
    
    # Check what challenge-related objects exist
    objs = page.evaluate("""() => {
        const results = {};
        // Check Roblox namespace
        if (window.Roblox) {
            results.RobloxKeys = Object.keys(window.Roblox);
            if (window.Roblox.Challenge) {
                results.ChallengeKeys = Object.keys(window.Roblox.Challenge);
                results.ChallengeProto = {};
                for (const k of Object.keys(window.Roblox.Challenge)) {
                    const v = window.Roblox.Challenge[k];
                    if (typeof v === 'function') {
                        results.ChallengeProto[k] = v.toString().substring(0, 200);
                    } else {
                        results.ChallengeProto[k] = typeof v;
                    }
                }
            }
        }
        // Check for challenge-related globals
        results.globalChallengeKeys = Object.keys(window).filter(k => 
            k.toLowerCase().includes('challenge') || k.toLowerCase().includes('captcha'));
        return results;
    }""")
    print("Roblox.Challenge:", flush=True)
    for k, v in objs.items():
        if isinstance(v, dict):
            print(f"  {k}:", flush=True)
            for k2, v2 in v.items():
                print(f"    {k2}: {str(v2)[:150]}", flush=True)
        else:
            print(f"  {k}: {str(v)[:200]}", flush=True)
    
    # Get full challenge metadata (raw)
    csrf = page.evaluate(f"""() => {{
        return fetch('https://auth.roblox.com/v2/login', {{
            method: 'POST', credentials: 'include',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}),
        }}).then(r => r.headers.get('x-csrf-token'));
    }}""")
    
    chall_data = page.evaluate(f"""() => {{
        return new Promise((resolve) => {{
            const xhr = new XMLHttpRequest();
            xhr.open('POST', 'https://auth.roblox.com/v2/login', true);
            xhr.setRequestHeader('Content-Type', 'application/json');
            xhr.setRequestHeader('x-csrf-token', '{csrf}');
            xhr.withCredentials = true;
            xhr.onload = function() {{
                const headers = {{}};
                xhr.getAllResponseHeaders().trim().split('\\n').forEach(h => {{
                    const [k, ...v] = h.split(':');
                    if (k && v.length) headers[k.trim().toLowerCase()] = v.join(':').trim();
                }});
                resolve({{status: xhr.status, headers: headers}});
            }};
            xhr.onerror = () => resolve({{error: 'XHR failed'}});
            xhr.send(JSON.stringify({{ctype:'Username', cvalue:'{USER}', password:'{PASS}'}}));
        }});
    }}""")
    
    chall_meta_b64 = chall_data.get('headers', {}).get('rblx-challenge-metadata', '')
    if chall_meta_b64:
        # Add padding if needed
        padded = chall_meta_b64 + '=' * (4 - len(chall_meta_b64) % 4) if len(chall_meta_b64) % 4 else chall_meta_b64
        try:
            raw = base64.b64decode(padded)
            print(f"\nMetadata raw bytes ({len(raw)}): {raw}", flush=True)
            print(f"Metadata decoded: {raw.decode('utf-8', errors='replace')}", flush=True)
        except Exception as e:
            print(f"\nMetadata decode error: {e}", flush=True)
            print(f"Metadata raw base64: {chall_meta_b64}", flush=True)
    
    time.sleep(2)
    browser.close()
