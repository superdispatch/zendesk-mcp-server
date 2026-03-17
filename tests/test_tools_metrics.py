"""Tests for metrics tool registration and argument passing."""

import json
from unittest.mock import MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from zendesk_mcp_server.tools.metrics import register


@pytest.mark.asyncio
async def test_register_adds_all_metrics_tools():
    mcp = FastMCP("test")
    client = MagicMock()
    register(mcp, client)
    tool_names = [t.name for t in await mcp.list_tools()]
    assert "get_ticket_metrics" in tool_names
    assert "get_sla_policies" in tool_names
    assert "get_satisfaction_ratings" in tool_names


@pytest.mark.asyncio
async def test_get_ticket_metrics_calls_client_with_correct_ticket_id():
    mcp = FastMCP("test")
    client = MagicMock()
    client.get_ticket_metrics.return_value = {
        "ticket_metric": {
            "id": 99,
            "ticket_id": 42,
            "reopens": 1,
            "replies": 3,
            "reply_time_in_minutes": {"calendar": 15, "business": 10},
            "full_resolution_time_in_minutes": {"calendar": 120, "business": 60},
            "requester_wait_time_in_minutes": {"calendar": 30, "business": 20},
        }
    }
    register(mcp, client)

    result = await mcp.call_tool("get_ticket_metrics", {"ticket_id": 42})

    client.get_ticket_metrics.assert_called_once_with(ticket_id=42)
    content_list = result[0]
    parsed = json.loads(content_list[0].text)
    assert parsed["ticket_metric"]["ticket_id"] == 42
    assert parsed["ticket_metric"]["reopens"] == 1
    assert parsed["ticket_metric"]["replies"] == 3


@pytest.mark.asyncio
async def test_get_sla_policies_calls_client_correctly():
    mcp = FastMCP("test")
    client = MagicMock()
    client.get_sla_policies.return_value = {
        "sla_policies": [
            {"id": 1, "title": "Urgent", "filter": {}, "policy_metrics": []},
            {"id": 2, "title": "Normal", "filter": {}, "policy_metrics": []},
        ]
    }
    register(mcp, client)

    result = await mcp.call_tool("get_sla_policies", {})

    client.get_sla_policies.assert_called_once()
    content_list = result[0]
    parsed = json.loads(content_list[0].text)
    assert len(parsed["sla_policies"]) == 2
    assert parsed["sla_policies"][0]["title"] == "Urgent"


@pytest.mark.asyncio
async def test_get_satisfaction_ratings_passes_filters():
    mcp = FastMCP("test")
    client = MagicMock()
    client.get_satisfaction_ratings.return_value = {
        "satisfaction_ratings": [
            {"id": 10, "score": "good", "ticket_id": 100},
        ],
        "count": 1,
        "next_page": "https://example.com/next",
        "previous_page": None,
    }
    register(mcp, client)

    result = await mcp.call_tool(
        "get_satisfaction_ratings",
        {
            "score": "good",
            "start_time": "2025-01-01",
            "end_time": "2025-06-01",
            "page": 2,
        },
    )

    client.get_satisfaction_ratings.assert_called_once_with(
        score="good",
        start_time="2025-01-01",
        end_time="2025-06-01",
        page=2,
    )
    content_list = result[0]
    parsed = json.loads(content_list[0].text)
    assert parsed["results"] == [{"id": 10, "score": "good", "ticket_id": 100}]
    assert parsed["count"] == 1
    assert parsed["page"] == 2
    assert parsed["has_more"] is True


@pytest.mark.asyncio
async def test_get_satisfaction_ratings_defaults():
    mcp = FastMCP("test")
    client = MagicMock()
    client.get_satisfaction_ratings.return_value = {
        "satisfaction_ratings": [],
        "count": 0,
        "next_page": None,
        "previous_page": None,
    }
    register(mcp, client)

    result = await mcp.call_tool("get_satisfaction_ratings", {})

    client.get_satisfaction_ratings.assert_called_once_with(
        score=None,
        start_time=None,
        end_time=None,
        page=1,
    )
    content_list = result[0]
    parsed = json.loads(content_list[0].text)
    assert parsed["results"] == []
    assert parsed["count"] == 0
    assert parsed["page"] == 1
    assert parsed["has_more"] is False
