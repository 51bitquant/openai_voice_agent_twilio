#!/usr/bin/env python3
"""
Simple server testing script
Verify that all components are working properly
"""
import asyncio
import json
import aiohttp
from urllib.parse import urlparse

async def test_server(base_url: str = "http://localhost:8081"):
    """Test basic server functionality"""
    
    print(f"🧪 Testing server: {base_url}")
    print("=" * 50)
    
    async with aiohttp.ClientSession() as session:
        
        # Test root endpoint
        try:
            async with session.get(f"{base_url}/") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Root endpoint OK")
                    print(f"   Response: {data}")
                else:
                    print(f"❌ Root endpoint error: {response.status}")
        except Exception as e:
            print(f"❌ Root endpoint exception: {e}")
        
        # Test public-url endpoint
        try:
            async with session.get(f"{base_url}/public-url") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ public-url endpoint OK")
                    print(f"   Public URL: {data.get('publicUrl')}")
                else:
                    print(f"❌ public-url endpoint error: {response.status}")
        except Exception as e:
            print(f"❌ public-url endpoint exception: {e}")
        
        # Test tools endpoint
        try:
            async with session.get(f"{base_url}/tools") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ tools endpoint OK")
                    tools = data.get('tools', [])
                    print(f"   Available tools count: {len(tools)}")
                    for tool in tools:
                        print(f"   - {tool.get('name')}: {tool.get('description')}")
                else:
                    print(f"❌ tools endpoint error: {response.status}")
        except Exception as e:
            print(f"❌ tools endpoint exception: {e}")
        
        # Test TwiML endpoint
        try:
            async with session.get(f"{base_url}/twiml") as response:
                if response.status == 200:
                    content = await response.text()
                    print("✅ TwiML endpoint OK")
                    if "Connect" in content and "Stream" in content:
                        print("   TwiML format correct")
                    else:
                        print("   ⚠️  TwiML format may have issues")
                else:
                    print(f"❌ TwiML endpoint error: {response.status}")
        except Exception as e:
            print(f"❌ TwiML endpoint exception: {e}")
    
    print("=" * 50)
    print("🎉 Testing completed!")
    print("\n📝 Next steps:")
    print("1. Ensure correct environment variables are set (OPENAI_API_KEY, PUBLIC_URL)")
    print("2. Use 'ngrok http 8081' to expose service to public internet")
    print("3. Configure Webhook URL in Twilio Console")
    print("4. Call Twilio phone number for testing")

async def test_websocket(ws_url: str = "ws://localhost:8081/ws/logs"):
    """Test WebSocket connection"""
    try:
        import websockets
        print(f"\n🔌 Testing WebSocket connection: {ws_url}")
        
        async with websockets.connect(ws_url) as websocket:
            print("✅ WebSocket connection successful")
            
            # Send test message
            test_message = {"type": "test", "message": "Hello from test script"}
            await websocket.send(json.dumps(test_message))
            print("✅ Message sent successfully")
            
    except ImportError:
        print("⚠️  websockets package not installed, skipping WebSocket test")
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")

if __name__ == "__main__":
    import sys
    
    base_url = "http://localhost:8081"
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    
    asyncio.run(test_server(base_url))
    asyncio.run(test_websocket()) 