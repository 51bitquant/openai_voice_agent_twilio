"""
Session management service
Manages session state between Twilio, OpenAI and frontend connections
"""
import json
import logging
from typing import Optional, Dict, Any
from fastapi import WebSocket

from app.models.schemas import SessionState, WebSocketMessageType
from app.services.openai_client import OpenAIClient
from app.services.function_handlers import function_handler_service

logger = logging.getLogger(__name__)


class SessionManager:
    """Session manager"""

    def __init__(self):
        self.state = SessionState()
        self.twilio_websocket: Optional[WebSocket] = None
        self.frontend_websocket: Optional[WebSocket] = None
        self.openai_client: Optional[OpenAIClient] = None

    async def handle_twilio_connection(self, websocket: WebSocket):
        """Handle Twilio WebSocket connection"""
        await self._cleanup_twilio_connection()
        self.twilio_websocket = websocket
        logger.info("Twilio WebSocket connected")

    async def handle_frontend_connection(self, websocket: WebSocket):
        """Handle frontend WebSocket connection"""
        await self._cleanup_frontend_connection()
        self.frontend_websocket = websocket
        logger.info("Frontend WebSocket connected")

    async def handle_twilio_message(self, message: Dict[str, Any]):
        """Handle messages from Twilio"""
        event = message.get("event")

        if event == WebSocketMessageType.TWILIO_START:
            await self._handle_twilio_start(message)
        elif event == WebSocketMessageType.TWILIO_MEDIA:
            await self._handle_twilio_media(message)
        elif event == WebSocketMessageType.TWILIO_CLOSE:
            await self._handle_twilio_close()

    async def handle_frontend_message(self, message: Dict[str, Any]):
        """Handle messages from frontend"""
        # Forward to OpenAI
        if self.openai_client:
            await self.openai_client.send_message(message)

        # If it's a session update, save configuration
        if message.get("type") == WebSocketMessageType.OPENAI_SESSION_UPDATE:
            self.state.saved_config = message.get("session", {})

    async def handle_openai_message(self, message: Dict[str, Any]):
        """Handle messages from OpenAI"""
        # Forward to frontend for monitoring
        await self._send_to_frontend(message)

        message_type = message.get("type")

        if message_type == WebSocketMessageType.OPENAI_INPUT_AUDIO_BUFFER_SPEECH_STARTED:
            await self._handle_speech_started()
        elif message_type == WebSocketMessageType.OPENAI_RESPONSE_AUDIO_DELTA:
            await self._handle_audio_delta(message)
        elif message_type == WebSocketMessageType.OPENAI_RESPONSE_OUTPUT_ITEM_DONE:
            await self._handle_output_item_done(message)

    async def disconnect_all(self):
        """Disconnect all connections"""
        await self._cleanup_twilio_connection()
        await self._cleanup_frontend_connection()
        await self._cleanup_openai_connection()
        self.state = SessionState()
        logger.info("All connections disconnected")

    def _safe_int(self, value, default=0):
        """Safely convert to integer"""
        try:
            return int(value) if value is not None else default
        except (ValueError, TypeError):
            return default

    async def _handle_twilio_start(self, message: Dict[str, Any]):
        """Handle Twilio start message"""
        start_data = message.get("start", {})
        self.state.stream_sid = start_data.get("streamSid")
        self.state.latest_media_timestamp = 0
        self.state.last_assistant_item = None
        self.state.response_start_timestamp = None

        logger.info(f"Twilio stream started: {self.state.stream_sid}")
        await self._try_connect_openai()

    async def _handle_twilio_media(self, message: Dict[str, Any]):
        """Handle Twilio media message"""
        media_data = message.get("media", {})
        # Safely handle timestamp
        timestamp = media_data.get("timestamp", 0)
        self.state.latest_media_timestamp = self._safe_int(timestamp)

        # Forward audio to OpenAI
        if self.openai_client and self.openai_client.is_connected:
            audio_message = {
                "type": WebSocketMessageType.OPENAI_INPUT_AUDIO_BUFFER_APPEND,
                "audio": media_data.get("payload", "")
            }
            await self.openai_client.send_message(audio_message)

    async def _handle_twilio_close(self):
        """Handle Twilio close message"""
        logger.info("Twilio stream closed")
        await self.disconnect_all()

    async def _handle_speech_started(self):
        """Handle speech started event"""
        await self._handle_truncation()

    async def _handle_audio_delta(self, message: Dict[str, Any]):
        """Handle audio delta message"""
        if not self.twilio_websocket or not self.state.stream_sid:
            return

        # Set response start timestamp
        if self.state.response_start_timestamp is None:
            self.state.response_start_timestamp = self.state.latest_media_timestamp or 0

        # Record current assistant item ID
        item_id = message.get("item_id")
        if item_id:
            self.state.last_assistant_item = item_id

        # Send audio to Twilio
        audio_payload = message.get("delta", "")
        if audio_payload:
            media_message = {
                "event": "media",
                "streamSid": self.state.stream_sid,
                "media": {"payload": audio_payload}
            }
            await self._send_to_twilio(media_message)

            # Send mark
            mark_message = {
                "event": "mark",
                "streamSid": self.state.stream_sid
            }
            await self._send_to_twilio(mark_message)

    async def _handle_output_item_done(self, message: Dict[str, Any]):
        """Handle output item done message"""
        item = message.get("item", {})

        if item.get("type") == "function_call":
            await self._handle_function_call(item)

    async def _handle_function_call(self, item: Dict[str, Any]):
        """Handle function call"""
        try:
            function_name = item.get("name", "")
            function_args = item.get("arguments", "{}")
            call_id = item.get("call_id", "")

            logger.info(f"Handling function call: {function_name}")

            # Execute function
            result = await function_handler_service.handle_function_call(
                function_name, function_args
            )

            # Send result to OpenAI
            if self.openai_client:
                # Create function call output item
                output_message = {
                    "type": WebSocketMessageType.OPENAI_CONVERSATION_ITEM_CREATE,
                    "item": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": result
                    }
                }
                await self.openai_client.send_message(output_message)

                # Trigger response creation
                response_message = {
                    "type": WebSocketMessageType.OPENAI_RESPONSE_CREATE
                }
                await self.openai_client.send_message(response_message)

        except Exception as e:
            logger.error(f"Error handling function call: {e}")

    async def _handle_truncation(self):
        """Handle truncation logic"""
        if (not self.state.last_assistant_item or
                self.state.response_start_timestamp is None):
            return

        # Safely calculate audio end time
        latest_timestamp = self._safe_int(self.state.latest_media_timestamp)
        response_timestamp = self._safe_int(self.state.response_start_timestamp)
        elapsed_ms = latest_timestamp - response_timestamp
        audio_end_ms = max(elapsed_ms, 0)

        # Send truncation message to OpenAI
        if self.openai_client:
            truncate_message = {
                "type": WebSocketMessageType.OPENAI_CONVERSATION_ITEM_TRUNCATE,
                "item_id": self.state.last_assistant_item,
                "content_index": 0,
                "audio_end_ms": audio_end_ms
            }
            await self.openai_client.send_message(truncate_message)

        # Clear Twilio audio buffer
        if self.twilio_websocket and self.state.stream_sid:
            clear_message = {
                "event": "clear",
                "streamSid": self.state.stream_sid
            }
            await self._send_to_twilio(clear_message)

        # Reset state
        self.state.last_assistant_item = None
        self.state.response_start_timestamp = None

    async def _try_connect_openai(self):
        """Try to connect to OpenAI"""
        if not self.state.stream_sid:
            return

        if self.openai_client and self.openai_client.is_connected:
            return

        self.openai_client = OpenAIClient()
        self.openai_client.set_message_handler(self.handle_openai_message)

        # Configure reconnection parameters
        self.openai_client.configure_reconnect(
            auto_reconnect=True,
            max_attempts=10,  # Increase reconnection attempts
            initial_delay=2.0,
            max_delay=60.0
        )

        # Set connection state callbacks
        self.openai_client.set_connection_callbacks(
            on_connected=self._on_openai_connected,
            on_disconnected=self._on_openai_disconnected
        )

        # Set session configuration
        if self.state.saved_config:
            self.openai_client.update_session_config(self.state.saved_config)

        success = await self.openai_client.connect()
        if success:
            logger.info("OpenAI connection established")
        else:
            logger.error("Failed to establish OpenAI connection")

    async def _send_to_twilio(self, message: Dict[str, Any]):
        """Send message to Twilio"""
        if self.twilio_websocket:
            try:
                await self.twilio_websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending to Twilio: {e}")

    async def _send_to_frontend(self, message: Dict[str, Any]):
        """Send message to frontend"""
        if self.frontend_websocket:
            try:
                await self.frontend_websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending to frontend: {e}")

    async def _cleanup_twilio_connection(self):
        """Clean up Twilio connection"""
        if self.twilio_websocket:
            try:
                await self.twilio_websocket.close()
            except Exception as e:
                logger.error(f"Error closing Twilio websocket: {e}")
            finally:
                self.twilio_websocket = None

    async def _cleanup_frontend_connection(self):
        """Clean up frontend connection"""
        if self.frontend_websocket:
            try:
                await self.frontend_websocket.close()
            except Exception as e:
                logger.error(f"Error closing frontend websocket: {e}")
            finally:
                self.frontend_websocket = None

    async def _cleanup_openai_connection(self):
        """Clean up OpenAI connection"""
        if self.openai_client:
            await self.openai_client.disconnect()
            self.openai_client = None

    async def _on_openai_connected(self):
        """OpenAI's connection success callback"""
        logger.info("OpenAI reconnected successfully")
        # Can add initialization logic after reconnection here
        await self._send_to_frontend({
            "type": "connection_status",
            "status": "openai_connected",
            "message": "OpenAI connection established"
        })

    async def _on_openai_disconnected(self):
        """OpenAI's connection disconnected callback"""
        logger.warning("OpenAI connection lost, attempting to reconnect...")
        # Notify frontend of connection status
        await self._send_to_frontend({
            "type": "connection_status",
            "status": "openai_disconnected",
            "message": "OpenAI connection lost, reconnecting..."
        })


# Global session manager instance
session_manager = SessionManager()
