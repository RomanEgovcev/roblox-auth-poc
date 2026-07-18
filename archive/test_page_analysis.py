"""Search page for Arkose/FunCaptcha related code and check if there's an alternative approach."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

patched = px_script
patched = patched.replace('new Function("return this")()', "(window||self||globalThis)")
patched = patched.replace("new EvalError", "new Error")

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    
    def intercept(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body=patched, content_type='application/javascript')
        else:
            route.continue_()
    
    page.route("**/main.min.js", intercept)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    # Search page source for Arkose-related content
    page_source = page.content()
    
    print(f"Page source length: {len(page_source)}", flush=True)
    
    arkose_patterns = ['arkose', 'funcaptcha', 'game-core', 'api.arkoselabs', 'client-api.arkoselabs',
                       'px-captcha', 'px.enforcement', 'enforcement', 'gameSight', 'Arcade.game']
    
    for pattern in arkose_patterns:
        if pattern.lower() in page_source.lower():
            idx = page_source.lower().index(pattern.lower())
            ctx = page_source[max(0, idx-100):idx+200]
            print(f"\n[+] Found '{pattern}' at {idx}:", flush=True)
            print(f"  ...{ctx}...", flush=True)
        else:
            print(f"[-] '{pattern}' NOT found", flush=True)
    
    # Check page scripts for Arkose URLs
    scripts = page.evaluate("""() => {
        return Array.from(document.scripts).map(s => ({
            src: s.src.substring(0, 150),
            id: s.id,
            type: s.type
        }));
    }""")
    print(f"\nScripts ({len(scripts)}):", flush=True)
    for s in scripts:
        if s['src']:
            print(f"  {s['src']}", flush=True)
    
    # Check for meta tags or data attributes with Arkose
    meta_info = page.evaluate("""() => {
        const metas = document.querySelectorAll('meta[name]');
        const result = {};
        metas.forEach(m => { result[m.getAttribute('name')] = m.getAttribute('content'); });
        return result;
    }""")
    print(f"\nMeta tags:", flush=True)
    for k, v in meta_info.items():
        if 'challenge' in k.lower() or 'captcha' in k.lower() or 'arkose' in k.lower():
            print(f"  {k}: {v}", flush=True)
    
    page.screenshot(path="page_analysis.png")
    time.sleep(5)
    browser.close()
