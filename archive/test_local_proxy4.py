"""Debug: test fetch from about:blank (no CSP) through local proxy."""
import os, time, subprocess, json, urllib.request, sys, threading

proxy_dir = "C:\\Users\\regov\\Desktop\\lua"

proxy_proc = subprocess.Popen(
    [sys.executable, f"{proxy_dir}\\local_proxy.py"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

def print_proxy():
    for line in iter(proxy_proc.stdout.readline, ''):
        print(f"[PROXY] {line.rstrip()}", flush=True)
threading.Thread(target=print_proxy, daemon=True).start()

time.sleep(3)

# Verify proxy
try:
    proxy_handler = urllib.request.ProxyHandler({'https': 'http://127.0.0.1:8888'})
    opener = urllib.request.build_opener(proxy_handler)
    resp = opener.open('https://api.nopecha.com/v1/status', timeout=10)
    print(f"[+] Proxy test: {resp.status}", flush=True)
except Exception as e:
    print(f"[-] Proxy test failed: {e}", flush=True)
    proxy_proc.kill()
    exit(1)

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
    page.on("console", lambda msg: print(f"[CONSOLE {msg.type}] {msg.text}", flush=True))
    page.on("pageerror", lambda err: print(f"[PAGE_ERROR] {err}", flush=True))
    
    # Test 1: about:blank
    page.goto("about:blank")
    result = page.evaluate("""async () => {
        try {
            const resp = await fetch('https://api.nopecha.com/v1/status');
            const txt = await resp.text();
            return 'OK: ' + txt.slice(0, 200);
        } catch(e) {
            return 'FAIL: ' + e.message + ' | name: ' + e.name;
        }
    }""")
    print(f"[*] about:blank fetch: {result}", flush=True)
    time.sleep(2)
    
    # Test 2: XMLHttpRequest (synchronous style)
    result = page.evaluate("""() => {
        return new Promise(resolve => {
            const xhr = new XMLHttpRequest();
            xhr.onload = () => resolve('XHR OK: ' + xhr.responseText.slice(0, 100));
            xhr.onerror = (e) => resolve('XHR FAIL');
            xhr.timeout = 10000;
            xhr.open('GET', 'https://api.nopecha.com/v1/status');
            xhr.send();
        });
    }""")
    print(f"[*] XHR: {result}", flush=True)
    time.sleep(2)
    
    # Test 3: create iframe
    result = page.evaluate("""async () => {
        return new Promise(resolve => {
            const iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            iframe.onload = () => {
                try {
                    const f = iframe.contentWindow.fetch('https://api.nopecha.com/v1/status');
                    f.then(r => r.text()).then(t => resolve('iframe fetch OK: ' + t.slice(0,100)));
                } catch(e) {
                    resolve('iframe FAIL: ' + e.message);
                }
            };
            iframe.onerror = () => resolve('iframe load error');
            iframe.src = 'https://api.nopecha.com';
            document.body.appendChild(iframe);
        });
    }""")
    print(f"[*] iframe: {result}", flush=True)
    time.sleep(2)
    
    # Test 4: Test roblox.com CSP - try from roblox.com
    page.goto("https://www.roblox.com", wait_until="domcontentloaded", timeout=15000)
    time.sleep(3)
    result = page.evaluate("""async () => {
        try {
            const resp = await fetch('https://api.nopecha.com/v1/status');
            const txt = await resp.text();
            return 'OK: ' + txt.slice(0, 200);
        } catch(e) {
            return 'FAIL: ' + e.message;
        }
    }""")
    print(f"[*] roblox.com fetch: {result}", flush=True)
    time.sleep(2)
    
    # Test 5: test what CSP roblox.com has
    csp = page.evaluate("""() => {
        const meta = document.querySelector('meta[http-equiv="Content-Security-Policy"]');
        if (meta) return meta.content;
        return document.getElementById('csp')?.textContent || 'no CSP meta found';
    }""")
    print(f"[*] CSP: {csp}", flush=True)
    time.sleep(1)

chrome_proc.kill()
proxy_proc.kill()
