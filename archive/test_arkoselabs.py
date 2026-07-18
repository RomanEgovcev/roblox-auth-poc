"""Test extension on arkoselabs.com demo page (no proxy)."""
import os, time, subprocess, json, urllib.request, sys

proxy_dir = "C:\\Users\\regov\\Desktop\\lua"
chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext_path = f"{proxy_dir}\\chromium_automation"
profile = f"{proxy_dir}\\pw_profile"

# Launch WITHOUT proxy
chrome_proc = subprocess.Popen(
    [chrome_path, f"--user-data-dir={profile}", f"--load-extension={ext_path}",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*",
     "--ignore-certificate-errors",
     "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("[*] Chrome launched (no proxy)", flush=True)
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
    page.on("framenavigated", lambda f: print(f"[FRAME] {f.url[:200]}", flush=True))
    page.on("pageerror", lambda err: print(f"[PAGE_ERR] {err}", flush=True))
    
    # Arkose Labs demo
    print("[*] Navigating to arkoselabs demo...", flush=True)
    try:
        page.goto("https://demo.arkoselabs.com/", wait_until="domcontentloaded", timeout=20000)
    except:
        print("[-] Timeout on page load", flush=True)
    
    time.sleep(5)
    print(f"[*] URL: {page.url}", flush=True)
    
    # Check for iframes
    iframes = page.evaluate("""() => {
        const frames = document.querySelectorAll('iframe');
        return Array.from(frames).map(f => ({
            src: (f.src || '').slice(0, 300),
            visible: f.offsetHeight > 0
        }));
    }""")
    print(f"[*] Iframes: {json.dumps(iframes, indent=2)}", flush=True)
    
    # Try clicking buttons to trigger captcha
    page.evaluate("""() => {
        const buttons = document.querySelectorAll('button');
        buttons.forEach(b => console.log('Button:', b.textContent, b.id, b.className));
    }""")
    
    # Wait and monitor
    for i in range(60):
        # Check for captcha iframes
        frames = page.evaluate("""() => {
            const frames = document.querySelectorAll('iframe');
            return Array.from(frames).map(f => ({
                src: (f.src || '').slice(0, 300),
                visible: f.offsetHeight > 0
            }));
        }""")
        arko = [f for f in frames if 'arkoselabs' in f['src'] or 'funcaptcha' in f['src'] or 'fc/assets' in f['src']]
        if arko:
            print(f"[+] Captcha iframe at {i}s: {json.dumps(arko)}", flush=True)
            break
        if i % 10 == 0:
            print(f"  [{i}s] iframes: {len(frames)}", flush=True)
        time.sleep(1)
    else:
        print("[-] No captcha iframe after 60s", flush=True)
    
    # Wait for auto-solve
    for i in range(120):
        frames = page.evaluate("""() => {
            const frames = document.querySelectorAll('iframe');
            return Array.from(frames).map(f => ({
                src: (f.src || '').slice(0, 300)
            }));
        }""")
        arko = [f for f in frames if 'arkoselabs' in f['src'] or 'funcaptcha' in f['src']]
        if arko:
            solved = page.evaluate("""() => {
                const frames = document.querySelectorAll('iframe');
                for (const f of frames) {
                    try {
                        const doc = f.contentDocument || f.contentWindow?.document;
                        if (doc) {
                            const html = doc.body?.innerHTML || '';
                            return 'iframe content: ' + html.slice(0, 300);
                        }
                    } catch(e) {}
                }
                return null;
            }""")
            if solved:
                print(f"  [{i}s] {solved}", flush=True)
        if i % 10 == 0:
            print(f"  [{i}s] waiting...", flush=True)
        time.sleep(1)

chrome_proc.kill()
