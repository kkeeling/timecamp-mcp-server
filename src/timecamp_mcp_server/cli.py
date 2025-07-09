"""CLI entry point for TimeCamp MCP Server."""

import sys
from .server import mcp


def main():
    """Main entry point for the TimeCamp MCP server."""
    if "--help" in sys.argv or "-h" in sys.argv:
        print("TimeCamp MCP Server")
        print("===================")
        print()
        print("A Model Context Protocol server for TimeCamp time tracking.")
        print()
        print("Usage: timecamp-mcp-server")
        print()
        print("Environment Variables:")
        print("  TIMECAMP_API_TOKEN - Your TimeCamp API token (required)")
        print()
        print("Configure in Claude Desktop by adding to config:")
        print('{')
        print('  "mcpServers": {')
        print('    "timecamp": {')
        print('      "command": "timecamp-mcp-server",')
        print('      "env": {')
        print('        "TIMECAMP_API_TOKEN": "YOUR_API_TOKEN"')
        print('      }')
        print('    }')
        print('  }')
        print('}')
        print()
        print("For more information, visit: https://github.com/yourusername/timecamp-mcp-server")
        sys.exit(0)
    
    # Run the MCP server
    mcp.run()


if __name__ == "__main__":
    main()