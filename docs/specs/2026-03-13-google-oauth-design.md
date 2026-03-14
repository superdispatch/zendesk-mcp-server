# Google OAuth Authentication for Zendesk MCP Server

## Overview

Add MCP-spec OAuth 2.1 authentication to the Zendesk MCP server using Google as the Authorization Server. Only users in an email allowlist can access the server. Replaces IAP which is incompatible with Claude Desktop connectors.

## Architecture

```
Claude Desktop Connector
    │
    ├── GET /.well-known/oauth-protected-resource
    │   └── SDK auto-serves RFC 9728 Protected Resource Metadata
    │       (includes authorization_servers: ["https://accounts.google.com"])
    │
    ├── Google OAuth flow (user logs in with @superdispatch.com)
    │   └── Returns opaque access_token (+ id_token separately)
    │
    └── POST /mcp (Authorization: Bearer <access_token>)
        └── GoogleTokenVerifier:
            1. Call Google userinfo endpoint to validate token and get email
            2. Check email is in ALLOWED_EMAILS
            3. Check email_verified is true
```

## Components

### 1. GoogleTokenVerifier

New class in `auth.py` implementing the MCP SDK's `TokenVerifier` protocol.

**Token validation approach:** The MCP client sends Google's opaque access token (not the JWT id_token) as the Bearer token. Therefore we cannot decode it locally. Instead:

- Call `https://www.googleapis.com/oauth2/v3/userinfo` with the access token
- Google returns `{ email, email_verified, sub, ... }`
- Check `email` is in `ALLOWED_EMAILS` and `email_verified` is true
- Return `AccessToken` on success, `None` on failure
- Cache responses briefly (e.g. 5 min TTL) to avoid hitting Google on every MCP call

```python
class GoogleTokenVerifier(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code != 200:
                return None
            info = resp.json()
        if not info.get("email_verified"):
            return None
        if info["email"] not in ALLOWED_EMAILS:
            return None
        return AccessToken(
            token=token,
            client_id=info.get("sub", ""),
            scopes=["openid", "email"],
        )
```

### 2. FastMCP Server

Refactor from low-level `Server` class to `FastMCP`:

- Tools re-registered with `@mcp.tool()` decorators (SDK generates schemas from type hints)
- Auth configured via `token_verifier` and `auth` constructor params
- `READ_ONLY` logic: conditionally skip registering write tools at startup
- Both transports: `mcp.run(transport="stdio")` and `mcp.run(transport="streamable-http")`
- **Host binding:** Pass `host="0.0.0.0"` to FastMCP constructor (default is `127.0.0.1` which is unreachable in Docker)

```python
mcp = FastMCP(
    "Zendesk Server",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8080")),
    token_verifier=GoogleTokenVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl("https://accounts.google.com"),
        resource_server_url=AnyHttpUrl(os.getenv(
            "RESOURCE_SERVER_URL",
            "https://zendesk-mcp.superdispatch.org"
        )),
    ),
)
```

### 3. Prompts and Resources Migration

**Prompts:** Current `@server.list_prompts()` / `@server.get_prompt()` handlers migrate to `@mcp.prompt()` decorators. FastMCP prompts return strings or `Message` objects instead of manually constructed `GetPromptResult`.

**Resources:** The `zendesk://knowledge-base` resource migrates to `@mcp.resource("zendesk://knowledge-base")`. The `ttl_cache` for articles stays as-is.

**Image content:** The `get_ticket_attachment` tool returns `ImageContent` for images. Need to verify FastMCP's `tool_manager` handles `ContentBlock` return types, or return base64 string with content type metadata instead.

### 4. DCR (Dynamic Client Registration) Handling

Google does not support DCR. The MCP client SDK will attempt DCR if no client credentials are pre-configured, which will fail.

**Solution:** Users pre-register credentials in Claude Desktop's connector advanced settings (OAuth Client ID and Secret). The SDK's `AuthSettings.client_registration_options` defaults to `enabled=False`, which skips DCR. Claude Desktop's stored `client_info` contains the pre-registered credentials, so the SDK uses those directly for the authorization code flow.

