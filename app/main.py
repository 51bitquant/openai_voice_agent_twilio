"""
FastAPI main application
Provides HTTP API endpoints and WebSocket connection handling
"""
import logging
from urllib.parse import urlparse
from pathlib import Path
from fastapi import FastAPI, Request, WebSocket, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models.schemas import PublicUrlResponse, ToolsResponse
from app.services.function_handlers import function_handler_service
from app.websocket.handlers import websocket_handler
from app.utils.health_check import health_checker
from app.utils.error_handler import error_collector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Twilio OpenAI Realtime API",
    description="FastAPI implementation of Twilio + OpenAI Realtime voice calling system",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Read TwiML template
TWIML_TEMPLATE_PATH = Path(__file__).parent / "templates" / "twiml.xml"
try:
    with open(TWIML_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        TWIML_TEMPLATE = f.read()
except FileNotFoundError:
    logger.error(f"TwiML template not found: {TWIML_TEMPLATE_PATH}")
    TWIML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>Connected</Say>
  <Connect>
    <Stream url="{{WS_URL}}" />
  </Connect>
  <Say>Disconnected</Say>
</Response>"""


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Twilio OpenAI Realtime API Server",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/public-url", response_model=PublicUrlResponse)
async def get_public_url():
    """
    Get server public URL
    
    Returns:
        PublicUrlResponse: Response containing public URL
    """
    return PublicUrlResponse(publicUrl=settings.public_url)


@app.api_route("/twiml", methods=["GET", "POST"])
async def handle_twiml(request: Request):
    """
    Handle TwiML requests
    Supports GET and POST methods
    
    Args:
        request: HTTP request object
        
    Returns:
        TwiML XML response
    """
    try:
        # Build WebSocket URL
        parsed_url = urlparse(settings.public_url)
        ws_url = f"wss://{parsed_url.netloc}/ws/call"

        # Replace placeholders in template
        twiml_content = TWIML_TEMPLATE.replace("{{WS_URL}}", ws_url)

        return Response(
            content=twiml_content,
            media_type="application/xml"
        )
    except Exception as e:
        logger.error(f"Error generating TwiML: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/tools", response_model=ToolsResponse)
async def get_tools():
    """
    Get list of available tools/functions
    
    Returns:
        ToolsResponse: Response containing list of tool schemas
    """
    try:
        schemas = function_handler_service.get_function_schemas()
        return ToolsResponse(tools=schemas)
    except Exception as e:
        logger.error(f"Error getting tools: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
async def health_check():
    """
    Health check endpoint
    
    Returns:
        Health status information
    """
    try:
        health_results = await health_checker.run_all_checks()

        # Calculate overall status
        overall_status = "healthy"
        for result in health_results:
            if result.status == "critical":
                overall_status = "critical"
                break
            elif result.status == "warning" and overall_status == "healthy":
                overall_status = "warning"

        return {
            "status": overall_status,
            "timestamp": health_results[0].timestamp.isoformat() if health_results else None,
            "services": [
                {
                    "service": result.service,
                    "status": result.status,
                    "message": result.message,
                    "details": result.details
                }
                for result in health_results
            ],
            "errors": error_collector.get_error_summary()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "critical",
            "message": f"Health check failed: {str(e)}"
        }


@app.websocket("/ws/call")
async def websocket_call_endpoint(websocket: WebSocket):
    """
    Twilio call WebSocket endpoint
    
    Args:
        websocket: WebSocket connection
    """
    await websocket_handler.handle_call_connection(websocket)


@app.websocket("/ws/logs")
async def websocket_logs_endpoint(websocket: WebSocket):
    """
    Frontend logs WebSocket endpoint
    
    Args:
        websocket: WebSocket connection
    """
    await websocket_handler.handle_logs_connection(websocket)


@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    logger.info("=== Twilio OpenAI Realtime API Server Starting ===")
    logger.info(f"Public URL: {settings.public_url}")
    logger.info(f"Port: {settings.port}")
    logger.info(f"OpenAI Model: {settings.openai_model}")
    logger.info("=== Server Ready ===")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    logger.info("=== Server Shutting Down ===")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True,
        log_level="info"
    )
