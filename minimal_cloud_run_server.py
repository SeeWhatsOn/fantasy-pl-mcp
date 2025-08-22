#!/usr/bin/env python3
"""
Minimal working Cloud Run server for FPL MCP.
Just focuses on getting the container to start and respond to health checks.
"""

import json
import logging
import os
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class MinimalHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for Cloud Run"""
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path in ["/", "/health"]:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {
                "status": "healthy",
                "service": "Fantasy Premier League MCP Server",
                "version": "0.1.6",
                "timestamp": time.time(),
                "port": os.environ.get("PORT", "8080"),
                "message": "Server is running successfully"
            }
            
            self.wfile.write(json.dumps(response, indent=2).encode())
        
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())
    
    def do_POST(self):
        """Handle POST requests"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        response = {
            "message": "POST endpoint available",
            "path": self.path,
            "timestamp": time.time()
        }
        
        self.wfile.write(json.dumps(response).encode())
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        """Use structured logging"""
        logger.info(format % args)

def main():
    """Main entry point"""
    port = int(os.environ.get("PORT", 8080))
    
    logger.info("Starting Minimal Fantasy Premier League MCP Server")
    logger.info(f"Port: {port}")
    logger.info(f"Environment: {os.environ.get('ENVIRONMENT', 'production')}")
    
    try:
        server = HTTPServer(('0.0.0.0', port), MinimalHandler)
        logger.info(f"Server started successfully on 0.0.0.0:{port}")
        logger.info("Server is ready to handle requests")
        
        # Run the server
        server.serve_forever()
        
    except Exception as e:
        logger.error(f"Server startup failed: {e}")
        logger.exception("Full exception details:")
        sys.exit(1)

if __name__ == "__main__":
    main()