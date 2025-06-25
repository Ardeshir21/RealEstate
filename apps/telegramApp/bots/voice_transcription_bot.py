from typing import Optional, Dict, Any
import replicate
import requests
import tempfile
import os
from django.conf import settings
import logging
import openai

from .base import TelegramBot

logger = logging.getLogger(__name__)

class VoiceTranscriptionBot(TelegramBot):
    def __init__(self):
        try:
            # Check if token exists
            if not hasattr(settings, 'TELEGRAM_VOICE_BOT_TOKEN'):
                logger.error("TELEGRAM_VOICE_BOT_TOKEN not found in settings")
                raise ValueError("TELEGRAM_VOICE_BOT_TOKEN is required")
            
            token = settings.TELEGRAM_VOICE_BOT_TOKEN
            if not token:
                logger.error("TELEGRAM_VOICE_BOT_TOKEN is empty")
                raise ValueError("TELEGRAM_VOICE_BOT_TOKEN cannot be empty")
            
            super().__init__(token)
            
            # Validate that we have the required settings
            if not hasattr(settings, 'REPLICATE_API_TOKEN') or not settings.REPLICATE_API_TOKEN:
                logger.error("REPLICATE_API_TOKEN not found in settings")
                raise ValueError("REPLICATE_API_TOKEN is required for voice transcription bot")
            
            # Set Replicate API token as environment variable (preferred method)
            os.environ["REPLICATE_API_TOKEN"] = settings.REPLICATE_API_TOKEN
            
            try:
                # Initialize replicate client for the new API version
                self.replicate_client = replicate.Client(api_token=settings.REPLICATE_API_TOKEN)
            except Exception as e:
                logger.error(f"Failed to initialize Replicate client: {e}")
                # Don't raise here - allow bot to work for text commands even if Replicate fails
                self.replicate_client = None
            
            # Initialize OpenAI client
            if hasattr(settings, 'CHATGPT_API') and settings.CHATGPT_API:
                self.openai_client = openai.OpenAI(api_key=settings.CHATGPT_API)
            else:
                logger.error("CHATGPT_API not found in settings")
                self.openai_client = None
                
        except Exception as e:
            logger.error(f"Failed to initialize VoiceTranscriptionBot: {e}", exc_info=True)
            raise

    def handle_command(self, message: Dict[str, Any]) -> Optional[str]:
        try:
            # Handle voice messages
            if 'voice' in message:
                if not self.replicate_client:
                    return "❌ Voice transcription is currently unavailable. Please try again later."
                return self._handle_voice_message(message)
            
            # Handle text commands
            message_text = message.get('text', '')
            
            if message_text == '/start':
                return (
                    "🎤 Voice Transcription Bot\n\n"
                    "Send me a voice message and I'll transcribe it to Persian text and provide an English translation!\n\n"
                    "📝 Features:\n"
                    "• High-quality speech-to-text conversion\n"
                    "• Persian language transcription\n"
                    "• English translation with AI\n"
                    "• Fast processing\n\n"
                    "Just send a voice message to get started! 🚀"
                )
            elif message_text == '/help':
                return (
                    "🆘 How to use:\n\n"
                    "1. Record a voice message in Telegram\n"
                    "2. Send it to this bot\n"
                    "3. Receive Persian transcription\n"
                    "4. Receive English translation\n\n"
                    "💡 Tips:\n"
                    "• Speak clearly for better results\n"
                    "• Avoid background noise\n"
                    "• Keep messages under 5 minutes\n\n"
                    "Commands:\n"
                    "/start - Welcome message\n"
                    "/help - Show this help"
                )
            else:
                return (
                    "Please send me a voice message to transcribe, or use /help for more information."
                )
                
        except Exception as e:
            logger.error(f"Error in VoiceTranscriptionBot.handle_command: {e}", exc_info=True)
            return f"❌ An error occurred: {str(e)}"

    def _handle_voice_message(self, message: Dict[str, Any]) -> str:
        """Handle voice message - transcribe directly in Persian and translate to English"""
        try:
            voice = message.get('voice', {})
            file_id = voice.get('file_id')
            duration = voice.get('duration', 0)
            chat_id = str(message.get('chat', {}).get('id'))
            
            if not file_id:
                return "❌ Could not process the voice message. Please try again."
            
            # Check duration (optional limit)
            if duration > 300:  # 5 minutes
                return "❌ Voice message is too long. Please keep it under 5 minutes."
            
            # Send processing message
            self.send_message(chat_id, "🎤 Processing your voice message...")
            
            # Process the voice message in Persian
            transcription = self._process_voice_message(file_id)
            
            if transcription:
                # Send Persian transcription first
                if len(transcription) > 4000:
                    truncated_transcription = transcription[:4000] + "... (truncated)"
                    self.send_message(chat_id, f"{truncated_transcription}")
                else:
                    self.send_message(chat_id, f"{transcription}")
                
                # Translate to English if OpenAI is available
                if self.openai_client:
                    translation = self._translate_to_english(transcription)
                    
                    if translation:
                        if len(translation) > 4000:
                            translation = translation[:4000] + "... (truncated)"
                        self.send_message(chat_id, f"{translation}")
                    else:
                        self.send_message(chat_id, "❌ Could not translate to English. Translation service is unavailable.")
                else:
                    self.send_message(chat_id, "❌ Translation service is not configured.")
                
                return None  # We've already sent the messages
            else:
                return "❌ Could not transcribe the voice message. Please try again with a clearer recording."
                
        except Exception as e:
            logger.error(f"Error handling voice message: {e}", exc_info=True)
            return f"❌ Error processing voice message: {str(e)}"

    def _translate_to_english(self, persian_text: str) -> Optional[str]:
        """Translate Persian text to English using OpenAI GPT"""
        try:
            prompt = f"{persian_text}"

            response = self.openai_client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {
                                    "role": "system",
                                    "content": (
                                        "You are an expert translator. "
                                        "You translate informal Persian (Farsi) into fluent, natural, and conversational English. "
                                        "Focus on how native English speakers would commonly say the same thing. "
                                        "Avoid word-for-word translation — preserve the meaning, tone, and cultural context."
                                    )
                                },
                                {
                                    "role": "user",
                                    "content": prompt  # this should be the informal Persian text
                                }
                            ],
                            max_tokens=1000,
                            temperature=0.7  # Optional: Adjust for creativity; 0.7 gives a bit more natural variation
                        )
            
            translation = response.choices[0].message.content.strip()
            return translation
            
        except Exception as e:
            logger.error(f"Error translating text: {e}", exc_info=True)
            return None

    def _process_voice_message(self, file_id: str) -> Optional[str]:
        """Process voice message and transcribe in Persian"""
        try:
            # Get file info from Telegram
            file_info = self._get_file_info(file_id)
            if not file_info or not file_info.get('ok'):
                logger.error(f"Failed to get file info: {file_info}")
                return None
            
            file_path = file_info['result']['file_path']
            
            # Download the voice file
            voice_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            
            # Transcribe using Replicate with Persian language
            return self._transcribe_audio(voice_url)
                
        except Exception as e:
            logger.error(f"Error processing voice message: {e}", exc_info=True)
            return None

    def _get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file information from Telegram API"""
        try:
            url = f"{self.base_url}/getFile"
            response = requests.post(url, json={"file_id": file_id})
            return response.json()
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            return None

    def _transcribe_audio(self, audio_url: str) -> Optional[str]:
        """Transcribe audio using Replicate's Whisper model in Persian"""
        try:
            input_data = {
                "task": "transcribe",
                "audio": audio_url,
                "language": "persian",
                "timestamp": "chunk",
                "batch_size": 64,
                "diarise_audio": False
            }
            
            # Use the client instance for the new API version
            output = self.replicate_client.run(
                "vaibhavs10/incredibly-fast-whisper:3ab86df6c8f54c11309d4d1f930ac292bad43ace52d10c80d87eb258b3c9f79c",
                input=input_data
            )
            
            # Handle new API response format (1.0.7+)
            if isinstance(output, dict) and 'text' in output:
                text = output['text'].strip()
                return text
            elif isinstance(output, str):
                text = output.strip()
                return text
            else:
                logger.error(f"Unexpected output format: {type(output)} - {output}")
                # For debugging, let's also try to access as string
                try:
                    text_output = str(output)
                    return text_output
                except:
                    return None
                
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}", exc_info=True)
            return None

    def handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        """Handle callback queries (not used in this simplified bot)"""
        pass

    def send_message(self, chat_id: str, text: str, parse_mode: str = None, reply_markup: str = None):
        """Send a message to a chat"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": text
            }
            
            if parse_mode:
                data["parse_mode"] = parse_mode
            if reply_markup:
                data["reply_markup"] = reply_markup
                
            response = requests.post(url, json=data)
            return response.json()
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None 