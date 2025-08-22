#!/usr/bin/env python3
"""
HTTP server entry point for Fantasy Premier League MCP server on Google Cloud Run.
Implements proper MCP HTTP transport for remote connections.
"""

import asyncio
import os
import logging
import sys
import json
import time
from typing import Any, Dict

# Set up logging for Cloud Run
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Try to import MCP server
try:
    from mcp.server.fastmcp import FastMCP
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.server.sse import SseServerTransport
    from mcp import types
    
    # Import our MCP server
    from src.fpl_mcp.__main__ import mcp as fpl_mcp_server
    MCP_AVAILABLE = True
except ImportError as e:
    logger.warning(f"MCP imports not available: {e}")
    MCP_AVAILABLE = False

# HTTP Server implementation
from http.server import HTTPServer, BaseHTTPRequestHandler

class MCPHandler(BaseHTTPRequestHandler):
    """HTTP handler that implements MCP transport"""
    
    def do_GET(self):
        if self.path == "/health" or self.path == "/":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = {
                "status": "healthy",
                "service": "Fantasy Premier League MCP Server",
                "mcp_available": MCP_AVAILABLE,
                "timestamp": time.time()
            }
            self.wfile.write(json.dumps(response).encode())
        elif self.path == "/mcp" and MCP_AVAILABLE:
            # SSE endpoint for MCP connections
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()
            
            # Keep connection alive for SSE
            try:
                while True:
                    self.wfile.write(b"data: {\"type\": \"ping\"}\n\n")
                    self.wfile.flush()
                    time.sleep(30)  # Ping every 30 seconds
            except (BrokenPipeError, ConnectionResetError):
                logger.info("SSE connection closed by client")
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == "/mcp" and MCP_AVAILABLE:
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    post_data = self.rfile.read(content_length)
                    request_data = json.loads(post_data.decode('utf-8'))
                else:
                    request_data = {}
                
                # Handle MCP HTTP transport request
                response = self._handle_mcp_request(request_data)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                self.end_headers()
                
                self.wfile.write(json.dumps(response).encode())
                
            except Exception as e:
                logger.error(f"Error handling MCP request: {e}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                error_response = {
                    "jsonrpc": "2.0",
                    "id": request_data.get("id") if 'request_data' in locals() else None,
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": str(e)
                    }
                }
                self.wfile.write(json.dumps(error_response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_OPTIONS(self):
        # Handle CORS preflight requests
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def _handle_mcp_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP JSON-RPC request"""
        try:
            method = request_data.get("method")
            params = request_data.get("params", {})
            request_id = request_data.get("id")
            
            logger.info(f"MCP request: {method}")
            
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
                # Return available resources
                resources = [
                    {"uri": "fpl://static/players", "name": "All Players", "description": "All FPL players with statistics"},
                    {"uri": "fpl://static/teams", "name": "All Teams", "description": "All Premier League teams"},
                    {"uri": "fpl://gameweeks/current", "name": "Current Gameweek", "description": "Current gameweek information"},
                    {"uri": "fpl://fixtures", "name": "Fixtures", "description": "All fixtures for the season"}
                ]
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"resources": resources}
                }
            elif method == "tools/list":
                # Return available tools
                tools = [
                    {
                        "name": "compare_players",
                        "description": "Compare multiple players across various metrics",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "player_names": {"type": "array", "items": {"type": "string"}},
                                "metrics": {"type": "array", "items": {"type": "string"}}
                            }
                        }
                    },
                    {
                        "name": "analyze_player_fixtures",
                        "description": "Analyze upcoming fixtures for a player",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "player_name": {"type": "string"},
                                "num_fixtures": {"type": "integer"}
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
                        "message": f"Method not found: {method}"
                    }
                }
                
        except Exception as e:
            logger.error(f"Error processing MCP request: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_data.get("id"),
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                }
            }
    
    def log_message(self, format, *args):
        # Use our logger instead of default
        logger.info(format % args)

def main():
    """Run HTTP server with MCP transport for Cloud Run."""
    # Get port from environment variable (Cloud Run sets this)
    port = int(os.environ.get("PORT", 8080))
    
    # Log environment info
    environment = os.environ.get("ENVIRONMENT", "development")
    logger.info(f"Starting Fantasy Premier League MCP HTTP server")
    logger.info(f"Environment: {environment}")
    logger.info(f"Port: {port}")
    logger.info(f"MCP transport available: {MCP_AVAILABLE}")
    
    # Check for credentials (optional for public endpoints)
    has_fpl_creds = bool(
        os.environ.get("FPL_EMAIL") and 
        os.environ.get("FPL_PASSWORD") and 
        os.environ.get("FPL_TEAM_ID")
    )
    logger.info(f"FPL credentials available: {has_fpl_creds}")
    
    try:
        # Start HTTP server with MCP transport
        server = HTTPServer(('0.0.0.0', port), MCPHandler)
        logger.info(f"MCP HTTP server started on 0.0.0.0:{port}")
        logger.info("Available endpoints:")
        logger.info("  GET  / or /health - Health check")
        logger.info("  GET  /mcp - SSE endpoint for MCP")
        logger.info("  POST /mcp - HTTP transport for MCP requests")
        logger.info("Server is ready to accept MCP connections")
        
        # Keep the server running
        server.serve_forever()
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        logger.exception("Server startup failed")
        sys.exit(1)

if __name__ == "__main__":
    main()