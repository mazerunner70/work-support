# MCP Server Plan: Work Support Data Server

## Overview

This document outlines a two-tier architecture for exposing work support data via MCP (Model Context Protocol). The design separates concerns between a robust work-support REST API server (always running in the background) and a lightweight MCP protocol server that acts as an adapter layer for AI agents.

## Architecture Decision: REST API + MCP Server

We use a **REST API + Lightweight MCP Server** architecture for optimal separation of concerns, scalability, and maintainability:

```
┌─────────────────┐    HTTP/REST    ┌──────────────────────┐
│   MCP Server    │ ◄─────────────► │  Work-Support Server │
│  (Lightweight)  │                 │    (REST API)        │
│   Port 8001     │                 │    Port 8000         │
└─────────────────┘                 └──────────────────────┘
         ▲                                       │
         │ MCP Protocol                          │ Direct DB Access
         ▼                                       │ Jira Integration
┌─────────────────┐                             │ Background Jobs
│   AI Clients    │                             ▼
│ (Claude, etc.)  │                 ┌──────────────────────┐
└─────────────────┘                 │     Database         │
                                    │   (SQLite/Postgres)  │
                                    └──────────────────────┘
```

### Benefits of This Architecture

1. **Always-Running Background Service**: Work-support server handles harvest jobs, data sync, and business logic continuously
2. **Separation of Concerns**: MCP server focuses only on protocol translation, REST API handles all business logic
3. **Multiple Client Support**: Same REST API can serve MCP clients, web dashboards, mobile apps, other integrations
4. **Independent Scaling**: Scale and deploy each service based on different resource needs
5. **Development Efficiency**: Test business logic independently with standard HTTP tools

## Data Architecture

### Core Data Models
- **Issues**: Jira issues with hierarchical relationships, status tracking, and team assignments
- **Team Members**: Team member profiles with Jira/GitHub ID mappings
- **Comments**: Issue comments and discussions
- **Changelogs**: Historical change tracking for all issue modifications
- **Harvest Jobs**: Data synchronization job tracking
- **Issue Types**: Hierarchical issue type definitions

### Key Capabilities
- Hierarchical issue harvesting from Jira
- Team member-specific issue queries
- Real-time connectivity testing
- Comprehensive change tracking and audit trails
- Bulk data processing with error handling

## Implementation Architecture

### 1. Work-Support REST API (Port 8000)

The main work-support server provides REST endpoints optimized for MCP consumption. These endpoints extend the existing FastAPI application:

#### MCP-Optimized REST Endpoints

```python
# Add to existing app/api/routes.py

@router.get("/api/mcp/issues", tags=["mcp"])
async def mcp_query_issues(
    assignee: Optional[str] = None,
    status: Optional[str] = None, 
    team: Optional[str] = None,
    issue_type: Optional[str] = None,
    parent_key: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """MCP-optimized issue querying with flexible filters"""
    return await issue_service.query_issues_for_mcp(...)

@router.get("/api/mcp/issues/{issue_key}", tags=["mcp"])
async def mcp_get_issue_details(
    issue_key: str,
    include_comments: bool = True,
    include_changelog: bool = True,
    include_children: bool = False,
    db: Session = Depends(get_db)
):
    """Get comprehensive issue details for MCP"""
    return await issue_service.get_issue_details_for_mcp(...)

@router.get("/api/mcp/team/{team_name}/metrics", tags=["mcp"])
async def mcp_team_metrics(
    team_name: str,
    date_range: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Team performance metrics for MCP"""
    return await analytics_service.get_team_metrics_for_mcp(...)

@router.post("/api/mcp/harvest/trigger", tags=["mcp"])
async def mcp_trigger_harvest(
    harvest_type: str = "incremental",
    dry_run: bool = False
):
    """Trigger harvest job via MCP"""
    return await harvest_service.trigger_harvest_for_mcp(...)

@router.get("/api/mcp/system/connectivity", tags=["mcp"])
async def mcp_test_connectivity():
    """Test system connectivity for MCP"""
    return await system_service.test_connectivity_for_mcp()
```

