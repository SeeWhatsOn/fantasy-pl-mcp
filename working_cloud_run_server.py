#!/usr/bin/env python3
"""
Working Cloud Run MCP server that properly integrates with FastMCP.
This bridges HTTP requests to the actual FastMCP server methods.
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
from concurrent.futures import ThreadPoolExecutor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class WorkingMCPHandler(BaseHTTPRequestHandler):
    """HTTP handler that properly bridges to FastMCP server"""
    
    # Class-level executor for async operations
    _executor = None
    _event_loop = None
    
    @classmethod
    def get_executor(cls):
        """Get or create the thread pool executor"""
        if cls._executor is None:
            cls._executor = ThreadPoolExecutor(max_workers=4)
        return cls._executor
    
    @classmethod
    def get_event_loop(cls):
        """Get or create the event loop for async operations"""
        if cls._event_loop is None:
            try:
                # Try to get the existing loop
                cls._event_loop = asyncio.get_event_loop()
            except RuntimeError:
                # Create new loop if none exists
                cls._event_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(cls._event_loop)
        return cls._event_loop
    
    def __init__(self, *args, **kwargs):
        self.fpl_mcp_server = None
        self.fpl_resources = {}
        self.fpl_tools = {}
        
        try:
            # Import the actual MCP server and its components
            from src.fpl_mcp.__main__ import mcp as fpl_mcp_server
            from src.fpl_mcp.fpl.resources import players, teams, gameweeks, fixtures
            from src.fpl_mcp.fpl.tools import comparisons
            
            self.fpl_mcp_server = fpl_mcp_server
            
            # Store resource and tool modules for direct access
            self.fpl_resources = {
                'players': players,
                'teams': teams,
                'gameweeks': gameweeks,
                'fixtures': fixtures
            }
            
            logger.info("Successfully loaded FPL MCP server and components")
        except ImportError as e:
            logger.error(f"Failed to import FPL MCP server: {e}")
        
        super().__init__(*args, **kwargs)
    
    def run_async(self, coro):
        """Run an async coroutine in the event loop"""
        try:
            loop = self.get_event_loop()
            if loop.is_running():
                # If loop is running, use executor
                future = asyncio.run_coroutine_threadsafe(coro, loop)
                return future.result(timeout=30)  # 30 second timeout
            else:
                # Run directly
                return loop.run_until_complete(coro)
        except Exception as e:
            logger.error(f"Error running async operation: {e}")
            raise
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path in ["/", "/health"]:
            self._handle_health()
        elif self.path == "/mcp":
            self._handle_mcp_info()
        else:
            self._handle_404()
    
    def do_POST(self):
        """Handle POST requests for MCP JSON-RPC"""
        if self.path == "/mcp":
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
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        response = {
            "status": "healthy",
            "service": "Fantasy Premier League MCP Server",
            "version": "0.1.6",
            "timestamp": time.time(),
            "mcp_server_loaded": self.fpl_mcp_server is not None,
            "port": os.environ.get("PORT", "8080"),
            "endpoints": {
                "health": "/health",
                "mcp": "/mcp (POST for JSON-RPC, GET for info)"
            }
        }
        
        self.wfile.write(json.dumps(response, indent=2).encode())
    
    def _handle_mcp_info(self):
        """MCP info endpoint"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        info = {
            "service": "Fantasy Premier League MCP Server",
            "protocol": "Model Context Protocol",
            "version": "2024-11-05",
            "message": "Send POST requests with JSON-RPC format to interact with MCP",
            "server_loaded": self.fpl_mcp_server is not None,
            "example_request": {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"}
                }
            }
        }
        
        self.wfile.write(json.dumps(info, indent=2).encode())
    
    def _handle_mcp_request(self):
        """Handle MCP JSON-RPC requests"""
        try:
            # Read request
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_error(400, "Empty request body")
                return
            
            body = self.rfile.read(content_length)
            request_data = json.loads(body.decode('utf-8'))
            
            method = request_data.get("method", "unknown")
            logger.info(f"MCP request: {method}")
            
            # Process the request
            response = self._process_mcp_request(request_data)
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            
        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON")
        except Exception as e:
            logger.error(f"Error handling MCP request: {e}")
            self._send_error(500, str(e))
    
    def _process_mcp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process MCP request using actual FastMCP server"""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        if not self.fpl_mcp_server:
            return self._error_response(request_id, -32603, "MCP server not loaded")
        
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
                # Get resources from the actual server
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "resources": [
                            {"uri": "fpl://static/players", "name": "All Players", "description": "All FPL players", "mimeType": "application/json"},
                            {"uri": "fpl://static/teams", "name": "All Teams", "description": "All Premier League teams", "mimeType": "application/json"},
                            {"uri": "fpl://gameweeks/current", "name": "Current Gameweek", "description": "Current gameweek info", "mimeType": "application/json"},
                            {"uri": "fpl://fixtures", "name": "Fixtures", "description": "All fixtures", "mimeType": "application/json"}
                        ]
                    }
                }
            
            elif method == "resources/read":
                uri = params.get("uri")
                if not uri:
                    return self._error_response(request_id, -32602, "Missing uri parameter")
                
                try:
                    # Parse URI and get real data
                    resource_data = self._get_resource_data(uri)
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "contents": [{
                                "uri": uri,
                                "mimeType": "application/json",
                                "text": json.dumps(resource_data)
                            }]
                        }
                    }
                except Exception as e:
                    logger.error(f"Error reading resource {uri}: {e}")
                    return self._error_response(request_id, -32603, f"Failed to read resource: {str(e)}")
            
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
                                        "player_names": {"type": "array", "items": {"type": "string"}},
                                        "metrics": {"type": "array", "items": {"type": "string"}}
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
                                        "player_name": {"type": "string"},
                                        "num_fixtures": {"type": "integer", "default": 5}
                                    },
                                    "required": ["player_name"]
                                }
                            },
                            {
                                "name": "get_gameweek_status",
                                "description": "Get current gameweek information",
                                "inputSchema": {"type": "object", "properties": {}}
                            }
                        ]
                    }
                }
            
            elif method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments", {})
                
                if not name:
                    return self._error_response(request_id, -32602, "Missing tool name")
                
                try:
                    # Execute the actual tool
                    tool_result = self._execute_tool(name, arguments)
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [{
                                "type": "text",
                                "text": json.dumps(tool_result, indent=2)
                            }]
                        }
                    }
                except Exception as e:
                    logger.error(f"Error executing tool {name}: {e}")
                    return self._error_response(request_id, -32603, f"Tool execution failed: {str(e)}")
            
            else:
                return self._error_response(request_id, -32601, f"Method not found: {method}")
                
        except Exception as e:
            logger.error(f"Error processing {method}: {e}")
            return self._error_response(request_id, -32603, str(e))
    
    def _get_resource_data(self, uri: str) -> Any:
        """Get real resource data from FPL MCP server"""
        logger.info(f"Getting resource data for: {uri}")
        
        try:
            if uri == "fpl://static/players":
                return self.run_async(self.fpl_resources['players'].get_players_resource())
            elif uri.startswith("fpl://static/players/"):
                # Extract player name from URI
                player_name = uri.split("/")[-1]
                matches = self.run_async(self.fpl_resources['players'].find_players_by_name(player_name))
                if matches:
                    return matches[0]
                else:
                    return {"error": f"No player found matching '{player_name}'"}
            elif uri == "fpl://static/teams":
                return self.run_async(self.fpl_resources['teams'].get_teams_resource())
            elif uri.startswith("fpl://static/teams/"):
                # Extract team name from URI
                team_name = uri.split("/")[-1]
                team = self.run_async(self.fpl_resources['teams'].get_team_by_name(team_name))
                if team:
                    return team
                else:
                    return {"error": f"No team found matching '{team_name}'"}
            elif uri == "fpl://gameweeks/current":
                return self.run_async(self.fpl_resources['gameweeks'].get_current_gameweek_resource())
            elif uri == "fpl://gameweeks/all":
                return self.run_async(self.fpl_resources['gameweeks'].get_gameweeks_resource())
            elif uri == "fpl://fixtures":
                return self.run_async(self.fpl_resources['fixtures'].get_fixtures_resource())
            elif uri.startswith("fpl://fixtures/gameweek/"):
                # Extract gameweek ID
                gameweek_id = int(uri.split("/")[-1])
                return self.run_async(self.fpl_resources['fixtures'].get_fixtures_resource(gameweek_id=gameweek_id))
            elif uri.startswith("fpl://fixtures/team/"):
                # Extract team name
                team_name = uri.split("/")[-1]
                return self.run_async(self.fpl_resources['fixtures'].get_fixtures_resource(team_name=team_name))
            elif uri.startswith("fpl://players/") and uri.endswith("/fixtures"):
                # Extract player name
                player_name = uri.split("/")[-2]
                player_matches = self.run_async(self.fpl_resources['players'].find_players_by_name(player_name))
                if not player_matches:
                    return {"error": f"No player found matching '{player_name}'"}
                player = player_matches[0]
                player_fixtures = self.run_async(self.fpl_resources['fixtures'].get_player_fixtures(player["id"]))
                return {
                    "player": {
                        "name": player["name"],
                        "team": player["team"],
                        "position": player["position"]
                    },
                    "fixtures": player_fixtures
                }
            elif uri == "fpl://gameweeks/blank":
                return self.run_async(self.fpl_resources['fixtures'].get_blank_gameweeks())
            elif uri == "fpl://gameweeks/double":
                return self.run_async(self.fpl_resources['fixtures'].get_double_gameweeks())
            else:
                return {"error": f"Unknown resource URI: {uri}"}
        except Exception as e:
            logger.error(f"Error getting resource data for {uri}: {e}")
            raise
    
    def _execute_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute real tool from FPL MCP server"""
        logger.info(f"Executing tool: {name} with args: {arguments}")
        
        try:
            # Import the specific tool functions we need
            from src.fpl_mcp.__main__ import (
                compare_players, analyze_player_fixtures, get_gameweek_status,
                analyze_players, analyze_fixtures, get_blank_gameweeks, get_double_gameweeks
            )
            
            if name == "compare_players":
                return self.run_async(compare_players(
                    player_names=arguments.get("player_names", []),
                    metrics=arguments.get("metrics", ["total_points", "form", "goals_scored", "assists", "bonus"]),
                    include_gameweeks=arguments.get("include_gameweeks", False),
                    num_gameweeks=arguments.get("num_gameweeks", 5),
                    include_fixture_analysis=arguments.get("include_fixture_analysis", True)
                ))
            elif name == "analyze_player_fixtures":
                return self.run_async(analyze_player_fixtures(
                    player_name=arguments.get("player_name"),
                    num_fixtures=arguments.get("num_fixtures", 5)
                ))
            elif name == "get_gameweek_status":
                return self.run_async(get_gameweek_status())
            elif name == "analyze_players":
                return self.run_async(analyze_players(**arguments))
            elif name == "analyze_fixtures":
                return self.run_async(analyze_fixtures(**arguments))
            elif name == "get_blank_gameweeks":
                return self.run_async(get_blank_gameweeks(
                    num_gameweeks=arguments.get("num_gameweeks", 5)
                ))
            elif name == "get_double_gameweeks":
                return self.run_async(get_double_gameweeks(
                    num_gameweeks=arguments.get("num_gameweeks", 5)
                ))
            else:
                return {"error": f"Unknown tool: {name}"}
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}")
            raise
    
    def _error_response(self, request_id, code: int, message: str) -> Dict[str, Any]:
        """Create error response"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message}
        }
    
    def _send_error(self, status_code: int, message: str):
        """Send HTTP error"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        error = {
            "error": {"code": status_code, "message": message, "timestamp": time.time()}
        }
        self.wfile.write(json.dumps(error).encode())
    
    def _handle_404(self):
        """Handle 404"""
        self.send_response(404)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        response = {
            "error": {
                "code": 404,
                "message": "Not Found",
                "available_endpoints": ["GET /health", "GET /mcp", "POST /mcp"]
            }
        }
        self.wfile.write(json.dumps(response, indent=2).encode())
    
    def log_message(self, format, *args):
        """Use structured logging"""
        logger.info(format % args)

def main():
    """Main entry point"""
    port = int(os.environ.get("PORT", 8080))
    
    logger.info("Starting Working Fantasy Premier League MCP Server for Cloud Run")
    logger.info(f"Port: {port}")
    logger.info(f"Environment: {os.environ.get('ENVIRONMENT', 'production')}")
    
    try:
        server = HTTPServer(('0.0.0.0', port), WorkingMCPHandler)
        logger.info(f"Server started successfully on 0.0.0.0:{port}")
        logger.info("Available endpoints:")
        logger.info("  GET  /health - Health check")
        logger.info("  GET  /mcp - MCP server info")
        logger.info("  POST /mcp - MCP JSON-RPC requests")
        logger.info("Server is ready for MCP connections")
        
        server.serve_forever()
        
    except Exception as e:
        logger.error(f"Server startup failed: {e}")
        logger.exception("Full exception details:")
        sys.exit(1)

if __name__ == "__main__":
    main()