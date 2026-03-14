import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import httpx

from zendesk_mcp_server.auth import GoogleTokenVerifier


def _mock_response(status_code: int, json_data: dict) -> httpx.Response:
    """Create a real httpx.Response with mocked data."""
    resp = httpx.Response(status_code=status_code, json=json_data)
    return resp


@pytest.mark.asyncio
async def test_verify_token_success():
    verifier = GoogleTokenVerifier(allowed_emails={"user@superdispatch.com"})
    resp = _mock_response(200, {
        "email": "user@superdispatch.com",
        "email_verified": True,
        "sub": "12345",
    })

    with patch("zendesk_mcp_server.auth.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = resp
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await verifier.verify_token("valid-token")

    assert result is not None
    assert result.client_id == "12345"
    assert result.scopes == ["openid", "email"]


@pytest.mark.asyncio
async def test_verify_token_email_not_allowed():
    verifier = GoogleTokenVerifier(allowed_emails={"admin@superdispatch.com"})
    resp = _mock_response(200, {
        "email": "hacker@evil.com",
        "email_verified": True,
        "sub": "99999",
    })

    with patch("zendesk_mcp_server.auth.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = resp
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await verifier.verify_token("some-token")

    assert result is None


@pytest.mark.asyncio
async def test_verify_token_invalid():
    verifier = GoogleTokenVerifier(allowed_emails={"user@superdispatch.com"})
    resp = _mock_response(401, {"error": "invalid_token"})

    with patch("zendesk_mcp_server.auth.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = resp
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await verifier.verify_token("bad-token")

    assert result is None


@pytest.mark.asyncio
async def test_verify_token_email_not_verified():
    verifier = GoogleTokenVerifier(allowed_emails={"user@superdispatch.com"})
    resp = _mock_response(200, {
        "email": "user@superdispatch.com",
        "email_verified": False,
        "sub": "12345",
    })

    with patch("zendesk_mcp_server.auth.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = resp
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await verifier.verify_token("some-token")

    assert result is None
