import hashlib
from mcp.server.auth.provider import AccessToken, TokenVerifier
from oauth2_provider.models import get_access_token_model
from core.mcp.sync_to_async_with_db_cleanup import sync_to_async_with_db_cleanup


def _lookup_access_token(token):
    """Look up a django-oauth-toolkit access token by its checksum.

    django-oauth-toolkit always stores a SHA-256 checksum of the raw token in
    token_checksum (and may redact the plaintext token column at rest under
    RFC 9700 storage), so we match on the checksum exactly as django-oauth-toolkit's
    own resource server does. See oauth2_provider.oauth2_validators.
    """
    token_checksum = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return (
        get_access_token_model()
        .objects.select_related("application", "user")
        .filter(token_checksum=token_checksum)
        .first()
    )


class DjangoOAuthToolkitTokenVerifier(TokenVerifier):
    """Resource-server token verifier backed by django-oauth-toolkit.

    The MCP SDK calls verify_token for the bearer token on every /mcp
    request. We look the token up in django-oauth-toolkit's AccessToken table
    over the shared database and translate a valid one into the SDK's AccessToken,
    which the SDK then exposes to handlers via get_access_token().
    """

    async def verify_token(self, token: str) -> AccessToken | None:
        stored_token = await sync_to_async_with_db_cleanup(_lookup_access_token)(token)

        # Unknown or expired token. `is_valid()` with no scopes checks expiry only.
        if stored_token is None or not stored_token.is_valid():
            return None

        # Mirror the issuance-time `is_usable()` gate so a disabled application's
        # live tokens stop working. The default implementation returns True.
        application = stored_token.application
        if application is None or not application.is_usable(request=None):
            return None

        return AccessToken(
            token=token,
            client_id=str(application.client_id),
            scopes=stored_token.scope.split(),
            subject=str(stored_token.user_id)
            if stored_token.user_id is not None
            else None,
            expires_at=int(stored_token.expires.timestamp()),
        )
