# __main__.py
# Entry point for running memory_mcp as a module: python -m memory_mcp

import os

# Use SDK version by default, fall back to custom implementation
USE_SDK = os.environ.get("MEMORY_MCP_USE_SDK", "1") == "1"

if USE_SDK:
    from memory_mcp.server_sdk import run
    if __name__ == "__main__":
        run()
else:
    from memory_mcp.server import main
    if __name__ == "__main__":
        main()
