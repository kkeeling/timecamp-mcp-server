#!/usr/bin/env python3
"""
Test script for UV-based TimeCamp MCP server
"""

import subprocess
import json
import os

# Test configuration
test_config = {
    "mcpServers": {
        "timecamp": {
            "command": "uv",
            "args": ["run", "timecamp-server.py"],
            "env": {
                "TIMECAMP_API_TOKEN": os.getenv("TIMECAMP_API_TOKEN", "test_token")
            }
        }
    }
}

print("TimeCamp MCP Server - UV Configuration Test")
print("=" * 50)
print("\nConfiguration to add to Claude Desktop:")
print(json.dumps(test_config, indent=2))
print("\nMake sure to:")
print("1. Replace 'timecamp-server.py' with the full path to the file")
print("2. Replace 'test_token' with your actual TimeCamp API token")
print("\nExample full path configuration:")

example_config = {
    "mcpServers": {
        "timecamp": {
            "command": "uv",
            "args": ["run", "/Users/yourusername/timecamp-server.py"],
            "env": {
                "TIMECAMP_API_TOKEN": "YOUR_ACTUAL_TOKEN_HERE"
            }
        }
    }
}

print(json.dumps(example_config, indent=2))