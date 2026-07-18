"""Debug login form structure and submit via correct form reference."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.on("response", lambda r: print(f"  [{r.status}] {r.url[:200]}", flush=True) if 'auth.roblox.com' in r.url or 'arkoselabs.roblox.com' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(1)
    
    # Debug form structure
    print("[1] Form structure...", flush=True)
    form_info = page.evaluate("""() => {
        const forms = document.querySelectorAll('form');
        const info = [];
        forms.forEach((f, i) => {
            info.push({
                idx: i,
                id: f.id,
                action: f.action,
                method: f.method,
                children: Array.from(f.querySelectorAll('input, button')).slice(0, 5).map(el => ({
                    tag: el.tagName,
                    type: el.type,
                    name: el.name || '',
                    id: el.id || '',
                })),
            });
        });
        return info;
    }""")
    print(f"  Forms: {json.dumps(form_info, indent=2)[:600]}", flush=True)
    
    # Find the right form and submit
    form_index = None
    for fi in form_info:
        if fi.get('method', '').lower() == 'post':
            form_index = fi['idx']
            break
    
    if form_index is not None:
        print(f"\n[2] Submitting via form idx {form_index}...", flush=True)
        result = page.evaluate(f"""async (idx) => {{
            try {{
                const forms = document.querySelectorAll('form');
                const form = forms[idx];
                if (!form) return {{error: 'no form at idx ' + idx}};
                const fd = new FormData(form);
                // Add username and password if not present
                const inputs = form.querySelectorAll('input');
                inputs.forEach(i => {{
                    if (i.name && i.value) {{
                        fd.set(i.name, i.value);
                    }}
                }});
                const resp = await fetch('/v2/login', {{
                    method: 'POST',
                    body: fd,
                    credentials: 'include',
                }});
                const text = await resp.text();
                const headers = {{}};
                resp.headers.forEach((v, k) => {{
                    if (k.startsWith('rblx') || k === 'content-type') headers[k] = v;
                }});
                return {{
                    status: resp.status,
                    headers: JSON.stringify(headers).substring(0, 300),
                    bodyLen: text.length,
                    bodyPreview: text.substring(0, 200),
                }};
            }} catch(e) {{
                return {{error: e.message}};
            }}
        }}""", form_index)
        print(f"  Result: {json.dumps(result)[:500]}", flush=True)
    else:
        print("  No POST form found!", flush=True)
    
    time.sleep(5)
    
    # Check for enforcement
    print(f"\n[3] Checking frames...", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:200]}", flush=True)
    
    time.sleep(3)
    browser.close()
