"""Download and analyze Roblox's Challenge.js and CaptchaCore.js."""
import os, time, json, base64, re

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
    
    downloaded = {}
    
    def capture_js(response):
        url = response.url
        for name in ['Challenge.js', 'CaptchaCore.js', 'Captcha.js', 'ReactLogin.js']:
            if name in url:
                if url not in downloaded:
                    try:
                        body = response.text()
                        # Only keep first 500 chars
                        downloaded[url] = body[:2000]
                        print(f"[+] Downloaded {name} ({len(body)} bytes)", flush=True)
                    except:
                        pass
    
    page.on("response", capture_js)
    
    def intercept(route):
        url = route.request.url
        if 'main.min.js' in url and ('px-cloud' in url or 'px-cdn' in url):
            route.fulfill(status=200, body=patched, content_type='application/javascript')
        else:
            route.continue_()
    
    page.route("**/main.min.js", intercept)
    
    page.goto("https://www.roblox.com/login", wait_until="networkidle")
    time.sleep(3)
    
    print(f"\nDownloaded {len(downloaded)} files:", flush=True)
    for url, body in downloaded.items():
        name = url.split('/')[-1][:50]
        print(f"\n--- {name} ---", flush=True)
        # Print first 1000 chars
        print(body[:1000], flush=True)
        print("...", flush=True)
    
    time.sleep(3)
    browser.close()
