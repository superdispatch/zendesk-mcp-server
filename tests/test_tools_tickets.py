from unittest.mock import MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from zendesk_mcp_server.tools.tickets import register


@pytest.mark.asyncio
async def test_register_read_tools():
    mcp = FastMCP("test")
    client = MagicMock()
    register(mcp, client, read_only=False)
    tool_names = [t.name for t in await mcp.list_tools()]
    assert "get_ticket" in tool_names
    assert "get_tickets" in tool_names
    assert "get_ticket_comments" in tool_names
    assert "get_ticket_attachment" in tool_names


@pytest.mark.asyncio
async def test_register_write_tools_when_not_read_only():
    mcp = FastMCP("test")
    client = MagicMock()
    register(mcp, client, read_only=False)
    tool_names = [t.name for t in await mcp.list_tools()]
    assert "create_ticket" in tool_names
    assert "create_ticket_comment" in tool_names
    assert "update_ticket" in tool_names


@pytest.mark.asyncio
async def test_register_hides_write_tools_when_read_only():
    mcp = FastMCP("test")
    client = MagicMock()
    register(mcp, client, read_only=True)
    tool_names = [t.name for t in await mcp.list_tools()]
    assert "create_ticket" not in tool_names
    assert "get_ticket" in tool_names
