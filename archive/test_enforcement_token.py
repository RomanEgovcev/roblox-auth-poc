"""Try enforcement iframe with random challenge token."""
import os, time, json, uuid

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

PUBLIC_KEY = "476068BF-9607-4799-B53D-966BE98E2B81"
CHALLENGE_TOKEN = str(uuid.uuid4())
ENFORCEMENT_HASH = f"enforcement.162a14c47922edcced45ca4d9b28e5d5.html"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    def log_resp(r):
        url = r.url
        if any(x in url for x in ['arkoselabs', 'enforcement', 'game-core', 'gt2', 'api.js', 'settings', 'pow']):
            short = url[40:200] if len(url) > 40 else url
            print(f"  [{r.status}] {short}", flush=True)
    
    page.on("response", log_resp)
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Create enforcement iframe with hash directly
    print(f"\n[1] Injecting enforcement iframe with token: {CHALLENGE_TOKEN}", flush=True)
    page.evaluate(f"""() => {{
        const enfUrl = 'https://arkoselabs.roblox.com/fc/assets/{ENFORCEMENT_HASH}#{PUBLIC_KEY}&{CHALLENGE_TOKEN}';
        const iframe = document.createElement('iframe');
        iframe.src = enfUrl;
        iframe.id = '__enforcement_test';
        iframe.style.width = '1px';
        iframe.style.height = '1px';
        document.body.appendChild(iframe);
        console.log('Enforcement iframe created:', enfUrl);
    }}""")
    
    # Watch for APIs
    print("[2] Watching for 30s...", flush=True)
    for i in range(60):
        frames = [(f.url, f.name) for f in page.frames]
        for url, name in frames:
            if 'game-core' in url:
                print(f"  [+] Game-core at {i*0.5:.0f}s!", flush=True)
                break
        if any('game-core' in url for url, _ in frames):
            break
        time.sleep(0.5)
    
    print(f"\n=== Frames ===", flush=True)
    for i, (url, name) in enumerate(set(frames)):
        print(f"  [{i}] {url[:200]} (name={name})", flush=True)
    
    time.sleep(3)
    browser.close()
