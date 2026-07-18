"""Focus: click Log In button correctly on /login page."""
import os, time, subprocess, json, urllib.request, sys, threading, random, string

proxy_dir = "C:\\Users\\regov\\Desktop\\lua"

proxy_proc = subprocess.Popen(
    [sys.executable, f"{proxy_dir}\\local_proxy.py"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
proxy_lines = []
def log_proxy():
    for l in iter(proxy_proc.stdout.readline, ''):
        l = l.rstrip(); proxy_lines.append(l); print(f"[P] {l}", flush=True)
threading.Thread(target=log_proxy, daemon=True).start()
time.sleep(3)

opener = urllib.request.build_opener(urllib.request.ProxyHandler({'https': 'http://127.0.0.1:8888'}))
try:
    assert opener.open('https://api.nopecha.com/v1/status', timeout=10).status == 200
    print("[+] Proxy OK", flush=True)
except: print("[-] Proxy DEAD", flush=True); proxy_proc.kill(); exit(1)

chrome_proc = subprocess.Popen(
    ["C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
     f"--user-data-dir={proxy_dir}\\pw_profile",
     f"--load-extension={proxy_dir}\\chromium_automation",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*",
     "--proxy-server=http://127.0.0.1:8888",
     "--ignore-certificate-errors",
     "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(5)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.set_default_timeout(15000)
    page.on("console", lambda msg: print(f"[CONSOLE {msg.type}] {msg.text[:200]}", flush=True))

    # Go to /login
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(3)

    for attempt in range(60):
        user = ''.join(random.choices(string.ascii_lowercase, k=6))
        try:
            page.fill("input[name='username']", user, timeout=3000)
            page.fill("input[name='password']", "wrong123!", timeout=3000)
            page.click("#login-button", timeout=3000)
        except:
            page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=10000)
            page.fill("input[name='username']", user)
            page.fill("input[name='password']", "wrong123!")
            page.click("#login-button")
        
        if attempt % 5 == 0:
            print(f"[*] Attempt {attempt+1}", flush=True)
        
        # Quick captcha check
        frames = page.evaluate("""() => {
            const f = document.querySelectorAll('iframe');
            return Array.from(f).map(x => (x.src||'').slice(0,200)).filter(x => x.includes('arkoselabs') || x.includes('funcaptcha'));
        }""")
        if frames:
            print(f"[+] CAPTCHA at attempt {attempt+1}: {frames}", flush=True)
            for i in range(60):
                now = len([l for l in proxy_lines if 'api.nopecha.com' in l])
                if i % 10 == 0: print(f"  [{i}s] nopecha: {now}", flush=True)
                time.sleep(1)
            break
            
        time.sleep(0.3)

    api_hits = [l for l in proxy_lines if 'api.nopecha.com' in l]
    print(f"\n[*] api.nopecha.com: {len(api_hits)}")
    for l in api_hits: print(f"  {l}")

chrome_proc.kill(); proxy_proc.kill()