### 2. MCP Server (Port 8001)

Lightweight MCP protocol server that translates MCP calls to REST API calls:

#### MCP Server Resources

#### Issue Resources
```typescript
// Individual issue data
jira://issues/{issue_key}
// Example: jira://issues/IAIPORT-123

// Issue collections by various filters
jira://issues/team/{team_name}
jira://issues/assignee/{assignee}
jira://issues/status/{status}
jira://issues/type/{issue_type}
jira://issues/parent/{parent_key}
```

#### Team Resources
```typescript
// Team member information
team://members/{member_name}
team://members/all

// Team-specific data aggregations
team://stats/{team_name}
team://workload/{team_name}
```

#### Analytics Resources
```typescript
// Change tracking and audit trails
analytics://changes/{issue_key}
analytics://activity/{date_range}
analytics://trends/status
analytics://trends/team-velocity

// System health and harvest status
system://harvest-jobs
system://connectivity
system://data-freshness
```

### 3. MCP Server Tools

The MCP server implements tools that call the work-support REST API:

#### Data Query Tools

##### `query_issues`
Query issues with flexible filtering options via REST API.
```python
# MCP Server Implementation
@server.call_tool()
async def query_issues(arguments: dict) -> types.TextContent:
    """Query issues through work-support REST API"""
    params = {k: v for k, v in arguments.items() if v is not None}
    response = await http_client.get("/api/mcp/issues", params=params)
    return types.TextContent(text=json.dumps(response.json()))
```

```json
{
  "name": "query_issues",
  "parameters": {
    "assignee": "optional string",
    "status": "optional string", 
    "team": "optional string",
    "issue_type": "optional string",
    "parent_key": "optional string",
    "limit": "optional integer (default 50, max 500)"
  }
}
```

##### `get_issue_details`
Get comprehensive details for a specific issue.
```json
{
  "name": "get_issue_details", 
  "parameters": {
    "issue_key": "required string",
    "include_comments": "optional boolean (default true)",
    "include_changelog": "optional boolean (default true)",
    "include_children": "optional boolean (default false)"
  }
}
```

##### `search_issues`
Full-text search across issue summaries and comments.
```json
{
  "name": "search_issues",
  "parameters": {
    "query": "required string",
    "fields": "optional array (summary, comments, both)",
    "limit": "optional integer (default 25)"
  }
}
```

#### Team Analysis Tools

##### `get_team_metrics`
Get team performance metrics and workload analysis.
```json
{
  "name": "get_team_metrics",
  "parameters": {
    "team_name": "optional string (all teams if omitted)",
    "date_range": "optional object with start/end",
    "metrics": "optional array (workload, velocity, completion_rate)"
  }
}
```

##### `analyze_assignee_workload`
Analyze individual assignee workload and patterns.
```json
{
  "name": "analyze_assignee_workload",
  "parameters": {
    "assignee": "required string",
    "include_historical": "optional boolean (default false)",
    "time_period": "optional string (week, month, quarter)"
  }
}
```

#### Trend Analysis Tools

##### `get_status_trends`
Analyze issue status transition patterns over time.
```json
{
  "name": "get_status_trends",
  "parameters": {
    "date_range": "required object with start/end",
    "group_by": "optional string (team, assignee, issue_type)",
    "status_transitions": "optional array of specific transitions"
  }
}
```

##### `analyze_cycle_time`
Calculate and analyze issue cycle times and bottlenecks.
```json
{
  "name": "analyze_cycle_time",
  "parameters": {
    "filters": "optional object (same as query_issues)",
    "breakdown_by": "optional string (team, assignee, issue_type)",
    "percentiles": "optional array (default [50, 75, 90, 95])"
  }
}
```

#### System Administration Tools

##### `test_connectivity`
Test Jira connectivity and system health.
```json
{
  "name": "test_connectivity",
  "parameters": {
    "include_details": "optional boolean (default false)"
  }
}
```

