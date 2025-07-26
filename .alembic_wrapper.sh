#!/bin/bash
# Alembic wrapper to always activate virtual environment first

# Get the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Run alembic with all passed arguments
alembic "$@" 