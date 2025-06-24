"""
OpenAI client service
Manages WebSocket connection to OpenAI Realtime API with auto-reconnect functionality
"""
import json
import asyncio
import logging
from typing import Optional, Callable, Awaitable, Dict, Any
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from app.config import settings
from app.models.schemas import OpenAISessionUpdate, OpenAISessionConfig

logger = logging.getLogger(__name__)


class OpenAIClient:
    """OpenAI Realtime API client with auto-reconnect support"""
    
    def __init__(self):
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.message_handler: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None
        self.session_config: Optional[Dict[str, Any]] = None
        
        # Reconnect configuration
        self.auto_reconnect = True
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 1.0  # Initial reconnect delay (seconds)
        self.max_reconnect_delay = 30.0  # Maximum reconnect delay (seconds)
        self.current_reconnect_attempts = 0
        self.reconnect_task: Optional[asyncio.Task] = None
        
        # Connection state callbacks
        self.on_connected: Optional[Callable[[], Awaitable[None]]] = None
        self.on_disconnected: Optional[Callable[[], Awaitable[None]]] = None
    
    async def connect(self) -> bool:
        """
        Connect to OpenAI Realtime API
        
        Returns:
            Whether connection was successful
        """
        try:
            logger.info("Connecting to OpenAI Realtime API...")
            
            self.websocket = await websockets.connect(
                settings.openai_realtime_url,
                extra_headers=settings.openai_headers,
                ping_interval=30,
                ping_timeout=10
            )
            
            self.is_connected = True
            self.current_reconnect_attempts = 0  # Reset reconnect counter
            logger.info("Successfully connected to OpenAI Realtime API")
            
            # Start message listening task
            await asyncio.create_task(self._listen_messages())
            
            # Send session configuration
            await self._send_session_update()
            
            # Call connection success callback
            if self.on_connected:
                try:
                    await self.on_connected()
                except Exception as e:
                    logger.error(f"Error in connection callback: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to OpenAI API: {e}")
            self.is_connected = False
            await self._handle_connection_failure()
            return False
    
    async def disconnect(self, disable_reconnect: bool = True):
        """
        Disconnect connection
        
        Args:
            disable_reconnect: Whether to disable auto-reconnect
        """
        if disable_reconnect:
            self.auto_reconnect = False
            
        self.is_connected = False
        
        # Cancel reconnect task
        if self.reconnect_task and not self.reconnect_task.done():
            self.reconnect_task.cancel()
            
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.error(f"Error closing OpenAI websocket: {e}")
            finally:
                self.websocket = None
    
    async def send_message(self, message: Dict[str, Any]) -> bool:
        """
        Send message to OpenAI API
        
        Args:
            message: Message dictionary to send
            
        Returns:
            Whether sending was successful
        """
        if not self.is_connected or not self.websocket:
            logger.warning("OpenAI websocket not connected")
            return False
        
        try:
            await self.websocket.send(json.dumps(message))
            return True
        except (ConnectionClosed, WebSocketException) as e:
            logger.error(f"OpenAI websocket connection error: {e}")
            await self._handle_disconnection()
            return False
        except Exception as e:
            logger.error(f"Error sending message to OpenAI: {e}")
            return False
    
    def set_message_handler(self, handler: Callable[[Dict[str, Any]], Awaitable[None]]):
        """Set message handler"""
        self.message_handler = handler
    
    def set_connection_callbacks(self, on_connected: Optional[Callable[[], Awaitable[None]]] = None,
                                 on_disconnected: Optional[Callable[[], Awaitable[None]]] = None):
        """Set connection state callbacks"""
        self.on_connected = on_connected
        self.on_disconnected = on_disconnected
    
    def update_session_config(self, config: Dict[str, Any]):
        """Update session configuration"""
        self.session_config = config
    
    def configure_reconnect(self, auto_reconnect: bool = True, max_attempts: int = 5, initial_delay: float = 1.0,
                            max_delay: float = 30.0):
        """
        Configure reconnect parameters
        
        Args:
            auto_reconnect: Whether to enable auto-reconnect
            max_attempts: Maximum reconnect attempts
            initial_delay: Initial reconnect delay (seconds)
            max_delay: Maximum reconnect delay (seconds)
        """
        self.auto_reconnect = auto_reconnect
        self.max_reconnect_attempts = max_attempts
        self.reconnect_delay = initial_delay
        self.max_reconnect_delay = max_delay
    
    async def _listen_messages(self):
        """Listen for messages from OpenAI"""
        try:
            async for message in self.websocket:
                if not self.is_connected:
                    break
                
                try:
                    data = json.loads(message)
                    if self.message_handler:
                        await self.message_handler(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse OpenAI message: {e}")
                except Exception as e:
                    logger.error(f"Error handling OpenAI message: {e}")
                    
        except ConnectionClosed:
            logger.info("OpenAI websocket connection closed")
            await self._handle_disconnection()
        except Exception as e:
            logger.error(f"Error in OpenAI message listener: {e}")
            await self._handle_disconnection()
    
    async def _handle_disconnection(self):
        """Handle connection disconnection"""
        if self.is_connected:
            self.is_connected = False
            logger.warning("OpenAI connection lost")
            
            # Call disconnection callback
            if self.on_disconnected:
                try:
                    await self.on_disconnected()
                except Exception as e:
                    logger.error(f"Error in disconnection callback: {e}")
            
            # Attempt reconnection
            if self.auto_reconnect:
                await self._start_reconnect()
    
    async def _handle_connection_failure(self):
        """Handle connection failure"""
        if self.auto_reconnect:
            await self._start_reconnect()
    
    async def _start_reconnect(self):
        """Start reconnection process"""
        if self.reconnect_task and not self.reconnect_task.done():
            return  # Reconnection already in progress
            
        self.reconnect_task = asyncio.create_task(self._reconnect_loop())
    
    async def _reconnect_loop(self):
        """Reconnection loop"""
        while (self.auto_reconnect and 
               self.current_reconnect_attempts < self.max_reconnect_attempts and
               not self.is_connected):
            
            self.current_reconnect_attempts += 1
            
            # Calculate reconnection delay (exponential backoff)
            delay = min(
                self.reconnect_delay * (2 ** (self.current_reconnect_attempts - 1)),
                self.max_reconnect_delay
            )
            
            logger.info(f"Attempting to reconnect to OpenAI API "
                        f"(attempt {self.current_reconnect_attempts}/{self.max_reconnect_attempts}) "
                        f"in {delay:.1f}s...")
            
            try:
                await asyncio.sleep(delay)
                
                if not self.auto_reconnect:  # Check if reconnection has been disabled
                    break
                    
                success = await self.connect()
                if success:
                    logger.info("Successfully reconnected to OpenAI API")
                    break
                    
            except asyncio.CancelledError:
                logger.info("Reconnection cancelled")
                break
            except Exception as e:
                logger.error(f"Reconnection attempt failed: {e}")
        
        if (self.current_reconnect_attempts >= self.max_reconnect_attempts
                and not self.is_connected):
            logger.error(f"Failed to reconnect after {self.max_reconnect_attempts} attempts")
    
    async def _send_session_update(self):
        """Send session update configuration"""
        config = self.session_config or {}
        
        # Use default configuration and merge with user configuration
        default_config = OpenAISessionConfig()
        session_data = default_config.model_dump()
        session_data.update(config)
        
        session_update = OpenAISessionUpdate(session=OpenAISessionConfig(**session_data))
        
        await self.send_message(session_update.model_dump())
        logger.info("Session configuration sent to OpenAI")
