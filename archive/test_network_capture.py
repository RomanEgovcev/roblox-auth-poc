import subprocess, time, json
from playwright.sync_api import sync_playwright

ext_path = r'C:\Users\regov\Desktop\lua\chromium_automation'
profile = r'C:\Users\regov\Desktop\lua\pw_profile'

with sync_playwright() as p:
    chrome_path = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
    proc = subprocess.Popen(
        [chrome_path, f'--user-data-dir={profile}', f'--load-extension={ext_path}',
         '--no-first-run', '--remote-debugging-port=9222',
         '--remote-allow-origins=*',
         '--no-proxy-server'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(4)
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.set_default_timeout(15000)

    captcha_urls = []
    def on_req(req):
        url = req.url
        if any(x in url for x in ['arkoselabs', 'funcaptcha']):
            if any(x in url for x in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                captcha_urls.append(('IMG', url))
            elif any(x in url for x in ['game', 'api', 'config', 'challenge']):
                captcha_urls.append(('API', url))
        if 'nopecha' in url.lower():
            captcha_urls.append(('NOPECHA', url))
    page.on('request', on_req)

    page.goto('https://www.roblox.com/login', wait_until='domcontentloaded')
    page.wait_for_selector('#login-username', timeout=30000)
    page.fill('#login-username', 'CheatingHitmanner')
    page.fill('#login-password', 'TestAccountOpenCode123')
    time.sleep(0.5)
    btn = page.query_selector('button[data-testid="login-button"]')
    if btn:
        btn.click(force=True)

    print('[*] Waiting for captcha...', flush=True)
    for i in range(30):
        time.sleep(1)
        has = page.evaluate('document.querySelector(\'iframe[src*="arkoselabs"]\') ? true : false')
        if has:
            print(f'[+] Captcha at {i+1}s', flush=True)
            time.sleep(5)
            break

    print(f'[*] Captured {len(captcha_urls)} requests:', flush=True)
    for t, u in captcha_urls:
        print(f'  [{t}] {u[:200]}', flush=True)
    
    if len(captcha_urls) == 0:
        print('[*] No captcha URLs found. Trying page screenshot...', flush=True)
        # Navigate into captcha iframe and look for images
        for f in page.frames:
            if 'standard/index' in f.url or 'fc/assets' in f.url:
                # Get all resource URLs
                urls = f.evaluate("""() => {
                    let urls = [];
                    // All elements with src or srcset
                    document.querySelectorAll('*').forEach(el => {
                        if (el.src) urls.push(el.src);
                        if (el.href) urls.push(el.href);
                        if (el.style && el.style.backgroundImage) {
                            let m = el.style.backgroundImage.match(/url\(['"]?([^'")]+)['"]?\)/);
                            if (m) urls.push(m[1]);
                        }
                    });
                    return [...new Set(urls)].filter(u => u.startsWith('http'));
                }""")
                for u in urls:
                    if any(x in u for x in ['.png', '.jpg', '.webp', 'game', 'asset']):
                        print(f'  [SRC] {u[:200]}', flush=True)

    proc.kill()
