from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import requests
import logging

logger = logging.getLogger(__name__)

class TelegramBot(ABC):
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"

    def send_message(self, chat_id: str, text: str, reply_markup: Optional[Dict] = None) -> Dict[str, Any]:
        """Send a message to a specific chat with optional keyboard markup."""
        url = f"{self.base_url}/sendMessage"
        data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            data["reply_markup"] = reply_markup
        try:
            response = requests.post(url, json=data)
            return response.json()
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            logger.error(f"Response content: {getattr(response, 'content', 'N/A')}")
            return {"error": str(e)}

    def edit_message(self, chat_id: str, message_id: int, text: str, reply_markup: Optional[Dict] = None) -> Dict[str, Any]:
        """Edit an existing message."""
        url = f"{self.base_url}/editMessageText"
        data = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            data["reply_markup"] = reply_markup
        try:
            response = requests.post(url, json=data)
            return response.json()
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            return {"error": str(e)}

    def create_inline_keyboard(self, buttons: List[List[Dict[str, str]]]) -> Dict:
        """Create an inline keyboard markup from a list of button rows."""
        return {"inline_keyboard": buttons}

    def answer_callback_query(self, callback_query_id: str, text: Optional[str] = None) -> Dict[str, Any]:
        """Answer a callback query from an inline keyboard button."""
        url = f"{self.base_url}/answerCallbackQuery"
        data = {"callback_query_id": callback_query_id}
        if text:
            data["text"] = text
        try:
            response = requests.post(url, json=data)
            return response.json()
        except Exception as e:
            logger.error(f"Error answering callback query: {e}")
            return {"error": str(e)}

    @abstractmethod
    def handle_command(self, message: Dict[str, Any]) -> Optional[str]:
        """Handle incoming commands - to be implemented by specific bots."""
        pass

    @abstractmethod
    def handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        """Handle callback queries from inline keyboards - to be implemented by specific bots."""
        pass 