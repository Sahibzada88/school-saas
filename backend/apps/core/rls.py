"""Supabase hardening: only Django may reach the data.

Supabase exposes every table in the `public` schema through its auto-generated Data API
(PostgREST) using the `anon` / `authenticated` roles. We never use that API, so after every
`migrate` we (1) enable Row Level Security on every table (no policies = deny all) and
(2) revoke the API roles' grants. Django connects as the owning role, which is unaffected.

Runs on PostgreSQL only; a no-op for SQLite or when ENABLE_RLS_LOCKDOWN is false.
"""
import logging

from django.conf import settings
from django.db import connections

logger = logging.getLogger(__name__)

API_ROLES = ("anon", "authenticated")

LOCKDOWN_SQL = """
DO $$
DECLARE
    tbl record;
    api_role text;
BEGIN
    FOR tbl IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND NOT c.relrowsecurity
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', tbl.relname);
    END LOOP;

    FOREACH api_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = api_role) THEN
            EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', api_role);
            EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I', api_role);
            EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %I', api_role);
            EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %I', api_role);
        END IF;
    END LOOP;
END
$$;
"""

TABLES_WITHOUT_RLS_SQL = """
SELECT c.relname
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND NOT c.relrowsecurity
ORDER BY c.relname
"""


def lockdown_after_migrate(sender=None, using="default", **kwargs):
    if not getattr(settings, "ENABLE_RLS_LOCKDOWN", True):
        return
    connection = connections[using]
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute(LOCKDOWN_SQL)
    logger.info("RLS lockdown applied to the public schema.")


def tables_without_rls(using="default") -> list[str]:
    connection = connections[using]
    if connection.vendor != "postgresql":
        return []
    with connection.cursor() as cursor:
        cursor.execute(TABLES_WITHOUT_RLS_SQL)
        return [row[0] for row in cursor.fetchall()]