##### `trigger_harvest`
Initiate a data harvest from Jira (admin only).
```json
{
  "name": "trigger_harvest",
  "parameters": {
    "harvest_type": "optional string (full, incremental, team_only)",
    "dry_run": "optional boolean (default false)"
  }
}
```

##### `get_harvest_status`
Check status of recent harvest jobs.
```json
{
  "name": "get_harvest_status",
  "parameters": {
    "limit": "optional integer (default 10)",
    "include_failed": "optional boolean (default true)"
  }
}
```

#### Change Tracking Tools

##### `get_issue_history`
Get complete change history for an issue.
```json
{
  "name": "get_issue_history",
  "parameters": {
    "issue_key": "required string",
    "include_comments": "optional boolean (default true)",
    "date_range": "optional object with start/end"
  }
}
```

##### `analyze_change_patterns`
Analyze patterns in issue changes and updates.
```json
{
  "name": "analyze_change_patterns",
  "parameters": {
    "field": "optional string (status, assignee, etc.)",
    "date_range": "required object with start/end",
    "group_by": "optional string (team, assignee, issue_type)"
  }
}
```

### 3. Data Response Formats

#### Issue Response Format
```json
{
  "issue_key": "IAIPORT-123",
  "summary": "Implement user authentication",
  "assignee": "john.doe",
  "status": "In Progress", 
  "team": "Backend Team",
  "issue_type": "Story",
  "labels": ["authentication", "security"],
  "parent_key": "IAIPORT-100",
  "dates": {
    "created_at": "2024-01-15T10:00:00Z",
    "updated_at": "2024-01-20T15:30:00Z",
    "start_date": "2024-01-16T09:00:00Z",
    "transition_date": "2024-01-18T14:00:00Z",
    "end_date": null
  },
  "comments_count": 5,
  "changelog_count": 12,
  "children": ["IAIPORT-124", "IAIPORT-125"]
}
```

#### Metrics Response Format
```json
{
  "team": "Backend Team",
  "period": "2024-01-01 to 2024-01-31",
  "metrics": {
    "total_issues": 45,
    "completed_issues": 38,
    "completion_rate": 0.844,
    "average_cycle_time_days": 8.5,
    "active_issues": 7,
    "team_members": ["john.doe", "jane.smith", "bob.wilson"]
  },
  "status_breakdown": {
    "To Do": 3,
    "In Progress": 4, 
    "Done": 38
  }
}
```

### 4. Security and Access Control

#### Authentication
- API key-based authentication for external access
- Role-based permissions (read-only, admin)
- Rate limiting for resource-intensive operations

#### Data Privacy
- Sanitize sensitive information in responses
- Configurable field filtering
- Audit logging for all data access

### 5. Project Structure

#### Two-Service Architecture
```
work-support/
├── app/                           # Existing work-support REST API server
│   ├── api/
│   │   ├── routes.py              # Add MCP endpoints here
│   │   └── mcp_routes.py          # New MCP-specific routes
│   ├── services/
│   │   ├── mcp_adapters.py        # MCP response formatting
│   │   └── ...                    # Existing services
│   ├── models/                    # Existing database models  
│   └── ...                        # Existing structure
├── mcp_server/                    # New lightweight MCP server
│   ├── __init__.py
│   ├── server.py                  # Main MCP protocol server
│   ├── tools/                     # MCP tool implementations
│   │   ├── __init__.py
│   │   ├── query_tools.py         # Issue querying tools
│   │   ├── team_tools.py          # Team analytics tools
│   │   ├── admin_tools.py         # System administration tools
│   │   └── analysis_tools.py      # Trend analysis tools
│   ├── client.py                  # HTTP client for REST API calls
│   ├── config.py                  # MCP server configuration
│   └── utils.py                   # Response formatting utilities
├── scripts/
│   ├── run_work_support.py        # Start work-support server (port 8000)
│   ├── run_mcp_server.py          # Start MCP server (port 8001)
│   └── run_both.py                # Start both services
├── requirements-mcp.txt           # MCP server dependencies
└── ...                            # Existing files
```

