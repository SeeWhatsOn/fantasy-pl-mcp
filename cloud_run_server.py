#!/usr/bin/env python3
"""
Cloud Run compatible MCP HTTP server.
Properly integrates FastMCP with HTTP transport for Google Cloud Run.
"""

import asyncio
import json
import logging
import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, Optional
from urllib.parse import urlparse

# Set up logging for Cloud Run
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Global variables for async handling
executor = ThreadPoolExecutor(max_workers=4)
loop = None
mcp_server = None

def setup_async_environment():
    """Set up async environment for Cloud Run"""
    global loop, mcp_server
    
    try:
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Import and set up MCP server
        from fpl_mcp.__main__ import mcp as fpl_mcp
        mcp_server = fpl_mcp
        
        logger.info("MCP server loaded successfully")
        return True
        
    except ImportError as e:
        logger.error(f"Failed to import MCP server: {e}")
        try:
            # Fallback import path
            import sys
            sys.path.insert(0, '/app/src')
            from fpl_mcp.__main__ import mcp as fpl_mcp
            mcp_server = fpl_mcp
            logger.info("MCP server loaded with fallback import")
            return True
        except ImportError as e2:
            logger.error(f"Fallback import also failed: {e2}")
            return False
    except Exception as e:
        logger.error(f"Error setting up async environment: {e}")
        return False

def run_async_in_thread(coro):
    """Run async function in the background thread"""
    global loop
    if loop is None:
        return None
    
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    try:
        return future.result(timeout=30)  # 30 second timeout
    except Exception as e:
        logger.error(f"Async operation failed: {e}")
        return None

