"""Find a page with FunCaptcha + auto-solve."""
import os, time, subprocess, json, urllib.request, sys, threading

proxy_dir = "C:\\Users\\regov\\Desktop\\lua"

# --- Proxy ---
proxy_proc = subprocess.Popen(
    [sys.executable, f"{proxy_dir}\\local_proxy.py"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
proxy_lines = []
def log_proxy():
    for l in iter(proxy_proc.stdout.readline, ''):
        l = l.rstrip(); proxy_lines.append(l)
threading.Thread(target=log_proxy, daemon=True).start()
time.sleep(3)

opener = urllib.request.build_opener(urllib.request.ProxyHandler({'https': 'http://127.0.0.1:8888'}))
try:
    assert opener.open('https://api.nopecha.com/v1/status', timeout=10).status == 200
    print("[+] Proxy OK", flush=True)
except: print("[-] Proxy dead", flush=True); proxy_proc.kill(); exit(1)

# --- Chrome ---
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
    page.set_default_timeout(20000)
    page.on("console", lambda msg: print(f"[PAGE {msg.type}] {msg.text[:200]}", flush=True))

    # Try multiple pages
    urls = [
        "https://client-demo.arkoselabs.com/",
        "https://funcaptcha.com/",
        "https://www.roblox.com/",
        "https://www.roblox.com/login",
    ]
    
    for url in urls:
        print(f"\n[*] Trying: {url}", flush=True)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
        except:
            pass
        time.sleep(5)
        
        # Check for iframes
        frames = page.evaluate("""() => {
            const f = document.querySelectorAll('iframe');
            return Array.from(f).map(x => ({
                src: (x.src||'').slice(0,300),
                id: x.id,
                visible: x.offsetHeight > 0
            }));
        }""")
        arko = [f for f in frames if 'arkoselabs' in f['src'] or 'funcaptcha' in f['src'] or 'fc/assets' in f['src']]
        if arko:
            print(f"[+] CAPTCHA IFRAME: {json.dumps(arko, indent=2)}", flush=True)
            
            # If on roblox, try login
            if 'roblox' in url:
                page.fill("input[name='username']", "testuser123")
                page.fill("input[name='password']", "wrongpass!")
                page.press("input[name='password']", "Enter")
                time.sleep(3)
                frames2 = page.evaluate("""() => {
                    const f = document.querySelectorAll('iframe');
                    return Array.from(f).map(x => ({src: (x.src||'').slice(0,300)}));
                }""")
                arko2 = [f for f in frames2 if 'arkoselabs' in f['src'] or 'funcaptcha' in f['src']]
                if arko2: print(f"[+] After submit: {json.dumps(arko2)}", flush=True)
        else:
            print(f"[-] No captcha iframe on {url}", flush=True)
        
        # Check for arkoselabs script tags
        scripts = page.evaluate("""() => {
            const s = document.querySelectorAll('script');
            return Array.from(s).map(x => (x.src||'').slice(0,200)).filter(x => x);
        }""")
        arko_scripts = [s for s in scripts if 'arkoselabs' in s or 'funcaptcha' in s]
        if arko_scripts:
            print(f"[+] Arkose scripts: {arko_scripts}", flush=True)
    
    # If we found captcha, wait for solve
    for i in range(60):
        now = len([l for l in proxy_lines if 'api.nopecha.com' in l])
        if i % 10 == 0:
            print(f"  [{i}s] api.nopecha.com: {now}", flush=True)
        time.sleep(1)
    
    print(f"\n[*] Total api.nopecha.com: {len([l for l in proxy_lines if 'api.nopecha.com' in l])}", flush=True)

chrome_proc.kill(); proxy_proc.kill()
