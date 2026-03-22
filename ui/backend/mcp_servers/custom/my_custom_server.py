from mcp.server import FastMCP
from datetime import datetime

mcp = FastMCP("My First Custom Server")

@mcp.tool(description="Return a motivational message")
def motivate(name: str) -> dict:
    return {
        "message": f"Keep going {name}, you're doing amazing 🚀",
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    print("Starting custom MCP server...")
    mcp.run(transport="stdio")