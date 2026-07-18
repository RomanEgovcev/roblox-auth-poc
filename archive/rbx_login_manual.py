"""Manual solve flow: POW auto, captcha manual, cookie auto-capture."""
import os, time, json, sys

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"
PROFILE_DIR = os.path.abspath("pw_profile_manual")
os.makedirs(PROFILE_DIR, exist_ok=True)

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        PROFILE_DIR,
        headless=False,
        bypass_csp=True,
        args=["--disable-blink-features=AutomationControlled"],
        no_viewport=True,
    )
    page = ctx.pages[0]
    print("[*] Browser launched with persistent profile", flush=True)

    def on_resp(resp):
        url = resp.url
        if any(x in url for x in ["/v2/login", "pow-puzzle", "challenge/v1/continue", "worker-resources"]):
            marker = ""
            if "/v2/login" in url:
                marker = " <-- LOGIN"
            print(f"  [NET {resp.status}] {resp.request.method} {url.split('?')[0][:100]}{marker}", flush=True)

    def on_console(msg):
        t = msg.text.lower()
        if any(x in t for x in ["worker", "challenge", "proof", "pow", "eval", "error"]):
            print(f"  [CONSOLE] {msg.text[:250]}", flush=True)

    page.on("response", on_resp)
    page.on("console", on_console)

    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
    print("[*] Page loaded, waiting for PX init...", flush=True)
    time.sleep(5)

    has_login_retry = [False]
    start_time = time.time()

    def on_cookie(cookie):
        if cookie.get("name") == ".ROBLOSECURITY":
            elapsed = time.time() - start_time
            print(f"\n{'='*60}", flush=True)
            print(f"[SUCCESS at t={elapsed:.0f}s]", flush=True)
            print(f".ROBLOSECURITY={cookie['value']}", flush=True)
            print(f"{'='*60}", flush=True)
            has_login_retry[0] = True

    ctx.on("cookie", on_cookie)

    cookies_before = ctx.cookies()
    existing_rs = [c for c in cookies_before if c["name"] == ".ROBLOSECURITY"]
    if existing_rs:
        print(f"[!] Already have .ROBLOSECURITY cookie!", flush=True)
        print(f"  Value: {existing_rs[0]['value']}", flush=True)
        print(f"  Expires: {existing_rs[0].get('expires', '?')}", flush=True)
        ask = input("\n  Use existing session? (y/n): ").strip().lower()
        if ask == 'y':
            print("\nDone.", flush=True)
            ctx.close()
            sys.exit(0)

    print("[*] Filling credentials...", flush=True)
    page.evaluate("""() => {
        for (let i = 0; i < 30; i++)
            document.dispatchEvent(new MouseEvent('mousemove', {clientX: 50 + i * 40, clientY: 100 + i * 20, bubbles: true}));
        const u = document.querySelector('input[name="username"]');
        if (u) { u.focus(); u.dispatchEvent(new FocusEvent('focus', {bubbles: true})); }
    }""")
    time.sleep(0.5)
    page.fill('input[name="username"]', USER)
    time.sleep(0.3)
    page.fill('input[name="password"]', PASS)
    time.sleep(0.5)
    page.evaluate("""() => {
        for (let i = 0; i < 15; i++)
            document.dispatchEvent(new MouseEvent('mousemove', {clientX: 400 + i * 20, clientY: 300 + i * 5, bubbles: true}));
    }""")
    time.sleep(0.5)

    t0 = time.time()
    print("[*] Triggering login via fiber walker...", flush=True)
    page.evaluate("""() => {
        const root = document.querySelector('#login-base') || document.body;
        const key = Object.keys(root).find(k => k.startsWith('__reactFiber'));
        if (!key) return 'no fiber';
        function walk(f, d) {
            if (!f || d > 20) return null;
            if (f.memoizedProps && typeof f.memoizedProps.onFormSubmit === 'function') {
                f.memoizedProps.onFormSubmit();
                return 'ok';
            }
            return walk(f.child, d+1) || walk(f.sibling, d);
        }
        return walk(root[key], 0);
    }""")

    captcha_detected = False
    verify_detected = False
    challenge_detected = False

    print("\n[*] Waiting for challenge flow...", flush=True)
    print("    1. Login POST -> 403 (POW challenge)", flush=True)
    print("    2. Puzzle GET -> solve (native WebWorker)", flush=True)
    print("    3. Puzzle verify POST -> token", flush=True)
    print("    4. /challenge/v1/continue -> captcha", flush=True)
    print("    5. (YOU) Solve captcha in browser window", flush=True)
    print("    6. Auto-capture .ROBLOSECURITY cookie\n", flush=True)

    poll_start = time.time()

    while time.time() - poll_start < 300:
        elapsed = time.time() - t0

        if has_login_retry[0]:
            print(f"\n[DONE at t={elapsed:.0f}s]", flush=True)
            break

        cookies = ctx.cookies()
        rs = [c for c in cookies if c["name"] == ".ROBLOSECURITY"]
        if rs:
            print(f"\n{'='*60}", flush=True)
            print(f"[SUCCESS! at t={elapsed:.0f}s]", flush=True)
            print(f".ROBLOSECURITY={rs[0]['value']}", flush=True)
            print(f"{'='*60}", flush=True)
            has_login_retry[0] = True
            break

        cur_url = page.url
        if "home" in cur_url.lower() or "games" in cur_url.lower() or "/home" in cur_url:
            print(f"\n[SUCCESS!] Redirected to {cur_url} at t={elapsed:.0f}s", flush=True)
            cookies = ctx.cookies()
            rs = [c for c in cookies if c["name"] == ".ROBLOSECURITY"]
            if rs:
                print(f".ROBLOSECURITY={rs[0]['value']}", flush=True)
            has_login_retry[0] = True
            break

        if not captcha_detected:
            has_captcha = page.evaluate("""() => {
                const arkose0 = document.getElementById('arkose-0');
                const body = document.querySelector('.challenge-captcha-body');
                const container = document.querySelector('.captcha-container');
                const iframes = document.querySelectorAll('iframe');
                let hasArkose = false;
                for (let f of iframes) {
                    if (f.src && f.src.includes('arkoselabs')) hasArkose = true;
                }
                return {
                    arkose0: arkose0 ? arkose0.style.display : 'not found',
                    challengeBody: body ? 'exists' : 'not found',
                    container: container ? 'exists' : 'not found',
                    arkoseFrame: hasArkose,
                };
            }""")

            if has_captcha.get("arkoseFrame") or has_captcha.get("challengeBody") == "exists" or has_captcha.get("container") == "exists":
                captcha_detected = True
                print(f"\n{'!'*60}", flush=True)
                print(f"[CAPTCHA at t={elapsed:.0f}s] !!! SOLVE IN BROWSER WINDOW !!!", flush=True)
                print(f"{'!'*60}", flush=True)
                print(f"  The captcha is visible in the Chrome window.", flush=True)
                print(f"  Solve it there and the script will auto-capture the cookie.\n", flush=True)

        if not captcha_detected:
            chall_state = page.evaluate("""() => {
                const ch = document.querySelector('.challenge-container, #generic-challenge-container-proofofwork, .challenge-body');
                const arkose = document.getElementById('arkose-0');
                const pow = document.querySelector('[class*="proof"]');
                return {
                    challenge: ch ? 'exists' : 'no',
                    arkose0: arkose ? 'exists' : 'no',
                    pow: pow ? 'exists' : 'no',
                };
            }""")
            if chall_state.get("challenge") != "no" or chall_state.get("pow") != "no":
                print(f"  [t={elapsed:.0f}s] Challenge UI visible: {chall_state}", flush=True)

        time.sleep(2)

    elapsed_total = time.time() - t0
    print(f"\n{'='*60}", flush=True)
    print(f"TIMELINE: {elapsed_total:.0f}s total", flush=True)
    print(f"SUCCESS: {has_login_retry[0]}", flush=True)

    if not has_login_retry[0]:
        cookies = ctx.cookies()
        names = [c["name"] + "=" + c["value"][:20] for c in cookies]
        print(f"Cookies: {names}", flush=True)
        print(f"\nTip: If captcha appeared but wasn't solved, try again and solve it.", flush=True)

    page.screenshot(path="final_state.png")
    print(f"\nScreenshot saved to final_state.png", flush=True)
    input("\nPress Enter to close browser...")
    ctx.close()
