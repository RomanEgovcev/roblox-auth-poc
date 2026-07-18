"""Robust full flow: enforcement → game-core → extract captcha data."""
import os, time, json, sys, re

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

USER = "testuser123"
PASS = "TestPassword123!"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(8)
    
    page.fill("input[name='username']", USER)
    page.fill("input[name='password']", PASS)
    time.sleep(2)
    
    # Trigger enforcement
    print("[1] Triggering enforcement...", flush=True)
    enf = None
    for big_attempt in range(20):
        # Check for enforcement
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf = f
                break
        if enf:
            print(f"  Found enforcement at big attempt {big_attempt+1}!", flush=True)
            break
        
        # Prime PX with Enter
        page.evaluate("""() => {
            const pw = document.querySelector('input[name="password"]');
            if (pw) pw.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter',code:'Enter',keyCode:13,bubbles:true}));
        }""")
        time.sleep(1)
        
        # Dispatch click
        page.evaluate("""() => {
            const btn = document.getElementById('login-button');
            if (btn) btn.dispatchEvent(new MouseEvent('click', {bubbles:true,cancelable:true,view:window}));
        }""")
        time.sleep(5)
    
    if not enf:
        print("  No enforcement. Exiting.", flush=True)
        browser.close()
        exit()
    
    st = re.search(r'&([0-9a-f\-]{36})$', enf.url)
    print(f"  Session: {st.group(1) if st else 'none'}", flush=True)
    
    # Wait for page to settle
    time.sleep(8)
    
    # Call React onClick to trigger auth + game-core
    print("[2] Triggering login via React onClick...", flush=True)
    for attempt in range(10):
        btn_null = page.evaluate("""() => {
            const btn = document.getElementById('login-button');
            return btn === null;
        }""")
        
        if btn_null:
            print(f"  Button null, waiting 2s (attempt {attempt+1})...", flush=True)
            time.sleep(2)
            continue
        
        result = page.evaluate("""() => {
            const btn = document.getElementById('login-button');
            const propsKey = Object.keys(btn).find(k => k.startsWith('__reactProps'));
            if (!propsKey) return {error: 'no reactProps'};
            if (!btn[propsKey]?.onClick) return {error: 'no onClick'};
            btn[propsKey].onClick({});
            return {ok: true};
        }""")
        print(f"  React onClick: {result}", flush=True)
        
        if result.get('ok'):
            break
        time.sleep(2)
    
    # Wait for game-core
    print("\n[3] Waiting for game-core (10s)...", flush=True)
    gc = None
    for i in range(20):
        for f in page.frames:
            if 'game-core' in f.url or 'game_core' in f.url:
                gc = f
                break
        if gc:
            print(f"  Game-core found!", flush=True)
            break
        time.sleep(0.5)
    
    if not gc:
        print("  No game-core!", flush=True)
        print(f"\n=== Frames ===", flush=True)
        for fi, f in enumerate(page.frames):
            print(f"  [{fi}] {f.url[:200]}", flush=True)
        browser.close()
        exit()
    
    print(f"  URL: {gc.url[:250]}", flush=True)
    
    # Extract captcha images
    print("\n[4] Extracting captcha data...", flush=True)
    captcha_data = gc.evaluate("""() => {
        const data = {};
        
        // Find all images
        data.images = Array.from(document.querySelectorAll('img')).map(i => ({
            src: i.src.substring(0, 300),
            alt: i.alt,
            width: i.width,
            height: i.height,
            className: i.className,
        }));
        
        // Find all canvases
        data.canvases = document.querySelectorAll('canvas').length;
        
        // Find all script tags that might contain game data
        data.scripts = Array.from(document.querySelectorAll('script')).map(s => ({
            src: (s.src || '').substring(0, 200),
            id: s.id,
            textLen: (s.text || '').length,
        }));
        
        // Check for window.funCaptcha
        data.funCaptcha = !!window.funCaptcha;
        
        // Find the challenge div
        data.challengeDiv = document.getElementById('game-core')?.innerHTML?.substring(0, 500) || 'N/A';
        data.gameDiv = document.getElementById('game')?.innerHTML?.substring(0, 500) || 'N/A';
        
        return data;
    }""")
    print(f"  Captcha: {json.dumps(captcha_data)[:1000]}", flush=True)
    
    # Take a screenshot
    page.screenshot(path="game_core_captcha.png")
    
    # Keep browser open for inspection
    print("\n[5] Browser open for inspection (30s)...", flush=True)
    time.sleep(30)
    browser.close()
