"""
ARQ worker settings — configures the background worker process.

This module defines the WorkerSettings class that ARQ uses to:
  - Connect to Redis
  - Register task functions
  - Configure cron jobs (health checks)
  - Set concurrency and retry policies
"""

from arq import cron
from arq.connections import RedisSettings

from app.core.config import settings
from app.workers.pipeline import run_pipeline


def _parse_redis_url(url: str) -> RedisSettings:
    """Parse a redis:// URL into ARQ RedisSettings."""
    # redis://host:port or redis://host:port/db
    url = url.replace("redis://", "")
    parts = url.split("/")
    host_port = parts[0]
    database = int(parts[1]) if len(parts) > 1 else 0

    if ":" in host_port:
        host, port = host_port.rsplit(":", 1)
        port = int(port)
    else:
        host = host_port
        port = 6379

    return RedisSettings(host=host, port=port, database=database)


class WorkerSettings:
    """ARQ worker configuration.

    ARQ discovers this class automatically when started with:
      arq app.workers.settings.WorkerSettings
    """

    # Redis connection
    redis_settings = _parse_redis_url(settings.redis_url)

    # Task functions — must be actual callables, not string paths
    functions = [run_pipeline]

    # Cron jobs — periodic tasks
    cron_jobs = [
        cron(
            "app.workers.health.check_all_sites",  # dotted path to function
            second={0, 30},  # Run at :00 and :30 of every minute
        ),
        cron(
            "app.workers.poller.poll_git_repos",  # Git polling fallback
            second={15},  # Run at :15 of every minute (offset from health)
        ),
        cron(
            "app.workers.preview_cleanup.cleanup_previews",  # Preview TTL cleanup
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},  # Every 5 min
            second={45},
        ),
    ]

    # Worker settings
    max_jobs = 10  # Max concurrent pipeline jobs
    job_timeout = 600  # 10 minute timeout per job
    keep_result = 3600  # Keep results for 1 hour
    retry_jobs = False  # Don't auto-retry failed pipelines
