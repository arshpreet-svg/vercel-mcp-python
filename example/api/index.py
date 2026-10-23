import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import mcp
from vercel_mcp import serverless_app

app = serverless_app(mcp)
