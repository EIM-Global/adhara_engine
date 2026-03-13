"""Port allocation and conflict detection for deployed sites."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.site import Site


def allocate_port(db: Session, site_id: str | None = None) -> int:
    """Find the next available host port from the pool.

    Uses SELECT FOR UPDATE to prevent TOCTOU race conditions
    when multiple deployments allocate ports concurrently.
    """
    # Lock all site rows with assigned ports to prevent concurrent allocation
    used_ports = set(
        row[0]
        for row in db.execute(
            text(
                "SELECT host_port FROM sites WHERE host_port IS NOT NULL FOR UPDATE"
            )
        ).all()
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
