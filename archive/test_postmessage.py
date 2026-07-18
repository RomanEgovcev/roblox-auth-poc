"""Monitor postMessage between enforcement iframe and parent page."""
import os, time, json, base64, sys

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    # Intercept postMessage
    page.add_init_script("""
    window._postMessages = [];
    const origPostMessage = window.postMessage;
    window.postMessage = function(msg, target, transfer) {
        try {
            const msgStr = typeof msg === 'string' ? msg.substring(0, 500) : JSON.stringify(msg).substring(0, 500);
            window._postMessages.push({sent: true, msg: msgStr, time: Date.now()});
        } catch(e) {
            window._postMessages.push({sent: true, msg: '(error: ' + e.message + ')', time: Date.now()});
        }
        return origPostMessage.call(this, msg, target, transfer);
    };
    
    window.addEventListener('message', function(event) {
        try {
            const msgStr = typeof event.data === 'string' ? event.data.substring(0, 500) : JSON.stringify(event.data).substring(0, 500);
            window._postMessages.push({received: true, origin: event.origin, msg: msgStr, time: Date.now()});
        } catch(e) {}
    });
    """)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    # Track Arkose responses
    arkose_resp = []
    page.on("response", lambda r: arkose_resp.append(f"[{r.status}] {r.url[:200]}") 
             if 'arkoselabs.roblox.com' in r.url else None)
    
    # Trigger enforcement via Enter key dispatch
    print("[1] Dispatching Enter on password field...", flush=True)
    page.evaluate("""() => {
        const pw = document.querySelector('input[name="password"]');
        if (pw) {
            pw.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true}));
            pw.dispatchEvent(new KeyboardEvent('keypress', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true}));
            pw.dispatchEvent(new KeyboardEvent('keyup', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true}));
        }
    }""")
    
    # Wait for enforcement
    print("[2] Waiting for enforcement + postMessages (30s)...", flush=True)
    enf_frame = None
    for i in range(60):
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf_frame = f
                break
        if enf_frame:
            print(f"  [+] Enforcement at {i*0.5:.0f}s!", flush=True)
            break
        time.sleep(0.5)
    
    if not enf_frame:
        print("  [-] No enforcement. Trying keyboard.press Enter...", flush=True)
        page.keyboard.press("Enter")
        time.sleep(10)
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf_frame = f
                break
    
    if not enf_frame:
        print("  [-] Still no enforcement.", flush=True)
    
    # Get postMessages
    msgs = page.evaluate("""() => window._postMessages || []""")
    print(f"\n=== PostMessages captured ({len(msgs)}) ===", flush=True)
    for m in msgs[-30:]:
        t = m.get('time', 0)
        msg = m.get('msg', '')[:300]
        origin = m.get('origin', '')
        received = m.get('received', False)
        direction = '← RECV' if received else '→ SEND'
        print(f"  {direction} {msg}", flush=True)
    
    if enf_frame:
        print(f"\n=== Enforcement URL ===", flush=True)
        print(f"  {enf_frame.url[:250]}", flush=True)
        
        # Check enforcement state
        try:
            enf_state = enf_frame.evaluate("""() => ({
                bodyLen: document.body?.innerHTML?.length || 0,
                appHTML: document.getElementById('app')?.innerHTML?.substring(0, 400) || 'N/A',
            })""")
            print(f"\n=== Enforcement state ===", flush=True)
            print(f"  {json.dumps(enf_state)[:500]}", flush=True)
            
            # Check for verification token
            vt = enf_frame.evaluate("""() => {
                const el = document.getElementById('verification-token');
                return el ? el.value.substring(0, 300) : 'N/A';
            }""")
            print(f"\n  Verification token: {vt}", flush=True)
        except Exception as e:
            print(f"  Error: {e}", flush=True)
    
    print(f"\n=== Arkose API ({len(arkose_resp)}) ===", flush=True)
    for r in arkose_resp:
        print(f"  {r}", flush=True)
    
    print(f"\n=== Frames ===", flush=True)
    for fi, f in enumerate(page.frames):
        print(f"  [{fi}] {f.url[:180]}", flush=True)
    
    page.screenshot(path="postmessage_debug.png")
    time.sleep(10)
    browser.close()
