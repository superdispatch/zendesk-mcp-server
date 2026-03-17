"""Activity MCP tools (always available, regardless of read_only)."""

import json

from mcp.server.fastmcp import FastMCP

from zendesk_mcp_server.zendesk_client import ZendeskClient


def register(mcp: FastMCP, client: ZendeskClient) -> None:
    """Register activity tools on the MCP server."""

    @mcp.tool()
    def get_agent_activity(
        agent: str,
        start_date: str | None = None,
        end_date: str | None = None,
        page: int = 1,
    ) -> str:
        """Search for tickets assigned to a specific agent.

        Agent can be an email address or name. Optionally filter by date range
        using start_date and end_date (YYYY-MM-DD format).
        """
        data = client.get_agent_activity(
            agent=agent,
            start_date=start_date,
            end_date=end_date,
            page=page,
        )
        return json.dumps({
            "results": data.get("results", []),
            "count": data.get("count", 0),
            "page": page,
            "has_more": data.get("next_page") is not None,
        })

    @mcp.tool()
    def get_ticket_audits(ticket_id: int, page: int = 1) -> str:
        """Get the audit log (change history) for a specific ticket.

        Returns a list of audit events including field changes, comments,
        and other modifications made to the ticket.
        """
        data = client.get_ticket_audits(ticket_id=ticket_id, page=page)
        return json.dumps({
            "results": data.get("audits", []),
            "count": data.get("count", 0),
            "page": page,
            "has_more": data.get("next_page") is not None,
        })