#### Implementation Strategy

##### Phase 1: Extend REST API
1. Add MCP-optimized endpoints to existing FastAPI app
2. Create MCP response formatting utilities
3. Test endpoints with standard HTTP tools

##### Phase 2: Build MCP Server
4. Create lightweight MCP protocol server
5. Implement HTTP client to call REST API
6. Map MCP tools to REST endpoints

##### Phase 3: Integration & Deployment
7. Set up MCP server packaging and installation
8. Configure service communication and health checks
9. Add monitoring and logging integration

#### Service Communication
- **HTTP Client**: MCP server uses httpx async client for REST API calls
- **Service Discovery**: MCP server configured with work-support URL
- **Error Handling**: MCP server gracefully handles REST API failures
- **Authentication**: Pass-through authentication from MCP to REST API

#### MCP Server Configuration

##### Development Setup
```bash
# Terminal 1: Start work-support server
python scripts/run_work_support.py

# Terminal 2: Start MCP server  
python scripts/run_mcp_server.py

# Or run both:
python scripts/run_both.py
```

##### MCP Client Configuration

Add this to your MCP client configuration (e.g., Claude Desktop, VS Code, etc.):

```json
{
  "mcpServers": {
    "work-support": {
      "command": "python",
      "args": ["/path/to/work-support/mcp_server/server.py"],
      "env": {
        "WORK_SUPPORT_URL": "http://localhost:8000"
      }
    }
  }
}
```

##### Alternative: Use with uvx (Recommended)
```json
{
  "mcpServers": {
    "work-support": {
      "command": "uvx",
      "args": ["--from", "/path/to/work-support", "mcp-work-support"],
      "env": {
        "WORK_SUPPORT_URL": "http://localhost:8000"
      }
    }
  }
}
```

##### Environment Variables
```bash
# Required
WORK_SUPPORT_URL=http://localhost:8000

# Optional  
WORK_SUPPORT_API_KEY=your_api_key_if_required
MCP_LOG_LEVEL=INFO
```

### 6. Ready-to-Use MCP Configuration

#### Copy-Paste Configuration for Claude Desktop

```json
{
  "mcpServers": {
    "work-support": {
      "command": "python",
      "args": ["/path/to/your/work-support/mcp_server/server.py"],
      "env": {
        "WORK_SUPPORT_URL": "http://localhost:8000"
      }
    }
  }
}
```

**Setup Instructions:**
1. Replace `/path/to/your/work-support/` with your actual project path
2. Ensure work-support REST API is running on port 8000
3. Save this configuration to your MCP client config file

### 6.1. Additional MCP Configuration Templates

#### For Claude Desktop
```json
{
  "mcpServers": {
    "work-support": {
      "command": "python",
      "args": ["/Users/yourusername/path/to/work-support/mcp_server/server.py"],
      "env": {
        "WORK_SUPPORT_URL": "http://localhost:8000"
      }
    }
  }
}
```

#### For VS Code with MCP Extension
```json
{
  "mcp.servers": [
    {
      "name": "work-support",
      "command": "python",
      "args": ["/path/to/work-support/mcp_server/server.py"],
      "env": {
        "WORK_SUPPORT_URL": "http://localhost:8000"
      }
    }
  ]
}
```

#### For Remote Work-Support Server
```json
{
  "mcpServers": {
    "work-support": {
      "command": "python",
      "args": ["/path/to/work-support/mcp_server/server.py"],
      "env": {
        "WORK_SUPPORT_URL": "https://your-work-support-server.com",
        "WORK_SUPPORT_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

#### MCP Rules Integration

For AI agents to follow proper interaction patterns, include the MCP rules in your server documentation:

```python
# mcp_server/server.py - Add rules to server description
server = Server("work-support")
server.set_description("""
Work Support MCP Server - Provides access to Jira issue data and team metrics.

INTERACTION RULES:
- Use reasonable limits (10-50 for exploration)  
- Always provide context and interpret data
- Check system connectivity before troubleshooting
- Combine multiple tools for comprehensive analysis

See .mcp-rules file for complete interaction guidelines.
""")
```

#### Server Startup Script Example
```python
#!/usr/bin/env python3
# mcp_server/server.py

