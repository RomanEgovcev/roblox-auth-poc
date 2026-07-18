import requests
url = "https://arkoselabs.roblox.com/v2/4.4.2/enforcement.162a14c47922edcced45ca4d9b28e5d5.js"
r = requests.get(url, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://arkoselabs.roblox.com/",
}, timeout=15)
print(f"Status: {r.status_code}, size: {len(r.text)}")
with open("enforcement_162a14c47922edcced45ca4d9b28e5d5.js", "w", encoding="utf-8") as f:
    f.write(r.text)
print("Saved")
