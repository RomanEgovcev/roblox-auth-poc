"""Test extension on nopecha.com demo page with proxy."""
import os, time, subprocess, json, urllib.request, sys, threading

proxy_dir = "C:\\Users\\regov\\Desktop\\lua"

proxy_proc = subprocess.Popen(
    [sys.executable, f"{proxy_dir}\\local_proxy.py"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

proxy_log_lines = []
def print_proxy():
    for line in iter(proxy_proc.stdout.readline, ''):
        line = line.rstrip()
        proxy_log_lines.append(line)
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
    page.set_default_timeout(30000)
    page.on("console", lambda msg: print(f"[PAGE {msg.type}] {msg.text[:300]}", flush=True))

    # Go to nopecha demo page
    page.goto("https://nopecha.com/demo/funcaptcha", wait_until="domcontentloaded", timeout=30000)
    print("[*] Demo page loaded", flush=True)
    time.sleep(10)  # wait for extension to activate

    # Check for captcha iframe
    frames_info = page.evaluate("""() => {
        const frames = document.querySelectorAll('iframe');
        const info = [];
        frames.forEach(f => {
            info.push({src: (f.src || '').slice(0, 200), visible: f.offsetHeight > 0});
        });
        return JSON.stringify(info);
    }""")
    print(f"[*] Iframes: {frames_info}", flush=True)

    # Wait for auto-solve
    for i in range(120):
        # Check page state
        state = page.evaluate("""() => {
            const token = document.querySelector('textarea[name="token"]');
            if (token && token.value) return 'TOKEN: ' + token.value.slice(0, 100);
            const result = document.getElementById('result');
            if (result && result.textContent) return 'RESULT: ' + result.textContent.slice(0, 100);
            const solveBtn = document.querySelector('button:not([disabled])');
            return null;
        }""")
        if state:
            print(f"[+] State at {i}s: {state}", flush=True)
        
        # Check proxy for nopecha API calls
        recent = [l for l in proxy_log_lines[-10:] if 'api.nopecha.com' in l]
        if recent:
            print(f"[PROXY_ACTIVITY] at {i}s: {recent}", flush=True)
        
        time.sleep(1)
    else:
        print("[-] No solve in 120s", flush=True)
    
    # Print proxy summary
    nopecha_api = [l for l in proxy_log_lines if 'api.nopecha.com' in l]
    print(f"\n[*] Proxy api.nopecha.com connections: {len(nopecha_api)}")
    for l in nopecha_api[-10:]:
        print(f"  {l}")

chrome_proc.kill()
proxy_proc.kill()
