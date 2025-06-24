"""
Session cleanup service
Periodically clean up expired sessions and connections to prevent memory leaks
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Set, Optional

logger = logging.getLogger(__name__)


class SessionCleanupService:
    """Session cleanup service"""
    
    def __init__(self, cleanup_interval: int = 300):  # 5 minutes
        self.cleanup_interval = cleanup_interval
        self.active_sessions: Dict[str, datetime] = {}
        self.cleanup_task: Optional[asyncio.Task] = None
        self.is_running = False
    
    def start_cleanup(self):
        """Start cleanup task"""
        if not self.is_running:
            self.is_running = True
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Session cleanup service started")
    
    def stop_cleanup(self):
        """Stop cleanup task"""
        self.is_running = False
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            logger.info("Session cleanup service stopped")
    
    def register_session(self, session_id: str):
        """Register active session"""
        self.active_sessions[session_id] = datetime.now()
    
    def unregister_session(self, session_id: str):
        """Unregister session"""
        self.active_sessions.pop(session_id, None)
    
    async def _cleanup_loop(self):
        """Cleanup loop"""
        while self.is_running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def _cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        now = datetime.now()
        expired_threshold = now - timedelta(hours=3)  # 3 hours expiry
        
        expired_sessions = [
            session_id for session_id, last_activity 
            in self.active_sessions.items()
            if last_activity < expired_threshold
        ]
        
        for session_id in expired_sessions:
            logger.info(f"Cleaning up expired session: {session_id}")
            self.unregister_session(session_id)
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")


# Global cleanup service instance
cleanup_service = SessionCleanupService()
