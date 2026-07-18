"""Trigger captcha on Roblox and let extension solve it."""
import os, time, subprocess, json, urllib.request, sys, threading, random, string

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
    page.on("framenavigated", lambda frame: print(f"[FRAME] {frame.url[:200]}", flush=True))
    
    # Go to login
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    print("[*] Login page loaded", flush=True)
    time.sleep(5)
    
    # Fill random credentials to trigger captcha
    random_user = ''.join(random.choices(string.ascii_lowercase, k=10))
    page.fill("input[name='username']", random_user)
    page.fill("input[name='password']", "wrongpassword123!")
    print(f"[*] Filled credentials: {random_user}", flush=True)
    time.sleep(1)
    
    # Click login button
    page.click("button[type='submit']")
    print("[*] Submitted login", flush=True)
    time.sleep(3)
    
    # Wait for captcha iframe
    captcha_found = False
    for i in range(120):
        # Look for arkoselabs/funcaptcha iframes
        frames = page.evaluate("""() => {
            const frames = document.querySelectorAll('iframe');
            return Array.from(frames).map(f => ({
                src: (f.src || '').slice(0, 300),
                visible: f.offsetHeight > 0,
                id: f.id
            }));
        }""")
        
        arko = [f for f in frames if 'arkoselabs' in f['src'] or 'funcaptcha' in f['src']]
        if arko:
            print(f"[+] Captcha iframe at {i}s: {json.dumps(arko)}", flush=True)
            captcha_found = True
            break
        
        if frames:
            has_iframes = [f for f in frames if f['src']]
            if has_iframes:
                print(f"  [{i}s] Iframes: {json.dumps(has_iframes[:3])}", flush=True)
        
        # Check proxy for nopecha API
        nopecha_now = [l for l in proxy_log_lines if 'api.nopecha.com' in l]
        if len(nopecha_now) > 0 and i % 5 == 0:
            print(f"  [{i}s] Proxy nopecha hits: {len(nopecha_now)}", flush=True)
        
        time.sleep(1)
    else:
        print("[-] No captcha iframe after 120s", flush=True)
    
    if captcha_found:
        # Wait for solution
        for i in range(120):
            # Check state
            solved = page.evaluate("""() => {
                const frames = document.querySelectorAll('iframe');
                for (const f of frames) {
                    try {
                        const doc = f.contentDocument || f.contentWindow?.document;
                        if (doc) {
                            const body = doc.body?.innerText || '';
                            if (body.includes('solved') || body.includes('verified')) return 'SOLVED: ' + body.slice(0, 100);
                        }
                    } catch(e) {}
                }
                return null;
            }""")
            if solved:
                print(f"[+] Captcha solved at {i}s: {solved}", flush=True)
                break
            
            nopecha_now = [l for l in proxy_log_lines if 'api.nopecha.com' in l]
            if nopecha_now:
                print(f"  [{i}s] Proxy nopecha: {nopecha_now[-1]}", flush=True)
            
            if i % 10 == 0:
                print(f"  Waiting for solve... ({i}s)", flush=True)
            time.sleep(1)
        else:
            print("[-] Captcha not solved in 120s", flush=True)

    # Summary
    nopecha_api = [l for l in proxy_log_lines if 'api.nopecha.com' in l]
    print(f"\n[*] Proxy api.nopecha.com connections: {len(nopecha_api)}")
    for l in nopecha_api:
        print(f"  {l}")
    
    # Check total credit at end
    try:
        resp = opener.open('https://api.nopecha.com/v1/status', timeout=10)
        print(f"[*] Final status: {resp.read()[:200]}", flush=True)
    except:
        pass

chrome_proc.kill()
proxy_proc.kill()
