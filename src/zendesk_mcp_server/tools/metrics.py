"""Metrics & SLA-related MCP tools (always available, regardless of read_only)."""

import json

from mcp.server.fastmcp import FastMCP

from zendesk_mcp_server.zendesk_client import ZendeskClient


def register(mcp: FastMCP, client: ZendeskClient) -> None:
    """Register metrics tools on the MCP server."""

    @mcp.tool()
    def get_ticket_metrics(ticket_id: int) -> str:
        """Get performance metrics for a specific Zendesk ticket.

        Includes first reply time, full resolution time, reopens, replies,
        and requester wait time.
        """
        data = client.get_ticket_metrics(ticket_id=ticket_id)
        return json.dumps(data)

    @mcp.tool()
    def get_sla_policies() -> str:
        """List all SLA policies configured in Zendesk."""
        data = client.get_sla_policies()
        return json.dumps(data)

    @mcp.tool()
    def get_satisfaction_ratings(
        score: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        page: int = 1,
    ) -> str:
        """List customer satisfaction ratings with optional filters.

        Score can be: good, bad, offered, unoffered.
        """
        data = client.get_satisfaction_ratings(
            score=score,
            start_time=start_time,
            end_time=end_time,
            page=page,
        )
        return json.dumps({
            "results": data.get("satisfaction_ratings", []),
            "count": data.get("count", 0),
            "page": page,
            "has_more": data.get("next_page") is not None,
        })
