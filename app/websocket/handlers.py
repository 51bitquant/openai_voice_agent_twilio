"""
WebSocket message handler
Handle different types of WebSocket connections and messages
"""
import json
import logging
from typing import Dict, Any
from fastapi import WebSocket, WebSocketDisconnect

from app.websocket.connection_manager import connection_manager
from app.services.session_manager import session_manager

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """WebSocket handler class"""

    @staticmethod
    async def handle_call_connection(websocket: WebSocket):
        """
        Handle Twilio call WebSocket connection
        
        Args:
            websocket: Twilio WebSocket connection
        """
        try:
            await connection_manager.connect(websocket, "call")
            await session_manager.handle_twilio_connection(websocket)

            while True:
                # Receive messages
                data = await websocket.receive_text()
                message = WebSocketHandler._parse_message(data)

                if message:
                    await session_manager.handle_twilio_message(message)

        except WebSocketDisconnect:
            logger.info("Twilio WebSocket disconnected")
        except Exception as e:
            logger.error(f"Error in Twilio WebSocket handler: {e}")
        finally:
            connection_manager.disconnect(websocket)
            await session_manager.disconnect_all()

    @staticmethod
    async def handle_logs_connection(websocket: WebSocket):
        """
        Handle frontend logs WebSocket connection
        
        Args:
            websocket: Frontend WebSocket connection
        """
        try:
            await connection_manager.connect(websocket, "logs")
            await session_manager.handle_frontend_connection(websocket)

            while True:
                # Receive messages
                data = await websocket.receive_text()
                message = WebSocketHandler._parse_message(data)

                if message:
                    await session_manager.handle_frontend_message(message)

        except WebSocketDisconnect:
            logger.info("Frontend WebSocket disconnected")
        except Exception as e:
            logger.error(f"Error in frontend WebSocket handler: {e}")
        finally:
            connection_manager.disconnect(websocket)

    @staticmethod
    def _parse_message(data: str) -> Dict[str, Any] | None:
        """
        Parse WebSocket message
        
        Args:
            data: JSON string message
            
        Returns:
            Parsed message dictionary, returns None if parsing fails
        """
        try:
            return json.loads(data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse WebSocket message: {e}")
            return None


# Global WebSocket handler instance
websocket_handler = WebSocketHandler()
