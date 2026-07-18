"""Find the actual Challenge.js script and analyze PX behavior."""
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
    ctx = browser.new_context(bypass_csp=True)
    page = ctx.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="load", timeout=20000)
    time.sleep(8)
    
    # Find ALL scripts with their full content lengths
    scripts = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('script')).map((s, i) => ({
            idx: i,
            src: (s.src || '').substring(0, 300),
            id: s.id || '',
            type: s.type || '',
            textLen: (s.text || '').length,
            textPreview: (s.text || '').substring(0, 100),
        }));
    }""")
    
    print(f"=== Scripts ({len(scripts)}) ===", flush=True)
    for s in scripts:
        if s['textLen'] > 100:
            print(f"  [{s['idx']}] id={s['id']} src_len={len(s['src'])} text_len={s['textLen']}", flush=True)
            print(f"    src={s['src'][:200]}", flush=True)
            print(f"    preview={s['textPreview']}", flush=True)
        elif s['src']:
            print(f"  [{s['idx']}] id={s['id']} src={s['src'][:200]}", flush=True)
    
    # Check for PX-related functions
    print("\n=== PX details ===", flush=True)
    px_info = page.evaluate("""() => {
        const info = {};
        info.keys = PX ? Object.keys(PX) : 'NX';
        info.setChallengeType = typeof PX?.setChallenge;
        info.EventsType = typeof PX?.Events;
        info.ClientUuid = PX?.ClientUuid?.substring(0, 20);
        
        // Check chef-boy-ardee content
        const cba = document.getElementById('chef-boy-ardee');
        info.chefLen = cba?.text?.length || 0;
        info.chefStart = cba?.text?.substring(0, 200) || '';
        
        return info;
    }""")
    print(f"  {json.dumps(px_info, indent=2)[:500]}", flush=True)
    
    # Check what PX.Events contains
    events = page.evaluate("""() => {
        if (!PX?.Events) return 'NX';
        const keys = Object.keys(PX.Events);
        return keys.slice(0, 20);
    }""")
    print(f"\n  PX.Events keys: {events}", flush=True)
    
    # Check if any click handlers reference challenge
    click_check = page.evaluate("""() => {
        const btn = document.getElementById('login-button');
        const handlers = getEventListeners?.(btn) || [];
        return {listeners: handlers?.length || 'NX', onclick: typeof btn?.onclick};
    }""")
    print(f"\n  Button handlers: {click_check}", flush=True)
    
    browser.close()
