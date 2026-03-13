"""
Bootstrap script: create a platform-admin API token directly in the DB.

Runs inside the API container (has access to the database).
Also creates a platform_admin Membership so the token passes RBAC checks.

Usage:
    python scripts/create_token.py [--name NAME] [--user-id USER_ID]

Outputs the raw token to stdout (only line). All other messages go to stderr.
"""

import argparse
import hashlib
import secrets
import sys
import uuid

# Ensure app package is importable (container cwd is /app)
sys.path.insert(0, "/app")

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.api_token import APIToken
from app.models.membership import Membership


def create_admin_token(
    name: str = "Bootstrap Admin Token",
    user_id: str = "bootstrap-admin",
) -> str:
    """Create a platform-admin API token with matching Membership.

    Returns the raw token string (shown only once).
    """
    raw_token = f"ae_live_{secrets.token_urlsafe(32)}"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    token_prefix = raw_token[:16]

    # Platform-level admin scope
    scopes = [
        {
            "resource_type": "platform",
            "resource_id": "*",
            "permissions": ["*"],
        }
    ]

    db: Session = SessionLocal()
    try:
        # 1. Create the API token
        api_token = APIToken(
            id=uuid.uuid4(),
            user_id=user_id,
            name=name,
            token_hash=token_hash,
            token_prefix=token_prefix,
            scopes=scopes,
        )
        db.add(api_token)

        # 2. Ensure a platform_admin Membership exists for this user_id
        #    (authorize() checks memberships table, not token scopes)
        existing = (
            db.query(Membership)
            .filter(
                Membership.user_id == user_id,
                Membership.resource_type == "platform",
                Membership.role == "platform_admin",
            )
            .first()
        )
        if not existing:
            membership = Membership(
                id=uuid.uuid4(),
                user_id=user_id,
                user_email=f"{user_id}@adhara.local",
                resource_type="platform",
                resource_id=None,
                role="platform_admin",
                granted_by="bootstrap",
            )
            db.add(membership)
            print(f"Membership created: platform_admin for {user_id}", file=sys.stderr)
        else:
            print(f"Membership already exists: platform_admin for {user_id}", file=sys.stderr)

        db.commit()
        print(f"Token created: {name}", file=sys.stderr)
        print(f"  Prefix: {token_prefix}...", file=sys.stderr)
        print(f"  User:   {user_id}", file=sys.stderr)
        print(f"  Scope:  platform_admin", file=sys.stderr)
    finally:
        db.close()

    return raw_token


def main():
    parser = argparse.ArgumentParser(description="Create a bootstrap admin API token")
    parser.add_argument(
        "--name",
        default="Bootstrap Admin Token",
        help="Token display name (default: Bootstrap Admin Token)",
    )
    parser.add_argument(
        "--user-id",
        default="bootstrap-admin",
        help="User ID to assign the token to (default: bootstrap-admin)",
    )
    args = parser.parse_args()

    raw_token = create_admin_token(name=args.name, user_id=args.user_id)
    # Print only the raw token to stdout (for piping / capture)
    print(raw_token)


if __name__ == "__main__":
    main()
