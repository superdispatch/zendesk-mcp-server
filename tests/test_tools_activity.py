"""Tests for activity tool registration and argument passing."""

import json
from unittest.mock import MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from zendesk_mcp_server.tools.activity import register


@pytest.mark.asyncio
async def test_register_adds_all_activity_tools():
    mcp = FastMCP("test")
    client = MagicMock()
    register(mcp, client)
    tool_names = [t.name for t in await mcp.list_tools()]
    assert "get_agent_activity" in tool_names
    assert "get_ticket_audits" in tool_names


@pytest.mark.asyncio
async def test_get_agent_activity_calls_client_with_correct_params():
    mcp = FastMCP("test")
    client = MagicMock()
    client.get_agent_activity.return_value = {
        "results": [
            {"id": 1, "subject": "Ticket A"},
            {"id": 2, "subject": "Ticket B"},
        ],
        "count": 2,
        "next_page": "https://example.com/next",
        "previous_page": None,
    }
    register(mcp, client)

    result = await mcp.call_tool(
        "get_agent_activity",
        {
            "agent": "agent@example.com",
            "start_date": "2025-01-01",
            "end_date": "2025-06-01",
            "page": 2,
        },
    )

    client.get_agent_activity.assert_called_once_with(
        agent="agent@example.com",
        start_date="2025-01-01",
        end_date="2025-06-01",
        page=2,
    )
    content_list = result[0]
    parsed = json.loads(content_list[0].text)
    assert parsed["results"] == [
        {"id": 1, "subject": "Ticket A"},
        {"id": 2, "subject": "Ticket B"},
    ]
    assert parsed["count"] == 2
    assert parsed["page"] == 2
    assert parsed["has_more"] is True


@pytest.mark.asyncio
async def test_get_agent_activity_without_date_filters():
    mcp = FastMCP("test")
    client = MagicMock()
    client.get_agent_activity.return_value = {
        "results": [],
        "count": 0,
        "next_page": None,
        "previous_page": None,
    }
    register(mcp, client)

    result = await mcp.call_tool(
        "get_agent_activity",
        {"agent": "jane.doe"},
    )

    client.get_agent_activity.assert_called_once_with(
        agent="jane.doe",
        start_date=None,
        end_date=None,
        page=1,
    )
    content_list = result[0]
    parsed = json.loads(content_list[0].text)
    assert parsed["results"] == []
    assert parsed["count"] == 0
    assert parsed["page"] == 1
    assert parsed["has_more"] is False


@pytest.mark.asyncio
async def test_get_ticket_audits_calls_client_with_correct_ticket_id():
    mcp = FastMCP("test")
    client = MagicMock()
    client.get_ticket_audits.return_value = {
        "audits": [
            {"id": 100, "ticket_id": 42, "events": []},
            {"id": 101, "ticket_id": 42, "events": []},
        ],
        "count": 2,
        "next_page": "https://example.com/next",
        "previous_page": None,
    }
    register(mcp, client)

    result = await mcp.call_tool(
        "get_ticket_audits", {"ticket_id": 42, "page": 2}
    )

    client.get_ticket_audits.assert_called_once_with(ticket_id=42, page=2)
    content_list = result[0]
    parsed = json.loads(content_list[0].text)
    assert parsed["results"] == [
        {"id": 100, "ticket_id": 42, "events": []},
        {"id": 101, "ticket_id": 42, "events": []},
    ]
    assert parsed["count"] == 2
    assert parsed["page"] == 2
    assert parsed["has_more"] is True


@pytest.mark.asyncio
async def test_get_ticket_audits_default_page():
    mcp = FastMCP("test")
    client = MagicMock()
    client.get_ticket_audits.return_value = {
        "audits": [],
        "count": 0,
        "next_page": None,
        "previous_page": None,
    }
    register(mcp, client)

    result = await mcp.call_tool(
        "get_ticket_audits", {"ticket_id": 99}
    )

    client.get_ticket_audits.assert_called_once_with(ticket_id=99, page=1)
    content_list = result[0]
    parsed = json.loads(content_list[0].text)
    assert parsed["results"] == []
    assert parsed["count"] == 0
    assert parsed["page"] == 1
    assert parsed["has_more"] is False
