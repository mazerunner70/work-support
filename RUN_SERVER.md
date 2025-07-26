# 🚀 How to Run the Work Support Python Server

This document explains the different ways to start the FastAPI server.

**✨ NEW: All scripts can now be run from any directory!**

## Prerequisites

1. **Python 3.8+** installed
2. **Virtual environment** created: `python -m venv venv` (in project directory)
3. **Dependencies installed**: Activate venv and run `pip install -r requirements.txt`

## Quick Start Options

### Option 1: Bash Script (Linux/Mac) ⭐ RECOMMENDED
```bash
# Can run from anywhere - script will find project directory automatically
./run_server.sh

# Or from any directory:
/path/to/your/project/run_server.sh
```

### Option 2: Windows Batch Script
```cmd
REM Can run from anywhere - script will find project directory automatically
run_server.bat

REM Or from any directory:
C:\path\to\your\project\run_server.bat
```

### Option 3: Python Script (Cross-platform)
```bash
# Can run from anywhere - script will find project directory automatically
python run_server.py

# Or from any directory:
python /path/to/your/project/run_server.py

# Note: Virtual environment should still be activated first
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate.bat  # Windows
```

### Option 4: Direct Python Command
```bash
# Must be run from project directory
cd /path/to/your/project

# Activate virtual environment first
source venv/bin/activate  # Linux/Mac
# OR  
venv\Scripts\activate.bat  # Windows

# Then run directly
python app/main.py
```

### Option 5: Direct Uvicorn Command
```bash
# Must be run from project directory
cd /path/to/your/project

# Activate virtual environment first
source venv/bin/activate

# Run with uvicorn directly
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## What Each Script Does

All scripts automatically:
- ✅ **Detect script location** and change to project directory
- ✅ Check if virtual environment exists
- ✅ Activate the virtual environment [[memory:4401429]]
- ✅ Check if dependencies are installed
- ✅ Install dependencies if missing
- ✅ Load environment variables from `.env` (if exists)
- ✅ Start the FastAPI server

## Server Access

Once running, the server will be available at:
- **Main Server**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

## Stopping the Server

Press `Ctrl+C` to stop the server.

## Example Usage

```bash
# From your home directory
cd ~

# Run the server (script automatically finds project)
/path/to/work-support/run_server.sh

# Output:
# 🚀 Starting Work Support Python Server...
# 📁 Script location: /path/to/work-support
# 📂 Changed to project directory: /path/to/work-support
# 📦 Activating virtual environment...
# ✅ Dependencies are installed
# 🌐 Starting FastAPI server...
```

## Troubleshooting

### Virtual Environment Issues
```bash
# Create virtual environment (from project directory)
cd /path/to/your/project
python -m venv venv

# Activate it
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate.bat  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Permission Issues (Linux/Mac)
```bash
chmod +x /path/to/your/project/run_server.sh
```

### Port Already in Use
If port 8000 is busy, you can change it by:
1. Setting `SERVER_PORT=8001` in your `.env` file, OR
2. Running directly: `uvicorn app.main:app --port 8001`

### Script Not Found
If you get "command not found" errors:
```bash
# Make sure you're using the full path
/full/path/to/work-support/run_server.sh

# Or add to your PATH (optional)
export PATH="$PATH:/path/to/work-support"
``` 