from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Core
    app_name: str = "Adhara Engine"
    version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str = "postgresql://engine:engine@db:5432/adhara_engine"

    # Redis
    redis_url: str = "redis://redis:6379"

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "engine"
    minio_secret_key: str = "engine-secret"
    minio_secure: bool = False

    # OIDC provider (Logto, Zitadel, or any OIDC-compliant provider)
    oidc_internal_url: str = "http://logto:3001"
    oidc_issuer: str = "http://localhost:3001"
    oidc_jwks_path: str = "/oidc/jwks"
    oidc_userinfo_path: str = "/oidc/me"

    # Legacy Zitadel aliases (used when --profile zitadel is active)
    zitadel_domain: str = ""
    zitadel_issuer: str = ""

    # Port pool for deployed sites
    # Starts at 4001 to avoid conflicts with engine services
    # (Logto=3001, Grafana=3003, Loki=3100, etc.)
    port_range_start: int = 4001
    port_range_end: int = 5000

    # Engine
    engine_secret_key: str = "dev-secret-change-me"

    # Platform domain for auto-generated site subdomains
    # Sites get: {slug}.{workspace}.{tenant}.{platform_domain}
    platform_domain: str = "adharaengine.com"

    # Public IP of the engine server (shown in A record DNS instructions)
    # Set this to the actual public IP once deployed
    engine_public_ip: str = "76.76.21.21"

    # Docker Registry host for push/pull commands shown in UI
    # When HTTPS is enabled (ADHARA_DOMAIN set), set to registry.DOMAIN
    # When running locally, defaults to hostname:5000
    registry_host: str = ""

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
