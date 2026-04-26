"""derived field triggers — best_format/hdr/audio_owned + search_vector

Adds three derived columns to ``movies`` (``best_format_owned``,
``best_hdr_owned``, ``best_audio_owned``) and the triggers that keep them in
sync with ``collection_items``. Also adds a BEFORE INSERT/UPDATE trigger on
``movies`` that auto-populates ``search_vector`` from title/original_title/
tagline/overview.

Quality rankings:
- format:   4k_bluray > bluray > hddvd > dvd > digital > laserdisc > vhs
- HDR:      Dolby Vision > HDR10+ > HDR10 > HLG
- audio:    Atmos > DTS:X > TrueHD > DTS-HD MA > DTS-HD HR > DTS >
            Dolby Digital Plus / E-AC3 > Dolby Digital / AC3 > PCM > stereo

Revision ID: 0015
Revises: 0014
Create Date: 2026-04-26
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1. Derived columns ------------------------------------------------
    op.add_column("movies", sa.Column("best_format_owned", sa.Text()))
    op.add_column("movies", sa.Column("best_hdr_owned", sa.Text()))
    op.add_column("movies", sa.Column("best_audio_owned", sa.Text()))

    # --- 2. search_vector trigger -----------------------------------------
    # Builds a weighted tsvector from the columns directly available on the
    # movies row. Cast/genre weighting can be layered in later from
    # movie_credits if it becomes useful for ranking.
    op.execute("""
        CREATE OR REPLACE FUNCTION movies_update_search_vector()
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

    # --- 3. Per-movie derived-field recomputer ----------------------------
    # Single SQL UPDATE so all three columns are recomputed atomically. NULL
    # results when no non-deleted collection_items exist for the movie.
    op.execute("""
        CREATE OR REPLACE FUNCTION recalculate_movie_derived_fields(p_movie_id INTEGER)
        RETURNS VOID AS $$
        BEGIN
            UPDATE movies SET
                best_format_owned = (
                    SELECT format
                    FROM collection_items
                    WHERE movie_id = p_movie_id
                      AND deleted_at IS NULL
                    ORDER BY CASE format
                        WHEN '4k_bluray' THEN 1
                        WHEN 'bluray'    THEN 2
                        WHEN 'hddvd'     THEN 3
                        WHEN 'dvd'       THEN 4
                        WHEN 'digital'   THEN 5
                        WHEN 'laserdisc' THEN 6
                        WHEN 'vhs'       THEN 7
                        ELSE 99
                    END
                    LIMIT 1
                ),
                best_hdr_owned = (
                    SELECT hdr_format
                    FROM collection_items
                    WHERE movie_id = p_movie_id
                      AND deleted_at IS NULL
                      AND hdr_format IS NOT NULL
                      AND hdr_format <> ''
                    ORDER BY CASE lower(hdr_format)
                        WHEN 'dolby_vision' THEN 1
                        WHEN 'dolby vision' THEN 1
                        WHEN 'hdr10_plus'   THEN 2
                        WHEN 'hdr10+'       THEN 2
                        WHEN 'hdr10'        THEN 3
                        WHEN 'hlg'          THEN 4
                        ELSE 99
                    END
                    LIMIT 1
                ),
                best_audio_owned = (
                    SELECT audio
                    FROM (
                        SELECT unnest(audio_formats) AS audio
                        FROM collection_items
                        WHERE movie_id = p_movie_id
                          AND deleted_at IS NULL
                          AND audio_formats IS NOT NULL
                    ) sub
                    WHERE audio IS NOT NULL AND audio <> ''
                    ORDER BY CASE lower(audio)
                        WHEN 'dolby_atmos'        THEN 1
                        WHEN 'atmos'              THEN 1
                        WHEN 'dts_x'              THEN 2
                        WHEN 'dts:x'              THEN 2
                        WHEN 'truehd'             THEN 3
                        WHEN 'dolby_truehd'       THEN 3
                        WHEN 'dts_hd_ma'          THEN 4
                        WHEN 'dts-hd ma'          THEN 4
                        WHEN 'dts_hd_hr'          THEN 5
                        WHEN 'dts-hd hr'          THEN 5
                        WHEN 'dts'                THEN 6
                        WHEN 'dolby_digital_plus' THEN 7
                        WHEN 'eac3'               THEN 7
                        WHEN 'dolby_digital'      THEN 8
                        WHEN 'ac3'                THEN 8
                        WHEN 'pcm'                THEN 9
                        WHEN 'stereo'             THEN 10
                        ELSE 99
                    END
                    LIMIT 1
                )
            WHERE id = p_movie_id;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # --- 4. Trigger on collection_items -----------------------------------
    # AFTER INSERT/UPDATE/DELETE: refresh derived fields on the affected
    # movie(s). Soft-delete on collection_items goes through the existing
    # BEFORE DELETE trigger, which converts the DELETE into an UPDATE of
    # ``deleted_at`` — so this AFTER UPDATE branch picks up soft-deletes.
    op.execute("""
        CREATE OR REPLACE FUNCTION collection_items_recalc_movie()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                PERFORM recalculate_movie_derived_fields(NEW.movie_id);
            ELSIF TG_OP = 'UPDATE' THEN
                PERFORM recalculate_movie_derived_fields(NEW.movie_id);
                IF OLD.movie_id IS DISTINCT FROM NEW.movie_id THEN
                    PERFORM recalculate_movie_derived_fields(OLD.movie_id);
                END IF;
            ELSIF TG_OP = 'DELETE' THEN
                PERFORM recalculate_movie_derived_fields(OLD.movie_id);
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER collection_items_recalc_movie_trigger
        AFTER INSERT OR UPDATE OR DELETE ON collection_items
        FOR EACH ROW EXECUTE FUNCTION collection_items_recalc_movie();
    """)

    # --- 5. Backfill -------------------------------------------------------
    # Recompute search_vector for every existing movie row by triggering the
    # BEFORE UPDATE function (no-op write of title back onto itself).
    op.execute("UPDATE movies SET title = title;")

    # Recompute derived fields for every movie that has at least one
    # non-deleted collection_item.
    op.execute("""
        DO $$
        DECLARE r RECORD;
        BEGIN
            FOR r IN
                SELECT DISTINCT movie_id
                FROM collection_items
                WHERE deleted_at IS NULL
            LOOP
                PERFORM recalculate_movie_derived_fields(r.movie_id);
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS collection_items_recalc_movie_trigger ON collection_items;")
    op.execute("DROP FUNCTION IF EXISTS collection_items_recalc_movie;")
    op.execute("DROP FUNCTION IF EXISTS recalculate_movie_derived_fields(INTEGER);")
    op.execute("DROP TRIGGER IF EXISTS movies_search_vector_trigger ON movies;")
    op.execute("DROP FUNCTION IF EXISTS movies_update_search_vector;")
    op.drop_column("movies", "best_audio_owned")
    op.drop_column("movies", "best_hdr_owned")
    op.drop_column("movies", "best_format_owned")
