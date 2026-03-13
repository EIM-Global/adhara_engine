-- ============================================================
-- Adhara Engine - Database Initialization
-- ============================================================
-- Creates additional databases needed by optional services
-- sharing the same PostgreSQL instance.

-- Logto database (lightweight OIDC provider — default auth profile)
CREATE DATABASE logto OWNER engine;

-- Zitadel database and user (enterprise OIDC — zitadel profile)
-- WARNING: This password MUST match ZITADEL_DB_PASSWORD in your .env file.
-- Change both together if you change either one.
CREATE USER zitadel WITH PASSWORD 'zitadel';
CREATE DATABASE zitadel OWNER zitadel;
GRANT ALL PRIVILEGES ON DATABASE zitadel TO zitadel;
