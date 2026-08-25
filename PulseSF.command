#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=================================================="
echo "Starting PulseSF Workspace (CLEAN/_cl test build - port 8001)..."
echo "=================================================="

echo "Checking Python components..."
# Create a virtual environment if it doesn't exist to bypass macOS Sonoma restrictions
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate the virtual environment and install dependencies silently
source venv/bin/activate
pip3 install -q fastapi uvicorn jinja2 pydantic

echo "Checking and Updating Salesforce CLI..."
if ! command -v sf &> /dev/null; then
    echo "Salesforce CLI not found! Attempting auto-install..."
    if command -v npm &> /dev/null; then
        npm install -g @salesforce/cli
    elif command -v brew &> /dev/null; then
        brew install sf
    else
        echo "ERROR: Neither NPM nor Homebrew is installed. Please manually install the Salesforce CLI."
        exit 1
    fi
else
    echo "Auto-updating Salesforce CLI to the latest version..."
    npm update -g @salesforce/cli > /dev/null 2>&1 || sf update > /dev/null 2>&1
fi

lsof -ti:8001 | xargs kill -9 2>/dev/null

echo "Booting up the local Web Server (CLEAN build, port 8001)..."
# Run Python via the virtual environment as a detached background daemon
nohup venv/bin/python -m uvicorn main_cl:app --host 127.0.0.1 --port 8001 --log-level warning > /dev/null 2>&1 &

sleep 2
open http://127.0.0.1:8001/PulseSF

# Command the terminal to close this specific window.
nohup osascript -e 'tell application "Terminal" to close front window' > /dev/null 2>&1 &
exit 0
