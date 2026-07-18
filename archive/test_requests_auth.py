import requests, json, re

s = requests.Session()
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
})

r = s.get("https://www.roblox.com/login", timeout=15)
print(f"Login page: {r.status_code}, {len(r.text)} bytes")

# Extract CSRF token
csrf_match = re.search(r'csrf-token.*?content="([^"]+)"', r.text, re.IGNORECASE)
if csrf_match:
    csrf = csrf_match.group(1)
    print(f"CSRF token (meta content): {csrf}")
else:
    csrf_match2 = re.search(r'csrf-token[\s\S]*?data-token="([^"]+)"', r.text)
    if csrf_match2:
        csrf = csrf_match2.group(1)
        print(f"CSRF token (data-token): {csrf}")
    else:
        csrf = ""
        print("No CSRF token found")

print(f"\nCookies: {dict(s.cookies)}")

# Try login
print("\nTrying login...")
headers = {
    "Referer": "https://www.roblox.com/login",
    "Origin": "https://www.roblox.com",
}
if csrf:
    headers["X-CSRF-TOKEN"] = csrf

r2 = s.post("https://www.roblox.com/v2/login", data={
    "username": "testuser123",
    "password": "WrongPass123!",
}, headers=headers, timeout=15)
print(f"Login response: {r2.status_code}")
print(f"Response headers:")
for k, v in r2.headers.items():
    if 'challenge' in k.lower() or 'captcha' in k.lower() or 'rblx' in k.lower() or k.startswith('X-') or k.startswith('x-'):
        print(f"  {k}: {v}")
print(f"Body: {r2.text[:1000]}")
