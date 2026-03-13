-- ============================================================
-- Adhara Engine — Indicators of Compromise (IoC) Audit Queries
-- ============================================================
-- Run these against the adhara_engine database to detect
-- potential security issues or signs of compromise.
--
-- Usage:
--   docker compose exec -T db psql -U engine -d adhara_engine < scripts/ioc-audit.sql

-- ── 1. Unexpected platform_admin memberships ────────────────
-- Platform admins have full access to all resources.
-- Review this list for any unexpected entries.
SELECT
    m.id,
    m.user_id,
    m.role,
    m.resource_type,
    m.created_at,
    m.expires_at
FROM memberships m
WHERE m.role = 'platform_admin'
ORDER BY m.created_at DESC;

-- ── 2. Non-expiring API tokens ──────────────────────────────
-- API tokens without expiration dates are a risk if compromised.
SELECT
    t.id,
    t.name,
    t.user_id,
    t.created_at,
    t.last_used_at,
    t.expires_at,
    t.revoked
FROM api_tokens t
WHERE t.expires_at IS NULL
  AND t.revoked = false
ORDER BY t.created_at;

-- ── 3. API tokens not used recently but still active ────────
-- Tokens unused for 90+ days may be forgotten/leaked.
SELECT
    t.id,
    t.name,
    t.user_id,
    t.created_at,
    t.last_used_at,
    t.expires_at,
    EXTRACT(DAY FROM NOW() - COALESCE(t.last_used_at, t.created_at)) AS days_inactive
FROM api_tokens t
WHERE t.revoked = false
  AND COALESCE(t.last_used_at, t.created_at) < NOW() - INTERVAL '90 days'
ORDER BY days_inactive DESC;

-- ── 4. Tokens used from unusual patterns ────────────────────
-- Tokens with very high usage in a short period may indicate abuse.
-- (Requires audit logging — this query checks for tokens used
-- very recently that were created long ago, which could indicate
-- a leaked legacy token being exploited)
SELECT
    t.id,
    t.name,
    t.user_id,
    t.created_at,
    t.last_used_at,
    EXTRACT(DAY FROM NOW() - t.created_at) AS days_since_created
FROM api_tokens t
WHERE t.revoked = false
  AND t.last_used_at > NOW() - INTERVAL '1 day'
  AND t.created_at < NOW() - INTERVAL '180 days'
ORDER BY t.last_used_at DESC;

-- ── 5. Memberships with suspiciously broad access ───────────
-- Users with memberships at multiple levels may indicate
-- privilege escalation.
SELECT
    user_id,
    COUNT(*) AS membership_count,
    ARRAY_AGG(DISTINCT role) AS roles,
    ARRAY_AGG(DISTINCT resource_type) AS resource_types
FROM memberships
GROUP BY user_id
HAVING COUNT(*) > 5
ORDER BY membership_count DESC;

-- ── 6. Recently created platform-level memberships ──────────
-- Platform memberships created in the last 7 days should be reviewed.
SELECT
    m.id,
    m.user_id,
    m.role,
    m.resource_type,
    m.created_at
FROM memberships m
WHERE m.resource_type = 'platform'
  AND m.created_at > NOW() - INTERVAL '7 days'
ORDER BY m.created_at DESC;

-- ── Summary ─────────────────────────────────────────────────
SELECT 'IoC audit complete' AS status,
       NOW() AS run_at;
