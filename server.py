#!/usr/bin/env python3
"""
HTTP server entry point for Fantasy Premier League MCP server on Google Cloud Run.
"""

import os
import logging
import sys

# Set up logging for Cloud Run
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def main():
    """Run the MCP server for Cloud Run."""
    # Get port from environment variable (Cloud Run sets this)
    port = int(os.environ.get("PORT", 8080))
    
    # Set the port for the MCP server to use
    os.environ["PORT"] = str(port)
    
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
        # Import and run the main MCP server
        from src.fpl_mcp.__main__ import main as mcp_main
        
        logger.info("MCP server imported successfully")
        logger.info(f"Starting server on port {port}")
        
        # Run the MCP server main function
        mcp_main()
        
    except ImportError as e:
        logger.error(f"Failed to import MCP server: {e}")
        logger.error("Make sure the src/fpl_mcp package is properly installed")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        logger.exception("Server startup failed")
        sys.exit(1)

if __name__ == "__main__":
    main()