"""
Test the PoW puzzle endpoint and full login flow.
"""
import json, base64, time, sys
from curl_cffi import requests as curl_requests

SESSION = curl_requests.Session(impersonate="chrome123")
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Origin": "https://www.roblox.com",
    "Referer": "https://www.roblox.com/",
})

def solve_pow(N_str, A, T):
    N = int(N_str)
    val = A % N
    for _ in range(T):
        val = (val * val) % N
    return str(val)

# Step 1: Get CSRF
print("[1] Getting CSRF...")
resp = SESSION.post("https://auth.roblox.com/v2/login", json={}, timeout=10)
csrf = resp.headers.get("x-csrf-token", "")
print(f"    CSRF: {csrf[:20]}...")

# Step 2: Try login with fake creds
print("\n[2] Attempting login (will trigger challenge)...")
resp = SESSION.post(
    "https://auth.roblox.com/v2/login",
    json={"ctype": "Username", "cvalue": "TestUser", "password": "FakePass123!"},
    headers={"x-csrf-token": csrf},
    timeout=10
)
print(f"    HTTP {resp.status_code}")

if resp.status_code == 403:
    chall_id = resp.headers.get("rblx-challenge-id", "")
    chall_type = resp.headers.get("rblx-challenge-type", "")
    chall_meta_b64 = resp.headers.get("rblx-challenge-metadata", "")
    print(f"    Challenge ID: {chall_id}")
    print(f"    Challenge Type: {chall_type}")
    
    if chall_meta_b64:
        metadata = json.loads(base64.b64decode(chall_meta_b64))
        print(f"    Metadata: {json.dumps(metadata, indent=2)}")
    
    if chall_type == "proofofwork":
        print("\n[3] PoW challenge detected! Getting puzzle...")
        pw_url = "https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle"
        session_id = metadata.get("sessionId", "")
        print(f"    Session ID: {session_id}")
        
        puzzle_resp = SESSION.get(f"{pw_url}?sessionID={session_id}", timeout=10)
        print(f"    Puzzle HTTP {puzzle_resp.status_code}")
        
        if puzzle_resp.status_code == 200:
            puzzle = puzzle_resp.json()
            print(f"    Puzzle response: {json.dumps(puzzle, indent=2)}")
            
            artifacts = json.loads(puzzle.get("artifacts", "{}"))
            N_str = artifacts.get("N", "")
            A = int(artifacts.get("A", 0))
            T = int(artifacts.get("T", 0))
            print(f"\n[4] Solving PoW: N_len={len(N_str)}, A={A}, T={T}")
            
            solution = solve_pow(N_str, A, T)
            print(f"    Solution length: {len(solution)}")
            
            print("\n[5] Submitting PoW solution...")
            csrf2 = SESSION.post("https://auth.roblox.com/v2/login", json={}, timeout=10).headers.get("x-csrf-token", "")
            
            solve_resp = SESSION.post(
                pw_url,
                json={"sessionID": session_id, "solution": solution, "prefix": ""},
                headers={"x-csrf-token": csrf2},
                timeout=10
            )
            print(f"    Submit HTTP {solve_resp.status_code}")
            print(f"    Submit response: {solve_resp.text[:300]}")
            
            if solve_resp.status_code == 200:
                solve_data = solve_resp.json()
                redemption_token = solve_data.get("redemptionToken", "")
                print(f"    Redemption token: {redemption_token[:50] if redemption_token else 'NONE'}...")
                
                if redemption_token:
                    print("\n[6] Retrying login with redemption token...")
                    csrf3 = SESSION.post("https://auth.roblox.com/v2/login", json={}, timeout=10).headers.get("x-csrf-token", "")
                    
                    retry_resp = SESSION.post(
                        "https://auth.roblox.com/v2/login",
                        json={"ctype": "Username", "cvalue": "TestUser", "password": "FakePass123!"},
                        headers={
                            "x-csrf-token": csrf3,
                            "rblx-challenge-id": chall_id,
                            "rblx-challenge-type": "proofofwork",
                            "rblx-challenge-redemption-token": redemption_token,
                        },
                        timeout=10
                    )
                    print(f"    Retry HTTP {retry_resp.status_code}")
                    
                    if ".ROBLOSECURITY" in retry_resp.cookies:
                        print(f"\n✅ SUCCESS! Cookie: {retry_resp.cookies['.ROBLOSECURITY'][:50]}...")
                    else:
                        print(f"    Response: {retry_resp.text[:300]}")
                        
                        # Try with rblx-challenge-metadata header too
                        print("\n[7] Also trying with metadata header...")
                        csrf4 = SESSION.post("https://auth.roblox.com/v2/login", json={}, timeout=10).headers.get("x-csrf-token", "")
                        
                        retry2 = SESSION.post(
                            "https://auth.roblox.com/v2/login",
                            json={"ctype": "Username", "cvalue": "TestUser", "password": "FakePass123!"},
                            headers={
                                "x-csrf-token": csrf4,
                                "rblx-challenge-id": chall_id,
                                "rblx-challenge-type": "proofofwork",
                                "rblx-challenge-redemption-token": redemption_token,
                                "rblx-challenge-metadata": chall_meta_b64,
                            },
                            timeout=10
                        )
                        print(f"    Retry2 HTTP {retry2.status_code}")
                        print(f"    Response: {retry2.text[:300]}")
        
        else:
            print(f"    Error response: {puzzle_resp.text[:300]}")
    
    elif chall_type == "funcaptcha" or "arkose" in chall_type.lower():
        print("\n[3] FunCaptcha challenge detected!")
        print("    Need to solve manually via HTML page.")
    
    else:
        print(f"\n[3] Unknown challenge type: {chall_type}")
else:
    print(f"    Response: {resp.text[:200]}")

print("\nDone.")
