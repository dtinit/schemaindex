from mcp.server.auth.provider import AccessToken, TokenVerifier
from oauth2_provider.settings import oauth2_settings
from oauthlib.common import Request as OAuthlibRequest
from core.mcp.sync_to_async_with_db_cleanup import sync_to_async_with_db_cleanup


def _validate_bearer_token(token):
    validator = oauth2_settings.OAUTH2_VALIDATOR_CLASS()
    request = OAuthlibRequest(oauth2_settings.OAUTH2_PROTECTED_RESOURCE_IDENTIFIER)
    if not validator.validate_bearer_token(token, None, request):
        return None

    return request.access_token


class DjangoOAuthToolkitTokenVerifier(TokenVerifier):
    """Resource-server token verifier backed by django-oauth-toolkit.

    The MCP SDK calls verify_token for the bearer token on every /mcp
    request. We hand the token to django-oauth-toolkit for validation and
    translate a valid one into the SDK's AccessToken, which the SDK then
    exposes to handlers via get_access_token().
    """

    async def verify_token(self, token):
        stored_token = await sync_to_async_with_db_cleanup(_validate_bearer_token)(
            token
        )

        if stored_token is None:
            return None

        # django-oauth-toolkit leaves `application` unset on tokens minted from an
        # introspection response. We are our own authorization server, so every
        # token we accept has one; treat a missing application as a rejection
        # rather than inventing a client_id for it.
        application = stored_token.application
        if application is None:
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
