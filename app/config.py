"""
Configuration management module
Manages environment variables and application configuration
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Settings:
    """Application configuration class"""
    
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.public_url = os.getenv("PUBLIC_URL", "")
        self.port = int(os.getenv("PORT", "8081"))
        self.openai_model = "gpt-4o-realtime-preview-2024-12-17"
        self.openai_ws_url = "wss://api.openai.com/v1/realtime"
        
        # Validate required environment variables
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        if not self.public_url:
            raise ValueError("PUBLIC_URL environment variable is required")
    
    @property
    def openai_headers(self) -> dict:
        """Get OpenAI WebSocket connection headers"""
        return {
            "Authorization": f"Bearer {self.openai_api_key}",
            "OpenAI-Beta": "realtime=v1"
        }
    
    @property
    def openai_realtime_url(self) -> str:
        """Get complete OpenAI Realtime API URL"""
        return f"{self.openai_ws_url}?model={self.openai_model}"


# Global configuration instance
settings = Settings()
