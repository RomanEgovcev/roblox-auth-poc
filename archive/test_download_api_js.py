"""Load api.js on fresh page and capture its content/initialization."""
import os, time, json, re

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

# First, download api.js directly
import urllib.request
print("[1] Downloading api.js...", flush=True)
req = urllib.request.Request(
    'https://arkoselabs.roblox.com/v2/476068BF-9607-4799-B53D-966BE98E2B81/api.js',
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
)
try:
    resp = urllib.request.urlopen(req)
    api_content = resp.read().decode('utf-8')
    print(f"  Downloaded: {len(api_content)} bytes", flush=True)
    
    # Save it for analysis
    with open('api.js.downloaded.js', 'w', encoding='utf-8') as f:
        f.write(api_content)
    print(f"  Saved to api.js.downloaded.js", flush=True)
    
    # Find the variable name it sets
    for pattern in [r'window\.(\w+)\s*=', r'window\[[\'"](\w+)[\'"]\]\s*=', r'window\.(\w+)\s*\|\|']:
        m = re.search(pattern, api_content)
        if m:
            print(f"  Variable pattern '{pattern}': {m.group(1)}", flush=True)
    
    # Search for specific code patterns
    for keyword in ['arkose', 'funcaptcha', 'enforcement', 'challenge']:
        idx = api_content.find(keyword)
        if idx >= 0:
            print(f"  Found '{keyword}' at pos {idx}", flush=True)
except Exception as e:
    print(f"  Error: {e}", flush=True)

# Now load on page and check carefully
print("\n[2] Loading on fresh page...", flush=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(3)
    
    # Load api.js via add_script_tag
    print("  Loading api.js...", flush=True)
    page.add_script_tag(url='https://arkoselabs.roblox.com/v2/476068BF-9607-4799-B53D-966BE98E2B81/api.js')
    time.sleep(2)
    
    # Check ALL window keys for the api variable
    print("\n[3] Checking ALL window keys for API object...", flush=True)
    result = page.evaluate("""() => {
        const keys = Object.keys(window);
        // Find keys that look like the Arkose API (long, has underscore)
        const apiCandidates = keys.filter(k => 
            (k.startsWith('arkose') || k.startsWith('Ark') || k.startsWith('_Ark') || 
             (k.length > 20 && (k.includes('Client') || k.includes('Api') || k.includes('Labs'))))
        );
        const info = {};
        for (const k of apiCandidates) {
            const v = window[k];
            info[k] = {
                type: typeof v,
                defined: k in window,
                own: window.hasOwnProperty(k),
                valueIfObj: typeof v === 'object' && v ? Object.keys(v).slice(0, 10) : null,
            };
        }
        return info;
    }""")
    print(f"  Candidates: {json.dumps(result, indent=2)[:800]}", flush=True)
    
    # Also monitor requests for gt2
    print("\n[4] Calling gt2 from this page context...", flush=True)
    gt2 = page.evaluate("""async () => {
        try {
            const resp = await fetch('https://arkoselabs.roblox.com/fc/gt2/public_key/476068BF-9607-4799-B53D-966BE98E2B81?callback=cb');
            const text = await resp.text();
            return {status: resp.status, text: text.substring(0, 500)};
        } catch(e) {
            return {error: e.message};
        }
    }""")
    print(f"  GT2: {json.dumps(gt2)[:500]}", flush=True)
    
    time.sleep(3)
    browser.close()
