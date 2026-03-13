# Zendesk MCP Server

Fork of [reminia/zendesk-mcp-server](https://github.com/reminia/zendesk-mcp-server) with Cloud Run deployment support.

## Architecture

```
Claude Desktop / Cowork  →  IAP (Google auth)  →  Cloud Run  →  Zendesk API
```

- **Transport**: stdio (local) or Streamable HTTP (Cloud Run)
- **Auth to MCP server**: Google IAP — restricted to `@superdispatch.com`
- **Auth to Zendesk**: API token via env vars (service account)
- **Write control**: `READ_ONLY=true` env var hides and blocks write tools

## Deployment

- **GCP project**: `superdispatch-tools`
- **Region**: `us-central1`
- **Service**: `zendesk-mcp`
- **URL**: `https://zendesk-mcp.superdispatch.org/mcp`
- **IAP**: enabled, domain-wide access for `@superdispatch.com`

### Deploy a new revision

```bash
gcloud run deploy zendesk-mcp \
  --source . \
  --region us-central1 \
  --quiet
```

### Manage IAP access

```bash
# Grant a user
gcloud beta iap web add-iam-policy-binding \
  --member=user:someone@superdispatch.com \
  --role=roles/iap.httpsResourceAccessor \
  --region=us-central1 \
  --resource-type=cloud-run \
  --service=zendesk-mcp

# Grant entire domain
gcloud beta iap web add-iam-policy-binding \
  --member=domain:superdispatch.com \
  --role=roles/iap.httpsResourceAccessor \
  --region=us-central1 \
  --resource-type=cloud-run \
  --service=zendesk-mcp
```

## Development

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

### Setup

```bash
cp .env.example .env  # fill in Zendesk credentials
uv sync
```

### Run locally (stdio)

```bash
uv run zendesk
```

### Run locally (HTTP, simulates Cloud Run)

```bash
uv run zendesk-http
# Server starts on http://localhost:8080/mcp
```

### Test

```bash
# Verify server loads
ZENDESK_SUBDOMAIN=test ZENDESK_EMAIL=test@test.com ZENDESK_API_KEY=fake \
  uv run python -c "from zendesk_mcp_server.server import main, main_http; print('OK')"
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ZENDESK_SUBDOMAIN` | Yes | Zendesk instance subdomain (e.g. `superdispatchhelp`) |
| `ZENDESK_EMAIL` | Yes | Email for Zendesk API auth |
| `ZENDESK_API_KEY` | Yes | Zendesk API token |
| `READ_ONLY` | No | Set `true` to disable write tools |
| `PORT` | No | HTTP server port (default: `8080`, set by Cloud Run) |
| `HOST` | No | HTTP server bind address (default: `0.0.0.0`) |

## MCP Tools

### Read tools (always available)
- `get_ticket` — retrieve a ticket by ID
- `get_tickets` — list tickets with pagination
- `get_ticket_comments` — get all comments for a ticket
- `get_ticket_attachment` — fetch an attachment as base64

### Write tools (hidden when `READ_ONLY=true`)
- `create_ticket` — create a new ticket
- `create_ticket_comment` — add a comment to a ticket
- `update_ticket` — update ticket fields

### Resources
- `zendesk://knowledge-base` — Help Center articles (cached 1 hour)

### Prompts
- `analyze-ticket` — analyze a ticket and provide insights
- `draft-ticket-response` — draft a professional response
