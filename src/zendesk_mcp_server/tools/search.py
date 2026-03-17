"""Search-related MCP tools (always available, regardless of read_only)."""

import json

from mcp.server.fastmcp import FastMCP

from zendesk_mcp_server.zendesk_client import ZendeskClient


def register(mcp: FastMCP, client: ZendeskClient) -> None:
    """Register search tools on the MCP server."""

    @mcp.tool()
    def search_tickets(
        query: str,
        status: str | None = None,
        assignee: str | None = None,
        group: str | None = None,
        tags: list[str] | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
        sort_by: str = "relevance",
        sort_order: str = "desc",
        page: int = 1,
    ) -> str:
        """Search Zendesk tickets using query text and optional filters.

        Filters narrow results by status, assignee, group, tags, or date range.
        Dates should be in YYYY-MM-DD format.
        """
        filters: dict[str, str] = {}
        if status is not None:
            filters["status"] = status
        if assignee is not None:
            filters["assignee"] = assignee
        if group is not None:
            filters["group"] = group
        if tags is not None:
            filters["tags"] = ",".join(tags)
        if created_after is not None:
            filters["created>"] = created_after
        if created_before is not None:
            filters["created<"] = created_before

        data = client.search(
            query=query,
            type="ticket",
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
        )
        return json.dumps({
            "results": data.get("results", []),
            "count": data.get("count", 0),
            "page": page,
            "has_more": data.get("next_page") is not None,
        })

    @mcp.tool()
    def search_users(
        query: str,
        role: str | None = None,
        organization: str | None = None,
        page: int = 1,
    ) -> str:
        """Search Zendesk users by name, email, or other attributes."""
        filters: dict[str, str] = {}
        if role is not None:
            filters["role"] = role
        if organization is not None:
            filters["organization"] = organization

        data = client.search(
            query=query,
            type="user",
            filters=filters,
            page=page,
        )
        return json.dumps({
            "results": data.get("results", []),
            "count": data.get("count", 0),
            "page": page,
            "has_more": data.get("next_page") is not None,
        })

    @mcp.tool()
    def search_organizations(
        query: str,
        tags: list[str] | None = None,
        page: int = 1,
    ) -> str:
        """Search Zendesk organizations by name or tags."""
        filters: dict[str, str] = {}
        if tags is not None:
            filters["tags"] = ",".join(tags)

        data = client.search(
            query=query,
            type="organization",
            filters=filters,
            page=page,
        )
        return json.dumps({
            "results": data.get("results", []),
            "count": data.get("count", 0),
            "page": page,
            "has_more": data.get("next_page") is not None,
        })

    @mcp.tool()
    def search_articles(
        query: str,
        locale: str | None = None,
        category_id: int | None = None,
        section_id: int | None = None,
        page: int = 1,
    ) -> str:
        """Search Zendesk Help Center articles by keyword."""
        data = client.search_articles(
            query=query,
            locale=locale,
            category_id=category_id,
            section_id=section_id,
            page=page,
        )
        return json.dumps({
            "results": data.get("results", []),
            "count": data.get("count", 0),
            "page": page,
            "has_more": data.get("next_page") is not None,
        })
