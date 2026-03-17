"""Tests for views tool registration and argument passing."""

import json
from unittest.mock import MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from zendesk_mcp_server.tools.views import register


@pytest.mark.asyncio
async def test_register_adds_all_view_tools():
    mcp = FastMCP("test")
    client = MagicMock()
    register(mcp, client)
    tool_names = [t.name for t in await mcp.list_tools()]
    assert "get_views" in tool_names
    assert "get_view_tickets" in tool_names
    assert "get_view_count" in tool_names


@pytest.mark.asyncio
async def test_get_views_returns_expected_json_shape():
    mcp = FastMCP("test")
    client = MagicMock()
    client.get_views.return_value = {
        "views": [{"id": 1, "title": "My open tickets"}],
        "count": 1,
        "next_page": "https://example.com/next",
        "previous_page": None,
    }
    register(mcp, client)

    result = await mcp.call_tool("get_views", {"page": 2})

    client.get_views.assert_called_once_with(page=2)
    content_list = result[0]
    parsed = json.loads(content_list[0].text)
    assert parsed["results"] == [{"id": 1, "title": "My open tickets"}]
    assert parsed["count"] == 1
    assert parsed["page"] == 2
    assert parsed["has_more"] is True


@pytest.mark.asyncio
async def test_get_views_default_page():
    mcp = FastMCP("test")
    client = MagicMock()
    client.get_views.return_value = {
        "views": [],
        "count": 0,
        "next_page": None,
        "previous_page": None,
    }
    register(mcp, client)

    result = await mcp.call_tool("get_views", {})

    client.get_views.assert_called_once_with(page=1)
    content_list = result[0]
    parsed = json.loads(content_list[0].text)
    assert parsed["page"] == 1
    assert parsed["has_more"] is False


@pytest.mark.asyncio
async def test_get_view_tickets_calls_client_with_correct_view_id():
    mcp = FastMCP("test")
    client = MagicMock()
    client.get_view_tickets.return_value = {
        "tickets": [{"id": 42, "subject": "Help me"}],
        "count": 1,
        "next_page": None,
        "previous_page": None,
    }
    register(mcp, client)

    result = await mcp.call_tool(
        "get_view_tickets", {"view_id": 123, "page": 3}
    )

    client.get_view_tickets.assert_called_once_with(view_id=123, page=3)
    content_list = result[0]
    parsed = json.loads(content_list[0].text)
    assert parsed["results"] == [{"id": 42, "subject": "Help me"}]
    assert parsed["count"] == 1
    assert parsed["page"] == 3
    assert parsed["has_more"] is False


@pytest.mark.asyncio
async def test_get_view_tickets_default_page():
    mcp = FastMCP("test")
    client = MagicMock()
    client.get_view_tickets.return_value = {
        "tickets": [],
        "count": 0,
        "next_page": None,
        "previous_page": None,
    }
    register(mcp, client)

    await mcp.call_tool("get_view_tickets", {"view_id": 99})

    client.get_view_tickets.assert_called_once_with(view_id=99, page=1)


@pytest.mark.asyncio
async def test_get_view_count_calls_client_with_correct_view_id():
    mcp = FastMCP("test")
    client = MagicMock()
    client.get_view_count.return_value = {
        "view_count": {
            "view_id": 25,
            "value": 42,
            "pretty": "42",
            "fresh": True,
        }
    }
    register(mcp, client)

    result = await mcp.call_tool("get_view_count", {"view_id": 25})

    client.get_view_count.assert_called_once_with(view_id=25)
    content_list = result[0]
    parsed = json.loads(content_list[0].text)
    assert parsed["view_count"]["view_id"] == 25
    assert parsed["view_count"]["value"] == 42
