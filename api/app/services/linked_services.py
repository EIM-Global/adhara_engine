"""
Linked service provisioning engine.

Provisions and manages dependent infrastructure for sites:
  - postgres:     PostgreSQL database container
  - redis:        Redis cache/queue container
  - minio_bucket: MinIO bucket (uses the shared MinIO instance)

Each service generates secure credentials and injects connection
details into the site's runtime environment automatically.
"""

import logging
import secrets
import string

import docker
from docker.errors import NotFound
from sqlalchemy.orm import Session

from app.models.linked_service import LinkedService
from app.models.site import Site

logger = logging.getLogger(__name__)

NETWORK_NAME = "adhara-engine-net"

# Service definitions: image, port, env template
SERVICE_DEFS = {
    "postgres": {
        "image": "postgres:16-alpine",
        "internal_port": 5432,
        "env_template": lambda name, password: {
            "POSTGRES_USER": name,
            "POSTGRES_PASSWORD": password,
            "POSTGRES_DB": name,
        },
        "connection_env": lambda container_name, name, password, port: {
            "DATABASE_URL": f"postgresql://{name}:{password}@{container_name}:{port}/{name}",
            "PGHOST": container_name,
            "PGPORT": str(port),
            "PGUSER": name,
            "PGPASSWORD": password,
            "PGDATABASE": name,
        },
        "healthcheck": {
            "test": ["CMD-SHELL", "pg_isready -U {user}"],
            "interval": 5_000_000_000,  # 5s in nanoseconds
            "timeout": 3_000_000_000,
            "retries": 5,
        },
    },
    "redis": {
        "image": "redis:7-alpine",
        "internal_port": 6379,
        "env_template": lambda name, password: {},
        "connection_env": lambda container_name, name, password, port: {
            "REDIS_URL": f"redis://{container_name}:{port}",
        },
        "healthcheck": {
            "test": ["CMD", "redis-cli", "ping"],
            "interval": 5_000_000_000,
            "timeout": 3_000_000_000,
            "retries": 5,
        },
    },
}


def _generate_password(length: int = 24) -> str:
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _service_container_name(site_slug: str, service_type: str) -> str:
    """Generate container name for a linked service."""
    return f"ae-svc-{site_slug}-{service_type}"


async def provision_service(
    db: Session, linked_service: LinkedService, site: Site
) -> LinkedService:
    """Provision a linked service container.

    Creates a Docker container, generates credentials, and stores
    connection details in the LinkedService record.
    """
    service_type = linked_service.service_type

    if service_type == "minio_bucket":
        return await _provision_minio_bucket(db, linked_service, site)

    if service_type not in SERVICE_DEFS:
        linked_service.status = "error"
        db.commit()
        raise ValueError(f"Unknown service type: {service_type}")

    definition = SERVICE_DEFS[service_type]
    container_name = _service_container_name(site.slug, service_type)
    password = _generate_password()
    db_name = site.slug.replace("-", "_")

    linked_service.status = "provisioning"
    linked_service.container_name = container_name
    db.commit()

    client = docker.from_env()

    try:
        # Clean up existing container if any
        try:
            existing = client.containers.get(container_name)
            existing.stop(timeout=10)
            existing.remove()
        except NotFound:
            pass

        # Ensure network exists
        try:
            client.networks.get(NETWORK_NAME)
        except NotFound:
            client.networks.create(NETWORK_NAME, driver="bridge")

        # Build container env
        env = definition["env_template"](db_name, password)

        # Build healthcheck
        healthcheck = None
        if "healthcheck" in definition:
            hc = definition["healthcheck"].copy()
            if isinstance(hc.get("test"), list):
                hc["test"] = [
                    t.replace("{user}", db_name) for t in hc["test"]
                ]
            healthcheck = hc

        # Create and start container
        container = client.containers.run(
            image=definition["image"],
            name=container_name,
            detach=True,
            environment=env,
            network=NETWORK_NAME,
            labels={
                "adhara.engine": "true",
                "adhara.linked_service": "true",
                "adhara.site_id": str(site.id),
                "adhara.service_type": service_type,
            },
            restart_policy={"Name": "unless-stopped"},
            healthcheck=healthcheck,
        )

        # Generate connection env vars
        port = definition["internal_port"]
        connection_env = definition["connection_env"](
            container_name, db_name, password, port
        )

        # Update linked service record
        linked_service.container_id = container.id
        linked_service.status = "running"
        linked_service.connection_env = connection_env
        linked_service.config = {
            "password": password,
            "db_name": db_name,
            "port": port,
        }
        db.commit()

        # Inject connection env into site runtime env
        _inject_env(db, site, connection_env)

        logger.info(
            f"Provisioned {service_type} for {site.slug}: {container_name}"
        )
        return linked_service

    except Exception as e:
        linked_service.status = "error"
        db.commit()
        logger.error(f"Failed to provision {service_type} for {site.slug}: {e}")
        raise


