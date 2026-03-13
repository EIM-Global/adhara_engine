"""
Authentication module for Adhara Engine.

Supports two authentication methods:
  1. OIDC JWT — for browser-based users (Logto, Zitadel, or any provider)
     - Validated via JWKS from the configured OIDC provider
     - Token format: standard JWT (eyJ...)
  2. API Tokens — for CI/CD, mobile apps, service accounts
     - Token format: ae_live_<random> (prefixed for detection)
     - Looked up by SHA-256 hash in api_tokens table
     - Scoped to specific resources and permissions

The auth middleware detects which type based on the token prefix
and routes to the appropriate validation logic.
"""

import hashlib
import logging
from datetime import datetime, timezone

import httpx
import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db

security = HTTPBearer(auto_error=False)

_jwks_cache: dict | None = None

# ── API Token prefix ─────────────────────────────────────────
API_TOKEN_PREFIX = "ae_"

logger = logging.getLogger("auth")


def _get_oidc_urls() -> tuple[str, str, str]:
    """Return (jwks_url, userinfo_url, issuer) for the active OIDC provider.

    Supports Zitadel legacy env vars as override:
      - If ZITADEL_DOMAIN is set, use Zitadel-style URLs
      - Otherwise, use the generic OIDC settings (Logto default)
    """
    if settings.zitadel_domain:
        return (
            f"http://{settings.zitadel_domain}/oauth/v2/keys",
            f"http://{settings.zitadel_domain}/oidc/v1/userinfo",
            settings.zitadel_issuer or settings.oidc_issuer,
        )
    return (
        f"{settings.oidc_internal_url}{settings.oidc_jwks_path}",
        f"{settings.oidc_internal_url}{settings.oidc_userinfo_path}",
        settings.oidc_issuer,
    )


async def _get_jwks() -> dict:
    """Fetch and cache the OIDC provider's JWKS for JWT verification."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    jwks_url, _, issuer = _get_oidc_urls()

    try:
        headers = {}
        # Zitadel requires Host header matching its EXTERNALDOMAIN
        if settings.zitadel_domain:
            from urllib.parse import urlparse
            external_host = urlparse(issuer).hostname or "localhost"
            headers["Host"] = external_host

        async with httpx.AsyncClient() as client:
            resp = await client.get(jwks_url, headers=headers)
            resp.raise_for_status()
            _jwks_cache = resp.json()
            return _jwks_cache
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        )


async def _validate_token_via_userinfo(token: str) -> dict:
    """Validate a token via the OIDC provider's userinfo endpoint."""
    _, userinfo_url, issuer = _get_oidc_urls()

    try:
        headers = {"Authorization": f"Bearer {token}"}
        # Zitadel requires Host header
        if settings.zitadel_domain:
            from urllib.parse import urlparse
            external_host = urlparse(issuer).hostname or "localhost"
            headers["Host"] = external_host

        async with httpx.AsyncClient() as client:
            resp = await client.get(userinfo_url, headers=headers)
            if resp.status_code == 401:
                raise HTTPException(status_code=401, detail="Invalid or expired token")
            resp.raise_for_status()
            return resp.json()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        )


async def _validate_jwt(token: str) -> dict:
    """Validate an OIDC JWT and return user claims."""
    _, _, issuer = _get_oidc_urls()

    try:
        jwks = await _get_jwks()
        header = jwt.get_unverified_header(token)
        key = None
        for k in jwks.get("keys", []):
            if k["kid"] == header.get("kid"):
                key = jwt.algorithms.RSAAlgorithm.from_jwk(k)
                break
        if key is None:
            raise HTTPException(status_code=401, detail="Invalid token signing key")

        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": False},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def _validate_api_token(token: str, db: Session) -> dict:
    """Validate an API token and return synthetic user claims."""
    from app.models.api_token import APIToken

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    api_token = db.query(APIToken).filter(APIToken.token_hash == token_hash).first()

    if api_token is None:
        raise HTTPException(status_code=401, detail="Invalid API token")

    if api_token.revoked:
        raise HTTPException(status_code=401, detail="API token has been revoked")

    if api_token.expires_at and api_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="API token has expired")

    # Update last_used_at
    api_token.last_used_at = datetime.now(timezone.utc)
    db.commit()

    # Return synthetic claims that match JWT structure
    return {
        "sub": api_token.user_id,
        "token_type": "api_token",
        "token_id": str(api_token.id),
        "token_name": api_token.name,
        "scopes": api_token.scopes,
    }


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
    db: Session = Depends(get_db),
) -> dict | None:
    """
    Validate authentication and return user claims.

    Detects token type by prefix:
      - "ae_" prefix -> API token (database lookup)
      - Anything else -> OIDC JWT (JWKS validation)

    Returns None if no token is provided (allows optional auth).
    Raises 401 if token is invalid.
    """
    if credentials is None:
        return None

    token = credentials.credentials

    if token.startswith(API_TOKEN_PREFIX):
        return await _validate_api_token(token, db)

    # Try JWT validation first (fast, local). If the token is opaque
    # (Zitadel's default), fall back to the userinfo endpoint.
    if token.count(".") == 2:
        claims = await _validate_jwt(token)
    else:
        claims = await _validate_token_via_userinfo(token)
    logger.info(f"Authenticated user sub={claims.get('sub')}")
    return claims


async def require_auth(
    user: dict | None = Depends(get_current_user),
) -> dict:
    """Require authentication — returns user claims or raises 401."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_role(role: str):
    """
    Dependency that requires a specific project role.
    Checks both Zitadel-style and standard role claims.
    DEPRECATED: Use authorize() from app.core.authorize instead
    for resource-scoped RBAC.
    """

    async def _check(user: dict = Depends(require_auth)) -> dict:
        # Check Zitadel-style role claim
        user_roles = user.get("urn:zitadel:iam:org:project:roles", {})
        # Also check standard roles claim (Logto, etc.)
        standard_roles = user.get("roles", [])
        if isinstance(standard_roles, list):
            for r in standard_roles:
                user_roles[r] = True

        if role not in user_roles and "super_admin" not in user_roles:
            raise HTTPException(status_code=403, detail=f"Role '{role}' required")
        return user

    return _check
