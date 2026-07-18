"""Inspect login page for challenge infrastructure."""
import os, time, json, base64

os.system("taskkill /F /IM chrome.exe 2>$null")
time.sleep(2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})
    
    page.goto("https://www.roblox.com/login", wait_until="networkidle", timeout=30000)
    time.sleep(5)
    
    # Check for challenge infrastructure
    info = page.evaluate("""() => ({
        hasIframes: document.querySelectorAll('iframe').length,
        hasCaptcha: !!document.querySelector('.captcha, .g-recaptcha, #captcha'),
        hasChallengeContainer: !!document.querySelector('#challenge-container, [class*="challenge"], [id*="challenge"]'),
        robloxGlobal: typeof Roblox !== 'undefined' && !!Roblox.AccountIntegrityChallengeService,
        availableServices: Roblox && Roblox.AccountIntegrityChallengeService ? Object.keys(Roblox.AccountIntegrityChallengeService) : [],
        iframes: Array.from(document.querySelectorAll('iframe')).map(f => ({id: f.id, src: f.src?.substring(0,100), className: f.className})),
        challengeElements: Array.from(document.querySelectorAll('[id*="challenge" i], [class*="challenge" i]')).map(e => ({id: e.id, className: e.className, tag: e.tagName})),
        loginButtonHTML: document.querySelector('button[type="submit"], .login-button')?.outerHTML?.substring(0, 300),
    })""")
    
    print("Page challenge info:", flush=True)
    for k, v in info.items():
        print(f"  {k}: {v}", flush=True)
    
    # Check for the Challenge.js bundle
    scripts = page.evaluate("""() => 
        Array.from(document.querySelectorAll('script')).map(s => ({
            src: s.src?.substring(0, 120),
            id: s.id,
            textLength: s.text?.length || 0
        })).filter(s => s.textLength > 100 || s.src.includes('challenge') || s.src.includes('Challenge'))
    """)
    
    print(f"\nRelevant scripts ({len(scripts)}):", flush=True)
    for s in scripts:
        print(f"  src={s['src'][:100]}, id={s['id']}, len={s['textLength']}", flush=True)
    
    # Check what happens when we make a fetch login that returns challenge
    # Can we trigger the challenge processing
    hasChallengeJS = page.evaluate("""() => {
        const r = Roblox && Roblox.AccountIntegrityChallengeService;
        return {
            hasProofOfWork: !!(r && r.ProofOfWork),
            hasCaptcha: !!(r && r.Captcha),
            hasGeneric: !!(r && r.Generic),
            hasProofOfSpace: !!(r && r.ProofOfSpace),
        }
    }""")
    print(f"\nChallenge services available: {hasChallengeJS}", flush=True)
    
    # Check window.parent for hybrid
    parentInfo = page.evaluate("""() => {
        try {
            return { parent: window.parent !== window, parentOrigin: window.parent?.location?.origin || 'n/a' };
        } catch(e) {
            return { parent: false, error: e.message };
        }
    }""")
    print(f"Window parent: {parentInfo}", flush=True)
    
    time.sleep(2)
    browser.close()
