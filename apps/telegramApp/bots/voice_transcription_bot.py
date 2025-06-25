from typing import Optional, Dict, Any
import replicate
import requests
import tempfile
import os
from django.conf import settings
import logging
import json

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
                
            # Store pending voice messages for language selection
            self.pending_voice_messages = {}
            
        except Exception as e:
            logger.error(f"Failed to initialize VoiceTranscriptionBot: {e}", exc_info=True)
            raise

    def _create_language_keyboard(self):
        """Create inline keyboard with language options"""
        return {
            "inline_keyboard": [
                [
                    {"text": "🇺🇸 English", "callback_data": "lang_en"},
                    {"text": "🇮🇷 Persian (فارسی)", "callback_data": "lang_fa"}
                ]
            ]
        }

    def _send_language_selection(self, chat_id: str, message_id: int = None):
        """Send language selection message with inline keyboard"""
        try:
            text = "🌐 Please select the language of your voice message:"
            keyboard = self._create_language_keyboard()
            
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": json.dumps(keyboard),
                "parse_mode": "HTML"
            }
            
            if message_id:
                data["reply_to_message_id"] = message_id
            
            response = requests.post(url, json=data)
            return response.json()
            
        except Exception as e:
            logger.error(f"Error sending language selection: {e}")
            return None

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
                    "🎤 <b>Voice Transcription Bot</b>\n\n"
                    "Send me a voice message and I'll transcribe it to text for you!\n\n"
                    "📝 <b>Features:</b>\n"
                    "• High-quality speech-to-text conversion\n"
                    "• Supports English and Persian languages\n"
                    "• Fast processing with AI\n\n"
                    "Just send a voice message to get started! 🚀"
                )
            elif message_text == '/help':
                return (
                    "🆘 <b>How to use:</b>\n\n"
                    "1. Record a voice message in Telegram\n"
                    "2. Send it to this bot\n"
                    "3. Select the language (English or Persian)\n"
                    "4. Wait for the transcription\n\n"
                    "💡 <b>Tips:</b>\n"
                    "• Speak clearly for better results\n"
                    "• Avoid background noise\n"
                    "• Keep messages under 5 minutes\n\n"
                    "Commands:\n"
                    "/start - Welcome message\n"
                    "/help - Show this help"
                )
            else:
                return (
                    "I can only transcribe voice messages. 🎤\n"
                    "Please send me a voice message or use /help for more information."
                )
                
        except Exception as e:
            logger.error(f"Error in VoiceTranscriptionBot.handle_command: {e}", exc_info=True)
            return f"❌ An error occurred: {str(e)}"

    def _handle_voice_message(self, message: Dict[str, Any]) -> str:
        """Handle voice message - store it and ask for language selection"""
        try:
            voice = message.get('voice', {})
            file_id = voice.get('file_id')
            duration = voice.get('duration', 0)
            chat_id = str(message.get('chat', {}).get('id'))
            message_id = message.get('message_id')
            
            if not file_id:
                return "❌ Could not process the voice message. Please try again."
            
            # Check duration (optional limit)
            if duration > 300:  # 5 minutes
                return "❌ Voice message is too long. Please keep it under 5 minutes."
            
            # Store the voice message for later processing
            self.pending_voice_messages[chat_id] = {
                'file_id': file_id,
                'duration': duration,
                'message_id': message_id
            }
            
            # Send language selection keyboard
            self._send_language_selection(chat_id, message_id)
            
            return None  # Don't send a text response, we sent the keyboard instead
                
        except Exception as e:
            logger.error(f"Error handling voice message: {e}", exc_info=True)
            return f"❌ Error processing voice message: {str(e)}"

    def handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        """Handle callback queries for language selection"""
        try:
            callback_data = callback_query.get('data', '')
            chat_id = str(callback_query.get('message', {}).get('chat', {}).get('id'))
            callback_query_id = callback_query.get('id')
            
            # Answer the callback query to remove loading state
            self._answer_callback_query(callback_query_id)
            
            if callback_data.startswith('lang_'):
                language_code = callback_data.split('_')[1]
                
                # Get the pending voice message
                if chat_id not in self.pending_voice_messages:
                    self.send_message(chat_id, "❌ No pending voice message found. Please send a new voice message.")
                    return
                
                voice_data = self.pending_voice_messages[chat_id]
                
                # Map language codes to Whisper language parameters
                language_map = {
                    'en': 'english',
                    'fa': 'persian'
                }
                
                language = language_map.get(language_code, 'None')
                language_display = "English 🇺🇸" if language_code == 'en' else "Persian 🇮🇷"
                
                # Send processing message
                self.send_message(chat_id, f"🎤 Processing your voice message in {language_display}...")
                
                # Process the voice message with selected language
                transcription = self._process_voice_with_language(voice_data['file_id'], language)
                
                if transcription:
                    # Send transcription result
                    if len(transcription) > 4000:
                        transcription = transcription[:4000] + "... (truncated)"
                    
                    self.send_message(chat_id, f"📝 <b>Transcription ({language_display}):</b>\n\n{transcription}", parse_mode="HTML")
                    
                    # Send language selection for next voice message
                    self._send_language_selection(chat_id)
                else:
                    self.send_message(chat_id, "❌ Could not transcribe the voice message. Please try again with a clearer recording.")
                    # Send language selection again for retry
                    self._send_language_selection(chat_id)
                
                # Clean up pending message
                del self.pending_voice_messages[chat_id]
                
        except Exception as e:
            logger.error(f"Error handling callback query: {e}", exc_info=True)
            if chat_id:
                self.send_message(chat_id, f"❌ Error processing language selection: {str(e)}")

    def _answer_callback_query(self, callback_query_id: str, text: str = ""):
        """Answer callback query to remove loading state"""
        try:
            url = f"{self.base_url}/answerCallbackQuery"
            data = {
                "callback_query_id": callback_query_id,
                "text": text
            }
            requests.post(url, json=data)
        except Exception as e:
            logger.error(f"Error answering callback query: {e}")

    def _process_voice_with_language(self, file_id: str, language: str) -> Optional[str]:
        """Process voice message with specified language"""
        try:
            # Get file info from Telegram
            file_info = self._get_file_info(file_id)
            if not file_info or not file_info.get('ok'):
                logger.error(f"Failed to get file info: {file_info}")
                return None
            
            file_path = file_info['result']['file_path']
            
            # Download the voice file
            voice_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            
            # Transcribe using Replicate with language parameter
            return self._transcribe_audio(voice_url, language)
                
        except Exception as e:
            logger.error(f"Error processing voice with language: {e}", exc_info=True)
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

    def _transcribe_audio(self, audio_url: str, language: str = "None") -> Optional[str]:
        """Transcribe audio using Replicate's Whisper model with language parameter"""
        try:
            input_data = {
                "task": "transcribe",
                "audio": audio_url,
                "language": language,
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