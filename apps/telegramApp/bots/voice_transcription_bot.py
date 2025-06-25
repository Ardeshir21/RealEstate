from typing import Optional, Dict, Any
import replicate
import requests
import tempfile
import os
from django.conf import settings
import logging

from .base import TelegramBot

logger = logging.getLogger(__name__)

class VoiceTranscriptionBot(TelegramBot):
    def __init__(self):
        super().__init__(settings.TELEGRAM_VOICE_BOT_TOKEN)
        # Set Replicate API token as environment variable (preferred method)
        os.environ["REPLICATE_API_TOKEN"] = settings.REPLICATE_API_TOKEN

    def handle_command(self, message: Dict[str, Any]) -> Optional[str]:
        try:
            # Handle voice messages
            if 'voice' in message:
                return self._handle_voice_message(message)
            
            # Handle text commands
            message_text = message.get('text', '')
            
            if message_text == '/start':
                return (
                    "🎤 <b>Voice Transcription Bot</b>\n\n"
                    "Send me a voice message and I'll transcribe it to text for you!\n\n"
                    "📝 <b>Features:</b>\n"
                    "• High-quality speech-to-text conversion\n"
                    "• Supports multiple languages\n"
                    "• Fast processing with AI\n\n"
                    "Just send a voice message to get started! 🚀"
                )
            elif message_text == '/help':
                return (
                    "🆘 <b>How to use:</b>\n\n"
                    "1. Record a voice message in Telegram\n"
                    "2. Send it to this bot\n"
                    "3. Wait for the transcription\n\n"
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
            logger.error(f"Error in VoiceTranscriptionBot: {e}")
            return f"❌ An error occurred: {str(e)}"

    def _handle_voice_message(self, message: Dict[str, Any]) -> str:
        """Handle voice message transcription"""
        try:
            voice = message.get('voice', {})
            file_id = voice.get('file_id')
            duration = voice.get('duration', 0)
            
            if not file_id:
                return "❌ Could not process the voice message. Please try again."
            
            # Check duration (optional limit)
            if duration > 300:  # 5 minutes
                return "❌ Voice message is too long. Please keep it under 5 minutes."
            
            # Get file info from Telegram
            file_info = self._get_file_info(file_id)
            if not file_info or not file_info.get('ok'):
                logger.error(f"Failed to get file info: {file_info}")
                return "❌ Could not retrieve voice message. Please try again."
            
            file_path = file_info['result']['file_path']
            
            # Download the voice file
            voice_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            logger.info(f"Processing voice message from URL: {voice_url}")
            
            # Send initial processing message
            chat_id = str(message.get('chat', {}).get('id'))
            self.send_message(chat_id, "🎤 Processing your voice message...")
            
            # Transcribe using Replicate
            transcription = self._transcribe_audio(voice_url)
            
            if transcription:
                # Limit response length to avoid Telegram message limits
                if len(transcription) > 4000:
                    transcription = transcription[:4000] + "... (truncated)"
                return f"📝 <b>Transcription:</b>\n\n{transcription}"
            else:
                return "❌ Could not transcribe the voice message. Please try again with a clearer recording."
                
        except Exception as e:
            logger.error(f"Error handling voice message: {e}", exc_info=True)
            return f"❌ Error processing voice message: {str(e)}"

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
        """Transcribe audio using Replicate's Whisper model"""
        try:
            logger.info(f"Starting transcription for audio URL: {audio_url}")
            
            input_data = {
                "audio": audio_url,
                "batch_size": 64
            }
            
            output = replicate.run(
                "vaibhavs10/incredibly-fast-whisper:3ab86df6c8f54c11309d4d1f930ac292bad43ace52d10c80d87eb258b3c9f79c",
                input=input_data
            )
            
            logger.info(f"Received output from Replicate: {type(output)}")
            
            # Extract text from output
            if isinstance(output, dict) and 'text' in output:
                text = output['text'].strip()
                logger.info(f"Extracted text (length: {len(text)}): {text[:100]}...")
                return text
            elif isinstance(output, str):
                text = output.strip()
                logger.info(f"Direct text output (length: {len(text)}): {text[:100]}...")
                return text
            else:
                logger.error(f"Unexpected output format: {type(output)} - {output}")
                return None
                
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}", exc_info=True)
            return None

    def handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        """Handle callback queries (not used in this bot)"""
        pass 