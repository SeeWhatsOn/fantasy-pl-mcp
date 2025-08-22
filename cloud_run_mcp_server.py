#!/usr/bin/env python3
"""
Cloud Run MCP server that works with the existing FastMCP setup.
Uses a simple approach to run the existing server.
"""

import logging
import os
import sys

# Set up logging for Cloud Run
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point for Cloud Run MCP server"""
    try:
        # Get port from Cloud Run environment and set it
        port = int(os.environ.get("PORT", 8080))
        
        logger.info("Starting Fantasy Premier League MCP Server for Cloud Run")
        logger.info(f"Port: {port}")
        logger.info(f"Environment: {os.environ.get('ENVIRONMENT', 'production')}")
        
        # Check for FPL credentials (optional)
        has_creds = bool(
            os.environ.get("FPL_EMAIL") and 
            os.environ.get("FPL_PASSWORD") and 
            os.environ.get("FPL_TEAM_ID")
        )
        logger.info(f"FPL credentials configured: {has_creds}")
        
        # Set environment variables for FastMCP HTTP mode
        os.environ["MCP_HTTP_PORT"] = str(port)
        os.environ["MCP_HTTP_HOST"] = "0.0.0.0"
        
        logger.info(f"Starting MCP server on 0.0.0.0:{port}")
        
        # Import and run the existing main function
        from src.fpl_mcp.__main__ import main as fpl_main
        fpl_main()
        
    except ImportError as e:
        logger.error(f"MCP import failed: {e}")
        logger.exception("Import error details:")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Server startup failed: {e}")
        logger.exception("Full exception details:")
        sys.exit(1)

if __name__ == "__main__":
    main()