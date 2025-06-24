"""
Data models and schema definitions
Define all data structures using Pydantic
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from enum import Enum


class WebSocketMessageType(str, Enum):
    """WebSocket message type enumeration"""
    # Twilio message types
    TWILIO_START = "start"
    TWILIO_MEDIA = "media"
    TWILIO_CLOSE = "close"
    TWILIO_MARK = "mark"

    # OpenAI message types
    OPENAI_SESSION_UPDATE = "session.update"
    OPENAI_INPUT_AUDIO_BUFFER_APPEND = "input_audio_buffer.append"
    OPENAI_INPUT_AUDIO_BUFFER_SPEECH_STARTED = "input_audio_buffer.speech_started"
    OPENAI_RESPONSE_AUDIO_DELTA = "response.audio.delta"
    OPENAI_RESPONSE_OUTPUT_ITEM_DONE = "response.output_item.done"
    OPENAI_CONVERSATION_ITEM_CREATE = "conversation.item.create"
    OPENAI_RESPONSE_CREATE = "response.create"
    OPENAI_CONVERSATION_ITEM_TRUNCATE = "conversation.item.truncate"


class TwilioStartMessage(BaseModel):
    """Twilio start message"""
    event: str
    sequenceNumber: str
    start: Dict[str, Any]
    streamSid: str


class TwilioMediaMessage(BaseModel):
    """Twilio media message"""
    event: str
    sequenceNumber: str
    media: Dict[str, Any]
    streamSid: str


class TwilioCloseMessage(BaseModel):
    """Twilio close message"""
    event: str
    sequenceNumber: str
    streamSid: str


class OpenAISessionConfig(BaseModel):
    """OpenAI session configuration"""
    modalities: List[str] = ["text", "audio"]
    turn_detection: Dict[str, str] = {"type": "server_vad"}
    voice: str = "ash"
    input_audio_transcription: Dict[str, str] = {"model": "whisper-1"}
    input_audio_format: str = "g711_ulaw"
    output_audio_format: str = "g711_ulaw"


class OpenAISessionUpdate(BaseModel):
    """OpenAI session update message"""
    type: str = "session.update"
    session: OpenAISessionConfig


class FunctionCallItem(BaseModel):
    """Function call item"""
    type: str = "function_call"
    name: str
    arguments: str
    call_id: Optional[str] = None
    item_id: Optional[str] = None


class FunctionSchema(BaseModel):
    """Function schema definition"""
    name: str
    type: str = "function"
    description: Optional[str] = None
    parameters: Dict[str, Any]


class FunctionHandler(BaseModel):
    """Function handler"""
    function_schema: FunctionSchema

    class Config:
        arbitrary_types_allowed = True


class SessionState(BaseModel):
    """Session state"""
    stream_sid: Optional[str] = None
    latest_media_timestamp: Optional[int] = None
    response_start_timestamp: Optional[int] = None
    last_assistant_item: Optional[str] = None
    saved_config: Optional[Dict[str, Any]] = None

    class Config:
        arbitrary_types_allowed = True


class PublicUrlResponse(BaseModel):
    """Public URL response"""
    publicUrl: str


class ToolsResponse(BaseModel):
    """Tools list response"""
    tools: List[FunctionSchema]
