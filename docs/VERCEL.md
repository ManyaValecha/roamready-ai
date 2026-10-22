# Vercel demo deployment

This deploys the existing app as a demo-only Python ASGI function. `app.py` routes both the dashboard and Streamable HTTP MCP endpoint through one function. The deployment forces deterministic demo mode, uses `/tmp/roamready.db`, and requires two secrets:

- `TRIP_SCOUT_TOKEN`: bearer token for MCP requests. The browser never receives this value.
- `ROAMREADY_SESSION_SECRET`: signs the browser's opaque demo-session cookie.

## Configure and deploy

From the repository root, after signing in to Vercel and linking this directory to a project:

```sh
vercel env add TRIP_SCOUT_TOKEN production
vercel env add ROAMREADY_SESSION_SECRET production
vercel deploy --prod
```

When prompted, provide separate cryptographically random values for the two secrets. Do not put them in `.env`, source control, screenshots, logs, or client-side settings. To deploy a preview, add the same variables to the Preview environment before using `vercel deploy`.

The deployment uses `VERCEL_PROJECT_PRODUCTION_URL` when available (falling back to `VERCEL_URL`) for its server-side MCP request. This avoids routing that internal request through a deployment-specific URL that may be protected by Vercel Authentication. MCP host and origin checks are bound to the selected hostname. Requests to MCP without its bearer token receive `401`. The public web app's own server-side proxy supplies the token and allows only the offline demo tools.

## Data and operational limits

This configuration does not set up a database, domain, paid service, Alexa+ preview access, or Alexa device connection. SQLite under `/tmp` is temporary and instance-local: data can disappear on cold start, redeploy, or instance replacement, and different serverless instances may not share it. The UI discloses this behavior. No live flight/hotel results or bookings are used. Use a durable shared database only after choosing and authorizing a storage provider.

Before sharing a deployed URL, verify the home page, browser trip plan and rescue, session isolation, temporary-storage disclosure, and an authenticated MCP `initialize`/`tools/list`/`tools/call` flow. Do not publish the bearer token.
