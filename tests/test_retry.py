import urllib.error
from unittest.mock import patch, MagicMock
from zendesk_mcp_server.zendesk_client import ZendeskClient


def _make_client():
    with patch("zendesk_mcp_server.zendesk_client.Zenpy"):
        return ZendeskClient(subdomain="test", email="t@t.com", token="fake")


def test_api_request_retries_on_429():
    client = _make_client()
    # First call returns 429 with Retry-After: 0, second succeeds
    error_429 = urllib.error.HTTPError(
        url="http://test", code=429, msg="Rate Limited",
        hdrs=MagicMock(), fp=None
    )
    error_429.headers = {"Retry-After": "0"}
    success_response = MagicMock()
    success_response.read.return_value = b'{"results":[]}'
    success_response.__enter__ = MagicMock(return_value=success_response)
    success_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", side_effect=[error_429, success_response]):
        result = client._api_request("/test.json")
    assert result == {"results": []}


def test_api_request_raises_after_max_retries():
    client = _make_client()
    error_429 = urllib.error.HTTPError(
        url="http://test", code=429, msg="Rate Limited",
        hdrs=MagicMock(), fp=None
    )
    error_429.headers = {"Retry-After": "0"}

    with patch("urllib.request.urlopen", side_effect=[error_429, error_429, error_429, error_429]):
        try:
            client._api_request("/test.json")
            assert False, "Should have raised"
        except Exception as e:
            assert "429" in str(e) or "Rate" in str(e)
