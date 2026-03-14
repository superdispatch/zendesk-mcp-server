# Google OAuth Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add MCP-spec OAuth 2.1 to the Zendesk MCP server using Google as Authorization Server with email allowlist.

**Architecture:** Refactor from low-level `Server` to `FastMCP` with `TokenVerifier` and `AuthSettings`. GoogleTokenVerifier validates opaque access tokens via Google's userinfo endpoint. Auth disabled for stdio transport (local dev), enabled for HTTP transport (Cloud Run).

**Tech Stack:** MCP Python SDK 1.26.0 (`FastMCP`, `TokenVerifier`, `AuthSettings`), `httpx` (async Google userinfo calls), `cachetools` (token cache)

**Spec:** `docs/specs/2026-03-13-google-oauth-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/zendesk_mcp_server/auth.py` | Create | GoogleTokenVerifier — validates Google access tokens, checks email allowlist |
| `src/zendesk_mcp_server/server.py` | Rewrite | FastMCP server with tools, prompts, resources, auth config, dual transport |
| `src/zendesk_mcp_server/__init__.py` | Modify | Update entrypoints for FastMCP |
| `pyproject.toml` | Modify | Add `httpx`, `cachetools` deps |
| `tests/test_auth.py` | Create | Unit tests for GoogleTokenVerifier |
| `tests/test_server.py` | Create | Smoke tests for FastMCP tool registration |

---

## Chunk 1: GoogleTokenVerifier

### Task 1: Add dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add httpx and cachetools to pyproject.toml**

```toml
dependencies = [
    "mcp>=1.23.0",
    "httpx>=0.28.0",
    "cachetools>=5.5.0",
    "python-dotenv>=1.0.1",
    "zenpy>=2.0.56",
]
```

- [ ] **Step 2: Lock and sync**

Run: `uv lock && uv sync`
Expected: Resolves without errors

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "Add httpx and cachetools dependencies"
```

### Task 2: Create GoogleTokenVerifier

**Files:**
- Create: `src/zendesk_mcp_server/auth.py`
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write failing test for successful token verification**

```python
# tests/test_auth.py
import pytest
from unittest.mock import AsyncMock, patch
from zendesk_mcp_server.auth import GoogleTokenVerifier


@pytest.mark.asyncio
async def test_verify_token_success():
    verifier = GoogleTokenVerifier(
        allowed_emails={"user@superdispatch.com"}
    )

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "email": "user@superdispatch.com",
        "email_verified": True,
        "sub": "12345",
    }

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        result = await verifier.verify_token("valid-token")

    assert result is not None
    assert result.client_id == "12345"
    assert result.scopes == ["openid", "email"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_auth.py::test_verify_token_success -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'zendesk_mcp_server.auth'`

- [ ] **Step 3: Write failing test for email not in allowlist**

```python
# tests/test_auth.py (append)
@pytest.mark.asyncio
async def test_verify_token_email_not_allowed():
    verifier = GoogleTokenVerifier(
        allowed_emails={"admin@superdispatch.com"}
    )

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "email": "hacker@evil.com",
        "email_verified": True,
        "sub": "99999",
    }

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        result = await verifier.verify_token("some-token")

    assert result is None
```

- [ ] **Step 4: Write failing test for invalid token**

```python
# tests/test_auth.py (append)
@pytest.mark.asyncio
async def test_verify_token_invalid():
    verifier = GoogleTokenVerifier(
        allowed_emails={"user@superdispatch.com"}
    )

    mock_response = AsyncMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {"error": "invalid_token"}

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        result = await verifier.verify_token("bad-token")

    assert result is None
```

- [ ] **Step 5: Write failing test for email not verified**

```python
# tests/test_auth.py (append)
@pytest.mark.asyncio
async def test_verify_token_email_not_verified():
    verifier = GoogleTokenVerifier(
        allowed_emails={"user@superdispatch.com"}
    )

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "email": "user@superdispatch.com",
        "email_verified": False,
        "sub": "12345",
    }

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        result = await verifier.verify_token("some-token")

    assert result is None
