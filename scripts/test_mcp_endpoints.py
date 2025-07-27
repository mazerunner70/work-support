#!/usr/bin/env python3
"""
Test script for MCP endpoints in work-support API.

Tests all MCP endpoints to ensure they're working correctly and returning
properly formatted responses for MCP clients.
"""
import asyncio
import httpx
import json
from typing import Dict, Any


class MCPEndpointTester:
    """Test MCP endpoints with various scenarios."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=30.0)
    
    async def test_endpoint(self, method: str, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Test a single endpoint and return results."""
        try:
            if method.upper() == "GET":
                response = await self.client.get(endpoint, params=params)
            elif method.upper() == "POST":
                response = await self.client.post(endpoint, params=params)
            else:
                return {"error": f"Unsupported method: {method}"}
            
            return {
                "endpoint": endpoint,
                "method": method,
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "response_size": len(response.content),
                "content_type": response.headers.get("content-type", "unknown"),
                "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text[:500]
            }
        except Exception as e:
            return {
                "endpoint": endpoint,
                "method": method,
                "success": False,
                "error": str(e)
            }
    
    async def test_all_endpoints(self):
        """Test all MCP endpoints with various parameters."""
        print("🚀 Testing MCP Endpoints for Work-Support API")
        print("=" * 60)
        
        test_cases = [
            # Basic connectivity test
            {
                "name": "System Connectivity",
                "method": "GET",
                "endpoint": "/api/mcp/system/connectivity",
                "description": "Test system health and connectivity"
            },
            
            # Issues endpoint tests
            {
                "name": "Query All Issues (No Filters)",
                "method": "GET", 
                "endpoint": "/api/mcp/issues",
                "params": {"limit": 10},
                "description": "Query issues without filters, limited to 10 results"
            },
            {
                "name": "Query Issues by Team",
                "method": "GET",
                "endpoint": "/api/mcp/issues",
                "params": {"team": "Backend Team", "limit": 5},
                "description": "Query issues filtered by team"
            },
            {
                "name": "Query Issues by Status",
                "method": "GET",
                "endpoint": "/api/mcp/issues",
                "params": {"status": "In Progress", "limit": 5},
                "description": "Query issues filtered by status"
            },
            {
                "name": "Query Issues by Source",
                "method": "GET",
                "endpoint": "/api/mcp/issues",
                "params": {"source": "jira", "limit": 5},
                "description": "Query issues filtered by source"
            },
            
            # Issue details test (will need an actual issue key)
            {
                "name": "Get Issue Details (Test Key)",
                "method": "GET",
                "endpoint": "/api/mcp/issues/TEST-123",
                "params": {"include_comments": True, "include_changelog": True},
                "description": "Get detailed information for a specific issue"
            },
            
            # Team metrics tests
            {
                "name": "Team Metrics (Backend Team)",
                "method": "GET",
                "endpoint": "/api/mcp/team/Backend Team/metrics",
                "description": "Get metrics for Backend Team"
            },
            {
                "name": "Team Metrics (Non-existent Team)",
                "method": "GET",
                "endpoint": "/api/mcp/team/NonExistentTeam/metrics",
                "description": "Test metrics for a team that doesn't exist"
            },
            
            # Harvest endpoint tests
            {
                "name": "Trigger Harvest (Dry Run)",
                "method": "POST",
                "endpoint": "/api/mcp/harvest/trigger",
                "params": {"harvest_type": "incremental", "dry_run": True},
                "description": "Test harvest trigger with dry run"
            },
            
            # Error handling tests
            {
                "name": "Invalid Source Filter",
                "method": "GET",
                "endpoint": "/api/mcp/issues",
                "params": {"source": "invalid_source"},
                "description": "Test error handling for invalid source filter"
            },
            {
                "name": "Invalid Harvest Type",
                "method": "POST",
                "endpoint": "/api/mcp/harvest/trigger",
                "params": {"harvest_type": "invalid_type", "dry_run": True},
                "description": "Test error handling for invalid harvest type"
            }
        ]
        
        results = []
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{i:2d}. {test_case['name']}")
            print(f"    {test_case['description']}")
            print(f"    {test_case['method']} {test_case['endpoint']}")
            
            if test_case.get('params'):
                print(f"    Params: {test_case['params']}")
            
            result = await self.test_endpoint(
                test_case['method'],
                test_case['endpoint'],
                test_case.get('params')
            )
            results.append({**test_case, **result})
            
            if result['success']:
                print(f"    ✅ SUCCESS - Status: {result['status_code']}, Size: {result['response_size']} bytes")
                
                # Print sample of response for successful calls
                if isinstance(result.get('response'), dict):
                    if 'issues' in result['response']:
                        issue_count = len(result['response']['issues'])
                        print(f"    📊 Found {issue_count} issues")
                    elif 'team' in result['response']:
                        metrics = result['response'].get('metrics', {})
                        total = metrics.get('total_issues', 0)
                        print(f"    📊 Team has {total} total issues")
                    elif 'status' in result['response']:
                        status = result['response']['status']
                        print(f"    📊 System status: {status}")
            else:
                print(f"    ❌ FAILED - {result.get('error', 'Unknown error')}")
                if 'status_code' in result:
                    print(f"    Status: {result['status_code']}")
        
        # Summary
        print("\n" + "=" * 60)
        print("📋 TEST SUMMARY")
        print("=" * 60)
        
        successful = sum(1 for r in results if r['success'])
        total = len(results)
        
        print(f"Total Tests: {total}")
        print(f"Successful: {successful}")
        print(f"Failed: {total - successful}")
        print(f"Success Rate: {(successful/total)*100:.1f}%")
        
        if successful < total:
            print("\n❌ FAILED TESTS:")
            for result in results:
                if not result['success']:
                    print(f"  - {result['name']}: {result.get('error', 'Unknown error')}")
        
        return results
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


async def main():
    """Run MCP endpoint tests."""
    tester = MCPEndpointTester()
    
    try:
        results = await tester.test_all_endpoints()
        
        # Save detailed results to file
        with open("mcp_test_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Detailed results saved to: mcp_test_results.json")
        
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
    finally:
        await tester.close()


if __name__ == "__main__":
    print("MCP Endpoint Testing Script")
    print("Make sure your work-support server is running on http://localhost:8000")
    print()
    
    asyncio.run(main()) 