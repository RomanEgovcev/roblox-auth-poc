import os, time
from playwright.sync_api import sync_playwright

pw_profile = os.path.abspath(r'C:\Users\regov\Desktop\lua\pw_profile')

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=pw_profile, headless=False,
        args=["--no-proxy-server"],
    )
    page = context.pages[0]
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    print("[*] Браузер открыт. Введи логин/пароль и нажми Login.")
    print("[*] Если появится капча — скажи мне.")
    print("[*] Жду 120 секунд...")
    time.sleep(120)
    print("[*] Закрываю...")
    context.close()
