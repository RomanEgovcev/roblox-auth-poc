"""Test: captcha appears, full network/CDP/SW monitoring. System proxy (HAPP VPN)."""
import os, time, subprocess, json, sys, threading

proxy_dir = "C:\\Users\\regov\\Desktop\\lua"
chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext_path = f"{proxy_dir}\\chromium_automation"
profile = f"{proxy_dir}\\pw_profile"

chrome_proc = subprocess.Popen(
    [chrome_path, f"--user-data-dir={profile}", f"--load-extension={ext_path}",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*",
     "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(5)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.set_default_timeout(30000)

    seen_requests = set()

    def log_console(msg):
        text = msg.text[:200]
        loc = msg.location
        print(f"[C] {loc.get('url','?')[:80]} | {text}", flush=True)

    def log_frame(f):
        url = f.url[:150]
        if 'roblox' in url or 'arkoselabs' in url or 'funcaptcha' in url or 'nopecha' in url:
            print(f"[F] {url}", flush=True)

    page.on("console", log_console)
    page.on("framenavigated", log_frame)

    cdp = page.context.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.on("Network.requestWillBeSent", lambda params: _log_req(params))
    cdp.on("Network.loadingFailed", lambda params: _log_fail(params))

    def _log_req(params):
        req = params.get('request', {})
        url = req.get('url', '')
        if not any(x in url for x in ['nopecha', 'arkoselabs', 'funcaptcha', 'roblox']):
            return  # skip irrelevant
        if url in seen_requests:
            return
        seen_requests.add(url)
        method = req.get('method', '')
        print(f"[R] {method} {url[:200]}", flush=True)

    def _log_fail(params):
        url = params.get('documentURL', '') or params.get('url', '')
        typ = params.get('type', '')
        err = params.get('errorText', params.get('localizedDescription', ''))
        if any(x in url for x in ['nopecha', 'arkoselabs', 'funcaptcha', 'roblox','nopecha.com']):
            print(f"[!] FAIL {url[:150]} | type={typ} | {err}", flush=True)

    # Monitor CDP targets
    def check_targets():
        while True:
            time.sleep(5)
            try:
                targets = cdp.send("Target.getTargets")
                for t in targets.get('targetInfos', []):
                    tid = t.get('targetId','')[:16]
                    url = t.get('url','')[:120]
                    tt = t.get('type','')
                    if 'nopecha' in url or tt == 'service_worker':
                        print(f"[T] type={tt} url={url} id={tid}", flush=True)
            except:
                break

    t = threading.Thread(target=check_targets, daemon=True)
    t.start()

    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(3)

    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    page.click("#login-button")
    print("[*] Submitted login, waiting 120s...", flush=True)

    captcha_seen = False
    for i in range(120):
        try:
            frames = page.evaluate("""() => {
                const f = document.querySelectorAll('iframe');
                return Array.from(f).map(x => ({src:(x.src||'').slice(0,300), id:x.id}));
            }""")
            arko = [f for f in frames if 'arkoselabs' in f['src'] or 'funcaptcha' in f['src']]
            if arko and not captcha_seen:
                captcha_seen = True
                print(f"[+] CAPTCHA FOUND: {json.dumps(arko)}", flush=True)
            if i % 10 == 0:
                print(f"  [{i}s] iframes: {len(frames)}", flush=True)
        except Exception as e:
            print(f"  [{i}s] ERROR: {e}", flush=True)
            break
        time.sleep(1)

chrome_proc.kill()
