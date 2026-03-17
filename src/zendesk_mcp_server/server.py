import json
import logging
import os

from cachetools.func import ttl_cache
from dotenv import load_dotenv
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

from zendesk_mcp_server.auth import GoogleTokenVerifier
from zendesk_mcp_server.tools.tickets import register as register_ticket_tools
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


# --- Auth (only when credentials are configured) ---
def _build_auth_kwargs() -> dict:
    """Return auth kwargs for FastMCP if credentials are configured."""
    if not ALLOWED_EMAILS or not RESOURCE_SERVER_URL:
        return {}
    return {
        "token_verifier": GoogleTokenVerifier(allowed_emails=ALLOWED_EMAILS),
        "auth": AuthSettings(
            issuer_url=AnyHttpUrl("https://accounts.google.com"),
            resource_server_url=AnyHttpUrl(RESOURCE_SERVER_URL),
            required_scopes=["openid", "email"],
        ),
    }


# --- FastMCP server ---
mcp = FastMCP(
    "Zendesk Server",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8080")),
    **_build_auth_kwargs(),
)


# --- Tools ---
if zendesk_client:
    register_ticket_tools(mcp, zendesk_client, read_only=READ_ONLY)


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
    if not zendesk_client:
        raise ValueError(
            "Zendesk credentials not configured. "
            "Set ZENDESK_SUBDOMAIN, ZENDESK_EMAIL, and ZENDESK_API_KEY env vars."
        )
    return zendesk_client.get_all_articles()


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
