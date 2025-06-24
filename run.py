#!/usr/bin/env python3
"""
Twilio OpenAI Realtime API Server startup script
"""
import uvicorn
from app.config import settings

if __name__ == "__main__":
    print("🚀 Starting Twilio OpenAI Realtime API Server...")
    print(f"📡 Public URL: {settings.public_url}")
    print(f"🔌 Port: {settings.port}")
    print(f"🤖 OpenAI Model: {settings.openai_model}")
    print("=" * 50)
    
    uvicorn.run(
        "app.main:app",  # Use import string instead of app object
        host="0.0.0.0",
        port=settings.port,
        reload=True,
        log_level="info"
    ) 