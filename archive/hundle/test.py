"""
test.py — Browser-based captcha hunter.
Launches Chrome via subprocess (NOT Playwright), connects via CDP.
Tries login until FunCaptcha appears, sends blob to Telegram.
"""
import json
import time
import os
import subprocess
import requests
from playwright.sync_api import sync_playwright

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "708684405")
TG_API = f"https://api.telegram.org/bot{TG_BOT_TOKEN}"

LOGIN_URL = "https://www.roblox.com/login"
MAX_ATTEMPTS = 20
DELAY = 3
CDP_PORT = 9222
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def tg_send(text):
    try:
        payload = {"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"}
        resp = requests.post(f"{TG_API}/sendMessage", json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"[TG] Sent")
        else:
            print(f"[TG] Error: {resp.text[:100]}")
    except Exception as e:
        print(f"[TG] Error: {e}")


def start_chrome():
    args = [
        CHROME,
        f"--user-data-dir={os.path.abspath('cdp_profile')}",
        "--no-first-run",
        "--no-default-browser-check",
        "--remote-debugging-port=9222",
        "--remote-allow-origins=*",
        "--window-size=800,600",
        "--window-position=-4000,-4000",
        "--disable-web-security",
        "--disable-site-isolation-trials",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-blink-features=AutomationControlled",
        "--disable-sync",
        "--disable-background-networking",
        "--mute-audio",
    ]
    print("[CHROME] Launching Chrome...")
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    return proc


def wait_for_cdp(max_attempts=20):
    import http.client
    for i in range(max_attempts):
        try:
            conn = http.client.HTTPConnection("localhost", CDP_PORT, timeout=3)
            conn.request("GET", "/json")
            resp = conn.getresponse()
            tabs = json.loads(resp.read())
            conn.close()
            if tabs:
                url = tabs[0]["webSocketDebuggerUrl"]
                print(f"[CDP] Connected: {url}")
                return url
        except:
            pass
        print(f"[CDP] Waiting for Chrome ({i+1}/{max_attempts})...")
        time.sleep(1)
    raise RuntimeError("Could not connect to Chrome CDP")


def extract_blob(page):
    try:
        blob = page.evaluate("""() => {
            const els = document.querySelectorAll('[data-exchange-blob]');
            for (const el of els) {
                const b = el.getAttribute('data-exchange-blob');
                if (b) return b;
            }
            const iframes = document.querySelectorAll('iframe[src*="arkose"], iframe[src*="funcaptcha"]');
            for (const f of iframes) {
                const src = f.getAttribute('src') || '';
                const m = src.match(/embed[/=]([^"&?]+)/);
                if (m) return m[1];
            }
            if (window.__funcaptcha && window.__funcaptcha.data) {
                return window.__funcaptcha.data;
            }
            return null;
        }""")
        if blob:
            return blob
    except Exception as e:
        print(f"[BLOB] eval error: {e}")

    try:
        iframes = page.query_selector_all("iframe")
        for iframe in iframes:
            src = iframe.get_attribute("src") or ""
            if "arkose" in src or "funcaptcha" in src or "rlcdn" in src:
                print(f"[BLOB] Found captcha iframe: {src[:120]}")
    except Exception as e:
        print(f"[BLOB] iframe scan error: {e}")

    return None


def main():
    print("=" * 60)
    print("BROWSER CAPTCHA HUNTER")
    print("=" * 60)

    username = input("Username: ").strip()
    password = input("Password: ").strip()

    chrome_proc = start_chrome()
    cdp_url = wait_for_cdp()

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp_url)
        page = browser.new_page()
        page.goto(LOGIN_URL, wait_until="domcontentloaded")
        print("[PAGE] Waiting for login form...")
        page.wait_for_selector("input[name='username']", timeout=30000)
        print("[PAGE] Login form loaded.")

        for attempt in range(1, MAX_ATTEMPTS + 1):
            print(f"\n--- Attempt {attempt}/{MAX_ATTEMPTS} ---")

            try:
                page.evaluate("""() => {
                    const banner = document.getElementById('cookie-banner-wrapper');
                    if (banner) banner.remove();
                }""")
                page.fill("input[name='username']", username)
                page.fill("input[name='password']", password)
                page.click("button[type='submit']", force=True)
                time.sleep(5)

                blob = extract_blob(page)
                if blob:
                    print(f"\n[CAPTCHA] BLOB CAPTURED!")
                    text = (
                        f"🔐 <b>КАПЧА ROBLOX</b>\n\n"
                        f"👤 Аккаунт: <code>{username}</code>\n"
                        f"📦 <b>DataExchangeBlob:</b>\n<code>{blob}</code>\n\n"
                        f"Открой captcha_solver.html, вставь blob и реши."
                    )
                    tg_send(text)
                    print(f"[BLOB] {blob[:100]}...")
                    print("\nBrowser stays open. Copy blob manually if needed. Ctrl+C to exit.")
                    input("Press Enter to close browser...")
                    browser.close()
                    chrome_proc.kill()
                    return

                print(f"[{attempt}] No captcha yet, retrying...")
            except Exception as e:
                print(f"[{attempt}] Error: {e}")

            if attempt < MAX_ATTEMPTS:
                print(f"Waiting {DELAY}s...")
                time.sleep(DELAY)

        print("\nNo captcha after max attempts.")
        tg_send(f"❌ Капча не поймана за {MAX_ATTEMPTS} попыток.")
        input("Press Enter to close browser...")
        browser.close()
        chrome_proc.kill()


if __name__ == "__main__":
    main()
