"""Full integration test: proxy + extension + captcha auto-solve."""
import os, time, subprocess, json, urllib.request, sys, threading

proxy_dir = "C:\\Users\\regov\\Desktop\\lua"

# --- Start proxy ---
proxy_proc = subprocess.Popen(
    [sys.executable, f"{proxy_dir}\\local_proxy.py"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

proxy_log = []
def print_proxy():
    for line in iter(proxy_proc.stdout.readline, ''):
        line = line.rstrip()
        proxy_log.append(line)
        print(f"[PROXY] {line}", flush=True)
threading.Thread(target=print_proxy, daemon=True).start()
time.sleep(3)

# Verify proxy
proxy_handler = urllib.request.ProxyHandler({'https': 'http://127.0.0.1:8888'})
opener = urllib.request.build_opener(proxy_handler)
try:
    resp = opener.open('https://api.nopecha.com/v1/status', timeout=10)
    print(f"[+] Proxy OK: {resp.status}", flush=True)
except Exception as e:
    print(f"[-] Proxy failed: {e}", flush=True); proxy_proc.kill(); exit(1)

# --- Launch Chrome ---
chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext_path = f"{proxy_dir}\\chromium_automation"
profile = f"{proxy_dir}\\pw_profile"

chrome_proc = subprocess.Popen(
    [chrome_path, f"--user-data-dir={profile}", f"--load-extension={ext_path}",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*",
     "--proxy-server=http://127.0.0.1:8888",
     "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("[*] Chrome launched", flush=True)
time.sleep(5)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = None
    for attempt in range(10):
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            print("[+] CDP connected", flush=True)
            break
        except Exception as e:
            if attempt == 9: print(f"[-] CDP failed: {e}", flush=True); exit(1)
            time.sleep(2)
    
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.set_default_timeout(20000)
    
    page.on("console", lambda msg: print(f"[PAGE {msg.type}] {msg.text[:200]}", flush=True))
    page.on("pageerror", lambda err: print(f"[PAGE_ERR] {err}", flush=True))
    
    # Navigate to roblox.com
    page.goto("https://www.roblox.com", wait_until="domcontentloaded", timeout=20000)
    print("[*] Page loaded", flush=True)
    time.sleep(3)
    
    # Click login
    login_btn = page.query_selector("#login-button")
    if login_btn:
        login_btn.click()
        print("[*] Clicked login button", flush=True)
    else:
        page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=20000)
        print("[*] Navigated to /login", flush=True)
    
    time.sleep(5)
    
    # Check for captcha iframe
    result = page.evaluate("""() => {
        const frames = document.querySelectorAll('iframe');
        const info = [];
        frames.forEach(f => {
            const src = f.src || '';
            info.push({src: src.slice(0, 200), visible: f.offsetHeight > 0});
        });
        return JSON.stringify(info);
    }""")
    print(f"[*] Iframes: {result}", flush=True)
    
    # Check for arkoselabs frames
    for i in range(60):
        frames_info = page.evaluate("""() => {
            const frames = document.querySelectorAll('iframe');
            const arkoselabs = [];
            frames.forEach(f => {
                if (f.src && (f.src.includes('arkoselabs') || f.src.includes('funcaptcha'))) {
                    arkoselabs.push({src: f.src.slice(0, 200), visible: f.offsetHeight > 0});
                }
            });
            return JSON.stringify(arkoselabs);
        }""")
        if frames_info != "[]":
            print(f"[+] Captcha iframe found at {i}s: {frames_info}", flush=True)
            break
        if i % 10 == 0:
            print(f"  Waiting for captcha... ({i}s)", flush=True)
        time.sleep(1)
    else:
        print("[-] No captcha iframe found in 60s", flush=True)
    
    # Wait for auto-solve (poll for state changes)
    for i in range(120):
        # Check proxy for nopecha connections
        nopecha_reqs = [l for l in proxy_log if 'nopecha' in l.lower()]
        if nopecha_reqs:
            print(f"[+] NopeCHA request detected via proxy at {i}s:", flush=True)
            for l in nopecha_reqs[-5:]:
                print(f"    {l}", flush=True)
        
        # Check page state
        state = page.evaluate("""() => {
            const el = document.querySelector('[data-testid="captcha-input"]');
            if (el && el.value) return 'captcha_value: ' + el.value.slice(0, 50);
            const grecaptcha = document.querySelector('.g-recaptcha response');
            if (grecaptcha && grecaptcha.textContent) return 'g-recaptcha response';
            
            const frames = document.querySelectorAll('iframe');
            let solved = false;
            frames.forEach(f => {
                try {
                    if (f.contentDocument && f.contentDocument.querySelector('.solved')) solved = true;
                } catch(e) {}
            });
            if (solved) return 'SOLVED';
            return null;
        }""")
        if state:
            print(f"[+] Captcha state at {i}s: {state}", flush=True)
            if 'SOLVED' in state:
                print("[+] CAPTCHA SOLVED!", flush=True)
                break
        
        if i % 10 == 0 and i > 0:
            print(f"  Waiting for solve... ({i}s)", flush=True)
        time.sleep(1)
    else:
        print("[-] Captcha not solved in 120s", flush=True)
    
    # Print proxy summary
    nopecha_lines = [l for l in proxy_log if 'nopecha' in l.lower()]
    print(f"\n[*] Proxy nopecha connections: {len(nopecha_lines)}")
    for l in nopecha_lines:
        print(f"  {l}")
    
    print(f"\n[*] Total proxy log lines: {len(proxy_log)}")

chrome_proc.kill()
proxy_proc.kill()
