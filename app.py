"""Vercel ASGI entry point for the demo-only RoamReady deployment."""
import os

if not os.environ.get("TRIP_SCOUT_TOKEN"):
    raise RuntimeError("TRIP_SCOUT_TOKEN must be configured for the hosted demo.")
if not os.environ.get("ROAMREADY_SESSION_SECRET"):
    raise RuntimeError("ROAMREADY_SESSION_SECRET must be configured for the hosted demo.")

os.environ["ROAMREADY_DEPLOYMENT_MODE"] = "vercel"
os.environ["ROAMREADY_DEMO_MODE"] = "1"
os.environ["TRIP_SCOUT_STATELESS_HTTP"] = "1"
os.environ["TRIP_SCOUT_DB"] = "/tmp/roamready.db"

# VERCEL_URL is the deployment-specific host. Vercel may protect that host with
# deployment authentication, which blocks the app's server-side MCP client.
# Prefer the public production alias for this internal HTTP hop.
deployment_host = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL") or os.environ.get("VERCEL_URL")
if not deployment_host:
    raise RuntimeError("VERCEL_URL is required to bind the hosted MCP endpoint to this deployment.")
os.environ["TRIP_SCOUT_MCP_URL"] = f"https://{deployment_host}/mcp"
os.environ["TRIP_SCOUT_ALLOWED_HOSTS"] = deployment_host
os.environ["TRIP_SCOUT_ALLOWED_ORIGINS"] = f"https://{deployment_host}"

from web.app import app as web_app  # noqa: E402
from trip_scout.server import build_app as build_mcp_app, mcp  # noqa: E402

mcp_app = build_mcp_app()


class VercelASGI:
    """Route the browser and Streamable HTTP MCP transport through one function."""

    def __init__(self, web, mcp_transport):
        self.web = web
        self.mcp_transport = mcp_transport

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            async with mcp.session_manager.run():
                while True:
                    event = await receive()
                    if event["type"] == "lifespan.startup":
                        await send({"type": "lifespan.startup.complete"})
                    elif event["type"] == "lifespan.shutdown":
                        await send({"type": "lifespan.shutdown.complete"})
                        return
        elif scope["type"] == "http" and scope.get("path", "").startswith("/mcp"):
            await self.mcp_transport(scope, receive, send)
        else:
            await self.web(scope, receive, send)


app = VercelASGI(web_app, mcp_app)
