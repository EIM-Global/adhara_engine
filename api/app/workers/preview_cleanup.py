"""
Preview environment cleanup cron — destroys stale and closed previews.

Runs every 5 minutes to:
  - Destroy previews that exceeded their TTL
  - Destroy previews for merged/closed PRs
"""

import logging

from app.core.database import SessionLocal
from app.services.preview_manager import cleanup_stale_previews

logger = logging.getLogger(__name__)


async def cleanup_previews(ctx: dict):
    """ARQ cron: clean up expired and closed preview environments."""
    db = SessionLocal()
    try:
        destroyed = await cleanup_stale_previews(db)
        if destroyed > 0:
            logger.info(f"Preview cleanup: destroyed {destroyed} stale previews")
    except Exception as e:
        logger.error(f"Preview cleanup failed: {e}")
    finally:
        db.close()
