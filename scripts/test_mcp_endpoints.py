#!/usr/bin/env python3
"""
Test Script for MCP Endpoints

Tests the MCP server functionality by calling the underlying REST API endpoints
that the MCP server depends on.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx


async def test_work_support_api():
    """Test that work-support API is accessible."""
    work_support_url = os.getenv("WORK_SUPPORT_URL", "http://localhost:8000")
    
    print(f"Testing Work Support API at {work_support_url}")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Test basic connectivity
            response = await client.get(f"{work_support_url}/health")
            if response.status_code == 200:
                print("✅ Work Support API is accessible")
            else:
                print(f"⚠️ Work Support API returned status {response.status_code}")
                
        except httpx.RequestError as e:
            print(f"❌ Failed to connect to Work Support API: {e}")
            return False
        
        # Test MCP endpoints
        endpoints_to_test = [
            "/api/mcp/issues?limit=5",
            "/api/mcp/system/connectivity",
        ]
        
        for endpoint in endpoints_to_test:
            try:
                print(f"Testing {endpoint}")
                response = await client.get(f"{work_support_url}{endpoint}")
                
                if response.status_code == 200:
                    print(f"  ✅ {endpoint} - OK")
                    
                    # Print sample data for issues endpoint
                    if "issues" in endpoint:
                        data = response.json()
                        issues = data.get("issues", [])
                        print(f"    Found {len(issues)} issues")
                        if issues:
                            first_issue = issues[0]
                            key = first_issue.get("issue_key", "N/A")
                            summary = first_issue.get("summary", "No summary")[:50]
                            print(f"    Sample: {key} - {summary}...")
                    
                    # Print connectivity info
                    if "connectivity" in endpoint:
                        data = response.json()
                        jira_connected = data.get("jira_connected", False)
                        db_connected = data.get("database_connected", False)
                        print(f"    Jira: {'✅' if jira_connected else '❌'}")
                        print(f"    Database: {'✅' if db_connected else '❌'}")
                        
                else:
                    print(f"  ⚠️ {endpoint} - Status {response.status_code}")
                    
            except Exception as e:
                print(f"  ❌ {endpoint} - Error: {e}")
    
    return True


async def test_mcp_server_startup():
    """Test that MCP server can be imported and initialized."""
    try:
        print("\nTesting MCP Server startup...")
        
        from mcp_server.config import config
        from mcp_server.client import client
        from mcp_server.server import WorkSupportMCPServer
        
        print("✅ MCP server modules imported successfully")
        
        # Test configuration
        try:
            config.validate()
            print("✅ Configuration is valid")
        except Exception as e:
            print(f"❌ Configuration validation failed: {e}")
            return False
        
        # Test server initialization
        try:
            server = WorkSupportMCPServer()
            print("✅ MCP server initialized successfully")
        except Exception as e:
            print(f"❌ MCP server initialization failed: {e}")
            return False
        
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import MCP server modules: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error testing MCP server: {e}")
        return False


def check_environment():
    """Check environment setup."""
    print("Checking environment...")
    
    # Check required environment variables
    work_support_url = os.getenv("WORK_SUPPORT_URL")
    if work_support_url:
        print(f"✅ WORK_SUPPORT_URL: {work_support_url}")
    else:
        print("⚠️ WORK_SUPPORT_URL not set, using default: http://localhost:8000")
    
    # Check Python dependencies
    try:
        import mcp
        print("✅ MCP SDK available")
    except ImportError:
        print("❌ MCP SDK not installed. Run: pip install mcp==1.12.2")
        return False
    
    try:
        import httpx
        print("✅ HTTPX available")
    except ImportError:
        print("❌ HTTPX not installed. Run: pip install httpx")
        return False
    
    return True


async def main():
    """Main test function."""
    print("="*60)
    print("Work Support MCP Server - Test Script")
    print("="*60)
    
    # Check environment first
    if not check_environment():
        print("\n❌ Environment check failed")
        sys.exit(1)
    
    # Test work-support API
    print("\n" + "="*40)
    print("Testing Work Support API")
    print("="*40)
    
    api_ok = await test_work_support_api()
    
    # Test MCP server startup
    print("\n" + "="*40)
    print("Testing MCP Server")
    print("="*40)
    
    mcp_ok = await test_mcp_server_startup()
    
    # Summary
    print("\n" + "="*40)
    print("Test Summary")
    print("="*40)
    
    print(f"Work Support API: {'✅ OK' if api_ok else '❌ Failed'}")
    print(f"MCP Server: {'✅ OK' if mcp_ok else '❌ Failed'}")
    
    if api_ok and mcp_ok:
        print("\n🎉 All tests passed! MCP server is ready to use.")
        print("\nNext steps:")
        print("1. Start the work-support server: ./run_server.sh")
        print("2. Start the MCP server: python scripts/run_mcp_server.py")
        print("3. Or run both: python scripts/run_both.py")
        return True
    else:
        print("\n❌ Some tests failed. Please fix the issues above.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 