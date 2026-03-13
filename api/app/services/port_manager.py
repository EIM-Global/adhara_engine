"""Port allocation and conflict detection for deployed sites."""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.site import Site


def allocate_port(db: Session, site_id: str | None = None) -> int:
    """Find the next available host port from the pool.

    Scans the configured range (default 3001-4000) and returns the first
    port not already assigned to a site.
    """
    used_ports = set(
        row[0]
        for row in db.query(Site.host_port)
        .filter(Site.host_port.isnot(None))
        .all()
    )

    for port in range(settings.port_range_start, settings.port_range_end + 1):
        if port not in used_ports:
            return port

    raise RuntimeError(
        f"No available ports in range {settings.port_range_start}-{settings.port_range_end}"
    )


def check_port_conflict(db: Session, port: int, exclude_site_id: str | None = None) -> Site | None:
    """Check if a port is already in use by another site."""
    query = db.query(Site).filter(Site.host_port == port)
    if exclude_site_id:
        query = query.filter(Site.id != exclude_site_id)
    return query.first()
