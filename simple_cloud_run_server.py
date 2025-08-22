#!/usr/bin/env python3
"""
Simple, robust Cloud Run server for Fantasy Premier League MCP.
Focuses on reliability and proper Cloud Run integration.
"""

import json
import logging
import os
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Set up logging for Cloud Run
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class SimpleCloudRunHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for Cloud Run MCP server"""
    
    def do_GET(self):
        """Handle GET requests"""
        path = urlparse(self.path).path
        
        # CORS headers for all responses
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        
        if path in ["/", "/health"]:
            self._handle_health()
        elif path == "/mcp/capabilities":
            self._handle_capabilities()
        elif path == "/mcp":
            self._handle_mcp_info()
        else:
            self._handle_404()
    
    def do_POST(self):
        """Handle POST requests"""
        path = urlparse(self.path).path
        
        # CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        
        if path == "/mcp":
            self._handle_mcp_request()
        else:
            self._handle_404()
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
    
    def _handle_health(self):
        """Health check endpoint"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        health_data = {
            "status": "healthy",
            "service": "Fantasy Premier League MCP Server",
            "version": "0.1.6",
            "timestamp": time.time(),
            "environment": os.environ.get("ENVIRONMENT", "production"),
            "port": os.environ.get("PORT", "8080"),
            "endpoints": {
                "health": "/health",
                "mcp": "/mcp",
                "capabilities": "/mcp/capabilities"
            },
            "features": {
                "fpl_data": True,
                "player_analysis": True,
                "fixture_analysis": True,
                "team_comparison": True
            }
        }
        
        self.wfile.write(json.dumps(health_data, indent=2).encode())
    
    def _handle_capabilities(self):
        """MCP capabilities endpoint"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        capabilities = {
            "protocol_version": "2024-11-05",
            "server_info": {
                "name": "Fantasy Premier League MCP Server",
                "version": "0.1.6",
                "description": "MCP server providing Fantasy Premier League data and analysis tools"
            },
            "capabilities": {
                "resources": {
                    "supported": True,
                    "schemes": ["fpl"]
                },
                "tools": {
                    "supported": True,
                    "count": 8
                },
                "prompts": {
                    "supported": True,
                    "count": 5
                }
            },
            "transport": "http",
            "available_resources": [
                "fpl://static/players",
                "fpl://static/teams", 
                "fpl://gameweeks/current",
                "fpl://gameweeks/all",
                "fpl://fixtures"
            ],
            "available_tools": [
                "compare_players",
                "analyze_player_fixtures",
                "get_gameweek_status",
                "analyze_players",
                "analyze_fixtures",
                "get_blank_gameweeks",
                "get_double_gameweeks",
                "check_fpl_authentication"
            ]
        }
        
        self.wfile.write(json.dumps(capabilities, indent=2).encode())
    
    def _handle_mcp_info(self):
        """MCP info endpoint for GET requests"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        info = {
            "service": "Fantasy Premier League MCP Server",
            "transport": "http",
            "protocol": "Model Context Protocol",
            "version": "2024-11-05",
            "message": "This is the MCP endpoint. Send POST requests with JSON-RPC format.",
            "example_request": {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "test-client",
                        "version": "1.0.0"
                    }
                }
            },
            "documentation": "https://github.com/rishijatia/fantasy-pl-mcp"
        }
        
        self.wfile.write(json.dumps(info, indent=2).encode())
    
    def _handle_mcp_request(self):
        """Handle MCP JSON-RPC requests"""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_error(400, "Empty request body")
                return
            
            body = self.rfile.read(content_length)
            request_data = json.loads(body.decode('utf-8'))
            
            method = request_data.get("method", "unknown")
            params = request_data.get("params", {})
            request_id = request_data.get("id")
            
            logger.info(f"MCP request: {method}")
            
            # Handle MCP methods
            response = self._process_mcp_method(method, params, request_id)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            
        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON in request body")
        except Exception as e:
            logger.error(f"Error handling MCP request: {e}")
            self._send_error(500, f"Internal server error: {str(e)}")
    
    def _process_mcp_method(self, method: str, params: dict, request_id) -> dict:
        """Process MCP method and return response"""
        
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
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "resources": [
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
                            "uri": "fpl://fixtures",
                            "name": "All Fixtures",
                            "description": "All fixtures for the current season",
                            "mimeType": "application/json"
                        }
                    ]
                }
            }
        
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
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
                                        "description": "Metrics to compare (optional)"
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
                                        "description": "Number of fixtures to analyze (default: 5)",
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
                }
            }
        
        elif method == "prompts/list":
            return {
                "jsonrpc": "2.0", 
                "id": request_id,
                "result": {
                    "prompts": [
                        {
                            "name": "player_analysis_prompt",
                            "description": "Create a prompt for analyzing an FPL player in depth",
                            "arguments": [
                                {"name": "player_name", "description": "Player name", "required": True},
                                {"name": "include_comparisons", "description": "Include comparisons", "required": False}
                            ]
                        },
                        {
                            "name": "transfer_advice_prompt", 
                            "description": "Create a prompt for transfer advice",
                            "arguments": [
                                {"name": "budget", "description": "Available budget", "required": True},
                                {"name": "position", "description": "Target position", "required": False}
                            ]
                        }
                    ]
                }
            }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                    "data": {
                        "available_methods": [
                            "initialize",
                            "resources/list", 
                            "resources/read",
                            "tools/list",
                            "tools/call", 
                            "prompts/list",
                            "prompts/get"
                        ]
                    }
                }
            }
    
    def _send_error(self, status_code: int, message: str):
        """Send error response"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        error = {
            "error": {
                "code": status_code,
                "message": message,
                "timestamp": time.time()
            }
        }
        
        self.wfile.write(json.dumps(error).encode())
    
    def _handle_404(self):
        """Handle 404 responses"""
        self.send_response(404)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        response = {
            "error": {
                "code": 404,
                "message": "Not Found",
                "available_endpoints": [
                    "GET /health - Health check",
                    "GET /mcp/capabilities - Server capabilities",
                    "GET /mcp - MCP info",
                    "POST /mcp - MCP JSON-RPC requests"
                ]
            }
        }
        
        self.wfile.write(json.dumps(response, indent=2).encode())
    
    def log_message(self, format, *args):
        """Use structured logging"""
        logger.info(format % args)

def main():
    """Main entry point for Cloud Run"""
    port = int(os.environ.get("PORT", 8080))
    
    logger.info("Starting Simple Fantasy Premier League MCP Server for Cloud Run")
    logger.info(f"Port: {port}")
    logger.info(f"Environment: {os.environ.get('ENVIRONMENT', 'production')}")
    
    # Check for FPL credentials
    has_creds = bool(
        os.environ.get("FPL_EMAIL") and 
        os.environ.get("FPL_PASSWORD")
    )
    logger.info(f"FPL credentials configured: {has_creds}")
    
    try:
        # Create and start server
        server = HTTPServer(('0.0.0.0', port), SimpleCloudRunHandler)
        
        logger.info(f"Server started successfully on 0.0.0.0:{port}")
        logger.info("Available endpoints:")
        logger.info("  GET  /health - Health check")
        logger.info("  GET  /mcp/capabilities - Server capabilities")
        logger.info("  GET  /mcp - MCP endpoint info") 
        logger.info("  POST /mcp - MCP JSON-RPC requests")
        logger.info("Ready to serve MCP requests")
        
        # Run the server
        server.serve_forever()
        
    except Exception as e:
        logger.error(f"Server startup failed: {e}")
        logger.exception("Full exception details:")
        sys.exit(1)

if __name__ == "__main__":
    main()