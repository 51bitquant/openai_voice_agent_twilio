"""
WebSocket connection manager
Manages multiple WebSocket connections and connection pools
"""
import logging
from typing import Dict, List, Optional
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket connection manager"""

    def __init__(self):
        # Active connection pools
        self.active_connections: Dict[str, List[WebSocket]] = {
            "call": [],  # Twilio call connections
            "logs": []  # Frontend log connections
        }
        # Connection to type mapping
        self.connection_types: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, connection_type: str):
        """
        Connect WebSocket
        
        Args:
            websocket: WebSocket connection
            connection_type: Connection type ("call" or "logs")
        """
        await websocket.accept()

        # If it's a call connection, disconnect previous connections (only allow one call connection)
        if connection_type == "call" and self.active_connections["call"]:
            for old_ws in self.active_connections["call"]:
                await self._disconnect_websocket(old_ws)
            self.active_connections["call"].clear()

        # If it's a logs connection, disconnect previous connections (only allow one logs connection)
        if connection_type == "logs" and self.active_connections["logs"]:
            for old_ws in self.active_connections["logs"]:
                await self._disconnect_websocket(old_ws)
            self.active_connections["logs"].clear()

        # Add new connection
        self.active_connections[connection_type].append(websocket)
        self.connection_types[websocket] = connection_type

        logger.info(f"WebSocket connected: {connection_type}")

    def disconnect(self, websocket: WebSocket):
        """
        Disconnect WebSocket connection
        
        Args:
            websocket: WebSocket connection to disconnect
        """
        connection_type = self.connection_types.get(websocket)
        if connection_type and websocket in self.active_connections[connection_type]:
            self.active_connections[connection_type].remove(websocket)
            del self.connection_types[websocket]
            logger.info(f"WebSocket disconnected: {connection_type}")

    async def send_to_connection(self, websocket: WebSocket, message: str):
        """
        Send message to specific connection
        
        Args:
            websocket: Target WebSocket connection
            message: Message to send
        """
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending message to websocket: {e}")
            self.disconnect(websocket)

    async def broadcast_to_type(self, connection_type: str, message: str):
        """
        Broadcast message to all connections of specified type
        
        Args:
            connection_type: Connection type
            message: Message to broadcast
        """
        if connection_type not in self.active_connections:
            return

        disconnected = []
        for websocket in self.active_connections[connection_type]:
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to {connection_type}: {e}")
                disconnected.append(websocket)

        # Clean up disconnected connections
        for ws in disconnected:
            self.disconnect(ws)

    def get_connection_count(self, connection_type: str) -> int:
        """
        Get connection count of specified type
        
        Args:
            connection_type: Connection type
            
        Returns:
            Connection count
        """
        return len(self.active_connections.get(connection_type, []))

    def get_active_connection(self, connection_type: str) -> Optional[WebSocket]:
        """
        Get active connection of specified type (if exists)
        
        Args:
            connection_type: Connection type
            
        Returns:
            WebSocket connection or None
        """
        connections = self.active_connections.get(connection_type, [])
        return connections[0] if connections else None

    async def _disconnect_websocket(self, websocket: WebSocket):
        """
        Internal method: Safely disconnect WebSocket connection
        
        Args:
            websocket: WebSocket connection to disconnect
        """
        try:
            await websocket.close()
        except Exception as e:
            logger.error(f"Error closing websocket: {e}")


# Global connection manager instance
connection_manager = ConnectionManager()
