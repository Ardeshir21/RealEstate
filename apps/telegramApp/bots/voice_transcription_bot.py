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
                # Send language selection immediately
                chat_id = str(message.get('chat', {}).get('id'))
                self._send_language_selection(chat_id)
                return None  # Don't send text response, we sent the keyboard
            elif message_text == '/help':
                return (
                    "🆘 How to use:\n\n"
                    "1. Use /start to begin\n"
                    "2. Select your preferred language\n"
                    "3. Send a voice message\n"
                    "4. Receive your transcription\n\n"
                    "💡 Tips:\n"
                    "• Speak clearly for better results\n"
                    "• Avoid background noise\n"
                    "• Keep messages under 5 minutes\n\n"
                    "Commands:\n"
                    "/start - Start transcription\n"
                    "/help - Show this help"
                )
            else:
                return (
                    "Please use /start to begin voice transcription or /help for more information."
                )
                
        except Exception as e:
            logger.error(f"Error in VoiceTranscriptionBot.handle_command: {e}", exc_info=True)
            return f"❌ An error occurred: {str(e)}"

    def _handle_voice_message(self, message: Dict[str, Any]) -> str:
        """Handle voice message - check if language is selected"""
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
            
            # Initialize pending_voice_messages for this chat if it doesn't exist
            if chat_id not in self.pending_voice_messages:
                self.pending_voice_messages[chat_id] = {}
            
            # Check if user has selected a language
            if 'selected_language' not in self.pending_voice_messages[chat_id]:
                # No language selected, store voice message and ask for language selection
                self.pending_voice_messages[chat_id]['file_id'] = file_id
                self.pending_voice_messages[chat_id]['duration'] = duration
                self._send_language_selection(chat_id)
                return None
            
            # Language already selected, process immediately
            selected_language = self.pending_voice_messages[chat_id]['selected_language']
            language_display = "English 🇺🇸" if selected_language == 'english' else "Persian 🇮🇷"
            
            # Send processing message
            self.send_message(chat_id, f"🎤 Processing your voice message in {language_display}...")
            
            # Process the voice message
            transcription = self._process_voice_with_language(file_id, selected_language)
            
            if transcription:
                # Send transcription result
                if len(transcription) > 4000:
                    transcription = transcription[:4000] + "... (truncated)"
                
                self.send_message(chat_id, f"📝 Transcription ({language_display}):\n\n{transcription}")
                
                # Clear selected language and send language selection for next voice message
                if 'selected_language' in self.pending_voice_messages[chat_id]:
                    del self.pending_voice_messages[chat_id]['selected_language']
                self._send_language_selection(chat_id)
                return None
            else:
                self.send_message(chat_id, "❌ Could not transcribe the voice message. Please try again with a clearer recording.")
                # Send language selection again for retry
                self._send_language_selection(chat_id)
                return None
                
        except Exception as e:
            logger.error(f"Error handling voice message: {e}", exc_info=True)
            return f"❌ Error processing voice message: {str(e)}"

    def handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        """Handle callback queries for language selection"""
        try:
            callback_data = callback_query.get('data', '')
            chat_id = str(callback_query.get('message', {}).get('chat', {}).get('id'))
            callback_query_id = callback_query.get('id')
            message_id = callback_query.get('message', {}).get('message_id')
            
            # Answer the callback query to remove loading state
            self._answer_callback_query(callback_query_id)
            
            if callback_data.startswith('lang_'):
                language_code = callback_data.split('_')[1]
                
                # Map language codes to Whisper language parameters
                language_map = {
                    'en': 'english',
                    'fa': 'persian'
                }
                
                language = language_map.get(language_code, 'None')
                language_display = "English 🇺🇸" if language_code == 'en' else "Persian 🇮🇷"
                
                # Store selected language
                if chat_id not in self.pending_voice_messages:
                    self.pending_voice_messages[chat_id] = {}
                self.pending_voice_messages[chat_id]['selected_language'] = language
                
                # Edit the message to remove buttons and show waiting message
                self._edit_message(chat_id, message_id, f"✅ Language selected: {language_display}\n\n🎤 Please send your voice message now.")
                
                # If there's a pending voice message, process it now
                if 'file_id' in self.pending_voice_messages[chat_id]:
                    file_id = self.pending_voice_messages[chat_id]['file_id']
                    
                    # Send processing message
                    self.send_message(chat_id, f"🎤 Processing your voice message in {language_display}...")
                    
                    # Process the voice message
                    transcription = self._process_voice_with_language(file_id, language)
                    
                    if transcription:
                        # Send transcription result
                        if len(transcription) > 4000:
                            transcription = transcription[:4000] + "... (truncated)"
                        
                        self.send_message(chat_id, f"📝 Transcription ({language_display}):\n\n{transcription}")
                        
                        # Clear selected language and send language selection for next voice message
                        if 'selected_language' in self.pending_voice_messages[chat_id]:
                            del self.pending_voice_messages[chat_id]['selected_language']
                        self._send_language_selection(chat_id)
                        return None
                    else:
                        self.send_message(chat_id, "❌ Could not transcribe the voice message. Please try again with a clearer recording.")
                        # Send language selection again for retry
                        self._send_language_selection(chat_id)
                    
                    # Clean up only the file_id and duration, keep selected_language
                    if 'file_id' in self.pending_voice_messages[chat_id]:
                        del self.pending_voice_messages[chat_id]['file_id']
                    if 'duration' in self.pending_voice_messages[chat_id]:
                        del self.pending_voice_messages[chat_id]['duration']
                
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

    def _edit_message(self, chat_id: str, message_id: int, new_text: str):
        """Edit an existing message"""
        try:
            url = f"{self.base_url}/editMessageText"
            data = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": new_text
            }
            requests.post(url, json=data)
        except Exception as e:
            logger.error(f"Error editing message: {e}") 