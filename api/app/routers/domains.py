"""
Custom domain management for sites.

Each site automatically gets a platform subdomain:
  {slug}.{workspace_slug}.{tenant_slug}.adharaengine.com

Users can also add custom domains. For each custom domain, the API
returns the DNS records the user must configure at their registrar
(GoDaddy, Cloudflare, Namecheap, etc.):

  1. CNAME record: custom.domain -> platform subdomain
  2. TXT record:   _adhara-verify.custom.domain -> verification token

Verification checks that the domain resolves to the engine's IP.
"""

import hashlib
import socket
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import require_auth
from app.core.config import settings
from app.core.database import get_db
from app.models.site import Site
from app.models.workspace import Workspace
from app.models.tenant import Tenant

router = APIRouter(tags=["domains"])

# The base domain for platform subdomains.
# In production this comes from settings; fallback to localhost for dev.
PLATFORM_DOMAIN = getattr(settings, "platform_domain", None) or "adharaengine.com"


# ── Schemas ────────────────────────────────────────────────────────────


class DNSRecord(BaseModel):
    type: str          # "CNAME", "A", "TXT"
    name: str          # Host/record name
    value: str         # Target value
    purpose: str       # Human-readable explanation


class DomainAdd(BaseModel):
    domain: str = Field(..., min_length=3, max_length=255)


class DomainResponse(BaseModel):
    domain: str
    is_platform: bool = False
    verified: bool = False
    dns_records: list[DNSRecord] = []
    verification_token: str | None = None


# ── Helpers ────────────────────────────────────────────────────────────


def _get_platform_subdomain(site: Site, db: Session) -> str:
    """Build the platform subdomain for a site: slug.workspace.tenant.adharaengine.com"""
    workspace = db.query(Workspace).filter(Workspace.id == site.workspace_id).first()
    tenant = db.query(Tenant).filter(Tenant.id == site.tenant_id).first()
    ws_slug = workspace.slug if workspace else "default"
    t_slug = tenant.slug if tenant else "default"
    return f"{site.slug}.{ws_slug}.{t_slug}.{PLATFORM_DOMAIN}"


def _verification_token(site_id: uuid.UUID, domain: str) -> str:
    """Generate a deterministic verification token for a domain+site pair."""
    raw = f"{site_id}:{domain}"
    return f"adhara-verify={hashlib.sha256(raw.encode()).hexdigest()[:32]}"


def _is_apex_domain(domain: str) -> bool:
    """Check if this looks like a root/apex domain (e.g., example.com vs www.example.com)."""
    parts = domain.rstrip(".").split(".")
    # Two parts = apex (example.com), three+ with common TLD = could be apex (example.co.uk)
    # Simple heuristic: if there are exactly 2 parts, it's apex
    return len(parts) <= 2


def _build_dns_records(domain: str, platform_subdomain: str, site_id: uuid.UUID) -> list[DNSRecord]:
    """Return the DNS records the user needs to add at their registrar.

    For apex domains (example.com): recommend A record (CNAME not allowed on apex per RFC).
    For subdomains (www.example.com): recommend CNAME (simpler, follows IP changes).
    Always include both options so the user can choose.
    """
    is_apex = _is_apex_domain(domain)
    records: list[DNSRecord] = []

    if is_apex:
        # A record first (recommended for apex)
        records.append(DNSRecord(
            type="A",
            name=domain,
            value=settings.engine_public_ip,
            purpose="Recommended for root domains \u2014 points to engine IP",
        ))
        records.append(DNSRecord(
            type="CNAME",
            name=domain,
            value=f"{platform_subdomain}.",
            purpose="Alternative (some providers support CNAME flattening for apex)",
        ))
    else:
        # CNAME first (recommended for subdomains)
        records.append(DNSRecord(
            type="CNAME",
            name=domain,
            value=f"{platform_subdomain}.",
            purpose="Recommended for subdomains \u2014 auto-follows IP changes",
        ))
        records.append(DNSRecord(
            type="A",
            name=domain,
            value=settings.engine_public_ip,
            purpose="Alternative \u2014 use if CNAME isn't supported",
        ))

    # TXT record for verification (always required)
    records.append(DNSRecord(
        type="TXT",
        name=f"_adhara-verify.{domain}",
        value=_verification_token(site_id, domain),
        purpose="Required \u2014 proves domain ownership",
    ))

    return records


def _check_domain_verified(domain: str) -> bool:
    """Check if a domain resolves (basic DNS propagation check)."""
    try:
        result = socket.getaddrinfo(domain, None)
        return bool(result)
    except socket.gaierror:
        return False


# ── Endpoints ──────────────────────────────────────────────────────────


@router.get("/api/v1/sites/{site_id}/domains", response_model=list[DomainResponse])
def list_domains(
    site_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """List all domains for a site — platform subdomain + custom domains."""
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    platform_subdomain = _get_platform_subdomain(site, db)

    result: list[DomainResponse] = []

    # 1. Platform subdomain (always first, always verified)
    result.append(DomainResponse(
        domain=platform_subdomain,
        is_platform=True,
        verified=True,
        dns_records=[],
    ))

    # 2. Custom domains with DNS instructions
    for d in (site.custom_domains or []):
        verified = _check_domain_verified(d)
        result.append(DomainResponse(
            domain=d,
            is_platform=False,
            verified=verified,
            dns_records=_build_dns_records(d, platform_subdomain, site.id),
            verification_token=_verification_token(site.id, d),
        ))

    return result


@router.post("/api/v1/sites/{site_id}/domains", response_model=DomainResponse, status_code=201)
def add_domain(
    site_id: uuid.UUID,
    data: DomainAdd,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Add a custom domain to a site. Returns DNS records to configure."""
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    domains = list(site.custom_domains or [])
    if data.domain in domains:
        raise HTTPException(status_code=409, detail=f"Domain '{data.domain}' already added")

    domains.append(data.domain)
    site.custom_domains = domains
    db.commit()

    platform_subdomain = _get_platform_subdomain(site, db)

    return DomainResponse(
        domain=data.domain,
        is_platform=False,
        verified=False,
        dns_records=_build_dns_records(data.domain, platform_subdomain, site.id),
        verification_token=_verification_token(site.id, data.domain),
    )


@router.delete("/api/v1/sites/{site_id}/domains/{domain}", status_code=200)
def remove_domain(
    site_id: uuid.UUID,
    domain: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Remove a custom domain from a site."""
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    domains = list(site.custom_domains or [])
    if domain not in domains:
        raise HTTPException(status_code=404, detail=f"Domain '{domain}' not found on this site")

    domains.remove(domain)
    site.custom_domains = domains
    db.commit()

    return {"removed": domain, "remaining": domains}


@router.post("/api/v1/sites/{site_id}/domains/{domain}/verify", response_model=DomainResponse)
def verify_domain(
    site_id: uuid.UUID,
    domain: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Check DNS propagation for a custom domain."""
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    domains = site.custom_domains or []
    if domain not in domains:
        raise HTTPException(status_code=404, detail=f"Domain '{domain}' not found on this site")

    verified = _check_domain_verified(domain)
    platform_subdomain = _get_platform_subdomain(site, db)

    return DomainResponse(
        domain=domain,
        is_platform=False,
        verified=verified,
        dns_records=_build_dns_records(domain, platform_subdomain, site.id),
        verification_token=_verification_token(site.id, domain),
    )
