#!/usr/bin/env python3
"""
HTTP server entry point for Fantasy Premier League MCP server on Google Cloud Run.
"""

import os
import logging
import sys
from mcp.server.fastmcp import FastMCP
from mcp.server import serve

# Set up logging for Cloud Run
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def main():
    """Run the MCP server with HTTP transport for Cloud Run."""
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
        # Import the main MCP server
        from src.fpl_mcp.__main__ import mcp
        
        logger.info("MCP server imported successfully")
        
        # Serve using HTTP transport
        serve(
            mcp,
            transport_type="http",
            host="0.0.0.0",
            port=port
        )
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise

if __name__ == "__main__":
    main()