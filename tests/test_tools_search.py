"""Tests for search tool registration and argument passing."""

import json
from unittest.mock import MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from zendesk_mcp_server.tools.search import register


@pytest.mark.asyncio
async def test_register_adds_all_search_tools():
    mcp = FastMCP("test")
    client = MagicMock()
    register(mcp, client)
    tool_names = [t.name for t in await mcp.list_tools()]
    assert "search_tickets" in tool_names
    assert "search_users" in tool_names
    assert "search_organizations" in tool_names
    assert "search_articles" in tool_names


@pytest.mark.asyncio
async def test_search_tickets_builds_correct_filters():
    """search_tickets should translate its keyword args into the right
    client.search() call with type='ticket' and a filters dict."""
    mcp = FastMCP("test")
    client = MagicMock()
    client.search.return_value = {
        "results": [{"id": 1}],
        "count": 1,
        "next_page": None,
        "previous_page": None,
    }
    register(mcp, client)

    # Invoke the tool through FastMCP's call_tool (public API)
    result = await mcp.call_tool(
        "search_tickets",
        {
            "query": "login issue",
            "status": "open",
            "assignee": "agent@example.com",
            "group": "Support",
            "tags": ["vip", "urgent"],
            "created_after": "2025-01-01",
            "created_before": "2025-06-01",
            "sort_by": "updated_at",
            "sort_order": "asc",
            "page": 2,
        },
    )

    client.search.assert_called_once()
    call_kwargs = client.search.call_args
    assert call_kwargs.kwargs["query"] == "login issue"
    assert call_kwargs.kwargs["type"] == "ticket"
    assert call_kwargs.kwargs["sort_by"] == "updated_at"
    assert call_kwargs.kwargs["sort_order"] == "asc"
    assert call_kwargs.kwargs["page"] == 2

    filters = call_kwargs.kwargs["filters"]
    assert filters["status"] == "open"
    assert filters["assignee"] == "agent@example.com"
    assert filters["group"] == "Support"
    assert filters["tags"] == "vip,urgent"
    assert filters["created>"] == "2025-01-01"
    assert filters["created<"] == "2025-06-01"


@pytest.mark.asyncio
async def test_search_tickets_omits_none_filters():
    """When optional params are None they should not appear in filters."""
    mcp = FastMCP("test")
    client = MagicMock()
    client.search.return_value = {
        "results": [],
        "count": 0,
        "next_page": None,
        "previous_page": None,
    }
    register(mcp, client)

    await mcp.call_tool("search_tickets", {"query": "hello"})

    call_kwargs = client.search.call_args
    filters = call_kwargs.kwargs["filters"]
    assert filters == {}


@pytest.mark.asyncio
async def test_search_tickets_returns_expected_json_shape():
    mcp = FastMCP("test")
    client = MagicMock()
    client.search.return_value = {
        "results": [{"id": 42, "subject": "Test"}],
        "count": 1,
        "next_page": "https://example.com/next",
        "previous_page": None,
    }
    register(mcp, client)

    result = await mcp.call_tool("search_tickets", {"query": "test"})
    # call_tool returns (list_of_TextContent, metadata_dict)
    content_list = result[0]
    parsed = json.loads(content_list[0].text)
    assert parsed["results"] == [{"id": 42, "subject": "Test"}]
    assert parsed["count"] == 1
    assert parsed["page"] == 1
    assert parsed["has_more"] is True


@pytest.mark.asyncio
async def test_search_users_calls_client_correctly():
    mcp = FastMCP("test")
    client = MagicMock()
    client.search.return_value = {
        "results": [],
        "count": 0,
        "next_page": None,
        "previous_page": None,
    }
    register(mcp, client)

    await mcp.call_tool(
        "search_users",
        {"query": "john", "role": "agent", "organization": "Acme", "page": 3},
    )

    client.search.assert_called_once()
    call_kwargs = client.search.call_args
    assert call_kwargs.kwargs["type"] == "user"
    assert call_kwargs.kwargs["query"] == "john"
    assert call_kwargs.kwargs["page"] == 3
    filters = call_kwargs.kwargs["filters"]
    assert filters["role"] == "agent"
    assert filters["organization"] == "Acme"


@pytest.mark.asyncio
async def test_search_organizations_calls_client_correctly():
    mcp = FastMCP("test")
    client = MagicMock()
    client.search.return_value = {
        "results": [],
        "count": 0,
        "next_page": None,
        "previous_page": None,
    }
    register(mcp, client)

    await mcp.call_tool(
        "search_organizations",
        {"query": "acme", "tags": ["enterprise", "premium"], "page": 1},
    )

    client.search.assert_called_once()
    call_kwargs = client.search.call_args
    assert call_kwargs.kwargs["type"] == "organization"
    filters = call_kwargs.kwargs["filters"]
    assert filters["tags"] == "enterprise,premium"


@pytest.mark.asyncio
async def test_search_articles_calls_client_search_articles():
    mcp = FastMCP("test")
    client = MagicMock()
    client.search_articles.return_value = {
        "results": [{"id": 10, "title": "How to reset"}],
        "count": 1,
        "next_page": None,
        "previous_page": None,
    }
    register(mcp, client)

    result = await mcp.call_tool(
        "search_articles",
        {
            "query": "reset password",
            "locale": "en-us",
            "category_id": 5,
            "section_id": 12,
            "page": 2,
        },
    )

    client.search_articles.assert_called_once_with(
        query="reset password",
        locale="en-us",
        category_id=5,
        section_id=12,
        page=2,
    )

    content_list = result[0]
    parsed = json.loads(content_list[0].text)
    assert parsed["results"] == [{"id": 10, "title": "How to reset"}]
    assert parsed["count"] == 1
    assert parsed["page"] == 2
    assert parsed["has_more"] is False
