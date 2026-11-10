"""Search that finds what you mean: trigrams and accent folding (AE7, #355).

Revision ID: 077
Revises: 076

Postgres's `pg_trgm` and `unaccent` extensions, an immutable `search_fold(text)` that lowers a
string, takes its accents off and turns every run of anything but letters and digits into one
space ("Léon: The Professional" → "leon the professional", "Spider-Man" → "spider man"), and
trigram indexes on the folded titles and people's names, so a typo, a missing accent or a missing
hyphen still finds the film.

`unaccent()` itself is only STABLE (its dictionary could change), so it cannot sit in an index
expression. Naming the dictionary explicitly inside an IMMUTABLE SQL function is the usual way
round, and the dictionary is the extension's own, which nothing here changes.

No table is added, so the read-only and backup roles need no grant: a function is executable by
everyone by default. The downgrade removes everything this added.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "077"
down_revision: str | None = "076"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEXES = (
    ("ix_movies_title_trgm", "movies", "title"),
    ("ix_movies_original_title_trgm", "movies", "original_title"),
    ("ix_movie_credits_person_name_trgm", "movie_credits", "person_name"),
    ("ix_movie_credits_character_name_trgm", "movie_credits", "character_name"),
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute(
        """
        CREATE FUNCTION search_fold(value text) RETURNS text
        LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
        AS $$
            SELECT btrim(regexp_replace(
                lower(public.unaccent('public.unaccent'::regdictionary, value)),
                '[^[:alnum:]]+', ' ', 'g'))
        $$
        """
    )
    for name, table, column in INDEXES:
        op.execute(f"CREATE INDEX {name} ON {table} USING gin (search_fold({column}) gin_trgm_ops)")


def downgrade() -> None:
    for name, _table, _column in INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
    op.execute("DROP FUNCTION IF EXISTS search_fold(text)")
    op.execute("DROP EXTENSION IF EXISTS unaccent")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
