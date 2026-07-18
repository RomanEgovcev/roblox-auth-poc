"""Check game-core in depth, wait for challenge images to load."""
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
    for big_attempt in range(20):
        for f in page.frames:
            if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
                enf = f
                break
        if 'enf' in dir() and enf:
            break
        
        page.evaluate("""() => {
            const pw = document.querySelector('input[name="password"]');
            if (pw) pw.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter',code:'Enter',keyCode:13,bubbles:true}));
        }""")
        time.sleep(1)
        
        page.evaluate("""() => {
            const btn = document.getElementById('login-button');
            if (btn) btn.dispatchEvent(new MouseEvent('click', {bubbles:true,cancelable:true,view:window}));
        }""")
        time.sleep(5)
    
    enf = None
    for f in page.frames:
        if 'arkoselabs.roblox.com' in f.url and 'enforcement.' in f.url:
            enf = f
            break
    
    if not enf:
        print("No enforcement!", flush=True)
        browser.close()
        exit()
    
    print(f"  Enforcement found!", flush=True)
    
    # Wait for game-core
    print("[2] Waiting 15s for game-core to load...", flush=True)
    gc = None
    for i in range(60):
        for f in page.frames:
            if 'game-core' in f.url or 'game_core' in f.url:
                gc = f
                break
        if gc:
            break
        time.sleep(0.25)
    
    if gc:
        print(f"  Game-core found!", flush=True)
    else:
        print("  No game-core. Checking...", flush=True)
        # Check if game-core is nested in enforcement
        try:
            enf_iframes = enf.evaluate("""() => ({
                count: document.querySelectorAll('iframe').length,
                urls: Array.from(document.querySelectorAll('iframe')).map(i => i.src.substring(0, 200)),
            })""")
            print(f"  Enforcement iframes: {json.dumps(enf_iframes)[:500]}", flush=True)
        except:
            print("  Can't read enforcement", flush=True)
        
        # Check all frames again
        print(f"\n  All frames:", flush=True)
        for fi, f in enumerate(page.frames):
            print(f"  [{fi}] {f.url[:200]}", flush=True)
        
        browser.close()
        exit()
    
    print(f"  GC URL: {gc.url[:250]}", flush=True)
    
    # Monitor the game-core for 20 seconds, checking for images
    print("[3] Monitoring game-core for 20s...", flush=True)
    for i in range(40):
        state = gc.evaluate("""() => {
            const imgs = document.querySelectorAll('img');
            const canvases = document.querySelectorAll('canvas');
            const bodyLen = document.body?.innerHTML?.length || 0;
            
            // Check for match game specific elements
            const matchCells = document.querySelectorAll('[class*="cell"], [class*="tile"], [class*="match"]');
            const gameBoard = document.getElementById('game-board') || document.querySelector('[class*="board"]');
            
            return {
                t: new Date().toISOString().substring(11, 19),
                images: imgs.length,
                imgSrcs: Array.from(imgs).slice(0, 5).map(i => i.src.substring(0, 150)),
                canvases: canvases.length,
                bodyLen,
                matchCells: matchCells.length,
                hasGameBoard: !!gameBoard,
                challengeDiv: document.getElementById('game-core')?.childElementCount || 0,
                gameDiv: document.getElementById('game')?.childElementCount || 0,
            };
        }""")
        if state['images'] > 0 or state['canvases'] > 0 or state['bodyLen'] > 1000:
            print(f"  t={state['t']} imgs={state['images']} can={state['canvases']} bodyLen={state['bodyLen']}", flush=True)
        
        if state['bodyLen'] > 500:
            print(f"  State: {json.dumps(state)}", flush=True)
            break
        
        time.sleep(0.5)
    
    # Final state
    final = gc.evaluate("""() => {
        const bodyHTML = document.body?.innerHTML || '';
        return {
            bodyLen: bodyHTML.length,
            bodyHTML: bodyHTML.substring(0, 1000),
            funCaptcha: !!window.funCaptcha,
        };
    }""")
    print(f"\n  Final body: {json.dumps(final)[:1000]}", flush=True)
    
    page.screenshot(path="game_core_body.png")
    
    time.sleep(10)
    browser.close()