```

- [ ] **Step 6: Implement GoogleTokenVerifier**

```python
# src/zendesk_mcp_server/auth.py
import logging
from typing import Set

import httpx
from cachetools import TTLCache
from mcp.server.auth.provider import AccessToken, TokenVerifier

logger = logging.getLogger("zendesk-mcp-server")

GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleTokenVerifier(TokenVerifier):
    """Validates Google OAuth access tokens and checks email allowlist."""

    def __init__(self, allowed_emails: Set[str], cache_ttl: int = 300):
        self._allowed_emails = allowed_emails
        self._cache: TTLCache[str, AccessToken | None] = TTLCache(
            maxsize=256, ttl=cache_ttl
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        cached = self._cache.get(token)
        if cached is not None:
            return cached

        result = await self._verify_with_google(token)
        self._cache[token] = result
        return result

    async def _verify_with_google(self, token: str) -> AccessToken | None:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    GOOGLE_USERINFO_URL,
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code != 200:
                    logger.warning("Google userinfo returned %d", resp.status_code)
                    return None
                info = resp.json()
        except httpx.HTTPError as e:
            logger.error("Google userinfo request failed: %s", e)
            return None

        if not info.get("email_verified"):
            logger.warning("Email not verified for %s", info.get("email"))
            return None

        email = info.get("email", "")
        if email not in self._allowed_emails:
            logger.warning("Email %s not in allowlist", email)
            return None

        return AccessToken(
            token=token,
            client_id=info.get("sub", ""),
            scopes=["openid", "email"],
        )
```

- [ ] **Step 7: Add pytest and pytest-asyncio to dev deps**

Run: `uv add --dev pytest pytest-asyncio`

- [ ] **Step 8: Run all auth tests**

Run: `uv run pytest tests/test_auth.py -v`
Expected: 4 passed

- [ ] **Step 9: Commit**

```bash
git add src/zendesk_mcp_server/auth.py tests/test_auth.py
git commit -m "Add GoogleTokenVerifier with email allowlist"
```

---

## Chunk 2: Refactor server.py to FastMCP

### Task 3: Rewrite server.py with FastMCP

**Files:**
- Rewrite: `src/zendesk_mcp_server/server.py`

- [ ] **Step 1: Rewrite server.py**

Replace the entire file. Key changes:
- `Server` → `FastMCP`
- Manual tool schemas → `@mcp.tool()` with type hints
- Manual prompt handlers → `@mcp.prompt()`
- Manual resource handlers → `@mcp.resource()`
- Add auth config for HTTP transport
- `READ_ONLY` controls which tools are registered

```python
# src/zendesk_mcp_server/server.py
import json
import logging
import os
from typing import Any, Dict, List

from cachetools.func import ttl_cache
from dotenv import load_dotenv
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

from zendesk_mcp_server.auth import GoogleTokenVerifier
from zendesk_mcp_server.zendesk_client import ZendeskClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("zendesk-mcp-server")

load_dotenv()

# --- Config ---
READ_ONLY = os.getenv("READ_ONLY", "false").lower() in ("true", "1", "yes")
ALLOWED_EMAILS = set(
    e.strip()
    for e in os.getenv("ALLOWED_EMAILS", "").split(",")
    if e.strip()
)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
RESOURCE_SERVER_URL = os.getenv("RESOURCE_SERVER_URL", "")

# --- Zendesk client ---
_subdomain = os.getenv("ZENDESK_SUBDOMAIN")
_email = os.getenv("ZENDESK_EMAIL")
_token = os.getenv("ZENDESK_API_KEY")

zendesk_client = None
if _subdomain and _email and _token:
    zendesk_client = ZendeskClient(subdomain=_subdomain, email=_email, token=_token)
else:
    logger.warning(
        "Zendesk credentials not configured. "
        "Set ZENDESK_SUBDOMAIN, ZENDESK_EMAIL, and ZENDESK_API_KEY."
    )


def _require_client() -> ZendeskClient:
    if not zendesk_client:
        raise ValueError(
            "Zendesk credentials not configured. "
            "Set ZENDESK_SUBDOMAIN, ZENDESK_EMAIL, and ZENDESK_API_KEY env vars."
        )
    return zendesk_client


# --- Auth (only for HTTP transport) ---
def _build_auth_kwargs() -> dict:
    """Return auth kwargs for FastMCP if credentials are configured."""
    if not ALLOWED_EMAILS or not RESOURCE_SERVER_URL:
        return {}
    return {
        "token_verifier": GoogleTokenVerifier(allowed_emails=ALLOWED_EMAILS),
        "auth": AuthSettings(
            issuer_url=AnyHttpUrl("https://accounts.google.com"),
            resource_server_url=AnyHttpUrl(RESOURCE_SERVER_URL),
        ),
    }


# --- FastMCP server ---
mcp = FastMCP(
    "Zendesk Server",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8080")),
    **_build_auth_kwargs(),
)


# --- Tools: Read ---
@mcp.tool()
def get_ticket(ticket_id: int) -> str:
    """Retrieve a Zendesk ticket by its ID"""
    client = _require_client()
    return json.dumps(client.get_ticket(ticket_id))


@mcp.tool()
def get_tickets(
    page: int = 1,
    per_page: int = 25,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> str:
    """Fetch the latest tickets with pagination support"""
    client = _require_client()
    return json.dumps(
        client.get_tickets(
            page=page, per_page=per_page, sort_by=sort_by, sort_order=sort_order
        ),
        indent=2,
    )


@mcp.tool()
def get_ticket_comments(ticket_id: int) -> str:
    """Retrieve all comments for a Zendesk ticket by its ID"""
    client = _require_client()
    return json.dumps(client.get_ticket_comments(ticket_id))


@mcp.tool()
def get_ticket_attachment(content_url: str) -> str:
    """Fetch a Zendesk ticket attachment by its content_url and return as base64-encoded data.

    Use the attachment URLs returned by get_ticket_comments.
    """
    client = _require_client()
    result = client.get_ticket_attachment(content_url)
    return json.dumps(
        {"content_type": result["content_type"], "data_base64": result["data"]}
    )


# --- Tools: Write (conditional) ---
if not READ_ONLY:

    @mcp.tool()
    def create_ticket(
        subject: str,
        description: str,
        requester_id: int | None = None,
        assignee_id: int | None = None,
        priority: str | None = None,
        type: str | None = None,
        tags: List[str] | None = None,
        custom_fields: List[Dict[str, Any]] | None = None,
    ) -> str:
        """Create a new Zendesk ticket"""
        client = _require_client()
        created = client.create_ticket(
            subject=subject,
            description=description,
            requester_id=requester_id,
            assignee_id=assignee_id,
            priority=priority,
            type=type,
            tags=tags,
            custom_fields=custom_fields,
        )
        return json.dumps(
            {"message": "Ticket created successfully", "ticket": created}, indent=2
        )

    @mcp.tool()
    def create_ticket_comment(
        ticket_id: int, comment: str, public: bool = True
    ) -> str:
        """Create a new comment on an existing Zendesk ticket"""
        client = _require_client()
        result = client.post_comment(
            ticket_id=ticket_id, comment=comment, public=public
        )
        return f"Comment created successfully: {result}"

    @mcp.tool()
    def update_ticket(
        ticket_id: int,
        subject: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        type: str | None = None,
        assignee_id: int | None = None,
        requester_id: int | None = None,
        tags: List[str] | None = None,
        custom_fields: List[Dict[str, Any]] | None = None,
        due_at: str | None = None,
    ) -> str:
        """Update fields on an existing Zendesk ticket"""
        client = _require_client()
        fields = {
            k: v
            for k, v in {
                "subject": subject,
                "status": status,
                "priority": priority,
                "type": type,
                "assignee_id": assignee_id,
                "requester_id": requester_id,
                "tags": tags,
                "custom_fields": custom_fields,
                "due_at": due_at,
            }.items()
            if v is not None
        }
        updated = client.update_ticket(ticket_id=ticket_id, **fields)
        return json.dumps(
            {"message": "Ticket updated successfully", "ticket": updated}, indent=2
        )


# --- Prompts ---
TICKET_ANALYSIS_TEMPLATE = """
You are a helpful Zendesk support analyst. You've been asked to analyze ticket #{ticket_id}.

Please fetch the ticket info and comments to analyze it and provide:
1. A summary of the issue
2. The current status and timeline
3. Key points of interaction

Remember to be professional and focus on actionable insights.
"""

COMMENT_DRAFT_TEMPLATE = """
You are a helpful Zendesk support agent. You need to draft a response to ticket #{ticket_id}.

Please fetch the ticket info, comments and knowledge base to draft a professional and helpful response that:
1. Acknowledges the customer's concern
2. Addresses the specific issues raised
3. Provides clear next steps or ask for specific details need to proceed
4. Maintains a friendly and professional tone
5. Ask for confirmation before commenting on the ticket

The response should be formatted well and ready to be posted as a comment.
"""


@mcp.prompt()
def analyze_ticket(ticket_id: str) -> str:
    """Analyze a Zendesk ticket and provide insights"""
    return TICKET_ANALYSIS_TEMPLATE.format(ticket_id=ticket_id).strip()


@mcp.prompt()
def draft_ticket_response(ticket_id: str) -> str:
    """Draft a professional response to a Zendesk ticket"""
    return COMMENT_DRAFT_TEMPLATE.format(ticket_id=ticket_id).strip()


# --- Resources ---
@ttl_cache(ttl=3600)
def _get_cached_kb():
    client = _require_client()
    return client.get_all_articles()


@mcp.resource("zendesk://knowledge-base")
def knowledge_base() -> str:
    """Access to Zendesk Help Center articles and sections"""
    kb_data = _get_cached_kb()
    return json.dumps(
        {
            "knowledge_base": kb_data,
            "metadata": {
                "sections": len(kb_data),
                "total_articles": sum(
                    len(section["articles"]) for section in kb_data.values()
                ),
            },
        },
        indent=2,
    )
```

- [ ] **Step 2: Verify server loads without credentials**

Run: `uv run python -c "from zendesk_mcp_server.server import mcp; print('FastMCP OK'); print('Tools:', [t.name for t in mcp._tool_manager.list_tools()])"`
Expected: `FastMCP OK` and list of tool names

- [ ] **Step 3: Commit**

```bash
git add src/zendesk_mcp_server/server.py
git commit -m "Refactor server to FastMCP with Google OAuth auth"
```

### Task 4: Update entrypoints

**Files:**
- Modify: `src/zendesk_mcp_server/__init__.py`

- [ ] **Step 1: Rewrite __init__.py**

```python
# src/zendesk_mcp_server/__init__.py
from .server import mcp


def main():
    mcp.run(transport="stdio")


def main_http():
    mcp.run(transport="streamable-http")


__all__ = ["main", "main_http", "mcp"]
```

- [ ] **Step 2: Verify stdio entrypoint**

Run: `ZENDESK_SUBDOMAIN=test ZENDESK_EMAIL=test@test.com ZENDESK_API_KEY=fake uv run python -c "from zendesk_mcp_server import main; print('stdio OK')"`
Expected: `stdio OK`

- [ ] **Step 3: Verify HTTP entrypoint**

Run: `ZENDESK_SUBDOMAIN=test ZENDESK_EMAIL=test@test.com ZENDESK_API_KEY=fake uv run python -c "from zendesk_mcp_server import main_http; print('http OK')"`
Expected: `http OK`

- [ ] **Step 4: Commit**

```bash
git add src/zendesk_mcp_server/__init__.py
git commit -m "Update entrypoints for FastMCP"
```

---

## Chunk 3: Cloud Run deployment & testing

### Task 5: Remove IAP and allow unauthenticated

- [ ] **Step 1: Remove IAP from Cloud Run service**

```bash
gcloud beta run deploy zendesk-mcp \
  --region us-central1 \
  --image $(gcloud run revisions list --service=zendesk-mcp --region=us-central1 --format="value(image)" --limit=1) \
  --no-iap \
  --quiet
```

- [ ] **Step 2: Allow unauthenticated access (OAuth discovery must be public)**

```bash
gcloud run services add-iam-policy-binding zendesk-mcp \
  --region=us-central1 \
  --member="allUsers" \
  --role="roles/run.invoker"
```

- [ ] **Step 3: Set new env vars**

```bash
gcloud run services update zendesk-mcp \
  --region us-central1 \
  --set-env-vars="ZENDESK_SUBDOMAIN=superdispatchhelp,ZENDESK_EMAIL=rukhsora@superdispatch.com,ALLOWED_EMAILS=far@superdispatch.com;matt.bradley@superdispatch.com;rukhsora@superdispatch.com;lyubov@superdispatch.com;dave.mendelson@superdispatch.com,RESOURCE_SERVER_URL=https://zendesk-mcp.superdispatch.org"
```

Note: `GOOGLE_CLIENT_ID` added after OAuth Client is created.

### Task 6: Create Google OAuth Client

- [ ] **Step 1: Create OAuth consent screen** (if not already configured)

GCP Console → APIs & Services → OAuth consent screen
- User type: Internal (restricts to `@superdispatch.com` Google Workspace)
- Scopes: `openid`, `email`

- [ ] **Step 2: Create OAuth Client ID**

GCP Console → APIs & Services → Credentials → Create Credentials → OAuth Client ID
- Type: Web application
- Name: `zendesk-mcp-connector`
- Authorized redirect URIs: TBD (inspect Claude Desktop's redirect during first connection attempt, then update)

- [ ] **Step 3: Set GOOGLE_CLIENT_ID on Cloud Run**

```bash
gcloud run services update zendesk-mcp \
  --region us-central1 \
  --update-env-vars="GOOGLE_CLIENT_ID=<client-id-from-step-2>"
```

### Task 7: Deploy and test

- [ ] **Step 1: Deploy from source**

```bash
gcloud run deploy zendesk-mcp \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --quiet
```

- [ ] **Step 2: Verify discovery endpoint is publicly accessible**

```bash
curl -s https://zendesk-mcp.superdispatch.org/.well-known/oauth-protected-resource | jq .
```

Expected: JSON with `authorization_servers` containing `https://accounts.google.com`

- [ ] **Step 3: Verify unauthenticated MCP call is rejected**

```bash
curl -s -X POST https://zendesk-mcp.superdispatch.org/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Expected: 401 Unauthorized

- [ ] **Step 4: Test from Claude Desktop**

In Claude Desktop:
1. Settings → Connectors → Add custom connector
2. URL: `https://zendesk-mcp.superdispatch.org/mcp`
3. Advanced: enter Google OAuth Client ID and Secret
4. Attempt connection → Google login should appear
5. Sign in with `@superdispatch.com` account

- [ ] **Step 5: Commit all changes and push**

```bash
git add -A
git commit -m "Deploy FastMCP with Google OAuth to Cloud Run"
git push origin main
```

### Task 8: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md with OAuth details**

Add to the existing CLAUDE.md:
- Auth section explaining Google OAuth setup
- Updated env vars table
- Connector setup instructions for users
- Fallback plan reference

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "Update CLAUDE.md with Google OAuth documentation"
git push origin main
```
