"""Seed the database with sample data for development."""

import sys
sys.path.insert(0, "/app")

from app.core.database import SessionLocal
from app.models import Tenant, Workspace, Site


def seed():
    db = SessionLocal()
    try:
        # Check if already seeded
        if db.query(Tenant).first():
            print("Database already has data, skipping seed.")
            return

        # Create sample tenant
        tenant = Tenant(
            name="Acme Corp",
            slug="acme-corp",
            plan="pro",
            owner_email="admin@acme.com",
        )
        db.add(tenant)
        db.flush()

        # Create workspaces
        prod = Workspace(
            tenant_id=tenant.id,
            name="Production",
            slug="production",
            adhara_api_url="https://api.adharaweb.com",
            adhara_api_key="sk_live_example_key",
        )
        staging = Workspace(
            tenant_id=tenant.id,
            name="Staging",
            slug="staging",
            adhara_api_url="https://staging-api.adharaweb.com",
            adhara_api_key="sk_test_example_key",
        )
        db.add_all([prod, staging])
        db.flush()

        # Create sample sites
        main_site = Site(
            workspace_id=prod.id,
            tenant_id=tenant.id,
            name="Main Website",
            slug="main-website",
            source_type="git_repo",
            source_url="https://github.com/acme/website.git",
            container_port=3000,
            deploy_target="local",
            health_check_path="/api/health",
            runtime_env={
                "STRIPE_SECRET_KEY": "sk_test_example",
                "AUTH_SECRET": "dev-auth-secret",
            },
            build_env={
                "NEXT_PUBLIC_SITE_URL": "https://acme.com",
                "NEXT_PUBLIC_GA_ID": "G-XXXXXXXXXX",
            },
        )
        blog = Site(
            workspace_id=prod.id,
            tenant_id=tenant.id,
            name="Blog",
            slug="blog",
            source_type="docker_registry",
            source_url="ghcr.io/acme/blog:latest",
            container_port=3000,
            deploy_target="local",
            health_check_path="/api/health",
        )
        staging_site = Site(
            workspace_id=staging.id,
            tenant_id=tenant.id,
            name="Staging Site",
            slug="staging-site",
            source_type="docker_image",
            source_url="acme/website:staging",
            container_port=3000,
            deploy_target="local",
            health_check_path="/api/health",
            runtime_env={
                "STRIPE_SECRET_KEY": "sk_test_staging",
            },
            build_env={
                "NEXT_PUBLIC_SITE_URL": "https://staging.acme.com",
            },
        )
        db.add_all([main_site, blog, staging_site])
        db.commit()

        print("Seed data created successfully:")
        print(f"  Tenant: {tenant.name} ({tenant.slug})")
        print(f"  Workspaces: {prod.name}, {staging.name}")
        print(f"  Sites: {main_site.name}, {blog.name}, {staging_site.name}")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
