# Work Support MCP Server

A lightweight Model Context Protocol (MCP) server that provides AI agents with access to work support data including Jira issues, team metrics, and system health information.

## Overview

This MCP server acts as a bridge between AI agents (like Claude) and the work-support REST API. It translates MCP protocol calls into REST API requests and formats responses for optimal AI consumption.

## Architecture

```
┌─────────────────┐    MCP Protocol    ┌──────────────────────┐
│   AI Agents     │ ◄─────────────────► │   MCP Server         │
│  (Claude, etc.) │                     │   (Port 8001)        │
└─────────────────┘                     └──────────────────────┘
                                                    │
                                                    │ HTTP/REST
                                                    ▼
                                        ┌──────────────────────┐
                                        │  Work-Support Server │
                                        │    (Port 8000)       │
                                        └──────────────────────┘
```

## Installation

1. **Install MCP SDK**:
   ```bash
   pip install mcp==1.12.2
   ```

2. **Verify Installation**:
   ```bash
   python scripts/test_mcp_endpoints.py
   ```

## Usage

### Starting the MCP Server

1. **Set Environment Variables**:
   ```bash
   export WORK_SUPPORT_URL=http://localhost:8000
   export MCP_LOG_LEVEL=INFO  # Optional
   ```

2. **Start the MCP Server**:
   ```bash
   python scripts/run_mcp_server.py
   ```

3. **Or Start Both Servers**:
   ```bash
   python scripts/run_both.py
   ```

### Available Tools

The MCP server provides the following tools for AI agents:

#### Query Tools
- **`query_issues`**: Find issues by team, status, assignee, or type
- **`get_issue_details`**: Get comprehensive information about specific issues  
- **`search_issues`**: Search issues by keywords in summary/description

#### Team Tools
- **`get_team_metrics`**: Analyze team performance and workload
- **`analyze_assignee_workload`**: Review individual workload and patterns

#### Admin Tools
- **`test_connectivity`**: Check system health and data freshness
- **`trigger_harvest`**: Initiate data synchronization from Jira
- **`get_harvest_status`**: Monitor harvest job progress

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WORK_SUPPORT_URL` | Yes | `http://localhost:8000` | Work-support REST API URL |
| `WORK_SUPPORT_API_KEY` | No | None | API key for authentication |
| `MCP_LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `MCP_REQUEST_TIMEOUT` | No | `30.0` | Request timeout in seconds |
| `MCP_DEFAULT_LIMIT` | No | `50` | Default result limit |
| `MCP_MAX_LIMIT` | No | `500` | Maximum result limit |

### Claude Desktop Integration

Add this to your Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "work-support": {
      "command": "python",
      "args": ["/path/to/your/work-support/scripts/run_mcp_server.py"],
      "env": {
        "WORK_SUPPORT_URL": "http://localhost:8000"
      }
    }
  }
}
```

## Development

### Project Structure

```
mcp_server/
├── __init__.py              # Package initialization
├── config.py                # Configuration settings
├── client.py                # HTTP client for REST API
├── server.py                # Main MCP server
├── utils.py                 # Response formatting utilities
├── tools/                   # MCP tool implementations
│   ├── __init__.py
│   ├── query_tools.py       # Issue querying tools
│   ├── team_tools.py        # Team analytics tools
│   └── admin_tools.py       # System administration tools
└── README.md                # This file
```

### Adding New Tools

1. Create a new tool class in the appropriate file under `tools/`
2. Implement the tool method with proper type hints and documentation
3. Register the tool in the class's `_register_tools()` method
4. Initialize the tool class in `server.py`

Example:
```python
async def my_new_tool(self, param: str) -> List[types.TextContent]:
    """
    Description of what this tool does.
    
    Args:
        param: Description of the parameter
    
    Returns:
        Formatted response for the user
    """
    # Implementation here
    return [types.TextContent(type="text", text="Result")]
```

### Testing

Run the test script to verify everything is working:

```bash
# Test environment and connectivity
python scripts/test_mcp_endpoints.py

# Test with different environment
WORK_SUPPORT_URL=http://remote-server:8000 python scripts/test_mcp_endpoints.py
```

## Troubleshooting

### Common Issues

1. **"Failed to connect to Work Support API"**
   - Ensure the work-support server is running on the configured URL
   - Check network connectivity and firewall settings

2. **"Configuration validation failed"**
   - Verify `WORK_SUPPORT_URL` is set and valid
   - Check that the URL starts with `http://` or `https://`

3. **"MCP server initialization failed"**
   - Ensure MCP SDK is installed: `pip install mcp==1.12.2`
   - Check Python version compatibility (>= 3.10)

4. **Tools not appearing in AI client**
   - Verify MCP server is running and accessible
   - Check AI client MCP configuration
   - Review server logs for registration errors

### Debugging

Enable debug logging:
```bash
export MCP_LOG_LEVEL=DEBUG
python scripts/run_mcp_server.py
```

Check server logs for detailed error information and request/response data.

## Performance Notes

- The MCP server is designed to be lightweight and fast
- It caches no data - all requests go to the work-support API
- Response formatting is optimized for AI consumption
- Default limits prevent overwhelming responses while allowing detailed analysis

## Security

- The MCP server acts as a proxy to the work-support API
- It inherits all security measures from the underlying work-support system
- API keys are passed through if configured
- No sensitive data is logged or cached

## Version Compatibility

- **MCP SDK**: 1.12.2
- **Python**: 3.10+
- **Work-Support API**: Compatible with existing MCP endpoints

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review server logs for error details
3. Test with `scripts/test_mcp_endpoints.py`
4. Verify work-support API connectivity independently 