### 5. Google OAuth Client

Created in GCP Console under `superdispatch-tools` project:

- Type: Web application
- Authorized JavaScript origins: Claude Desktop's origin
- Authorized redirect URIs: Claude Desktop's OAuth callback URL (TBD — need to inspect Claude Desktop's redirect behavior)
- Scopes: `openid`, `email`
- Client ID → `GOOGLE_CLIENT_ID` env var on Cloud Run
- Client ID + Secret → shared with users for Claude Desktop connector advanced settings

### 6. Cloud Run Changes

- **Remove IAP** — MCP server handles auth directly
- **Allow unauthenticated** — OAuth discovery endpoints (`/.well-known/oauth-protected-resource`) must be publicly reachable
- **TokenVerifier** protects actual MCP tool calls
- Add `GOOGLE_CLIENT_ID`, `ALLOWED_EMAILS`, and `RESOURCE_SERVER_URL` env vars

## Environment Variables

| Variable | Required | Sensitive | Storage | Example |
|----------|----------|-----------|---------|---------|
| `ZENDESK_SUBDOMAIN` | Yes | No | Env var | `superdispatchhelp` |
| `ZENDESK_EMAIL` | Yes | No | Env var | `rukhsora@superdispatch.com` |
| `ZENDESK_API_KEY` | Yes | Yes | Secret Manager | `xxx` |
| `GOOGLE_CLIENT_ID` | Yes | No | Env var | `339211158071-xxx.apps.googleusercontent.com` |
| `ALLOWED_EMAILS` | Yes | No | Env var | `far@superdispatch.com,rukhsora@superdispatch.com,...` |
| `RESOURCE_SERVER_URL` | Yes | No | Env var | `https://zendesk-mcp.superdispatch.org` |
| `READ_ONLY` | No | No | Env var | `true` |

## File Changes

### Modified

- `src/zendesk_mcp_server/server.py` — Refactor to FastMCP with auth, migrate tools/prompts/resources
- `src/zendesk_mcp_server/__init__.py` — Update entrypoints for FastMCP
- `pyproject.toml` — Add `httpx` (for userinfo calls), add `cachetools` (make explicit)
- `CLAUDE.md` — Update with OAuth setup instructions

### New

- `src/zendesk_mcp_server/auth.py` — GoogleTokenVerifier class

### Unchanged

- `src/zendesk_mcp_server/zendesk_client.py` — No changes
- `Dockerfile` — No changes (FastMCP handles host/port binding)

## User Setup Flow

1. Admin creates Google OAuth Client in GCP Console
2. Admin deploys server with `GOOGLE_CLIENT_ID`, `ALLOWED_EMAILS`, `RESOURCE_SERVER_URL`
3. Each user in Claude Desktop:
   - Settings → Connectors → Add custom connector
   - URL: `https://zendesk-mcp.superdispatch.org/mcp`
   - Advanced: enter OAuth Client ID and Secret
4. Google login prompt → sign in with `@superdispatch.com` account
5. Connected

## Open Questions

1. **Claude Desktop redirect URI** — need to determine the exact callback URL Claude Desktop uses for OAuth redirects, to configure as authorized redirect URI in Google OAuth Client. Can be discovered by inspecting Claude Desktop's network traffic during an OAuth flow attempt.

## Risks

- **Claude Desktop OAuth bugs** — there are known issues with OAuth in Claude Desktop connectors. If the flow doesn't work, fallback is to remove auth and use the unguessable Cloud Run URL.
- **Token caching** — the GoogleTokenVerifier should cache userinfo responses to avoid latency on every MCP call. A 5-minute TTL balances security and performance.

## Fallback Plan

If OAuth doesn't work due to Claude Desktop bugs:
1. Remove auth from FastMCP (drop `token_verifier` and `auth` params)
2. Keep `--allow-unauthenticated` on Cloud Run
3. Use only the default Cloud Run URL (not the guessable custom domain)
4. Re-enable IAP when Claude Desktop fixes OAuth support
