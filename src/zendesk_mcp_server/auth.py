import logging
from typing import Set

import httpx
from cachetools import TTLCache
from mcp.server.auth.provider import AccessToken, TokenVerifier

logger = logging.getLogger("zendesk-mcp-server")

GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleTokenVerifier(TokenVerifier):
    """Validates Google OAuth access tokens and checks email allowlist."""

    def __init__(self, allowed_emails: Set[str], cache_ttl: int = 300):
        self._allowed_emails = allowed_emails
        self._cache: TTLCache[str, AccessToken | None] = TTLCache(
            maxsize=256, ttl=cache_ttl
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        cached = self._cache.get(token)
        if cached is not None:
            return cached

        result = await self._verify_with_google(token)
        self._cache[token] = result
        return result

    async def _verify_with_google(self, token: str) -> AccessToken | None:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    GOOGLE_USERINFO_URL,
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code != 200:
                    logger.warning("Google userinfo returned %d", resp.status_code)
                    return None
                info = resp.json()
        except httpx.HTTPError as e:
            logger.error("Google userinfo request failed: %s", e)
            return None

        if not info.get("email_verified"):
            logger.warning("Email not verified for %s", info.get("email"))
            return None

        email = info.get("email", "")
        if email not in self._allowed_emails:
            logger.warning("Email %s not in allowlist", email)
            return None

        return AccessToken(
            token=token,
            client_id=info.get("sub", ""),
            scopes=["openid", "email"],
        )
