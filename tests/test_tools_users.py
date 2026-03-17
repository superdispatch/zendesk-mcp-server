"""Tests for users & organizations tool registration and argument passing."""

import json
from unittest.mock import MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from zendesk_mcp_server.tools.users import register


@pytest.mark.asyncio
async def test_register_adds_all_user_tools():
    mcp = FastMCP("test")
    client = MagicMock()
    register(mcp, client)
    tool_names = [t.name for t in await mcp.list_tools()]
    assert "get_user" in tool_names
    assert "get_organization" in tool_names
    assert "get_organization_tickets" in tool_names
    assert "get_group_memberships" in tool_names


@pytest.mark.asyncio
async def test_get_user_calls_client_with_correct_user_id():
    mcp = FastMCP("test")
    client = MagicMock()
    client.get_user.return_value = {
        "user": {
            "id": 123,
            "name": "Jane Doe",
            "email": "jane@example.com",
            "role": "end-user",
        }
    }
    register(mcp, client)

    result = await mcp.call_tool("get_user", {"user_id": 123})

    client.get_user.assert_called_once_with(user_id=123)
    content_list = result[0]
    parsed = json.loads(content_list[0].text)
    assert parsed["user"]["id"] == 123
    assert parsed["user"]["name"] == "Jane Doe"


@pytest.mark.asyncio
async def test_get_organization_calls_client_with_correct_org_id():
    mcp = FastMCP("test")
    client = MagicMock()
    client.get_organization.return_value = {
        "organization": {
            "id": 456,
            "name": "Acme Corp",
            "domain_names": ["acme.com"],
        }
    }
    register(mcp, client)

    result = await mcp.call_tool("get_organization", {"organization_id": 456})

    client.get_organization.assert_called_once_with(organization_id=456)
    content_list = result[0]
    parsed = json.loads(content_list[0].text)
    assert parsed["organization"]["id"] == 456
    assert parsed["organization"]["name"] == "Acme Corp"


@pytest.mark.asyncio
async def test_get_organization_tickets_returns_pagination_shape():
    mcp = FastMCP("test")
    client = MagicMock()
    client.get_organization_tickets.return_value = {
        "tickets": [
            {"id": 1, "subject": "Issue A"},
            {"id": 2, "subject": "Issue B"},
        ],
        "count": 2,
        "next_page": "https://example.com/next",
        "previous_page": None,
    }
    register(mcp, client)

    result = await mcp.call_tool(
        "get_organization_tickets", {"organization_id": 456, "page": 2}
    )

    client.get_organization_tickets.assert_called_once_with(
        organization_id=456, page=2
    )
    content_list = result[0]
    parsed = json.loads(content_list[0].text)
    assert parsed["results"] == [
        {"id": 1, "subject": "Issue A"},
        {"id": 2, "subject": "Issue B"},
    ]
    assert parsed["count"] == 2
    assert parsed["page"] == 2
    assert parsed["has_more"] is True


@pytest.mark.asyncio
async def test_get_organization_tickets_default_page():
    mcp = FastMCP("test")
    client = MagicMock()
    client.get_organization_tickets.return_value = {
        "tickets": [],
        "count": 0,
        "next_page": None,
        "previous_page": None,
    }
    register(mcp, client)

    result = await mcp.call_tool(
        "get_organization_tickets", {"organization_id": 789}
    )

    client.get_organization_tickets.assert_called_once_with(
        organization_id=789, page=1
    )
    content_list = result[0]
    parsed = json.loads(content_list[0].text)
    assert parsed["page"] == 1
    assert parsed["has_more"] is False


@pytest.mark.asyncio
async def test_get_group_memberships_with_group_id():
    mcp = FastMCP("test")
    client = MagicMock()
    client.get_group_memberships.return_value = {
        "group_memberships": [
            {"id": 10, "user_id": 100, "group_id": 5},
        ],
        "count": 1,
        "next_page": None,
        "previous_page": None,
    }
    register(mcp, client)

    result = await mcp.call_tool(
        "get_group_memberships", {"group_id": 5, "page": 1}
    )

    client.get_group_memberships.assert_called_once_with(group_id=5, page=1)
    client.get_groups.assert_not_called()
    content_list = result[0]
    parsed = json.loads(content_list[0].text)
    assert parsed["results"] == [{"id": 10, "user_id": 100, "group_id": 5}]
    assert parsed["count"] == 1
    assert parsed["page"] == 1
    assert parsed["has_more"] is False


@pytest.mark.asyncio
async def test_get_group_memberships_without_group_id():
    mcp = FastMCP("test")
    client = MagicMock()
    client.get_groups.return_value = {
        "groups": [
            {"id": 1, "name": "Support"},
            {"id": 2, "name": "Sales"},
        ],
        "count": 2,
        "next_page": "https://example.com/next",
        "previous_page": None,
    }
    register(mcp, client)

    result = await mcp.call_tool("get_group_memberships", {"page": 1})

    client.get_groups.assert_called_once_with(page=1)
    client.get_group_memberships.assert_not_called()
    content_list = result[0]
    parsed = json.loads(content_list[0].text)
    assert parsed["results"] == [
        {"id": 1, "name": "Support"},
        {"id": 2, "name": "Sales"},
    ]
    assert parsed["count"] == 2
    assert parsed["page"] == 1
    assert parsed["has_more"] is True
