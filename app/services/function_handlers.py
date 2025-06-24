"""
Function handler service
Define OpenAI callable functions and their processing logic
"""
import json
import aiohttp
from typing import Dict, Any, List, Callable, Awaitable
from app.models.schemas import FunctionSchema, FunctionHandler


class FunctionHandlerService:
    """Function handler service class"""
    
    def __init__(self):
        self.handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[str]]] = {}
        self.schemas: List[FunctionSchema] = []
        self._register_default_functions()
    
    def _register_default_functions(self):
        """Register default functions"""
        self.register_function(
            name="get_weather_from_coords",
            description="Get the current weather from coordinates",
            parameters={
                "type": "object",
                "properties": {
                    "latitude": {
                        "type": "number",
                        "description": "Latitude coordinate"
                    },
                    "longitude": {
                        "type": "number", 
                        "description": "Longitude coordinate"
                    }
                },
                "required": ["latitude", "longitude"]
            },
            handler=self._get_weather_handler
        )
    
    def register_function(
        self, 
        name: str, 
        description: str, 
        parameters: Dict[str, Any],
        handler: Callable[[Dict[str, Any]], Awaitable[str]]
    ):
        """
        Register a new function
        
        Args:
            name: Function name
            description: Function description
            parameters: Function parameter schema
            handler: Function handler
        """
        schema = FunctionSchema(
            name=name,
            description=description,
            parameters=parameters
        )
        
        self.schemas.append(schema)
        self.handlers[name] = handler
    
    async def handle_function_call(self, name: str, arguments: str) -> str:
        """
        Handle function call
        
        Args:
            name: Function name
            arguments: JSON string arguments
            
        Returns:
            JSON string of function execution result
        """
        if name not in self.handlers:
            return json.dumps({
                "error": f"No handler found for function: {name}"
            })
        
        try:
            args = json.loads(arguments)
        except json.JSONDecodeError:
            return json.dumps({
                "error": "Invalid JSON arguments for function call"
            })
        
        try:
            result = await self.handlers[name](args)
            return result
        except Exception as e:
            return json.dumps({
                "error": f"Error running function {name}: {str(e)}"
            })
    
    def get_function_schemas(self) -> List[Dict[str, Any]]:
        """Get schema list of all functions"""
        return [function_schema.dict() for function_schema in self.schemas]
    
    async def _get_weather_handler(self, args: Dict[str, Any]) -> str:
        """Weather query function handler"""
        latitude = args.get("latitude")
        longitude = args.get("longitude")
        
        if latitude is None or longitude is None:
            return json.dumps({
                "error": "Missing latitude or longitude"
            })
        
        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast"
                f"?latitude={latitude}&longitude={longitude}"
                f"&current=temperature_2m,wind_speed_10m"
                f"&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m"
            )
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        current_temp = data.get("current", {}).get("temperature_2m")
                        return json.dumps({"temp": current_temp})
                    else:
                        return json.dumps({
                            "error": f"Weather API returned status {response.status}"
                        })
        except Exception as e:
            return json.dumps({
                "error": f"Failed to fetch weather data: {str(e)}"
            })


# Global function handler instance
function_handler_service = FunctionHandlerService()
