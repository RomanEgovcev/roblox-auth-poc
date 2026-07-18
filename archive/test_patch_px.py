"""Patch PX main.min.js - fix CSP eval issue."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

# Fix 1: Replace CSP-unsafe 'new Function("return this")()' with simple window ref
patched = px_script.replace(
    'new Function("return this")()',
    "(window||self||globalThis)"
)

if patched == px_script:
    print("[-] new Function pattern not found!", flush=True)
else:
    print("[+] Patched new Function -> window", flush=True)

# Fix 2: Wrap IIFE body in try-catch to survive CSP blocks
# The IIFE starts right after 'try {(function() {' in the original
# We add an inner try{ after the IIFE opening
old = "try {(function() {"
new = "try {(function() { try {"
if old in patched:
    patched = patched.replace(old, new, 1)
    print("[+] Added inner try block", flush=True)
else:
    print("[-] IIFE pattern not found!", flush=True)

# Fix 3: Close the inner try-catch before the outer })();
# The IIFE closes with '})();}catch(e){' 
# We need to add '}catch(e){}' before '})();'
old2 = "})();}catch(e){"
new2 = "}catch(e){} })();}catch(e){"
if old2 in patched:
    patched = patched.replace(old2, new2, 1)
    print("[+] Added inner catch block", flush=True)
else:
    print("[-] Close pattern not found!", flush=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    auth = []
    eval_errors = []
    
    def track(r):
        if 'auth.roblox' in r.url:
            auth.append({"url": r.url[:100], "status": r.status})
    page.on("response", track)
    
    def on_console(msg):
        if 'EvalError' in msg.text:
            eval_errors.append(msg.text[:150])
            print(f"[!] EvalError: {msg.text[:100]}", flush=True)
    page.on("console", on_console)
    
    def intercept(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            print(f"[*] Patching PX script", flush=True)
            route.fulfill(status=200, body=patched, content_type='application/javascript')
        elif 'init.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body='', content_type='application/javascript')
        elif 'collector' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body='[]', content_type='text/plain')
        else:
            route.continue_()
    
    page.route("**/*", intercept)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    print(f"[*] Page loaded. EvalErrors: {len(eval_errors)}", flush=True)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    print("[*] Clicking login...", flush=True)
    page.click("#login-button", timeout=5000)
    
    for i in range(30):
        if auth:
            print(f"[+] Auth at {i}s: {auth[-1]}", flush=True)
            break
        time.sleep(0.5)
    else:
        print(f"[-] No auth. EvalErrors: {len(eval_errors)}", flush=True)
    
    page.screenshot(path="patched_px.png")
    input("Enter...")
    browser.close()
