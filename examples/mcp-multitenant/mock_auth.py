"""Mock of Cognito authentication.

Issues opaque demo tokens and verifies them into AccessToken objects whose
claims mirror what a Cognito access/ID token would carry (sub, username).

In production, replace `MockCognitoVerifier.verify_token` with JWT
verification against the Cognito user pool JWKS
(https://cognito-idp.<region>.amazonaws.com/<pool>/.well-known/jwks.json).
Group membership is resolved from the DB per request rather than from the
`cognito:groups` claim, so an invite takes effect immediately without
waiting for a token refresh — swap in the claim if you prefer token-borne
membership.
"""
from mcp.server.auth.provider import AccessToken


# token -> user  (stand-in for Cognito-issued JWTs)
_TOKENS = {
    "token-alice": {"sub": "u-001", "username": "alice"},
    "token-bob": {"sub": "u-002", "username": "bob"},
    "token-carol": {"sub": "u-003", "username": "carol"},
}


class MockCognitoVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        user = _TOKENS.get(token)
        if user is None:
            return None  # -> 401
        return AccessToken(
            token=token,
            client_id="taskflow-demo-client",
            scopes=["taskflow/api"],
            subject=user["sub"],
            claims={"sub": user["sub"], "username": user["username"]},
        )