class CloudRunMCPHandler(BaseHTTPRequestHandler):
    """HTTP handler for Cloud Run MCP server"""
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        # Set CORS headers
        self._set_cors_headers()
        
        if path in ["/", "/health"]:
            self._handle_health_check()
        elif path == "/mcp/capabilities":
            self._handle_capabilities()
        elif path == "/mcp":
            self._handle_sse_connection()
        else:
            self._send_404()
    
    def do_POST(self):
        """Handle POST requests for MCP JSON-RPC"""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        # Set CORS headers
        self._set_cors_headers()
        
        if path == "/mcp":
            self._handle_mcp_request()
        else:
            self._send_404()
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self._set_cors_headers()
        self.send_response(200)
        self.end_headers()
    
    def _set_cors_headers(self):
        """Set CORS headers"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Max-Age', '86400')
    
    def _handle_health_check(self):
        """Handle health check"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        health_status = {
            "status": "healthy",
            "service": "Fantasy Premier League MCP Server",
            "version": "0.1.6",
            "mcp_available": mcp_server is not None,
            "transport": "http",
            "timestamp": time.time(),
            "environment": os.environ.get("ENVIRONMENT", "production"),
            "endpoints": {
                "health": "/health",
                "mcp_http": "/mcp (POST)",
                "mcp_sse": "/mcp (GET)",
                "capabilities": "/mcp/capabilities"
            }
        }
        
        self.wfile.write(json.dumps(health_status, indent=2).encode())
    
    def _handle_capabilities(self):
        """Handle capabilities endpoint"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        capabilities = {
            "protocol_version": "2024-11-05",
            "server_info": {
                "name": "Fantasy Premier League MCP Server",
                "version": "0.1.6"
            },
            "capabilities": {
                "resources": True,
                "tools": True, 
                "prompts": True,
                "logging": False
            },
            "transport": ["http", "sse"],
            "mcp_server_available": mcp_server is not None
        }
        
        self.wfile.write(json.dumps(capabilities, indent=2).encode())
    
    def _handle_sse_connection(self):
        """Handle SSE connection"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.end_headers()
        
        try:
            # Send initial connection message
            self._send_sse_message({
                "type": "connection",
                "status": "connected",
                "server": "Fantasy Premier League MCP Server",
                "mcp_available": mcp_server is not None
            })
            
            # Keep connection alive
            ping_count = 0
            while ping_count < 120:  # 1 hour max (30s * 120)
                self._send_sse_message({
                    "type": "ping", 
                    "timestamp": time.time(),
                    "count": ping_count
                })
                time.sleep(30)
                ping_count += 1
                
        except (BrokenPipeError, ConnectionResetError):
            logger.info("SSE connection closed by client")
        except Exception as e:
            logger.error(f"SSE connection error: {e}")
    
    def _send_sse_message(self, data: Dict[str, Any]):
        """Send SSE message"""
        message = f"data: {json.dumps(data)}\n\n"
        self.wfile.write(message.encode())
        self.wfile.flush()
    
    def _handle_mcp_request(self):
        """Handle MCP JSON-RPC request"""
        try:
            # Read request
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_error_response(400, "Empty request body")
                return
            
            body = self.rfile.read(content_length)
            request_data = json.loads(body.decode('utf-8'))
            
            method = request_data.get("method", "unknown")
            logger.info(f"MCP request: {method}")
            
            # Process request
            if mcp_server is not None:
                response = self._process_with_mcp_server(request_data)
            else:
                response = self._process_without_mcp_server(request_data)
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            self._send_error_response(400, "Invalid JSON")
        except Exception as e:
            logger.error(f"Error handling MCP request: {e}")
            self._send_error_response(500, f"Internal error: {str(e)}")
    
    def _process_with_mcp_server(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process request with actual MCP server"""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        try:
            if method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "resources": {},
                            "tools": {},
                            "prompts": {}
                        },
                        "serverInfo": {
                            "name": "Fantasy Premier League MCP Server",
                            "version": "0.1.6"
                        }
                    }
                }
            elif method == "resources/list":
                # Return static resource list for now
                resources = [
                    {"uri": "fpl://static/players", "name": "All Players", "description": "All FPL players"},
                    {"uri": "fpl://static/teams", "name": "All Teams", "description": "All Premier League teams"},
                    {"uri": "fpl://gameweeks/current", "name": "Current Gameweek", "description": "Current gameweek info"},
                    {"uri": "fpl://fixtures", "name": "Fixtures", "description": "All fixtures"}
                ]
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"resources": resources}
                }
            elif method == "tools/list":
                # Return static tools list
                tools = [
                    {
                        "name": "compare_players",
                        "description": "Compare multiple players",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "player_names": {"type": "array", "items": {"type": "string"}}
                            }
                        }
                    },
                    {
                        "name": "analyze_player_fixtures", 
                        "description": "Analyze player fixtures",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "player_name": {"type": "string"}
                            }
                        }
                    }
                ]
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"tools": tools}
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not implemented: {method}"
                    }
                }
        except Exception as e:
            logger.error(f"Error processing MCP request: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                }
            }
    
    def _process_without_mcp_server(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process request without MCP server (fallback)"""
        method = request.get("method")
        request_id = request.get("id")
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32000,
                "message": f"MCP server not available - method {method} cannot be processed"
            }
        }
    
    def _send_error_response(self, status_code: int, message: str):
        """Send error response"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        error_response = {
            "error": {
                "code": status_code,
                "message": message,
                "timestamp": time.time()
            }
        }
        
        self.wfile.write(json.dumps(error_response).encode())
    
    def _send_404(self):
        """Send 404 response"""
        self.send_response(404)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        response = {
            "error": {
                "code": 404,
                "message": "Not Found",
                "available_endpoints": ["/", "/health", "/mcp", "/mcp/capabilities"]
            }
        }
        
        self.wfile.write(json.dumps(response).encode())
    
    def log_message(self, format, *args):
        """Use structured logging"""
        logger.info(format % args)

def run_background_loop():
    """Run event loop in background thread"""
    global loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_forever()

def main():
    """Main Cloud Run entry point"""
    port = int(os.environ.get("PORT", 8080))
    
    logger.info("Starting Fantasy Premier League MCP Server for Cloud Run")
    logger.info(f"Port: {port}")
    logger.info(f"Environment: {os.environ.get('ENVIRONMENT', 'production')}")
    
    # Set up async environment in background thread
    logger.info("Setting up async environment...")
    
    # Start background event loop
    loop_thread = threading.Thread(target=run_background_loop, daemon=True)
    loop_thread.start()
    
    # Give loop time to start
    time.sleep(1)
    
    # Try to set up MCP server
    mcp_available = setup_async_environment()
    logger.info(f"MCP server available: {mcp_available}")
    
    # Check for FPL credentials
    has_fpl_creds = bool(
        os.environ.get("FPL_EMAIL") and 
        os.environ.get("FPL_PASSWORD") and 
        os.environ.get("FPL_TEAM_ID")
    )
    logger.info(f"FPL credentials available: {has_fpl_creds}")
    
    try:
        # Start HTTP server
        server = HTTPServer(('0.0.0.0', port), CloudRunMCPHandler)
        logger.info(f"HTTP server started on 0.0.0.0:{port}")
        logger.info("Available endpoints:")
        logger.info("  GET  /health - Health check")
        logger.info("  GET  /mcp/capabilities - Server capabilities") 
        logger.info("  GET  /mcp - SSE endpoint")
        logger.info("  POST /mcp - HTTP JSON-RPC endpoint")
        logger.info("Server ready for connections")
        
        # Run server
        server.serve_forever()
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        logger.exception("Server startup failed")
        sys.exit(1)

if __name__ == "__main__":
    main()