import asyncio
import os
from mcp import Server
from mcp.server.stdio import stdio_server

# Import your tool implementations
from tools.query_tools import QueryTools
from tools.team_tools import TeamTools
from tools.admin_tools import AdminTools

async def main():
    # Get work-support URL from environment
    work_support_url = os.getenv("WORK_SUPPORT_URL", "http://localhost:8000")
    
    # Initialize MCP server
    server = Server("work-support")
    
    # Initialize tool handlers
    query_tools = QueryTools(work_support_url)
    team_tools = TeamTools(work_support_url)
    admin_tools = AdminTools(work_support_url)
    
    # Register tools
    server.register_tool(query_tools.query_issues)
    server.register_tool(query_tools.get_issue_details)
    server.register_tool(team_tools.get_team_metrics)
    server.register_tool(admin_tools.test_connectivity)
    
    # Run server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)

if __name__ == "__main__":
    asyncio.run(main())
```

### 7. LLM Interaction Guidelines

#### MCP Tool Documentation for AI Agents

When documenting MCP tools for LLM consumption, each tool should include:

```json
{
  "name": "query_issues",
  "description": "Query Jira issues with flexible filtering options. Use this when the user wants to find, list, or search for issues based on various criteria like team, status, assignee, or issue type.",
  "usage_patterns": [
    "Finding issues by team: Set team parameter to team name",
    "Finding issues by status: Set status to 'In Progress', 'Done', 'To Do', etc.",
    "Finding someone's work: Set assignee to their name or email",
    "Limiting results: Always set reasonable limit (default 50, max 500)"
  ],
  "parameters": {
    "assignee": {
      "type": "string",
      "description": "Filter by assignee name or email address",
      "examples": ["john.doe", "jane.smith@company.com"]
    },
    "status": {
      "type": "string", 
      "description": "Filter by issue status",
      "examples": ["To Do", "In Progress", "Done", "Blocked"]
    },
    "team": {
      "type": "string",
      "description": "Filter by team name",
      "examples": ["Backend Team", "Frontend Team", "DevOps Team"]
    },
    "limit": {
      "type": "integer",
      "description": "Maximum results to return (1-500, default 50)",
      "default": 50,
      "range": [1, 500]
    }
  },
  "response_format": {
    "issues": "Array of issue objects with key, summary, status, assignee, etc.",
    "total_count": "Number of issues found",
    "timestamp": "When the query was executed"
  },
  "best_practices": [
    "Always use reasonable limits to avoid overwhelming responses",
    "Combine filters to narrow down results (e.g., team + status)",
    "Use exact team names as they appear in the system",
    "For large teams, consider filtering by status to get manageable results"
  ]
}
```

#### Common Query Patterns for LLMs

##### 1. **Team Workload Analysis**
```
User: "How is the Backend Team doing?"
LLM Should:
1. Call get_team_metrics with team="Backend Team"
2. Call query_issues with team="Backend Team" and status="In Progress"
3. Summarize metrics and current active work
```

##### 2. **Individual Workload Check** 
```
User: "What is john.doe working on?"
LLM Should:
1. Call query_issues with assignee="john.doe" and limit=20
2. Group by status to show current vs completed work
3. Highlight any blocked or overdue items
```

##### 3. **Issue Investigation**
```
User: "Tell me about issue PROJ-123"
LLM Should:
1. Call get_issue_details with issue_key="PROJ-123"
2. Include comments and changelog for full context
3. If it has children, include them for hierarchical view
```

##### 4. **System Health Check**
```
User: "Is the system healthy?"
LLM Should:
1. Call test_connectivity to check Jira and DB status
2. Interpret last_harvest timestamp to show data freshness
3. Provide clear status summary
```

#### Response Interpretation Guidelines

##### For Issue Lists:
- **Empty results**: Suggest alternative filters or broader search
- **Large results**: Summarize and offer to filter further
- **Status distribution**: Always highlight active vs completed work
- **Team insights**: Look for patterns in assignee distribution

##### For Team Metrics:
- **Completion rate**: Explain what constitutes "good" (>80% typically)
- **Active issues**: Flag if unusually high workload
- **Status breakdown**: Identify potential bottlenecks

##### For System Status:
- **Jira connectivity**: Essential for real-time data
- **Database health**: Required for all operations  
- **Last harvest**: Data freshness indicator (>24h may be stale)

### 8. Example Use Cases

#### Project Manager Queries
```
"Show me all high-priority issues assigned to the frontend team that are overdue"
→ LLM: query_issues(team="Frontend Team", status="In Progress", limit=100)
→ Filter by dates to identify overdue items

