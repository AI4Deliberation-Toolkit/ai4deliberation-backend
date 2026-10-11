from ninja.security import APIKeyHeader

from gateway.errors import UNAUTHORIZED, GatewayError
from gateway.keys import averify_key


class GatewayKeyAuth(APIKeyHeader):
    """`X-Gateway-Key` auth. On success `request.auth` is the ApiKey, with its platform loaded."""

    param_name = 'X-Gateway-Key'

    async def authenticate(self, request, key):
        # Ninja passes None when the header is missing; averify_key handles it.
        api_key = await averify_key(key)
        if api_key is None:
            raise GatewayError(UNAUTHORIZED)
        return api_key
