"""Test Edge via Playwright launch_persistent_context with extension."""
import os, time, json, sys
from playwright.sync_api import sync_playwright

ext_path = os.path.abspath("chromium_automation")
profile = os.path.abspath("pw_edge2")

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=profile,
        headless=False,
        channel="msedge",
        args=[
            f"--load-extension={ext_path}",
            "--disable-features=ChromeWhatsNewUI,InterestFeedContentSuggestions",
            "--no-first-run",
        ]
    )
    
    page = context.pages[0] if context.pages else context.new_page()
    
    # Check SW registrations via CDP
    cdp = context.new_cdp_session(page)
    cdp.send("ServiceWorker.enable")
    time.sleep(2)
    
    # Get initial SW registrations
    try:
        sw = cdp.send("ServiceWorker.getAllRegistrations")
        print(f"Initial SW: {json.dumps(sw, indent=2, default=str)[:500]}", flush=True)
    except Exception as e:
        print(f"  SW error: {e}", flush=True)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(3)
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    page.click("#login-button")
    print("[*] Login submitted", flush=True)
    
    for i in range(60):
        frames = page.frames
        game = any('game-core' in f.url for f in frames)
        if game:
            print(f"[+] Game-core at {i}s!", flush=True)
            # Check SW now
            try:
                sw = cdp.send("ServiceWorker.getAllRegistrations")
                for r in sw.get('registrations', []):
                    scope = r.get('scopeURL', '')
                    if 'dknlfmjaanfblgfdfebhijalfmhmjjjo' in scope:
                        print(f"[!!!] NopeCHA SW registered!", flush=True)
                    else:
                        print(f"  SW: {scope}", flush=True)
            except Exception as e:
                print(f"  SW: {e}", flush=True)
            break
        time.sleep(1)
    else:
        print("[-] No captcha in 60s", flush=True)
    
    # Final SW check
    try:
        sw = cdp.send("ServiceWorker.getAllRegistrations")
        print(f"\nAll SW: {json.dumps(sw, indent=2, default=str)[:1000]}", flush=True)
    except Exception as e:
        print(f"SW: {e}", flush=True)
    
    context.close()