"What's the average cycle time for stories completed last month?"
→ LLM: get_team_metrics(team="All", date_range="2024-01-01,2024-01-31")
→ Focus on completion_rate and cycle time metrics

"Which team members have the highest workload right now?"
→ LLM: query_issues(status="In Progress", limit=200)
→ Group by assignee and count active issues
```

#### Developer Insights
```
"Show me the change history for issue IAIPORT-123"
→ LLM: get_issue_details(issue_key="IAIPORT-123", include_changelog=true)
→ Present changelog in chronological order

"What are the most common status transitions for bugs?" 
→ LLM: query_issues(issue_type="Bug", limit=500)
→ Then get_issue_details for each to analyze changelog patterns

"Find all issues related to authentication that I'm assigned to"
→ LLM: query_issues(assignee="current_user")
→ Filter results by summary/description containing "authentication"
```

#### Management Reporting
```
"Generate a velocity report for Q1 2024 by team"
→ LLM: get_team_metrics for each team with date_range="2024-01-01,2024-03-31"
→ Compare completion rates and total issues across teams

"What's the trend in issue completion rates over the last 6 months?"
→ LLM: Multiple get_team_metrics calls with monthly date ranges
→ Calculate trend analysis from completion_rate data

"Which issue types take the longest to complete on average?"
→ LLM: query_issues by different issue types
→ Analyze created_at vs completion dates for cycle time
```

#### Product Version Analysis
```
"What product versions have I commented on since last Monday week?"
→ LLM: query_issues(assignee="current_user", limit=200)
→ Filter by fix_version and check changelog for user comments since last Monday
→ Present unique product versions with comment activity

"Show me all the product versions active"
→ LLM: query_issues(status="In Progress,To Do,Review", limit=500)
→ Extract and deduplicate fix_version/affected_version fields
→ Present sorted list of active product versions with issue counts

