from typing import Optional, Dict, Any
import openai
from django.conf import settings
import logging

from .base import TelegramBot

logger = logging.getLogger(__name__)

class DictionaryBot(TelegramBot):
    def __init__(self):
        super().__init__(settings.TELEGRAM_DICTIONARY_BOT_TOKEN)
        self.openai_client = openai.OpenAI(api_key=settings.CHATGPT_API)

    def handle_command(self, message: Dict[str, Any]) -> Optional[str]:
        try:
            message_text = message.get('text', '')
            
            if message_text == '/start':
                return "Hello, I'm your dictionary bot!"
            
            return self._get_dictionary_definition(message_text)
        except Exception as e:
            logger.error(f"Error in DictionaryBot: {e}")
            return f"An error occurred: {str(e)}"

    def _get_dictionary_definition(self, word: str) -> str:
        system_content = (
            f"Provide a comprehensive dictionary entry for the word {word} like Longman Contemporary style, including:  \n"
            "- Part of speech \n"
            "- Definition  \n"
            "- Phonetics (how to pronounce the word) \n"
            "- Two examples of how to use the word in a sentence \n"
            "- Its frequency or commonality. Is it common to use it in informal conversation? If yes, give two examples of that. \n"
            f"- What other common alternative words that I can use instead of {word}? \n"
            "- Give some of the common collocation for this word. \n"
            f"Do we have any common phrasal verb which contains {word}, give me an example of them."
        )

        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": word},
                {"role": "system", "content": system_content}
            ],
            temperature=0.8,
            max_tokens=3000,
        )
        
        return response.choices[0].message.content

    def handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        pass 