async def _provision_minio_bucket(
    db: Session, linked_service: LinkedService, site: Site
) -> LinkedService:
    """Create a MinIO bucket with scoped bucket policy.

    Root MinIO credentials are used only for the admin operation of
    creating the bucket and setting its policy.  They are NOT injected
    into site containers.  Sites that need direct S3 access should
    request scoped credentials through the engine API.

    TODO: When the MinIO Python admin SDK is available, create
    per-bucket service accounts instead of relying solely on
    bucket policies.
    """
    from minio import Minio
    from app.core.config import settings
    import json

    linked_service.status = "provisioning"
    db.commit()

    try:
        bucket_name = linked_service.name or f"ae-{site.slug}"

        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)

        # Set a bucket-scoped policy restricting access to this bucket only
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:DeleteObject",
                        "s3:ListBucket",
                        "s3:GetBucketLocation",
                    ],
                    "Resource": [
                        f"arn:aws:s3:::{bucket_name}",
                        f"arn:aws:s3:::{bucket_name}/*",
                    ],
                }
            ],
        }
        client.set_bucket_policy(bucket_name, json.dumps(policy))

        # Do NOT inject root MinIO credentials into site containers.
        # Sites access storage through the engine API or request
        # scoped credentials via the /api/v1/sites/{id}/storage endpoint.
        connection_env = {
            "S3_BUCKET": bucket_name,
            "S3_ENDPOINT": f"http://{settings.minio_endpoint}",
        }

        linked_service.status = "running"
        linked_service.connection_env = connection_env
        linked_service.config = {"bucket_name": bucket_name}
        db.commit()

        _inject_env(db, site, connection_env)

        logger.info(f"Provisioned MinIO bucket '{bucket_name}' for {site.slug}")
        return linked_service

    except Exception as e:
        linked_service.status = "error"
        db.commit()
        logger.error(f"Failed to provision MinIO bucket for {site.slug}: {e}")
        raise


async def deprovision_service(
    db: Session, linked_service: LinkedService, site: Site
) -> None:
    """Remove a linked service container and clean up."""
    if linked_service.service_type == "minio_bucket":
        # Don't delete buckets — just remove the record
        _remove_env(db, site, linked_service.connection_env or {})
        db.delete(linked_service)
        db.commit()
        return

    client = docker.from_env()

    # Stop and remove container
    if linked_service.container_name:
        try:
            container = client.containers.get(linked_service.container_name)
            container.stop(timeout=10)
            container.remove(v=linked_service.delete_on_site_removal)
            logger.info(f"Removed container {linked_service.container_name}")
        except NotFound:
            pass

    # Remove injected env vars from site
    _remove_env(db, site, linked_service.connection_env or {})

    db.delete(linked_service)
    db.commit()


def _inject_env(db: Session, site: Site, env: dict):
    """Add connection env vars to site's runtime env."""
    runtime_env = dict(site.runtime_env or {})
    runtime_env.update(env)
    site.runtime_env = runtime_env
    db.commit()


def _remove_env(db: Session, site: Site, env: dict):
    """Remove connection env vars from site's runtime env."""
    runtime_env = dict(site.runtime_env or {})
    for key in env:
        runtime_env.pop(key, None)
    site.runtime_env = runtime_env
    db.commit()
