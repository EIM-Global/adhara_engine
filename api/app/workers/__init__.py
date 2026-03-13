"""
ARQ background workers for Adhara Engine.

Workers handle long-running tasks asynchronously:
  - pipeline: Build pipeline orchestration (clone -> scan -> build -> push -> deploy)
  - health: Health monitoring cron job (30s interval, escalation ladder)
"""
