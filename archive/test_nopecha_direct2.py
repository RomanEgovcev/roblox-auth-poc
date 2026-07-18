"""Test NopeCHA without proxy."""
import os, time, json, requests

PUBLIC_KEY = "476068BF-9607-4799-B53D-966BE98E2B81"

print(f"[1] Calling NopeCHA /v1/task (no proxy)", flush=True)
payload = {
    "type": "funcaptcha",
    "public_key": PUBLIC_KEY,
    "pageurl": "https://www.roblox.com/login",
}

try:
    resp = requests.post(
        "https://api.nopecha.com/v1/task",
        json=payload,
        timeout=30
    )
    print(f"  Status: {resp.status_code}", flush=True)
    print(f"  Text: {resp.text[:500]}", flush=True)
except Exception as e:
    print(f"  Error: {e}", flush=True)

print(f"\nDone.", flush=True)
