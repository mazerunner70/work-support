#!/bin/bash
# Work Support Python Server - Run Script
# This script activates the virtual environment and starts the FastAPI server
# Can be run from any directory

set -e  # Exit on any error

echo "🚀 Starting Work Support Python Server..."
echo "========================================"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "📁 Script location: $SCRIPT_DIR"

# Change to the project directory
cd "$SCRIPT_DIR"
echo "📂 Changed to project directory: $(pwd)"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run from project directory: python -m venv venv"
    echo "Then run: source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
echo "🔍 Checking dependencies..."
if ! python -c "import fastapi, uvicorn" 2>/dev/null; then
    echo "❌ Dependencies not installed!"
    echo "Installing requirements..."
    pip install -r requirements.txt
fi

# Set environment variables if .env exists
if [ -f ".env" ]; then
    echo "⚙️  Loading environment variables from .env..."
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run the server
echo "🌐 Starting FastAPI server..."
echo "Server will be available at: http://localhost:8000"
echo "API documentation: http://localhost:8000/docs"
echo "Press Ctrl+C to stop the server"
echo "========================================"

# Start the server using the main.py entry point
python -m app.main

# Alternative: Run with uvicorn directly (uncomment if preferred)
# uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload 