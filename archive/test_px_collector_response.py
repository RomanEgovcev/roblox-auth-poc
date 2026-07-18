"""Capture real PX collector response."""
import os, time, json

os.system("taskkill /F /IM chrome.exe 2>NUL")
time.sleep(2)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    collector_responses = []
    def track(r):
        if 'collector' in r.url and 'px' in r.url:
            collector_responses.append(r)
    page.on("response", track)
    
    page.goto("https://www.roblox.com/login", wait_until="domcontentloaded")
    time.sleep(8)
    
    page.fill("input[name='username']", "testuser123")
    page.fill("input[name='password']", "wrongpass123!")
    
    page.click("#login-button", timeout=5000)
    
    time.sleep(5)
    
    for r in collector_responses:
        print(f"URL: {r.url[:100]}")
        print(f"Status: {r.status}")
        try:
            body = r.text()
            print(f"Body: {body[:300]}")
        except Exception as e:
            print(f"Body error: {e}")
        print("---")
    
    page.screenshot(path="collector_test.png")
    input("Enter...")
    browser.close()
