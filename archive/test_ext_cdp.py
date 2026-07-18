import os, sys, time, json, asyncio
from playwright.async_api import async_playwright

ext_path = os.path.abspath(r'C:\Users\regov\Desktop\lua\chromium_automation')
username = sys.argv[1] if len(sys.argv) > 1 else "CheatingHitmanner"
password = sys.argv[2] if len(sys.argv) > 2 else ""

async def main():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir='pw_profile',
            headless=False,
            args=["--no-proxy-server"],
        )
        page = await context.new_page()
        page.set_default_timeout(15000)

        # Load extension via CDP
        cdp = await context.new_cdp_session(page)
        try:
            result = await cdp.send("Extensions.loadUnpacked", {"path": ext_path})
            ext_id = result.get("id")
            print(f"[+] Extension loaded via CDP: {ext_id}", flush=True)
        except Exception as e:
            print(f"[-] CDP load failed: {e}", flush=True)
            # Fallback: try via extensions page
            ext_page = await context.new_page()
            await ext_page.goto("chrome://extensions/", wait_until="domcontentloaded")
            await asyncio.sleep(2)
            # Click "Load unpacked" button
            try:
                btn = await ext_page.query_selector("cr-toolbar cr-button:has-text('Load unpacked'), .page-container cr-button:has-text('Load unpacked')")
                if btn:
                    await btn.click()
                    await asyncio.sleep(2)
                    print("[*] Load unpacked clicked (needs file dialog)", flush=True)
                else:
                    print("[*] Load unpacked button not found", flush=True)
            except Exception as e2:
                print(f"[-] Ext page error: {e2}", flush=True)
            await ext_page.close()

        # Now navigate to login page
        await page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
        await page.wait_for_selector("#login-username", timeout=30000)

        # Fill form
        await page.fill("#login-username", username)
        await page.fill("#login-password", password)
        await asyncio.sleep(1)

        # Click login
        for sel in ["button[data-testid='login-button']", "#login-button"]:
            btn = await page.query_selector(sel)
            if btn:
                await btn.click(force=True)
                print(f"[*] Clicked: {sel}", flush=True)
                break

        print("[*] Observing. Close browser when done.\n", flush=True)

        for i in range(120):
            await asyncio.sleep(1)
            url = page.url
            info = f"  [{i+1}s] {url[:70]}"
            try:
                dom = await page.evaluate("""() => {
                    const arkose = document.querySelector('#arkose-0, .arkose-wrapper');
                    const captcha = document.querySelector('iframe[src*=\"arkoselabs\"]');
                    const error = document.querySelector('.error-message, .alert-error, [class*=\"error\"]:not([class*=\"hidden\"])');
                    return {arkose: !!arkose, captcha: !!captcha, error: error ? error.textContent.trim().slice(0,100) : null};
                }""")
                if dom['arkose'] or dom['captcha']:
                    info += " [CAPTCHA]"
                if dom['error']:
                    info += f" [ERROR: {dom['error']}]"
            except:
                pass
            print(info, flush=True)
            if "home" in url:
                print("\n[+] LOGGED IN!", flush=True)
                break

        await context.close()

asyncio.run(main())
