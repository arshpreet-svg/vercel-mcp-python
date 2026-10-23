import os
from urllib.parse import unquote

__all__ = ["serverless_app", "vercel_hosts", "PATH_PARAM"]
__version__ = "0.1.0"

PATH_PARAM = "__path"


def vercel_hosts() -> list[str]:
    names = ("VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL")
    return sorted({os.environ[n] for n in names if os.environ.get(n)})


def restore_path(scope: dict, param: str = PATH_PARAM) -> dict:
    key = param.encode() + b"="
    query = [kv for kv in scope.get("query_string", b"").split(b"&") if kv]
    original = [kv for kv in query if kv.startswith(key)]
    if not original:
        return scope
    path = unquote(original[0][len(key):].decode("latin-1"))
    if not path.startswith("/"):
        path = "/" + path
    rest = b"&".join(kv for kv in query if not kv.startswith(key))
    return dict(scope, path=path, raw_path=path.encode(), query_string=rest)


def serverless_app(server, *, allowed_hosts: list[str] | None = None, json_response: bool = True,
                   path_param: str = PATH_PARAM, **app_kwargs):
    if allowed_hosts is not None:
        from mcp.server.transport_security import TransportSecuritySettings

        app_kwargs.setdefault("transport_security", TransportSecuritySettings(
            enable_dns_rebinding_protection=True, allowed_hosts=list(allowed_hosts),
            allowed_origins=[f"https://{h}" for h in allowed_hosts]))
    else:
        app_kwargs.setdefault("host", "0.0.0.0")

    async def app(scope, receive, send):
        if scope["type"] == "lifespan":
            while (await receive())["type"] != "lifespan.shutdown":
                await send({"type": "lifespan.startup.complete"})
            await send({"type": "lifespan.shutdown.complete"})
            return
        scope = restore_path(scope, path_param)
        inner = server.streamable_http_app(stateless_http=True, json_response=json_response, **app_kwargs)
        async with inner.router.lifespan_context(inner):
            await inner(scope, receive, send)

    return app
