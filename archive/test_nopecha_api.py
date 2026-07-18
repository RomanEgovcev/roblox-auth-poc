import requests

# Check IP-based auth status (no key)
r = requests.get("https://api.nopecha.com/v1/status")
print("Status:", r.status_code)
if r.status_code == 200:
    data = r.json()
    print(f"Plan: {data.get('plan')}")
    print(f"Credit: {data.get('credit')}")
    print(f"Status: {data.get('status')}")
else:
    print("Response:", r.text[:500])
