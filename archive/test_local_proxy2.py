"""Start local proxy, test Chrome cross-origin fetch."""
import os, time, subprocess, json, urllib.request, sys, signal

proxy_dir = "C:\\Users\\regov\\Desktop\\lua"

# Start proxy as subprocess
proxy_proc = subprocess.Popen(
    [sys.executable, f"{proxy_dir}\\local_proxy.py"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
print(f"[*] Proxy PID: {proxy_proc.pid}", flush=True)
time.sleep(3)

# Verify proxy is up
try:
    proxy_handler = urllib.request.ProxyHandler({'https': 'http://127.0.0.1:8888'})
    opener = urllib.request.build_opener(proxy_handler)
    resp = opener.open('https://api.nopecha.com/v1/status', timeout=10)
    print(f"[+] Proxy test: {resp.status} OK", flush=True)
except Exception as e:
    print(f"[-] Proxy test failed: {e}", flush=True)
    proxy_proc.kill()
    exit(1)

# Launch Chrome
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
        except:
            time.sleep(2)
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.set_default_timeout(15000)
    
    # Test fetch
    page.goto("https://www.roblox.com", wait_until="domcontentloaded", timeout=15000)
    
    for mode in ['no-cors', 'cors']:
        result = page.evaluate(f"""async () => {{
            try {{
                const resp = await fetch('https://api.nopecha.com/v1/status', {{ mode: '{mode}' }});
                const txt = await resp.text();
                return 'OK: ' + txt.slice(0, 200);
            }} catch(e) {{
                return 'FAIL: ' + e.message;
            }}
        }}""")
        print(f"  mode={mode}: {result}", flush=True)
    
    # Also test with img
    result = page.evaluate("""async () => {
        return new Promise(resolve => {
            const img = new Image();
            img.onload = () => resolve('img loaded');
            img.onerror = () => resolve('img failed');
            img.src = 'https://api.nopecha.com/favicon.ico';
        });
    }""")
    print(f"  img: {result}", flush=True)

chrome_proc.kill()
proxy_proc.kill()
