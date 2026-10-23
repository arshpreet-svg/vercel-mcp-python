from mcp.server.mcpserver import MCPServer
from starlette.requests import Request
from starlette.responses import PlainTextResponse

mcp = MCPServer("hello-vercel", instructions="A tiny MCP server running on Vercel.")


@mcp.tool()
def greet(name: str) -> str:
    return f"Hello, {name}!"


@mcp.tool()
def add(a: float, b: float) -> float:
    return a + b


@mcp.custom_route("/", methods=["GET"])
async def home(request: Request) -> PlainTextResponse:
    return PlainTextResponse("hello-vercel MCP server. POST JSON-RPC to /mcp\n")
