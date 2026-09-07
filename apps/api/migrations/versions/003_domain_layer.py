"""domain layer — movies, movie_credits, collection_items and their triggers

Revision ID: 003
Revises: 002
Create Date: 2026-09-07

Batch 4. Re-lands roadmap phases 1.1 and 1.3–1.8 onto the re-scaffold baseline, and
fixes the defect 1.2/1.3 introduced: §3.4 designs ``location``, ``section`` and ``shelf``
on ``collection_items`` and the April migrations omitted all three, so the import
discarded the structure the parser had extracted for every row (`STATUS.md` gotcha 0b).

**This is not a transcription of the April schema.** That schema had drifted from §3.2–3.4
in ways that could not survive alongside the roadmap's own design: the TMDB id used as the
primary key, a scalar ``format`` where §3.4 specifies a ``formats`` array, scalar
``hdr_format``/``audio_formats[]`` where §3.4 specifies ``video_specs``/``audio_specs``
JSONB, and a second format vocabulary that the importer had to translate into. §3.4 wins
here; the derived-field triggers below are rewritten to read the JSONB shapes, preserving
the *behaviour* migration 0015 established rather than its column references.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _create_shared_trigger_functions()
    _create_movies()
    _create_movie_credits()
    _create_collection_items()
    _create_derived_field_triggers()


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS collection_items_recalc_movie_trigger ON collection_items;")
    op.execute("DROP FUNCTION IF EXISTS collection_items_recalc_movie();")
    op.execute("DROP FUNCTION IF EXISTS recalculate_movie_derived_fields(UUID);")
    op.execute("DROP TRIGGER IF EXISTS movies_search_vector_trigger ON movies;")
    op.execute("DROP FUNCTION IF EXISTS movies_update_search_vector();")

    op.drop_table("collection_items")
    op.drop_table("movie_credits")
    op.drop_table("movies")

    # Both functions are database-level objects that outlive their tables. Dropping them
    # is what makes `downgrade base` leave an empty database, which CI asserts on every
    # push — the same reason migration 002 drops the `user_role` enum.
    op.execute("DROP FUNCTION IF EXISTS soft_delete();")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")


# ---------------------------------------------------------------------------
# Shared trigger functions
# ---------------------------------------------------------------------------


def _create_shared_trigger_functions() -> None:
    # `NOW() AT TIME ZONE 'utc'` rather than the April schema's bare `NOW()`. Every
    # timestamp column in this app is naive-UTC (`AGENTS.md`), and a bare NOW() is a
    # timestamptz that Postgres casts using the *session* TimeZone — so a connection
    # opened in any other zone would silently write a local-time value into a column
    # every reader assumes is UTC.
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = (NOW() AT TIME ZONE 'utc');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Intercepts DELETE and rewrites it as a soft delete. Attached to collection_items
    # only: it is what makes a deleted disc still visible in the trash UI, and it is
    # also the mechanism the derived-field recalculation depends on — a DELETE arrives
    # at that trigger as an UPDATE of `deleted_at`.
    op.execute("""
        CREATE OR REPLACE FUNCTION soft_delete()
        RETURNS TRIGGER AS $$
        BEGIN
            EXECUTE format(
                'UPDATE %I SET deleted_at = (NOW() AT TIME ZONE ''utc'') '
                'WHERE id = $1 AND deleted_at IS NULL',
                TG_TABLE_NAME
            ) USING OLD.id;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)


# ---------------------------------------------------------------------------
# movies (§3.2)
# ---------------------------------------------------------------------------


