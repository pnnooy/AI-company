"""
Quick chat with 皮皮 via command line.
Usage: python tests/chat.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import time
from ai_engine.llm_client import LLMClient

client = LLMClient()
if not client.available:
    print("LLM not configured. Set SJTU_API_KEY env var.")
    sys.exit(1)

client.start()
print("Chat with 皮皮! Type your message (or /quit)")
print()

while True:
    try:
        msg = input("You: ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not msg:
        continue
    if msg == "/quit":
        break

    client.chat(msg, "INTERACT", 0.5, "normal", True, [])

    # Wait for reply
    for _ in range(50):  # ~5s max wait
        time.sleep(0.1)
        result = client.get_result()
        if result and result.get("reply"):
            print(f"皮皮: {result['reply']}")
            break
    else:
        print("皮皮: (thinking...)")

client.stop()
print("Bye!")
