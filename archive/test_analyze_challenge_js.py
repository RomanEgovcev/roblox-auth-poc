"""Download and analyze Challenge.js for POW algorithm."""
import os, time, json, re

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    # Capture Challenge.js content
    challenge_js = ['']
    page.on("response", lambda r: challenge_js.__setitem__(0, r.text()) if 'Challenge.js' in r.url else None)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(5)
    
    # Trigger challenge loading
    page.evaluate(f"""() => {{
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        const u = document.getElementById('login-username');
        const p = document.getElementById('login-password');
        if (u) {{ setter.call(u, 'testuser123'); u.dispatchEvent(new Event('input', {{bubbles: true}})); }}
        if (p) {{ setter.call(p, 'TestPassword123!'); p.dispatchEvent(new Event('input', {{bubbles: true}})); }}
    }}""")
    page.click('.login-button', timeout=5000)
    time.sleep(5)
    
    js = challenge_js[0]
    if not js:
        print("Challenge.js not captured!", flush=True)
        browser.close()
        exit()
    
    print(f"Challenge.js length: {len(js)} bytes", flush=True)
    
    # Search for keywords related to POW
    keywords = ['proofofwork', 'proofOfWork', 'proof_of_work', 'PoW', 'pow', 'difficulty', 'nonce', 'sha256', 'md5', 'hash', 'compute', 'solver', 'solution']
    
    for kw in keywords:
        positions = [m.start() for m in re.finditer(kw, js, re.IGNORECASE)]
        if positions:
            print(f"\n'{kw}' found at positions: {positions[:5]}", flush=True)
            # Show surrounding context for first occurrence
            pos = positions[0]
            start = max(0, pos - 100)
            end = min(len(js), pos + 200)
            context = js[start:end]
            print(f"  Context: ...{context}...", flush=True)
    
    # Also look for generic challenge handler
    for keyword in ['generic', 'GenericChallenge', 'challengeHandler', 'handler']:
        positions = [m.start() for m in re.finditer(keyword, js, re.IGNORECASE)]
        if positions:
            print(f"\n'{keyword}' found at positions: {positions[:3]}", flush=True)
            pos = positions[0]
            context = js[max(0,pos-50):min(len(js),pos+300)]
            print(f"  Context: ...{context}...", flush=True)
    
    # Save JS to file for analysis
    with open('challenge_js_content.txt', 'w', encoding='utf-8') as f:
        f.write(js)
    print(f"\nSaved to challenge_js_content.txt", flush=True)
    
    time.sleep(2)
    browser.close()