def _create_movies() -> None:
    op.create_table(
        "movies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tmdb_id", sa.Integer(), nullable=True),
        sa.Column("imdb_id", sa.String(20), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("original_title", sa.String(500), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("runtime_minutes", sa.Integer(), nullable=True),
        sa.Column("overview", sa.Text(), nullable=True),
        sa.Column("tagline", sa.Text(), nullable=True),
        sa.Column("poster_path", sa.String(255), nullable=True),
        sa.Column("backdrop_path", sa.String(255), nullable=True),
        sa.Column("tmdb_rating", sa.Numeric(3, 1), nullable=True),
        sa.Column("tmdb_vote_count", sa.Integer(), nullable=True),
        sa.Column("genres", postgresql.JSONB(), nullable=True),
        sa.Column("genre_ids", postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column("top_cast_summary", postgresql.JSONB(), nullable=True),
        sa.Column("trailer_key", sa.String(50), nullable=True),
        sa.Column("letterboxd_slug", sa.String(255), nullable=True),
        sa.Column("media_type", sa.String(50), nullable=True),
        sa.Column("is_tv", sa.Boolean(), nullable=False, server_default="false"),
        # Derived by trigger — never written by application code.
        sa.Column("best_format_owned", sa.String(50), nullable=True),
        sa.Column("best_hdr_owned", sa.String(50), nullable=True),
        sa.Column("best_audio_owned", sa.String(50), nullable=True),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column("last_tmdb_sync_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False
        ),
    )

    # Unique but nullable: a film TMDB has never heard of can still be catalogued, and
    # Postgres treats each NULL as distinct so several such rows can coexist.
    op.create_index("uq_movies_tmdb_id", "movies", ["tmdb_id"], unique=True)
    op.create_index("ix_movies_year", "movies", ["year"])
    op.create_index("ix_movies_search_vector", "movies", ["search_vector"], postgresql_using="gin")
    op.create_index("ix_movies_genre_ids", "movies", ["genre_ids"], postgresql_using="gin")
    # Partial: every list query filters deleted rows out, and indexing the 99.9% of rows
    # that are live is smaller than indexing the column.
    op.create_index(
        "ix_movies_title_live",
        "movies",
        ["title"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.execute("""
        CREATE TRIGGER movies_set_updated_at
        BEFORE UPDATE ON movies
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)


# ---------------------------------------------------------------------------
# movie_credits (§3.3)
# ---------------------------------------------------------------------------


def _create_movie_credits() -> None:
    op.create_table(
        "movie_credits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "movie_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("movies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("person_name", sa.String(255), nullable=False),
        sa.Column("tmdb_person_id", sa.Integer(), nullable=True),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("character_name", sa.String(255), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_check_constraint(
        "ck_movie_credits_role",
        "movie_credits",
        "role IN ('cast', 'director', 'writer', 'producer', 'composer')",
    )
    op.create_index("ix_movie_credits_movie_id", "movie_credits", ["movie_id"])
    op.create_index("ix_movie_credits_person_name", "movie_credits", ["person_name"])
    op.create_index("ix_movie_credits_tmdb_person_id", "movie_credits", ["tmdb_person_id"])
    # The "all cast for this film, in billing order" query the detail page runs.
    op.create_index(
        "ix_movie_credits_movie_role_order",
        "movie_credits",
        ["movie_id", "role", "display_order"],
    )


# ---------------------------------------------------------------------------
# collection_items (§3.4)
# ---------------------------------------------------------------------------


def _create_collection_items() -> None:
    op.create_table(
        "collection_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "movie_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("movies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("formats", postgresql.JSONB(), nullable=False, server_default="[]"),
        # The three columns §3.4 designed and the April schema omitted.
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("section", sa.String(100), nullable=True),
        sa.Column("shelf", sa.String(50), nullable=True),
        sa.Column("sub_category", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("purchase_price", sa.Numeric(8, 2), nullable=True),
        sa.Column("price_is_estimate", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("purchase_source", sa.String(255), nullable=True),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("condition", sa.String(50), nullable=True),
        sa.Column("condition_updated_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("has_playback_issues", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("playback_notes", sa.Text(), nullable=True),
        sa.Column("suggest_exclude", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("photo_urls", postgresql.JSONB(), nullable=True),
        sa.Column("barcode", sa.String(50), nullable=True),
        sa.Column("video_specs", postgresql.JSONB(), nullable=True),
        sa.Column("audio_specs", postgresql.JSONB(), nullable=True),
        sa.Column("special_features", postgresql.JSONB(), nullable=True),
        sa.Column("region_code", sa.String(20), nullable=True),
        sa.Column("release_label", sa.String(100), nullable=True),
        sa.Column("specs_source", sa.String(50), nullable=True),
        sa.Column("specs_last_synced_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("listing_status", sa.String(30), nullable=False, server_default="in_collection"),
        sa.Column("ebay_listing_url", sa.Text(), nullable=True),
        sa.Column("listing_price", sa.Numeric(8, 2), nullable=True),
        sa.Column(
            "added_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("added_at_utc", sa.DateTime(timezone=False), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False
        ),
    )

    # Enforced in the database, not merely asserted by a query after the import. The
    # acceptance criterion for this batch is that `section` values fall in this set;
    # a CHECK is what makes that true of every future write as well as this one.
    op.create_check_constraint(
        "ck_collection_items_section",
        "collection_items",
        "section IS NULL OR section IN ('Front', 'Back', 'Lounge', 'Garage', 'Digital')",
    )
    op.create_check_constraint(
        "ck_collection_items_condition",
        "collection_items",
        "condition IS NULL OR condition IN ('new', 'like_new', 'good', 'acceptable', 'damaged')",
    )
    op.create_check_constraint(
        "ck_collection_items_listing_status",
        "collection_items",
        "listing_status IN ('in_collection', 'listed_for_sale', 'sold', 'donated')",
    )
    # `formats` is read by the derived-field trigger with jsonb_array_elements_text.
    # Guaranteeing it is an array here means that trigger cannot be handed an object or
    # a bare string by some future write path.
    op.create_check_constraint(
        "ck_collection_items_formats_is_array",
        "collection_items",
        "jsonb_typeof(formats) = 'array'",
    )

    op.create_index("ix_collection_items_movie_id", "collection_items", ["movie_id"])
    op.create_index("ix_collection_items_deleted_at", "collection_items", ["deleted_at"])
    op.create_index("ix_collection_items_barcode", "collection_items", ["barcode"])
    op.create_index(
        "ix_collection_items_formats", "collection_items", ["formats"], postgresql_using="gin"
    )
    # The composite that answers "everything on the Front 2nd shelf" — §6.2's promise,
    # and Batch 6's whole subject. Partial for the same reason as the movies title index.
    op.create_index(
        "ix_collection_items_section_shelf_live",
        "collection_items",
        ["section", "shelf"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.execute("""
        CREATE TRIGGER collection_items_set_updated_at
        BEFORE UPDATE ON collection_items
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)
    op.execute("""
        CREATE TRIGGER collection_items_soft_delete
        BEFORE DELETE ON collection_items
        FOR EACH ROW EXECUTE FUNCTION soft_delete();
    """)


# ---------------------------------------------------------------------------
# Derived fields (§3.2, phase 1.8)
# ---------------------------------------------------------------------------


def _create_derived_field_triggers() -> None:
    # --- search_vector -----------------------------------------------------
    # Weighted from the columns on the movies row itself. §3.2 also names cast and
    # genres; those live in movie_credits and would need a join inside a BEFORE ROW
    # trigger, which is why April deferred them and why this does too. Batch 5 owns
    # search and can layer them in when ranking actually calls for it.
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

    # --- best_format / best_hdr / best_audio -------------------------------
    # One UPDATE so all three are recomputed atomically, and NULL when the movie has no
    # live collection_items left.
    #
    # Each subquery unnests a JSONB array through a LATERAL join. The CASE guard around
    # each one matters: jsonb_array_elements raises on a non-array, and a LATERAL is
    # evaluated per row *before* the WHERE clause could filter the bad row out.
    #
    # Ranking is by CASE position with the raw value as a tiebreak, so two formats of
    # equal rank resolve deterministically instead of by whichever row Postgres reaches
    # first. Both the snake_case codes the importer writes and the spaced display forms
    # §3.4's examples use are accepted, because both will exist in this column.
    op.execute("""
        CREATE OR REPLACE FUNCTION recalculate_movie_derived_fields(p_movie_id UUID)
        RETURNS VOID AS $$
        BEGIN
            UPDATE movies SET
                best_format_owned = (
                    SELECT t.fmt
                    FROM collection_items ci
                    CROSS JOIN LATERAL jsonb_array_elements_text(
                        CASE WHEN jsonb_typeof(ci.formats) = 'array'
                             THEN ci.formats ELSE '[]'::jsonb END
                    ) AS t(fmt)
                    WHERE ci.movie_id = p_movie_id
                      AND ci.deleted_at IS NULL
                      AND coalesce(t.fmt, '') <> ''
                    ORDER BY CASE lower(t.fmt)
                        WHEN '4k_uhd'  THEN 1
                        WHEN '4k'      THEN 1
                        WHEN 'blu_ray' THEN 2
                        WHEN 'blu-ray' THEN 2
                        WHEN 'dvd'     THEN 3
                        WHEN 'download' THEN 4
                        WHEN 'digital'  THEN 4
                        ELSE 99
                    END, t.fmt
                    LIMIT 1
                ),
                best_hdr_owned = (
                    SELECT t.hdr
                    FROM collection_items ci
                    CROSS JOIN LATERAL jsonb_array_elements_text(
                        CASE WHEN jsonb_typeof(ci.video_specs -> 'hdr') = 'array'
                             THEN ci.video_specs -> 'hdr' ELSE '[]'::jsonb END
                    ) AS t(hdr)
                    WHERE ci.movie_id = p_movie_id
                      AND ci.deleted_at IS NULL
                      AND coalesce(t.hdr, '') <> ''
                    ORDER BY CASE lower(t.hdr)
                        WHEN 'dolby_vision' THEN 1
                        WHEN 'dolby vision' THEN 1
                        WHEN 'hdr10_plus'   THEN 2
                        WHEN 'hdr10+'       THEN 2
                        WHEN 'hdr10'        THEN 3
                        WHEN 'hlg'          THEN 4
                        ELSE 99
                    END, t.hdr
                    LIMIT 1
                ),
                best_audio_owned = (
                    SELECT t.spec ->> 'format'
                    FROM collection_items ci
                    CROSS JOIN LATERAL jsonb_array_elements(
                        CASE WHEN jsonb_typeof(ci.audio_specs) = 'array'
                             THEN ci.audio_specs ELSE '[]'::jsonb END
                    ) AS t(spec)
                    WHERE ci.movie_id = p_movie_id
                      AND ci.deleted_at IS NULL
                      AND coalesce(t.spec ->> 'format', '') <> ''
                    ORDER BY CASE lower(t.spec ->> 'format')
                        WHEN 'dolby_atmos'        THEN 1
                        WHEN 'dolby atmos'        THEN 1
                        WHEN 'atmos'              THEN 1
                        WHEN 'dts_x'              THEN 2
                        WHEN 'dts:x'              THEN 2
                        WHEN 'truehd'             THEN 3
                        WHEN 'dolby_truehd'       THEN 3
                        WHEN 'dolby truehd'       THEN 3
                        WHEN 'dts_hd_ma'          THEN 4
                        WHEN 'dts-hd ma'          THEN 4
                        WHEN 'dts_hd_hr'          THEN 5
                        WHEN 'dts-hd hr'          THEN 5
                        WHEN 'dts'                THEN 6
                        WHEN 'dolby_digital_plus' THEN 7
                        WHEN 'dolby digital plus' THEN 7
                        WHEN 'eac3'               THEN 7
                        WHEN 'dolby_digital'      THEN 8
                        WHEN 'dolby digital'      THEN 8
                        WHEN 'ac3'                THEN 8
                        WHEN 'pcm'                THEN 9
                        WHEN 'stereo'             THEN 10
                        ELSE 99
                    END, t.spec ->> 'format'
                    LIMIT 1
                )
            WHERE id = p_movie_id;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # AFTER INSERT/UPDATE/DELETE on collection_items. The UPDATE branch recalculates
    # both movies when an item is moved between films, and it is also the branch a soft
    # delete arrives on — the BEFORE DELETE trigger above has already turned the DELETE
    # into an UPDATE of `deleted_at` by the time this fires.
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

    # No backfill pass. Migration 0015 needed one because it added these triggers to
    # tables that already held the April import; here the tables are created empty in
    # this same migration, so there is nothing to recompute.
