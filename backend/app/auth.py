"""認証。Cognito のログインと、Bearer トークンの検証。

Bearer として受け付けるのは 2 種類:
- Cognito のアクセストークン (画面からのログイン。JWKS で署名を検証)
- 個人アクセストークン tfp_... (MCP クライアント用。tokens.py)

ローカル (Floci) では admin/admin を開発用ユーザー (メールアドレス) に読み替えてから
Cognito に問い合わせる。Cognito を迂回するわけではないので、発行されるのは本物の JWT。
"""

from dataclasses import dataclass, field
from typing import Annotated, Literal

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import tokens
from .aws import cognito
from .config import get_settings


@dataclass
class CognitoIds:
    user_pool_id: str = ""
    client_id: str = ""


# 起動時 (main.lifespan → bootstrap) に確定する
ids = CognitoIds()


@dataclass(frozen=True)
class Principal:
    owner_id: str  # Cognito の sub
    email: str
    via: Literal["cognito", "token"]
    bearer: str = field(default="", repr=False)

    def resolved_email(self) -> str:
        """アクセストークンには email が無いので、要るときだけ Cognito に聞く。"""
        if self.email or self.via != "cognito":
            return self.email
        attrs = cognito().get_user(AccessToken=self.bearer)["UserAttributes"]
        return next((a["Value"] for a in attrs if a["Name"] == "email"), "")


class AuthError(Exception):
    pass


def issuer() -> str:
    s = get_settings()
    if s.cognito_issuer:
        return s.cognito_issuer.rstrip("/")
    if s.aws_endpoint_url:
        # Floci は FLOCI_BASE_URL (= このエンドポイント) を iss に使う
        return f"{s.aws_endpoint_url.rstrip('/')}/{ids.user_pool_id}"
    return f"https://cognito-idp.{s.aws_region}.amazonaws.com/{ids.user_pool_id}"


_jwks: dict[str, jwt.PyJWKClient] = {}


def _jwks_client() -> jwt.PyJWKClient:
    url = f"{issuer()}/.well-known/jwks.json"
    if url not in _jwks:
        _jwks[url] = jwt.PyJWKClient(url, cache_keys=True, lifespan=3600)
    return _jwks[url]


def decode_cognito(token: str, token_use: Literal["access", "id"]) -> dict:
    try:
        key = _jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            issuer=issuer(),
            # アクセストークンに aud は無い (client_id で確かめる)
            audience=ids.client_id if token_use == "id" else None,
            options={"verify_aud": token_use == "id", "require": ["exp", "sub", "token_use"]},
        )
    except jwt.PyJWTError as e:
        raise AuthError(f"invalid token: {e}") from e
    if claims.get("token_use") != token_use:
        raise AuthError("unexpected token_use")
    if token_use == "access" and claims.get("client_id") != ids.client_id:
        raise AuthError("token was issued for another client")
    return claims


def principal_from_bearer(token: str) -> Principal:
    if token.startswith(tokens.PREFIX):
        owner = tokens.verify(token)
        if not owner:
            raise AuthError("unknown or revoked token")
        return Principal(owner_id=owner.owner_id, email=owner.email, via="token")
    claims = decode_cognito(token, "access")
    # アクセストークンには email が無い。画面は ID トークンから表示用に取る
    return Principal(owner_id=claims["sub"], email=claims.get("email", ""), via="cognito", bearer=token)


# --- ログイン ---------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserInfo(BaseModel):
    sub: str
    email: str


class AuthResult(BaseModel):
    access_token: str
    id_token: str
    refresh_token: str | None = None
    expires_in: int
    user: UserInfo


def resolve_dev_login(username: str, password: str) -> tuple[str, str]:
    s = get_settings()
    if s.dev_login and username == "admin" and password == "admin":
        return s.dev_admin_email, s.dev_admin_password
    return username, password


def _result(r: dict, refresh_token: str | None = None) -> AuthResult:
    claims = decode_cognito(r["IdToken"], "id")
    return AuthResult(
        access_token=r["AccessToken"],
        id_token=r["IdToken"],
        refresh_token=r.get("RefreshToken") or refresh_token,
        expires_in=r.get("ExpiresIn", 3600),
        user=UserInfo(sub=claims["sub"], email=claims.get("email", "")),
    )


def login(username: str, password: str) -> AuthResult:
    username, password = resolve_dev_login(username.strip(), password)
    c = cognito()
    try:
        r = c.initiate_auth(
            ClientId=ids.client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )
    except (c.exceptions.NotAuthorizedException, c.exceptions.UserNotFoundException) as e:
        raise AuthError("メールアドレスまたはパスワードが違います") from e
    if "AuthenticationResult" not in r:
        # NEW_PASSWORD_REQUIRED など。管理者が仮パスワードで作ったユーザー
        raise AuthError(f"追加の手続きが必要です ({r.get('ChallengeName')})")
    return _result(r["AuthenticationResult"])


def refresh(refresh_token: str) -> AuthResult:
    c = cognito()
    try:
        r = c.initiate_auth(
            ClientId=ids.client_id,
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters={"REFRESH_TOKEN": refresh_token},
        )
    except c.exceptions.NotAuthorizedException as e:
        raise AuthError("セッションの有効期限が切れました") from e
    return _result(r["AuthenticationResult"], refresh_token)


# --- FastAPI の依存 --------------------------------------------------------

_bearer = HTTPBearer(auto_error=False)


def current_user(
    cred: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if not cred:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "認証が必要です", {"WWW-Authenticate": "Bearer"})
    try:
        return principal_from_bearer(cred.credentials)
    except AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e), {"WWW-Authenticate": "Bearer"}) from e


CurrentUser = Annotated[Principal, Depends(current_user)]
