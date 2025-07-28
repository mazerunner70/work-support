#!/bin/bash
export WORK_SUPPORT_URL="${WORK_SUPPORT_URL:-http://localhost:8000}"
# get directory of this script
SCRIPT_DIR=$(dirname "$0")
# get directory of this script's parent
PARENT_DIR=$(dirname "$SCRIPT_DIR")
# set the working directory to the parent directory
cd "$PARENT_DIR"
#run venv
source venv/bin/activate
# change to mcp_server directory and run the server
cd mcp_server
python server.py 
