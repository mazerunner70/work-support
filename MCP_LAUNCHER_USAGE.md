# MCP Server Launcher Usage

You can now start the Work Support MCP server from any directory using either of these methods:

## Method 1: Python Script (Recommended)

```bash
# From anywhere on your system:
/path/to/work-support/launch_mcp_server.py

# Or if you're in the work-support directory:
./launch_mcp_server.py
```

## Method 2: Shell Wrapper

```bash
# From anywhere on your system:
/path/to/work-support/mcp-server

# Or if you're in the work-support directory:
./mcp-server
```

## Environment Variables

Set these before running (optional):

```bash
# Set the work-support API URL (defaults to http://localhost:8000)
export WORK_SUPPORT_URL=http://localhost:8000

# Set logging level (defaults to INFO)
export MCP_LOG_LEVEL=DEBUG

# Then run from any directory:
/path/to/work-support/launch_mcp_server.py
```

## MCP Client Configuration

For Claude Desktop, add this to your MCP config:

```json
{
  "mcpServers": {
    "work-support": {
      "command": "/path/to/work-support/launch_mcp_server.py",
      "env": {
        "WORK_SUPPORT_URL": "http://localhost:8000"
      }
    }
  }
}
```

## How It Works

The launcher script:
1. **Auto-detects project root**: Finds the work-support directory by looking for `mcp_server/` and `app/` folders
2. **Sets up Python path**: Adds the project root to Python's import path
3. **Validates environment**: Checks that the MCP server files exist
4. **Changes working directory**: Ensures relative paths work correctly
5. **Starts the server**: Runs the actual MCP server with proper configuration

## Troubleshooting

### "MCP server not found" error
- Make sure you're pointing to the correct work-support project directory
- Verify that `mcp_server/server.py` exists in the project

### Import errors
- Check that all dependencies are installed (`pip install -r requirements.txt`)
- Ensure you're using the correct Python environment

### Connection issues
- Verify that the work-support REST API is running on the configured URL
- Check the `WORK_SUPPORT_URL` environment variable

## Example Usage

```bash
# Start work-support API server (terminal 1)
cd /path/to/work-support
python -m uvicorn app.main:app --reload --port 8000

# Start MCP server from anywhere (terminal 2)
cd ~/Documents/some-other-project
/path/to/work-support/launch_mcp_server.py
```

The MCP server will automatically connect to the work-support API and be ready for MCP clients to connect via stdio. 