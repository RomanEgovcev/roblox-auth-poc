"""Patch PX: fix both new Function() and EvalError fingerprinting."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

with open("main_min.js", "r", encoding="utf-8") as f:
    px_script = f.read()

patched = px_script

# Fix 1: Replace CSP-unsafe new Function
patched = patched.replace(
    'new Function("return this")()',
    "(window||self||globalThis)"
)

# Fix 2: Replace EvalError with Error (fingerprinting bypass)
patched = patched.replace(
    "new EvalError",
    "new Error"
)

print(f"[+] new Function patched: {patched != px_script}", flush=True)
print(f"[+] EvalError patched: {px_script.count('new EvalError')} -> {patched.count('new EvalError')}", flush=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    auth = []
    eval_errors = []
    
    def track(r):
        if 'auth.roblox' in r.url:
            auth.append({"url": r.url[:100], "status": r.status})
            print(f"[+] Auth: {r.status}", flush=True)
    page.on("response", track)
    
    def on_console(msg):
        t = msg.text
        if 'EvalError' in t:
            eval_errors.append(t[:200])
            print(f"[!] EvalError: {t[:100]}", flush=True)
    page.on("console", on_console)
    
    def intercept(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            print(f"[*] Serving double-patched PX", flush=True)
            route.fulfill(status=200, body=patched, content_type='application/javascript')
        else:
            route.continue_()
    
    page.route("**/main.min.js", intercept)
    
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
    
    game = [f for f in page.frames if 'game-core' in f.url]
    enf = [f for f in page.frames if 'enforcement' in f.url]
    print(f"[*] Frames: {len(page.frames)}, game-core: {len(game)}, enforcement: {len(enf)}", flush=True)
    
    page.screenshot(path="double_patched.png")
    input("Enter...")
    browser.close()
