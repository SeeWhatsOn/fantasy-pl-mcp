#!/usr/bin/env python3
"""
Proper MCP HTTP transport server for remote connections.
Integrates with the FastMCP server implementation.
"""

import asyncio
import json
import logging
import os
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, Optional
import threading
from urllib.parse import urlparse, parse_qs

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Import MCP components
try:
    from mcp.server.fastmcp import FastMCP
    from mcp import types
    
    # Import our MCP server
    from src.fpl_mcp.__main__ import mcp as fpl_mcp_server
    MCP_AVAILABLE = True
    logger.info("MCP server loaded successfully")
except ImportError as e:
    logger.error(f"Failed to import MCP components: {e}")
    MCP_AVAILABLE = False


class MCPTransportHandler(BaseHTTPRequestHandler):
    """HTTP handler implementing proper MCP transport"""
    
    def __init__(self, *args, **kwargs):
        self.mcp_server = None
        if MCP_AVAILABLE:
            self.mcp_server = fpl_mcp_server
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        # CORS headers for all responses
        self._set_cors_headers()
        
        if path in ["/", "/health"]:
            self._handle_health_check()
        elif path == "/mcp" and MCP_AVAILABLE:
            self._handle_sse_connection()
        elif path == "/mcp/capabilities" and MCP_AVAILABLE:
            self._handle_capabilities()
        else:
            self._send_404()
    
    def do_POST(self):
        """Handle POST requests for MCP JSON-RPC"""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        # CORS headers
        self._set_cors_headers()
        
        if path == "/mcp" and MCP_AVAILABLE:
            self._handle_mcp_request()
        else:
            self._send_404()
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self._set_cors_headers()
        self.send_response(200)
        self.end_headers()
    
    def _set_cors_headers(self):
        """Set CORS headers for all responses"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Max-Age', '86400')
    
    def _handle_health_check(self):
        """Handle health check endpoint"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        response = {
            "status": "healthy",
            "service": "Fantasy Premier League MCP Server",
            "version": "0.1.6",
            "mcp_available": MCP_AVAILABLE,
            "transport": "http",
            "timestamp": time.time(),
            "endpoints": {
                "health": "/health",
                "mcp_http": "/mcp (POST)",
                "mcp_sse": "/mcp (GET)",
                "capabilities": "/mcp/capabilities"
            }
        }
        
        self.wfile.write(json.dumps(response, indent=2).encode())
    
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
            "transport": ["http", "sse"]
        }
        
        self.wfile.write(json.dumps(capabilities, indent=2).encode())
    
    def _handle_sse_connection(self):
        """Handle SSE connection for MCP"""
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
                "server": "Fantasy Premier League MCP Server"
            })
            
            # Keep connection alive with periodic pings
            while True:
                self._send_sse_message({"type": "ping", "timestamp": time.time()})
                time.sleep(30)
                
        except (BrokenPipeError, ConnectionResetError):
            logger.info("SSE connection closed by client")
        except Exception as e:
            logger.error(f"SSE connection error: {e}")
    
    def _send_sse_message(self, data: Dict[str, Any]):
        """Send an SSE message"""
        message = f"data: {json.dumps(data)}\n\n"
        self.wfile.write(message.encode())
        self.wfile.flush()
    
    def _handle_mcp_request(self):
        """Handle MCP JSON-RPC request"""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_error_response(400, "Empty request body")
                return
            
            body = self.rfile.read(content_length)
            request_data = json.loads(body.decode('utf-8'))
            
            logger.info(f"MCP request: {request_data.get('method', 'unknown')}")
            
            # Process the request
            response = self._process_mcp_request(request_data)
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in request: {e}")
            self._send_error_response(400, "Invalid JSON")
        except Exception as e:
            logger.error(f"Error handling MCP request: {e}")
            self._send_error_response(500, f"Internal error: {str(e)}")
    
    def _process_mcp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process MCP JSON-RPC request and return response"""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        try:
            if method == "initialize":
                return self._handle_initialize(request_id, params)
            elif method == "resources/list":
                return self._handle_resources_list(request_id)
            elif method == "resources/read":
                return self._handle_resources_read(request_id, params)
            elif method == "tools/list":
                return self._handle_tools_list(request_id)
            elif method == "tools/call":
                return self._handle_tools_call(request_id, params)
            elif method == "prompts/list":
                return self._handle_prompts_list(request_id)
            elif method == "prompts/get":
                return self._handle_prompts_get(request_id, params)
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
        except Exception as e:
            logger.error(f"Error processing method {method}: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                }
            }
    
    def _handle_initialize(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "resources": {},
                    "tools": {},
                    "prompts": {},
                    "logging": {}
                },
                "serverInfo": {
                    "name": "Fantasy Premier League MCP Server",
                    "version": "0.1.6"
                }
            }
        }
    
    def _handle_resources_list(self, request_id: Any) -> Dict[str, Any]:
        """Handle resources/list request"""
        # This should be dynamically generated from the actual MCP server
        resources = [
            {
                "uri": "fpl://static/players",
                "name": "All Players",
                "description": "All FPL players with comprehensive statistics",
                "mimeType": "application/json"
            },
            {
                "uri": "fpl://static/teams",
                "name": "All Teams", 
                "description": "All Premier League teams with strength ratings",
                "mimeType": "application/json"
            },
            {
                "uri": "fpl://gameweeks/current",
                "name": "Current Gameweek",
                "description": "Information about the current gameweek",
                "mimeType": "application/json"
            },
            {
                "uri": "fpl://gameweeks/all",
                "name": "All Gameweeks",
                "description": "Information about all gameweeks",
                "mimeType": "application/json"
            },
            {
                "uri": "fpl://fixtures",
                "name": "All Fixtures",
                "description": "All fixtures for the current Premier League season",
                "mimeType": "application/json"
            }
        ]
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"resources": resources}
        }
    
    def _handle_resources_read(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/read request"""
        uri = params.get("uri")
        if not uri:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": "Missing uri parameter"}
            }
        
        # For now, return a placeholder - this should integrate with actual resource handlers
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps({"message": f"Resource {uri} would be fetched here"})
                    }
                ]
            }
        }
    
    def _handle_tools_list(self, request_id: Any) -> Dict[str, Any]:
        """Handle tools/list request"""
        tools = [
            {
                "name": "compare_players",
                "description": "Compare multiple players across various metrics",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "player_names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of player names to compare"
                        },
                        "metrics": {
                            "type": "array", 
                            "items": {"type": "string"},
                            "description": "Metrics to compare (e.g., total_points, form, goals_scored)"
                        }
                    },
                    "required": ["player_names"]
                }
            },
            {
                "name": "analyze_player_fixtures",
                "description": "Analyze upcoming fixtures for a player",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "player_name": {
                            "type": "string",
                            "description": "Name of the player to analyze"
                        },
                        "num_fixtures": {
                            "type": "integer",
                            "description": "Number of upcoming fixtures to analyze",
                            "default": 5
                        }
                    },
                    "required": ["player_name"]
                }
            },
            {
                "name": "get_gameweek_status",
                "description": "Get information about current, previous, and next gameweeks",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": tools}
        }
    
    def _handle_tools_call(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request"""
        name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not name:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": "Missing tool name"}
            }
        
        # For now, return a placeholder - this should integrate with actual tool handlers  
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": f"Tool {name} would be executed here with arguments: {json.dumps(arguments)}"
                    }
                ]
            }
        }
    
    def _handle_prompts_list(self, request_id: Any) -> Dict[str, Any]:
        """Handle prompts/list request"""
        prompts = [
            {
                "name": "player_analysis_prompt",
                "description": "Create a prompt for analyzing an FPL player in depth",
                "arguments": [
                    {
                        "name": "player_name",
                        "description": "Name of the player to analyze",
                        "required": True
                    },
                    {
                        "name": "include_comparisons", 
                        "description": "Whether to compare with similar players",
                        "required": False
                    }
                ]
            },
            {
                "name": "transfer_advice_prompt",
                "description": "Create a prompt for getting detailed FPL transfer advice",
                "arguments": [
                    {
                        "name": "budget",
                        "description": "Available budget in millions",
                        "required": True
                    },
                    {
                        "name": "position",
                        "description": "Position to target (optional)",
                        "required": False
                    }
                ]
            }
        ]
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"prompts": prompts}
        }
    
    def _handle_prompts_get(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/get request"""
        name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not name:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": "Missing prompt name"}
            }
        
        # For now, return a placeholder - this should integrate with actual prompt handlers
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "description": f"Prompt {name}",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": f"Prompt {name} would be generated here with arguments: {json.dumps(arguments)}"
                        }
                    }
                ]
            }
        }
    
    def _send_error_response(self, status_code: int, message: str):
        """Send an error response"""
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
        
        self.wfile.write(json.dumps(response, indent=2).encode())
    
    def log_message(self, format, *args):
        """Use our logger for request logging"""
        logger.info(format % args)


def main():
    """Run the MCP HTTP transport server"""
    port = int(os.environ.get("PORT", 8080))
    
    logger.info("Starting Fantasy Premier League MCP HTTP Transport Server")
    logger.info(f"Port: {port}")
    logger.info(f"MCP available: {MCP_AVAILABLE}")
    
    try:
        server = HTTPServer(('0.0.0.0', port), MCPTransportHandler)
        logger.info(f"Server started on 0.0.0.0:{port}")
        logger.info("Available endpoints:")
        logger.info("  GET  /health - Health check")
        logger.info("  GET  /mcp/capabilities - Server capabilities")
        logger.info("  GET  /mcp - SSE endpoint")
        logger.info("  POST /mcp - HTTP JSON-RPC endpoint")
        logger.info("Server ready for MCP connections")
        
        server.serve_forever()
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()