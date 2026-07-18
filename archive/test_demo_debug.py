"""Debug: check if content script runs on nopecha demo page."""
import os, time, subprocess, json, urllib.request, sys

proxy_dir = "C:\\Users\\regov\\Desktop\\lua"

# Start proxy
proxy_proc = subprocess.Popen(
    [sys.executable, f"{proxy_dir}\\local_proxy.py"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
import threading
def print_proxy():
    for line in iter(proxy_proc.stdout.readline, ''):
        line = line.rstrip()
        print(f"[PROXY] {line}", flush=True)
threading.Thread(target=print_proxy, daemon=True).start()
time.sleep(3)

# Start Chrome WITHOUT proxy first to test baseline
chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext_path = f"{proxy_dir}\\chromium_automation"
profile = f"{proxy_dir}\\pw_profile"

chrome_proc = subprocess.Popen(
    [chrome_path, f"--user-data-dir={profile}", f"--load-extension={ext_path}",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*",
     "--proxy-server=http://127.0.0.1:8888",
     "--ignore-certificate-errors",
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
    
    console_logs = []
    page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text[:300]}"))
    
    # Go to blank page first, then demo
    page.goto("about:blank")
    time.sleep(2)
    
    print("[*] Navigating to nopecha demo...", flush=True)
    try:
        page.goto("https://nopecha.com/demo/funcaptcha", wait_until="domcontentloaded", timeout=20000)
    except:
        print("[-] Page load timeout or error", flush=True)
    
    time.sleep(5)
    
    print(f"\n[*] URL: {page.url}", flush=True)
    print(f"[*] Title: {page.title()}", flush=True)
    
    # Check DOM
    dom = page.evaluate("""() => {
        const info = {
            bodyHTML: document.body?.innerHTML?.slice(0, 500) || 'no body',
            scripts: document.querySelectorAll('script').length,
            iframes: document.querySelectorAll('iframe').length,
            divs: document.querySelectorAll('div').length
        };
        return JSON.stringify(info);
    }""")
    print(f"[*] DOM: {dom}", flush=True)
    
    # Check for extension content script modifications
    result = page.evaluate("""() => {
        const allDivs = document.querySelectorAll('div');
        const texts = [];
        allDivs.forEach(d => {
            if (d.textContent) texts.push(d.textContent.slice(0, 100));
        });
        return JSON.stringify(texts);
    }""")
    print(f"[*] Div texts: {result}", flush=True)
    
    # Check if chrome.runtime exists in page
    result = page.evaluate("""() => {
        try {
            const hasChrome = typeof chrome !== 'undefined';
            const hasRuntime = hasChrome && typeof chrome.runtime !== 'undefined';
            const hasSendMessage = hasRuntime && typeof chrome.runtime.sendMessage !== 'undefined';
            return {hasChrome, hasRuntime, hasSendMessage};
        } catch(e) {
            return {error: e.message};
        }
    }""")
    print(f"[*] chrome.runtime: {result}", flush=True)
    
    print(f"\n--- Console logs ---", flush=True)
    for log in console_logs[-20:]:
        print(f"  {log}", flush=True)

chrome_proc.kill()
proxy_proc.kill()
