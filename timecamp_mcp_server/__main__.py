"""Entry point for timecamp-mcp-server when installed via pip/uvx."""

import sys
import os
import importlib.util
from typing import Optional, Any


def main() -> None:
    """Main entry point that runs the MCP server."""
    # Get the path to the original timecamp-server.py script
    package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = os.path.join(package_dir, 'timecamp-server.py')
    
    # Load the module from the file
    spec = importlib.util.spec_from_file_location("timecamp_server", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load timecamp-server.py")
    
    timecamp_module = importlib.util.module_from_spec(spec)
    sys.modules["timecamp_server"] = timecamp_module
    spec.loader.exec_module(timecamp_module)
    
    # Run the MCP server
    timecamp_module.mcp.run()  # type: ignore[attr-defined]


if __name__ == "__main__":
    main()
