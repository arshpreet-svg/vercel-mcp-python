# vercel-mcp-python

Run a server built with the official **MCP Python SDK** (Streamable HTTP, spec 2025-11-25) as a **Vercel serverless
function**, with one line:

```python
# api/index.py
from server import mcp                 # your MCPServer
from vercel_mcp import serverless_app

app = serverless_app(mcp)
```

```json
// vercel.json
{
  "functions": { "api/index.py": { "includeFiles": "server.py", "maxDuration": 30 } },
  "rewrites": [{ "source": "/(.*)", "destination": "/api/index?__path=/$1" }]
}
```

Your MCP endpoint is then `https://<project>.vercel.app/mcp`, and any `@mcp.custom_route` pages work too.

## Why this exists

Deploying an `MCPServer` to Vercel the obvious way fails in three separate ways:

| Symptom | Cause | What the adapter does |
|---|---|---|
| Every URL, including `/mcp`, returns plain-text `Not Found` | A catch-all rewrite sends requests to `/api/index`, and that is the path the ASGI app receives, so no route matches | The rewrite passes the original path as `?__path=`; the adapter puts it back and removes it from the query string |
| `RuntimeError: StreamableHTTPSessionManager .run() can only be called once per instance` | The session manager is started from the app's lifespan, and serverless instances are frozen and reused between requests | Builds a fresh **stateless** Streamable HTTP app for each request and runs it inside its own lifespan |
| `421 Invalid Host header` | The SDK turns on DNS-rebinding protection for localhost-only hosts by default, which rejects `*.vercel.app` | Off by default (Vercel preview URLs aren't known ahead of time); pass `allowed_hosts=` to keep it on |

The first one is the hardest to spot: the 404 comes from your own app, so Vercel's logs show a healthy function.

## Install

```bash
pip install "vercel-mcp-python @ git+https://github.com/arshpreet-svg/vercel-mcp-python"
```

Or copy `vercel_mcp/__init__.py` into your project; it has no dependencies beyond `mcp`.

## Options

```python
from vercel_mcp import serverless_app, vercel_hosts

app = serverless_app(
    mcp,
    allowed_hosts=vercel_hosts() + ["mcp.example.com"],  # keep DNS-rebinding protection on
    json_response=True,                                 # default; plain JSON instead of SSE
)
```

`vercel_hosts()` reads Vercel's system environment variables (`VERCEL_URL`, `VERCEL_BRANCH_URL`,
`VERCEL_PROJECT_PRODUCTION_URL`). Any other keyword is passed to `streamable_http_app` (for example
`streamable_http_path="/api/mcp"` or `max_request_body_size`).

## Try the example

```bash
cd example
vercel deploy        # or import the repo at vercel.com/new with "example" as the root directory
```

Then call it with any MCP client, or:

```bash
curl -s -X POST https://<project>.vercel.app/mcp \
  -H 'content-type: application/json' -H 'accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"greet","arguments":{"name":"Vercel"}}}'
```

## Limits of stateless serverless MCP

- No sessions: every request stands alone, so there is no `Mcp-Session-Id`, no GET event stream and no
  server-initiated requests (sampling, elicitation) or notifications between calls.
- Anything kept in memory or `/tmp` disappears when the instance is recycled. Use a real database for state.
- Vercel's request body limit (about 4.5 MB) applies.

For long-lived sessions, run `mcp.run(transport="streamable-http")` on a server instead.

## Tests

```bash
pip install "mcp>=2.3"
python -m unittest -v
```

The tests drive the adapter exactly as Vercel does after the rewrite: path restoration, `initialize` negotiating
2025-11-25 on a `*.vercel.app` host, repeated stateless tool calls, `allowed_hosts` rejecting a foreign host with
421, and a control test showing the unwrapped app returns 404.

## Where it came from

Extracted from [Storykeeper](https://github.com/arshpreet-svg/storykeeper), an Alexa+ MCP server for family memories,
which runs the same approach live at https://storykeeper-ivory.vercel.app/mcp.

## License

MIT
