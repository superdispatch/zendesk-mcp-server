"""Users & organizations MCP tools (always available, regardless of read_only)."""

import json

from mcp.server.fastmcp import FastMCP

from zendesk_mcp_server.zendesk_client import ZendeskClient


def register(mcp: FastMCP, client: ZendeskClient) -> None:
    """Register users and organizations tools on the MCP server."""

    @mcp.tool()
    def get_user(user_id: int) -> str:
        """Retrieve a Zendesk user by their ID.

        Returns user details including name, email, role, and organization.
        """
        data = client.get_user(user_id=user_id)
        return json.dumps(data)

    @mcp.tool()
    def get_organization(organization_id: int) -> str:
        """Retrieve a Zendesk organization by its ID.

        Returns organization details including name, domain names, and tags.
        """
        data = client.get_organization(organization_id=organization_id)
        return json.dumps(data)

    @mcp.tool()
    def get_organization_tickets(organization_id: int, page: int = 1) -> str:
        """List tickets belonging to a specific Zendesk organization."""
        data = client.get_organization_tickets(
            organization_id=organization_id, page=page
        )
        return json.dumps({
            "results": data.get("tickets", []),
            "count": data.get("count", 0),
            "page": page,
            "has_more": data.get("next_page") is not None,
        })

    @mcp.tool()
    def get_group_memberships(group_id: int | None = None, page: int = 1) -> str:
        """List group memberships for a specific group, or list all groups.

        If group_id is provided, returns memberships for that group.
        If group_id is omitted, returns a list of all available groups.
        """
        if group_id is not None:
            data = client.get_group_memberships(group_id=group_id, page=page)
            return json.dumps({
                "results": data.get("group_memberships", []),
                "count": data.get("count", 0),
                "page": page,
                "has_more": data.get("next_page") is not None,
            })
        else:
            data = client.get_groups(page=page)
            return json.dumps({
                "results": data.get("groups", []),
                "count": data.get("count", 0),
                "page": page,
                "has_more": data.get("next_page") is not None,
            })
