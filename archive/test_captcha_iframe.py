import os, sys, time, subprocess, json, urllib.request, threading
from playwright.sync_api import sync_playwright

ext_path = os.path.abspath(r'C:\Users\regov\Desktop\lua\chromium_automation')
profile = os.path.abspath(r'C:\Users\regov\Desktop\lua\pw_profile')
username = sys.argv[1] if len(sys.argv) > 1 else "CheatingHitmanner"
password = sys.argv[2] if len(sys.argv) > 2 else ""

with sync_playwright() as p:
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    proc = subprocess.Popen(
        [chrome_path, f"--user-data-dir={profile}", f"--load-extension={ext_path}",
         "--no-first-run", "--remote-debugging-port=9222",
         "--remote-allow-origins=*",
         "--no-proxy-server"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("[*] Chrome launched (no proxy)", flush=True)
    time.sleep(4)

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

    # Login
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    page.wait_for_selector("#login-username", timeout=30000)
    page.fill("#login-username", username)
    page.fill("#login-password", password)
    time.sleep(1)
    for sel in ["button[data-testid='login-button']", "#login-button"]:
        btn = page.query_selector(sel)
        if btn:
            btn.click(force=True)
            print(f"[*] Clicked {sel}", flush=True)
            break

    print("[*] Waiting for captcha...", flush=True)
    for i in range(120):
        time.sleep(1)
        url = page.url
        if "home" in url:
            print("\n[+] LOGGED IN (no captcha needed)!", flush=True)
            break
        # Check for captcha iframe
        has_captcha = page.evaluate("""() => {
            const frames = document.querySelectorAll('iframe');
            for (let f of frames) {
                if (f.src && f.src.includes('arkoselabs')) return f.src;
            }
            return false;
        }""")
        if has_captcha:
            print(f"\n[+] CAPTCHA DETECTED at {i+1}s", flush=True)
            print(f"    iframe src: {has_captcha[:200]}", flush=True)

            # Get all iframes info
            frames_info = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('iframe')).map(f => ({
                    id: f.id,
                    name: f.name,
                    src: (f.src || '').slice(0, 200),
                    title: f.title
                }));
            }""")
            for fi in frames_info:
                print(f"    iframe: {fi}", flush=True)

            # Try to access the arkoselabs iframe
            try:
                arko_frame = page.frame(name="arkose") or page.frame(url=r".*arkoselabs.*")
                if arko_frame:
                    print(f"[+] Found arkoselabs frame: {arko_frame.url[:100]}", flush=True)
                    # Get the challenge data from the frame
                    challenge = arko_frame.evaluate("""() => {
                        return {
                            url: location.href,
                            body: document.body ? document.body.innerHTML.slice(0, 2000) : 'no body'
                        };
                    }""")
                    print(f"    Challenge URL: {challenge['url'][:150]}", flush=True)
                    print(f"    Body: {challenge['body'][:500]}", flush=True)
                else:
                    # List all frames
                    all_frames = page.frames
                    print(f"[*] All frames ({len(all_frames)}):", flush=True)
                    for f in all_frames:
                        if 'arkoselabs' in f.url.lower() or 'funcaptcha' in f.url.lower():
                            print(f"    MATCH: {f.url[:150]}", flush=True)
                        else:
                            print(f"    frame: {f.url[:80]}", flush=True)
            except Exception as e:
                print(f"    Frame error: {e}", flush=True)

            # Wait and poll for inner challenge frame
            print("\n[*] Polling for inner challenge frame...", flush=True)
            inner_frame = None
            for attempt in range(30):
                time.sleep(1)
                # Check all frames for the inner challenge
                for f in page.frames:
                    if '/fc/assets/' in f.url or 'standard/index' in f.url or 'pow/' in f.url:
                        inner_frame = f
                        break
                if inner_frame:
                    break
                # Also re-check the arkoselabs frame for child iframes
                for f in page.frames:
                    if 'arkoselabs.roblox.com/v2/' in f.url:
                        try:
                            children = f.evaluate("""() => {
                                return Array.from(document.querySelectorAll('iframe')).map(x => x.src || '?');
                            }""")
                            if children:
                                print(f"    Child iframes loaded: {children}", flush=True)
                        except:
                            pass
                        break

            # Re-find inner frame (it may be recreated dynamically)
            for f in page.frames:
                if '/fc/assets/' in f.url or 'standard/index' in f.url or 'pow/' in f.url:
                    inner_frame = f
                    break
            if inner_frame:
                print(f"[+] Inner challenge frame found: {inner_frame.url[:150]}", flush=True)

                # Wait for canvas to appear (with re-find on detach)
                print("[*] Waiting for challenge to render...", flush=True)
                for attempt in range(20):
                    time.sleep(1)
                    try:
                        has_canvas = inner_frame.evaluate("document.querySelectorAll('canvas').length")
                        if has_canvas > 0:
                            print(f"    Canvas found at +{attempt+1}s: {has_canvas} canvas elements", flush=True)
                            break
                    except Exception as e:
                        # Frame might be detached, re-find it
                        print(f"    Frame detached, re-finding... ({e})", flush=True)
                        for f in page.frames:
                            if '/fc/assets/' in f.url or 'standard/index' in f.url or 'pow/' in f.url:
                                inner_frame = f
                                break
                        if not inner_frame:
                            print("[-] Inner frame lost forever", flush=True)
                            break

                try:
                    # Get full info from fully loaded challenge
                    info = inner_frame.evaluate("""() => {
                        return {
                            title: document.title,
                            body: (document.body ? document.body.innerHTML.slice(0, 15000) : 'no body'),
                        };
                    }""")
                    print(f"    body: {info['body'][:2000]}", flush=True)

                    # Get challenge data from FunCaptcha API hooks
                    # Before clicking start, try to extract game data
                    print("[*] Extracting MatchGame data...", flush=True)
                    match_data = inner_frame.evaluate("""() => {
                        let r = {};
                        // MatchGame data
                        try {
                            if (window.MatchGame) {
                                r.MatchGame_type = typeof window.MatchGame;
                                // Try to stringify
                                let str = JSON.stringify(window.MatchGame);
                                r.MatchGame_str = str.slice(0, 2000);
                            }
                        } catch(e) { r.MatchGame_err = e.message; }
                        // Check for images/levels
                        try {
                            if (window.MatchGame && window.MatchGame.prototype) {
                                r.MatchGame_proto = Object.getOwnPropertyNames(window.MatchGame.prototype).slice(0, 20);
                            }
                        } catch(e) {}
                        // Check window properties
                        let keys = Object.keys(window).filter(k => 
                            k.includes('Match') || k.includes('Game') || k.includes('level') || k.includes('Level') || k.includes('asset')
                        );
                        r.relevantKeys = keys.slice(0, 20);
                        // Check for WebGL context
                        let canvas = document.createElement('canvas');
                        let gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                        r.hasWebGL = !!gl;
                        return r;
                    }""")
                    print(f"    MatchGame data: {json.dumps(match_data, indent=2, default=str)[:2000]}", flush=True)

                    # Click the start challenge button
                    print("[*] Clicking start challenge...", flush=True)
                    try:
                        inner_frame.click("button:has-text('Начать')", timeout=3000)
                        print("    Clicked!", flush=True)
                    except:
                        try:
                            inner_frame.click("button:has-text('Start')", timeout=3000)
                            print("    Clicked!", flush=True)
                        except Exception as e:
                            print(f"    Could not click: {e}", flush=True)

                    # Wait for challenge to load
                    time.sleep(3)
                    for attempt in range(15):
                        time.sleep(1)
                        try:
                            has_canvas = inner_frame.evaluate("document.querySelectorAll('canvas').length")
                            if has_canvas > 0:
                                print(f"    Canvas appeared at +{attempt+1}s: {has_canvas}", flush=True)
                                break
                        except:
                            # Re-find frame
                            for f in page.frames:
                                if '/fc/assets/' in f.url or 'standard/index' in f.url or 'pow/' in f.url:
                                    inner_frame = f
                                    break

                    # Get challenge data after start
                    print("[*] Getting challenge data after start...", flush=True)
                    fc_data = inner_frame.evaluate("""() => {
                        let r = {};
                        let c = document.querySelectorAll('canvas');
                        r.canvasCount = c.length;
                        r.canvasSizes = Array.from(c).map(x => x.width+'x'+x.height);
                        r.canvasReadable = [];
                        for (let i = 0; i < Math.min(c.length, 10); i++) {
                            try {
                                let data = c[i].toDataURL('image/png');
                                r.canvasReadable.push(data.slice(0, 80) + ' len=' + data.length);
                            } catch(e) {
                                r.canvasReadable.push('TAINTED: ' + e.message);
                            }
                        }
                        // Extract full canvas data for the API
                        r.fullCanvasData = [];
                        for (let i = 0; i < Math.min(c.length, 10); i++) {
                            try {
                                r.fullCanvasData.push(c[i].toDataURL('image/png'));
                            } catch(e) {
                                r.fullCanvasData.push(null);
                            }
                        }
                        // Images
                        let imgs = document.querySelectorAll('img');
                        r.imageCount = imgs.length;
                        r.images = Array.from(imgs).map(i => ({src: i.src.slice(0,200), alt: i.alt}));
                        // GET CHALLENGE TEXT - look for the instruction text
                        let texts = document.querySelectorAll('[class*="text"], [class*="instruction"], p, span, h1, h2, h3');
                        r.instructionTexts = [];
                        for (let t of texts) {
                            let txt = (t.textContent || '').trim();
                            if (txt.length > 5 && txt.length < 200) {
                                r.instructionTexts.push(txt);
                            }
                        }
                        r.instructionTexts = [...new Set(r.instructionTexts)];
                        // Also try to get the challenge text from a visible element
                        let visible = document.querySelector('.challenge-text, .instruction, [data-theme]');
                        if (visible) r.visibleInstruction = visible.textContent.trim();
                        // Game data
                        try {
                            if (window.MatchGame) {
                                let mg = JSON.stringify(window.MatchGame);
                                r.MatchGame_data = mg.slice(0, 3000);
                                // Try to find task description
                                try {
                                    let parsed = JSON.parse(mg);
                                    if (parsed.task) r.task = parsed.task;
                                    if (parsed.instruction) r.task = parsed.instruction;
                                } catch(e) {}
                            }
                        } catch(e) { r.MatchGame_err = e.message; }
                        // Check webpack for game module
                        try {
                            if (window.webpackChunkmatch_game) {
                                r.webpackGame = JSON.stringify(window.webpackChunkmatch_game).slice(0, 500);
                            }
                        } catch(e) {}
                        return r;
                    }""")
                    print(f"    Challenge data: {json.dumps(fc_data, indent=2, default=str)[:5000]}", flush=True)
                except Exception as e:
                    print(f"    Inner inspect error: {e}", flush=True)
                except Exception as e:
                    print(f"    Inner inspect error: {e}", flush=True)
            else:
                print("[-] Inner challenge frame not found", flush=True)
            break
    else:
        print("[*] No captcha detected within 120s", flush=True)

    input("[*] Press Enter to close...")
    proc.kill()
