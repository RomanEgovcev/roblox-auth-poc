"""Extract API key from extension storage via CDP."""
import os, time, subprocess, json, urllib.request, sys

proxy_dir = "C:\\Users\\regov\\Desktop\\lua"
ext_id = "dknlfmjaanfblgfdfebhijalfmhmjjjo"

chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
ext_path = f"{proxy_dir}\\chromium_automation"
profile = f"{proxy_dir}\\pw_profile"

chrome_proc = subprocess.Popen(
    [chrome_path, f"--user-data-dir={profile}", f"--load-extension={ext_path}",
     "--no-first-run", "--remote-debugging-port=9222",
     "--remote-allow-origins=*",
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
    page.on("pageerror", lambda err: print(f"[PAGE_ERR] {err}", flush=True))
    
    # Try to open extension popup page
    popup_url = f"chrome-extension://{ext_id}/assets/ip10n8.html"
    print(f"[*] Navigating to popup: {popup_url}", flush=True)
    
    try:
        page.goto(popup_url, wait_until="domcontentloaded", timeout=15000)
        print("[*] Popup page loaded", flush=True)
        time.sleep(3)
        
        # Try to extract storage data
        result = page.evaluate("""async () => {
            try {
                const data = await chrome.storage.local.get(null);
                return JSON.stringify(data);
            } catch(e) {
                return 'storage error: ' + e.message;
            }
        }""")
        print(f"[*] Storage: {result}", flush=True)
        
        # Try runtime.getManifest()
        result2 = page.evaluate("""() => {
            try {
                const m = chrome.runtime.getManifest();
                return JSON.stringify(m.nopecha || {});
            } catch(e) {
                return 'manifest error: ' + e.message;
            }
        }""")
        print(f"[*] Manifest nopecha: {result2}", flush=True)
        
        # Also check if there's any API key in global scope
        result3 = page.evaluate("""() => {
            const keys = Object.keys(window);
            const relevant = keys.filter(k => k.toLowerCase().includes('key') || k.toLowerCase().includes('nopecha'));
            return JSON.stringify(relevant);
        }""")
        print(f"[*] Window keys: {result3}", flush=True)
        
    except Exception as e:
        print(f"[-] Error accessing popup: {e}", flush=True)
        
        # Alternative: try to access extension via chrome-extension:// page
        bg_url = f"chrome-extension://{ext_id}/_generated_background_page.html"
        print(f"[*] Trying background page: {bg_url}", flush=True)
        try:
            page.goto(bg_url, wait_until="domcontentloaded", timeout=10000)
            print("[*] BG page loaded", flush=True)
            time.sleep(2)
            
            result = page.evaluate("""async () => {
                try {
                    const data = await chrome.storage.local.get(null);
                    return JSON.stringify(data);
                } catch(e) {
                    return 'storage error: ' + e.message;
                }
            }""")
            print(f"[*] Storage: {result}", flush=True)
        except Exception as e2:
            print(f"[-] BG page error: {e2}", flush=True)
    
    # Also try navigating directly to the background service worker via CDP
    # The SW URL is assets/4ncg2v.js
    sw_url = f"chrome-extension://{ext_id}/assets/4ncg2v.js"
    print(f"[*] Trying SW URL: {sw_url}", flush=True)
    try:
        page.goto(sw_url, wait_until="domcontentloaded", timeout=5000)
        print("[*] SW page loaded", flush=True)
    except Exception as e:
        print(f"[-] SW page error: {e}", flush=True)
    
    # List all targets via CDP
    print("\n[*] All CDP targets:", flush=True)
    targets = browser.contexts
    for t in targets:
        print(f"  Context: {t}", flush=True)
        for pg in t.pages:
            print(f"    Page: {pg.url[:200]}", flush=True)

chrome_proc.kill()
