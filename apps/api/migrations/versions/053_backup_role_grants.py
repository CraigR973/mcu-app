"""the backup role reads every table but no credential

Revision ID: 053
Revises: 052
Create Date: 2026-10-14

Batch X4, "Weekly dump and restore drill" (DS44-03, #257). The weekly copy reads through
``mcu_backup``, made by hand with its password on 14 Oct (#268), as ``mcu_readonly`` was. This
grants it ``SELECT`` on every public table except the six that hold nothing but credentials,
and on every column of ``profiles`` and ``movie_night_sessions`` except their one credential
each (``pin_hash``, ``invite_token``).

**Guarded, as ``mcu_readonly``'s grants are**: CI's database has no such role, so there the
block does nothing. **The lists are this migration's own**, frozen with it; the backup's
current policy is ``src/services/backup.py``, and the dump checks the catalogue against it on
every run, so a table a later migration forgets to grant stops the copy rather than leaving
it out.

The downgrade takes every grant on the schema's tables back from the role; the role stays.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "053"
down_revision: str | None = "052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GRANTS = """
DO $$
DECLARE
    tbl record;
    readable text;
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_backup') THEN
        RETURN;
    END IF;
    GRANT USAGE ON SCHEMA public TO mcu_backup;
    FOR tbl IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
          AND c.relname NOT IN (
              'calendar_feed_tokens', 'ebay_accounts', 'ebay_connect_states',
              'push_subscriptions', 'rate_limit_counters', 'refresh_tokens',
              'profiles', 'movie_night_sessions'
          )
    LOOP
        EXECUTE format('GRANT SELECT ON public.%I TO mcu_backup', tbl.relname);
    END LOOP;
    SELECT string_agg(quote_ident(attname), ', ' ORDER BY attnum) INTO readable
    FROM pg_attribute
    WHERE attrelid = 'public.profiles'::regclass AND attnum > 0 AND NOT attisdropped
      AND attname <> 'pin_hash';
    EXECUTE format('GRANT SELECT (%s) ON public.profiles TO mcu_backup', readable);
    SELECT string_agg(quote_ident(attname), ', ' ORDER BY attnum) INTO readable
    FROM pg_attribute
    WHERE attrelid = 'public.movie_night_sessions'::regclass AND attnum > 0
      AND NOT attisdropped AND attname <> 'invite_token';
    EXECUTE format('GRANT SELECT (%s) ON public.movie_night_sessions TO mcu_backup', readable);
END $$
"""

REVOKES = """
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcu_backup') THEN
        REVOKE ALL ON ALL TABLES IN SCHEMA public FROM mcu_backup;
        REVOKE USAGE ON SCHEMA public FROM mcu_backup;
    END IF;
END $$
"""


def upgrade() -> None:
    op.execute(GRANTS)


def downgrade() -> None:
    op.execute(REVOKES)
