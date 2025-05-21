from typing import Optional, Dict, Any
import openai
from django.conf import settings
import logging

from .base import TelegramBot

logger = logging.getLogger(__name__)

class PhraseBot(TelegramBot):
    def __init__(self):
        super().__init__(settings.TELEGRAM_TOPIC_BOT_TOKEN)
        self.openai_client = openai.OpenAI(api_key=settings.CHATGPT_API)

    def handle_command(self, message: Dict[str, Any]) -> Optional[str]:
        try:
            message_text = message.get('text', '')
            
            if message_text == '/start':
                return "Hello, I'm your phrase helper bot!"
            
            return self._get_phrase_suggestions(message_text)
        except Exception as e:
            logger.error(f"Error in PhraseBot: {e}")
            return f"An error occurred: {str(e)}"

    def _get_phrase_suggestions(self, topic: str) -> str:
        system_content = (
            f"I'm looking to enhance my English vocabulary for discussions about {topic}. "
            "Could you provide me with some words or phrases, along with examples of how "
            "they are used in informal situations?"
        )

        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": topic},
                {"role": "system", "content": system_content}
            ],
            temperature=0.8,
            max_tokens=3000,
        )
        
        return response.choices[0].message.content

    def handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        pass 