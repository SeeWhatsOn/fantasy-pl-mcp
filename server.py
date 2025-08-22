#!/usr/bin/env python3
"""
HTTP server entry point for Fantasy Premier League MCP server on Google Cloud Run.
"""

import asyncio
import os
import logging
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import threading
import time

# Set up logging for Cloud Run
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class HealthHandler(BaseHTTPRequestHandler):
    """Simple health check handler for Cloud Run"""
    
    def do_GET(self):
        if self.path == "/health" or self.path == "/":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "status": "healthy",
                "service": "Fantasy Premier League MCP Server",
                "timestamp": time.time()
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        # Handle MCP requests
        if self.path == "/mcp":
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                # For now, return a basic response
                response = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "status": "MCP server running",
                        "message": "Basic HTTP transport active"
                    }
                }
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                logger.error(f"Error handling MCP request: {e}")
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Use our logger instead of default
        logger.info(format % args)

def main():
    """Run a basic HTTP server for Cloud Run."""
    # Get port from environment variable (Cloud Run sets this)
    port = int(os.environ.get("PORT", 8080))
    
    # Log environment info
    environment = os.environ.get("ENVIRONMENT", "development")
    logger.info(f"Starting Fantasy Premier League MCP server")
    logger.info(f"Environment: {environment}")
    logger.info(f"Port: {port}")
    
    # Check for credentials (optional for public endpoints)
    has_fpl_creds = bool(
        os.environ.get("FPL_EMAIL") and 
        os.environ.get("FPL_PASSWORD") and 
        os.environ.get("FPL_TEAM_ID")
    )
    logger.info(f"FPL credentials available: {has_fpl_creds}")
    
    try:
        # Try to import the MCP server (but don't start it yet)
        from src.fpl_mcp.__main__ import mcp
        logger.info("MCP server imported successfully")
        
        # Start simple HTTP server for Cloud Run health checks
        server = HTTPServer(('0.0.0.0', port), HealthHandler)
        logger.info(f"HTTP server started on 0.0.0.0:{port}")
        logger.info("Server is ready to accept connections")
        
        # Keep the server running
        server.serve_forever()
        
    except ImportError as e:
        logger.error(f"Failed to import MCP server: {e}")
        logger.error("Starting basic health server anyway...")
        
        # Start basic server even without MCP
        server = HTTPServer(('0.0.0.0', port), HealthHandler)
        logger.info(f"Basic HTTP server started on 0.0.0.0:{port}")
        server.serve_forever()
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        logger.exception("Server startup failed")
        sys.exit(1)

if __name__ == "__main__":
    main()