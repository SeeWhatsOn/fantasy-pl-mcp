#!/usr/bin/env python3
"""
Test script for Fantasy Premier League MCP server.
Can be used locally or to test the Cloud Run deployment.
"""

import asyncio
import httpx
import json
import logging
import sys
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_mcp_server(base_url: str = "http://localhost:8080"):
    """Test the MCP server endpoints"""
    
    logger.info(f"Testing MCP server at {base_url}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Test 1: Basic health check (if available)
            logger.info("Test 1: Health check")
            try:
                response = await client.get(f"{base_url}/health")
                if response.status_code == 200:
                    logger.info("✅ Health check passed")
                else:
                    logger.info("⚠️  Health endpoint not available (this is normal for MCP servers)")
            except httpx.RequestError:
                logger.info("⚠️  Health endpoint not available (this is normal for MCP servers)")
            
            # Test 2: MCP Initialize
            logger.info("Test 2: MCP Initialize")
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "roots": {
                            "listChanged": True
                        },
                        "sampling": {}
                    },
                    "clientInfo": {
                        "name": "test-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            response = await client.post(
                f"{base_url}/mcp",
                json=init_request,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info("✅ MCP Initialize successful")
                logger.info(f"Server info: {result.get('result', {}).get('serverInfo', 'N/A')}")
            else:
                logger.error(f"❌ MCP Initialize failed: {response.status_code} - {response.text}")
                return False
            
            # Test 3: List Resources
            logger.info("Test 3: List Resources")
            resources_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/list"
            }
            
            response = await client.post(
                f"{base_url}/mcp",
                json=resources_request,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                resources = result.get('result', {}).get('resources', [])
                logger.info(f"✅ Found {len(resources)} resources")
                for resource in resources[:3]:  # Show first 3 resources
                    logger.info(f"  - {resource.get('uri', 'N/A')}: {resource.get('description', 'N/A')}")
            else:
                logger.error(f"❌ List Resources failed: {response.status_code} - {response.text}")
                return False
            
            # Test 4: List Tools
            logger.info("Test 4: List Tools")
            tools_request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/list"
            }
            
            response = await client.post(
                f"{base_url}/mcp",
                json=tools_request,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                tools = result.get('result', {}).get('tools', [])
                logger.info(f"✅ Found {len(tools)} tools")
                for tool in tools[:3]:  # Show first 3 tools
                    logger.info(f"  - {tool.get('name', 'N/A')}: {tool.get('description', 'N/A')}")
            else:
                logger.error(f"❌ List Tools failed: {response.status_code} - {response.text}")
                return False
            
            # Test 5: Get a resource
            logger.info("Test 5: Get Teams Resource")
            teams_resource_request = {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "resources/read",
                "params": {
                    "uri": "fpl://static/teams"
                }
            }
            
            response = await client.post(
                f"{base_url}/mcp",
                json=teams_resource_request,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                contents = result.get('result', {}).get('contents', [])
                if contents:
                    teams_data = json.loads(contents[0].get('text', '[]'))
                    logger.info(f"✅ Retrieved {len(teams_data)} teams")
                    if teams_data:
                        logger.info(f"  Sample team: {teams_data[0].get('name', 'N/A')}")
                else:
                    logger.warning("⚠️  Teams resource returned no content")
            else:
                logger.error(f"❌ Get Teams Resource failed: {response.status_code} - {response.text}")
                return False
            
            logger.info("✅ All tests passed! MCP server is working correctly.")
            return True
            
        except httpx.RequestError as e:
            logger.error(f"❌ Request error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return False

async def main():
    """Main test function"""
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:8080"
    
    logger.info("Fantasy Premier League MCP Server Test")
    logger.info("=" * 50)
    
    success = await test_mcp_server(base_url)
    
    if success:
        logger.info("🎉 All tests passed!")
        sys.exit(0)
    else:
        logger.error("💥 Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())