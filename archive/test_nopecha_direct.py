"""Test NopeCHA FunCaptcha solve directly - no rendering needed."""
import os, time, json, requests

PUBLIC_KEY = "476068BF-9607-4799-B53D-966BE98E2B81"
PROXY = "http://127.0.0.1:10809"

# Try NopeCHA FunCaptcha solve
print(f"[1] Calling NopeCHA /v1/funcaptcha with public_key={PUBLIC_KEY}", flush=True)
print(f"  Using proxy: {PROXY}", flush=True)

# Note: NopeCHA API might be at different URLs
# The standard NopeCHA API is at api.nopecha.com

payload = {
    "type": "funcaptcha",
    "public_key": PUBLIC_KEY,
}

# Try with timeout
proxies = {"http": PROXY, "https": PROXY}

try:
    resp = requests.post(
        "https://api.nopecha.com/v1/funcaptcha",
        json=payload,
        proxies=proxies,
        timeout=30
    )
    print(f"  Status: {resp.status_code}", flush=True)
    print(f"  Response: {json.dumps(resp.json(), indent=2)[:1000]}", flush=True)
except Exception as e:
    print(f"  Error: {e}", flush=True)

# Try alternative: create task first, then get result
print(f"\n[2] Trying /v1/task with funcaptcha", flush=True)
payload2 = {
    "type": "funcaptcha",
    "public_key": PUBLIC_KEY,
    "pageurl": "https://www.roblox.com/login",
}

try:
    resp = requests.post(
        "https://api.nopecha.com/v1/task",
        json=payload2,
        proxies=proxies,
        timeout=30
    )
    print(f"  Status: {resp.status_code}", flush=True)
    data = resp.json()
    print(f"  Response: {json.dumps(data, indent=2)[:1000]}", flush=True)
    
    if 'data' in data:
        task_id = data['data']
        print(f"  Task ID: {task_id}", flush=True)
        
        # Wait and get result
        for i in range(30):
            time.sleep(2)
            resp2 = requests.post(
                "https://api.nopecha.com/v1/result",
                json={"id": task_id},
                proxies=proxies,
                timeout=15
            )
            print(f"  Poll {i*2}s: {resp2.status_code} {resp2.text[:200]}", flush=True)
            if resp2.status_code == 200:
                result = resp2.json()
                if result.get('data'):
                    print(f"  Solved! Token: {result['data'][:100]}", flush=True)
                    break
except Exception as e:
    print(f"  Error: {e}", flush=True)

# Try 2captcha style approach
print(f"\n[3] Trying 2captcha-style /in.php", flush=True)
try:
    resp = requests.post(
        "https://api.nopecha.com/in.php",
        data={
            "method": "funcaptcha",
            "publickey": PUBLIC_KEY,
            "pageurl": "https://www.roblox.com/login",
        },
        proxies=proxies,
        timeout=30
    )
    print(f"  Status: {resp.status_code}", flush=True)
    print(f"  Response: {resp.text[:200]}", flush=True)
except Exception as e:
    print(f"  Error: {e}", flush=True)

print(f"\nDone.", flush=True)