"For product version pro-7653 give me a summary of all descendant issues and their comments and changelog entries since 25 Jul 2025"
→ LLM: query_issues(parent_key="pro-7653", include_children=true, limit=500)
→ get_issue_details for each descendant with include_comments=true, include_changelog=true
→ Filter comments and changelog entries by date >= "2025-07-25"
→ Present hierarchical summary with recent activity highlighted
```

### 9. MCP Interaction Rules for LLMs

#### Core Principles
1. **Always start with system connectivity check** when user asks about system status
2. **Use appropriate limits** - start with small limits (10-50) and increase if needed
3. **Combine multiple calls** for comprehensive analysis (e.g., metrics + issue details)
4. **Provide context** - explain what the data means, don't just return raw results
5. **Handle errors gracefully** - if a tool fails, explain why and suggest alternatives

#### Tool Usage Patterns

##### query_issues
- **Start broad, then narrow**: Begin with team/status filters, add more specific filters as needed
- **Reasonable limits**: Use 10-50 for exploratory queries, up to 200 for analysis
- **Combine filters**: team + status is more useful than team alone
- **Empty results**: Suggest checking team names or expanding search criteria

##### get_issue_details  
- **Include context**: Always set include_comments=true and include_changelog=true for investigations
- **Child issues**: Set include_children=true for epic/story hierarchies
- **Error handling**: If issue not found, suggest checking issue key format

##### get_team_metrics
- **Date ranges**: Use ISO format YYYY-MM-DD,YYYY-MM-DD
- **Team names**: Use exact names from the system ("Backend Team", not "backend")
- **Interpretation**: Always explain what good/bad metrics look like

##### test_connectivity
- **Regular checks**: Call this if user reports system issues
- **Data freshness**: Warn if last_harvest is >24 hours old
- **Service status**: Explain what each service status means

#### Response Formatting Guidelines

##### Issue Summaries
```
✅ Good: "Found 15 issues for Backend Team: 8 In Progress, 5 Done, 2 Blocked"
❌ Bad: Raw JSON dump of all 15 issues
```

##### Team Analysis  
```
✅ Good: "Backend Team: 85% completion rate (good), 12 active issues (normal workload)"
❌ Bad: "completion_rate: 0.85, active_issues: 12"
```

##### Status Reports
```
✅ Good: "System healthy: Jira connected ✅, Database connected ✅, Last harvest: 2 hours ago"
❌ Bad: "jira_connected: true, db_connected: true, last_harvest: 2024-01-15T..."
```

#### Error Handling
- **API errors**: Explain what went wrong and suggest solutions
- **Missing data**: Guide user to check spellings or try broader searches  
- **Connectivity issues**: Direct user to check system status first
- **Rate limits**: Suggest reducing query scope or waiting

### 10. Future Enhancements

#### Advanced Analytics
- Predictive analytics for cycle time estimation
- Team productivity scoring algorithms
- Automated bottleneck detection
- Burndown chart generation

#### Integration Expansion
- GitHub integration for code-related metrics
- Slack integration for notification handling
- Calendar integration for sprint planning
- Export capabilities for external reporting tools

#### AI-Powered Features
- Natural language query interpretation
- Automated issue categorization
- Smart assignee recommendations
- Anomaly detection in team patterns

## Implementation Priority

### Phase 1: REST API Extensions (Week 1-2)
1. Add MCP-optimized endpoints to existing FastAPI app
   - `/api/mcp/issues` - Issue querying with filters
   - `/api/mcp/issues/{issue_key}` - Issue details
   - `/api/mcp/team/{team_name}/metrics` - Team metrics
   - `/api/mcp/system/connectivity` - Health checks
2. Create MCP response formatting utilities
3. Test endpoints with curl/Postman to ensure compatibility

### Phase 2: MCP Server Implementation (Week 2-3)
4. Create lightweight MCP protocol server
   - Basic server setup with MCP SDK
   - HTTP client configuration for REST API calls
   - Core tool implementations (query_issues, get_issue_details)
5. Implement essential MCP tools mapping to REST endpoints
6. Add error handling and response formatting

### Phase 3: Advanced Tools & Features (Week 3-4)
7. Team analytics and metrics tools
8. System administration tools (harvest triggers, connectivity tests)
9. Search and trend analysis capabilities
10. Comprehensive testing and integration

### Phase 4: MCP Integration & Operations (Week 4+)
11. Package MCP server for easy installation and configuration
12. Create MCP client configuration templates
13. Add monitoring, logging, and health checks
14. Documentation and user guides for MCP setup

### Advantages of This Phased Approach

1. **Incremental Value**: REST API extensions provide immediate value for testing and other integrations
2. **Risk Mitigation**: Test business logic separately before adding MCP protocol complexity
3. **Parallel Development**: Can work on MCP server while REST API endpoints are being refined
4. **Easy Rollback**: If MCP server has issues, core work-support functionality remains unaffected
5. **Future-Proof**: Architecture supports adding web dashboards, mobile apps, or other clients later

This two-tier architecture provides comprehensive access to your work support data while maintaining security, performance, and ease of use for AI agents and human operators. The separation of concerns ensures your core business logic remains robust and testable while providing a clean, protocol-specific interface for MCP clients. 