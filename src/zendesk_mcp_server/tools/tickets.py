"""Ticket-related MCP tools (read and write)."""

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from zendesk_mcp_server.zendesk_client import ZendeskClient


def register(mcp: FastMCP, client: ZendeskClient, read_only: bool) -> None:
    """Register ticket tools on the MCP server.

    Read tools are always registered.
    Write tools are only registered when *read_only* is ``False``.
    """

    # --- Read tools ---

    @mcp.tool()
    def get_ticket(ticket_id: int) -> str:
        """Retrieve a Zendesk ticket by its ID"""
        return json.dumps(client.get_ticket(ticket_id))

    @mcp.tool()
    def get_tickets(
        page: int = 1,
        per_page: int = 25,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> str:
        """Fetch the latest tickets with pagination support"""
        return json.dumps(
            client.get_tickets(
                page=page, per_page=per_page, sort_by=sort_by, sort_order=sort_order
            ),
            indent=2,
        )

    @mcp.tool()
    def get_ticket_comments(ticket_id: int) -> str:
        """Retrieve all comments for a Zendesk ticket by its ID"""
        return json.dumps(client.get_ticket_comments(ticket_id))

    @mcp.tool()
    def get_ticket_attachment(content_url: str) -> str:
        """Fetch a Zendesk ticket attachment by its content_url and return as base64-encoded data.

        Use the attachment URLs returned by get_ticket_comments.
        """
        result = client.get_ticket_attachment(content_url)
        return json.dumps(
            {"content_type": result["content_type"], "data_base64": result["data"]}
        )

    # --- Write tools (conditional) ---

    if not read_only:

        @mcp.tool()
        def create_ticket(
            subject: str,
            description: str,
            requester_id: int | None = None,
            assignee_id: int | None = None,
            priority: str | None = None,
            type: str | None = None,
            tags: list[str] | None = None,
            custom_fields: list[dict[str, Any]] | None = None,
        ) -> str:
            """Create a new Zendesk ticket"""
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
            tags: list[str] | None = None,
            custom_fields: list[dict[str, Any]] | None = None,
            due_at: str | None = None,
        ) -> str:
            """Update fields on an existing Zendesk ticket"""
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
