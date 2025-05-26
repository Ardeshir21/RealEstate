import requests
import json
import argparse
from typing import Optional, Dict, Any

class TelegramReminder:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, chat_id: str, text: str, reply_markup: Optional[Dict] = None) -> bool:
        """Send a message to a specific chat_id."""
        url = f"{self.base_url}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)

        try:
            response = requests.post(url, json=data)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
            return False

    def create_snooze_keyboard(self, birthday_id: int, days_until: int) -> Dict[str, Any]:
        """Create inline keyboard with snooze options."""
        buttons = []
        snooze_options = []
        
        # Add snooze options if there are enough days remaining
        if days_until > 3:
            snooze_options.append({"text": "⏰ 3 days before", "callback_data": f"snooze_{birthday_id}_3"})
        if days_until > 2:
            snooze_options.append({"text": "⏰ 2 days before", "callback_data": f"snooze_{birthday_id}_2"})
        if days_until > 1:
            snooze_options.append({"text": "⏰ 1 day before", "callback_data": f"snooze_{birthday_id}_1"})
        
        # Create rows of 2 buttons each
        for i in range(0, len(snooze_options), 2):
            row = snooze_options[i:i+2]
            buttons.append(row)
        
        # Add dismiss button
        buttons.append([{"text": "✅ Dismiss", "callback_data": f"dismiss_reminder_{birthday_id}"}])
        
        return {"inline_keyboard": buttons}

def main():
    parser = argparse.ArgumentParser(description='Send a test birthday reminder via Telegram')
    parser.add_argument('--token', type=str, required=True, help='Your Telegram bot token')
    parser.add_argument('--chat_id', type=str, required=True, help='Target chat ID to send reminder to')
    parser.add_argument('--name', type=str, required=True, help='Name of the person having birthday')
    parser.add_argument('--days', type=int, default=3, help='Days until birthday (default: 3)')
    parser.add_argument('--birthday_id', type=int, default=1, help='Birthday ID for snooze functionality')
    
    args = parser.parse_args()
    
    # Initialize bot
    bot = TelegramReminder(args.token)
    
    # Create message based on days
    if args.days == 0:
        message = (
            f"🎉 Happy Birthday! 🎂\n\n"
            f"Today is {args.name}'s birthday!\n"
        )
        keyboard = None
    else:
        message = (
            f"🎂 Birthday Reminder!\n\n"
            f"👤 {args.name}'s birthday is in {args.days} days!\n\n"
            f"Want to be reminded later? Use the snooze buttons below:"
        )
        keyboard = bot.create_snooze_keyboard(args.birthday_id, args.days)
    
    # Send message
    success = bot.send_message(args.chat_id, message, keyboard)
    
    if success:
        print(f"✅ Successfully sent test reminder to chat {args.chat_id}")
    else:
        print("❌ Failed to send reminder")

if __name__ == "__main__":
    main() 