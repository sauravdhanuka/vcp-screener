import os
import sys

# Add src to sys.path to ensure module is found
sys.path.append(os.path.join(os.getcwd(), 'src'))

from vcp_screener.config import settings

print("--- Environment Variables ---")
found_env = False
for key, value in os.environ.items():
    if "VCP" in key or "TELEGRAM" in key:
        found_env = True
        masked_val = "***"
        if len(value) > 8:
            masked_val = value[:4] + "***" + value[-4:]
        print(f"{key}: {masked_val}")

if not found_env:
    print("No VCP_ or TELEGRAM_ environment variables found.")

print("\n--- Loaded Settings from Config ---")
token = settings.telegram_bot_token
chat_id = settings.telegram_chat_id

masked_token = (token[:4] + "***" + token[-4:]) if token and len(token) > 8 else "***"
masked_chat_id = (chat_id[:4] + "***" + chat_id[-4:]) if chat_id and len(chat_id) > 8 else "***"

print(f"settings.telegram_bot_token: {masked_token if token else 'Empty/None'}")
print(f"settings.telegram_chat_id: {masked_chat_id if chat_id else 'Empty/None'}")

if not token:
    print("\nERROR: telegram_bot_token is MISSING within the application config.")
else:
    print("\nSUCCESS: telegram_bot_token is loaded.")

if not chat_id:
    print("ERROR: telegram_chat_id is MISSING within the application config.")
else:
    print("SUCCESS: telegram_chat_id is loaded.")
