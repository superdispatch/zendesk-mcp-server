"""Views-related MCP tools (always available, regardless of read_only)."""

import json

from mcp.server.fastmcp import FastMCP

from zendesk_mcp_server.zendesk_client import ZendeskClient


def register(mcp: FastMCP, client: ZendeskClient) -> None:
    """Register views tools on the MCP server."""

    @mcp.tool()
    def get_views(page: int = 1) -> str:
        """List all shared and personal Zendesk views available to the current user."""
        data = client.get_views(page=page)
        return json.dumps({
            "results": data.get("views", []),
            "count": data.get("count", 0),
            "page": page,
            "has_more": data.get("next_page") is not None,
        })

    @mcp.tool()
    def get_view_tickets(view_id: int, page: int = 1) -> str:
        """List tickets belonging to a specific Zendesk view."""
        data = client.get_view_tickets(view_id=view_id, page=page)
        return json.dumps({
            "results": data.get("tickets", []),
            "count": data.get("count", 0),
            "page": page,
            "has_more": data.get("next_page") is not None,
        })

    @mcp.tool()
    def get_view_count(view_id: int) -> str:
        """Get the ticket count for a specific Zendesk view."""
        data = client.get_view_count(view_id=view_id)
        return json.dumps(data)
