"""
Telegram Bot Setup Helper
Run this script to test your Telegram bot configuration.
"""

import os
import sys

# Add project root to path
_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _root)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(_root, ".env"))
except ImportError:
    pass

from notifier import TelegramNotifier


def main():
    print("=" * 60)
    print("TELEGRAM BOT SETUP GUIDE")
    print("=" * 60)
    print()
    
    # Check if already configured
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    
    if token and chat_id:
        print("✅ Telegram credentials found in environment!")
        print(f"   Token: {token[:10]}...{token[-5:]}")
        print(f"   Chat ID: {chat_id}")
        print()
        
        notifier = TelegramNotifier(token=token, chat_id=chat_id)
        
        print("Testing connection...")
        if notifier.test_connection():
            print()
            print("Sending test message...")
            if notifier.send_message("🧪 *Test Successful!*\n\nYour Trading Signal Analyzer is connected to Telegram!"):
                print("✅ Test message sent! Check your Telegram.")
            else:
                print("❌ Failed to send test message")
        else:
            print("❌ Connection test failed. Please check your credentials.")
    else:
        print("❌ Telegram not configured yet.")
        print()
        print("Follow these steps to set up Telegram notifications:")
        print()
        print("STEP 1: Create a Telegram Bot")
        print("  1. Open Telegram and search for @BotFather")
        print("  2. Send /newbot command")
        print("  3. Follow prompts to name your bot")
        print("  4. Copy the bot token (e.g., 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz)")
        print()
        print("STEP 2: Get Your Chat ID")
        print("  1. Search for @userinfobot on Telegram")
        print("  2. Start the bot")
        print("  3. Copy your chat ID (a number like 123456789)")
        print()
        print("STEP 3: Configure the Bot")
        print("  Option A - Environment Variables:")
        print("    Windows: set TELEGRAM_BOT_TOKEN=your_token")
        print("    Windows: set TELEGRAM_CHAT_ID=your_chat_id")
        print("    Mac/Linux: export TELEGRAM_BOT_TOKEN=your_token")
        print("    Mac/Linux: export TELEGRAM_CHAT_ID=your_chat_id")
        print()
        print("  Option B - Create .env file:")
        print(f"    Copy .env.example to .env and fill in your values")
        print()
        print("  Option C - Run with arguments:")
        print("    python main.py auto --telegram --token YOUR_TOKEN --chat-id YOUR_CHAT_ID")
        print()
    
    print()
    print("=" * 60)
    print("USAGE EXAMPLES")
    print("=" * 60)
    print()
    print("Automated Scanning (CLI mode):")
    print("  python main.py auto --interval 15")
    print("  python main.py auto --interval 5 --telegram")
    print("  python main.py auto -i 15 -t -m equity crypto")
    print()
    print("Interactive Mode:")
    print("  python main.py")
    print("  > auto 15")
    print("  > auto 5 telegram")
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
