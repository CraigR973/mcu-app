"""include credits and genres in the indexed movie search document

Revision ID: 005
Revises: 004
Create Date: 2026-09-08

Batch 5 re-lands full-text search. Migration 003 intentionally deferred cast and genre
terms even though §3.2 names them; this revision completes that search document and keeps
it current when credits change during the in-app identify flow.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS movies_search_vector_trigger ON movies;")
    op.execute("DROP FUNCTION IF EXISTS movies_update_search_vector();")

    op.execute("""
        CREATE FUNCTION movies_update_search_vector()
        RETURNS TRIGGER AS $$
        DECLARE
            credit_names TEXT;
            genre_names TEXT;
        BEGIN
            SELECT string_agg(person_name, ' ' ORDER BY person_name)
              INTO credit_names
              FROM movie_credits
             WHERE movie_id = NEW.id;

            SELECT string_agg(genre ->> 'name', ' ' ORDER BY genre ->> 'name')
              INTO genre_names
              FROM jsonb_array_elements(
                  CASE
                      -- SQLAlchemy's JSONB type serialises Python ``None`` as the JSON
                      -- scalar ``null`` by default. It is non-SQL-NULL, but it still
                      -- cannot be expanded as an array.
                      WHEN jsonb_typeof(NEW.genres) = 'array' THEN NEW.genres
                      ELSE '[]'::jsonb
                  END
              ) AS genre;

            NEW.search_vector :=
                setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.original_title, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.tagline, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(genre_names, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(credit_names, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(NEW.overview, '')), 'C');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER movies_search_vector_trigger
        BEFORE INSERT OR UPDATE OF title, original_title, overview, tagline, genres
        ON movies
        FOR EACH ROW EXECUTE FUNCTION movies_update_search_vector();
    """)

    op.execute("""
        CREATE FUNCTION movie_credits_refresh_search_vector()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                UPDATE movies SET title = title WHERE id = OLD.movie_id;
            ELSIF TG_OP = 'UPDATE' AND OLD.movie_id IS DISTINCT FROM NEW.movie_id THEN
                UPDATE movies SET title = title WHERE id = OLD.movie_id;
                UPDATE movies SET title = title WHERE id = NEW.movie_id;
            ELSE
                UPDATE movies SET title = title WHERE id = NEW.movie_id;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER movie_credits_search_vector_trigger
        AFTER INSERT OR UPDATE OR DELETE ON movie_credits
        FOR EACH ROW EXECUTE FUNCTION movie_credits_refresh_search_vector();
    """)

    # Existing rows predate the richer function. Naming ``title`` in the assignment
    # deliberately fires the UPDATE OF trigger while leaving the source value unchanged.
    op.execute("UPDATE movies SET title = title;")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS movie_credits_search_vector_trigger ON movie_credits;")
    op.execute("DROP FUNCTION IF EXISTS movie_credits_refresh_search_vector();")
    op.execute("DROP TRIGGER IF EXISTS movies_search_vector_trigger ON movies;")
    op.execute("DROP FUNCTION IF EXISTS movies_update_search_vector();")

    op.execute("""
        CREATE FUNCTION movies_update_search_vector()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.original_title, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.tagline, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(NEW.overview, '')), 'C');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER movies_search_vector_trigger
        BEFORE INSERT OR UPDATE OF title, original_title, overview, tagline
        ON movies
        FOR EACH ROW EXECUTE FUNCTION movies_update_search_vector();
    """)
    op.execute("UPDATE movies SET title = title;")
