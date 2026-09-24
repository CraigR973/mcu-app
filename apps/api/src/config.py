import sys
from collections.abc import Sequence
from enum import StrEnum
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_SECRETS = {
    "change-me-access",
    "change-me-refresh",
    "change-me-to-a-random-secret-at-least-32-chars",
    "change-me-to-another-random-secret-at-least-32-chars",
}
_MIN_SECRET_LENGTH = 32


def alembic_config_url(database_url: str) -> str:
    """Escape ConfigParser interpolation tokens in an Alembic database URL."""
    return database_url.replace("%", "%%")


def psycopg2_dsn(database_url: str) -> str:
    """Convert the app's SQLAlchemy URL into a libpq DSN psycopg2 can parse.

    :attr:`Settings.database_url` is normalised for asyncpg at load time — the scheme
    becomes ``postgresql+asyncpg`` and libpq's ``sslmode`` is renamed to asyncpg's
    ``ssl``. psycopg2 speaks libpq and rejects both, with an error naming the whole URL as
    an "invalid connection option", which reads like a malformed URL rather than the
    driver mismatch it is.

    This matters because the batch importer is sync psycopg2 while the API is async
    asyncpg, so one settings value has to serve two drivers. Handing
    ``settings.database_url`` straight to ``psycopg2.connect`` fails against every hosted
    database and succeeds against a bare local one, which is exactly the shape of bug that
    reaches production.
    """
    parts = urlsplit(database_url)
    scheme = "postgresql" if parts.scheme.startswith("postgresql") else parts.scheme

    query: list[tuple[str, str]] = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        query.append(("sslmode", value) if key == "ssl" else (key, value))

    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class ProcessRole(StrEnum):
    """What kind of process loaded these settings — `DECISIONS.md` #204.

    ``web`` serves the API and signs sessions, so it must never start without real secrets.
    ``job`` is a command under ``src.scripts`` — a Railway cron, an import — which signs no
    token and serves no browser. Until 2026-09-23 both were held to the web server's rule,
    and every scheduled run crashed on import for want of JWT secrets it never uses.
    """

    web = "web"
    job = "job"


def launched_role(argv: Sequence[str]) -> ProcessRole:
    """``job`` for ``python -m src.scripts.<name>``; ``web`` for anything else.

    Read from how the interpreter was launched rather than declared by each script,
    because this module validates at import: a script's own imports would run before any
    declaration it could make. ``PROCESS_ROLE`` in the environment still wins.
    """
    args = list(argv)
    try:
        target = args[args.index("-m") + 1]
    except (ValueError, IndexError):
        return ProcessRole.web
    return ProcessRole.job if target.startswith("src.scripts.") else ProcessRole.web


def _role_of_this_process() -> ProcessRole:
    return launched_role(sys.orig_argv)


class Environment(StrEnum):
    development = "development"
    staging = "staging"
    production = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mcu_app"

    # Auth secrets are consumed when Batch 3 lands PIN + JWT auth. Keeping them in
    # the foundation means a non-development deployment can never start weakly.
    jwt_access_secret: str = ""
    jwt_refresh_secret: str = ""

    # TMDB (optional at API boot; used by the Batch 4 import pipeline)
    tmdb_api_key: str = ""
    tmdb_read_token: str = ""

    # eBay (Batch 28). Optional at boot, like TMDB above: the API must start without
    # them. ``ebay_account_deletion_endpoint`` is the URL registered with eBay and is
    # hashed verbatim into the challenge reply, so it is configuration rather than
    # anything derived from an incoming request — see ``routers/ebay.py``.
    ebay_verification_token: str = ""
    ebay_account_deletion_endpoint: str = ""

    # The Browse API's client credentials (Batch 28, Phase 4.1). A self-service production
    # keyset — `DECISIONS.md` #126 established that Browse needs no partner approval.
    #
    # **Optional here and checked at use**, like the TMDB pair above, so the API boots
    # without them. That is only safe because the absence is *visible*:
    # `/api/v1/health/ready` reports `ebay`, and `EbayClient` raises `EbayNotConfigured`
    # before sending anything rather than letting eBay answer 401 to an empty credential.
    # Without both of those this is the shape of the 2026-09-09 TMDB outage exactly — a
    # value that lives only in a hosting variable has nothing testing it.
    ebay_client_id: str = ""
    ebay_client_secret: str = ""
    #: Which eBay site to search. `EBAY_GB` is the one the criterion's "UK median" means,
    #: and it is what #126 and #129 measured against.
    ebay_marketplace_id: str = "EBAY_GB"

    # Brave's web search (Batch T7, `DECISIONS.md` #202): it finds each disc's Blu-ray.com
    # release page, because #110 bars the site's own search. Optional at boot and checked
    # at use, like eBay above; the Disc specs page says when it is missing.
    brave_search_api_key: str = ""

    # Web Push (Batch 11). Set in Railway on 2026-09-09; the names here are fixed by
    # what is already there. Absent locally and in CI, where every send is stubbed.
    #
    # **The public key is served to the browser by the API** rather than baked into the
    # bundle as a `VITE_` variable. Two reasons, and the second is the one that matters:
    # a build-time copy needs a Vercel change plus a redeploy before push can work at
    # all, and it can drift from the private key silently — which is precisely the shape
    # of the TMDB outage, where a value living only in a hosting variable had no test and
    # no way to be noticed. Served from here, the key the browser subscribes with is
    # derived from the private key the API signs with, so they cannot disagree.
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    #: RFC 8292 §2.1 — a `mailto:` or `https:` URL a push service can use to contact the
    #: sender. Not a secret; required by Firefox's service, which 401s without it.
    vapid_subject: str = ""

    # The AI assistant (Batch 30). `ANTHROPIC_API_KEY` was set in Railway on 2026-09-09.
    #
    # **The model id lives here and nowhere else.** `docs/phase-batches.md` says "do not
    # guess a model id" — the April spec predates the current lineup by two generations —
    # so it is one config value, validated against `SUPPORTED_MODELS`, rather than a
    # string repeated across the code where only one copy gets updated.
    # Photos (Batch 25). Bytes live in Postgres — storage was settled as Neon by the owner
    # on 2026-09-09, and §3.10's "Supabase Storage" refers to a product this app does not
    # have (`DECISIONS.md` #17).
    #
    # **A setting rather than a constant, on purpose.** `OWNER-ACTIONS.md` reserves this
    # number as an owner choice because it "sets a shape that is annoying to reverse once
    # photos exist". Configuration is what stops that being true: changing it is an
    # environment variable and a re-upload, not a migration, and the database's CHECK sits
    # well above it so a tuned-up value needs no schema change either.
    photo_target_kb: int = 300

    anthropic_api_key: str = ""
    ai_model: str = "claude-sonnet-5"
    #: §9.7's cap. **50 messages per person per day** (owner, 2026-09-09) — a starting
    #: value, not a commitment, and editable in the app. This is the fallback for a person
    #: who has never changed it.
    ai_daily_message_cap: int = 50
    #: A second ceiling in dollars, because a message cap alone does not bound spend: one
    #: question over a long conversation costs many times a short one. Zero disables it.
    ai_daily_cost_cap_usd: float = 2.0

    # App
    frontend_origin: str = "http://localhost:5173"
    #: How many proxy hops in front of the app are ours. Exactly one on Railway, which
    #: is the default. Used to read ``X-Forwarded-For`` from the right-hand end — see
    #: :func:`src.rate_limit.client_address`, where reading the leftmost entry would let
    #: any caller forge a fresh rate-limit bucket per request.
    trusted_proxy_count: int = 1
    sentry_dsn_backend: str = ""
    log_level: str = "INFO"
    environment: Environment = Environment.development
    #: Web server or job. Derived from how the process was launched unless
    #: ``PROCESS_ROLE`` says otherwise; see :class:`ProcessRole`.
    process_role: ProcessRole = Field(default_factory=_role_of_this_process)
    # Railway injects this for Git-backed deployments. The health endpoint
    # exposes it so deployment verification can prove which commit is running.
    railway_git_commit_sha: str | None = None

    @field_validator("database_url", mode="before")
    @classmethod
    def _use_asyncpg_driver(cls, value: object) -> object:
        """Normalise hosted Postgres URLs for SQLAlchemy's asyncpg dialect.

        Neon emits libpq-style ``sslmode`` and ``channel_binding`` query
        parameters. asyncpg calls the first option ``ssl`` and does not support
        the second, so passing Neon's URL through unchanged raises ``TypeError``
        before a connection is attempted.
        """
        if not isinstance(value, str):
            return value

        parts = urlsplit(value)
        scheme = parts.scheme
        if scheme in {"postgres", "postgresql"}:
            scheme = "postgresql+asyncpg"

        sslmode: str | None = None
        has_asyncpg_ssl = False
        query: list[tuple[str, str]] = []
        for key, query_value in parse_qsl(parts.query, keep_blank_values=True):
            if key == "sslmode":
                sslmode = query_value
            elif key == "channel_binding":
                continue
            else:
                query.append((key, query_value))
                has_asyncpg_ssl = has_asyncpg_ssl or key == "ssl"

        if sslmode and not has_asyncpg_ssl:
            query.append(("ssl", sslmode))

        return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    @field_validator("ai_model")
    @classmethod
    def _known_model(cls, value: str) -> str:
        """Refuse a model id this app has no pricing for.

        A wrong id is otherwise a 404 on the first person to open the assistant, and an
        id that is merely *unpriced* is worse: it works, and silently logs every call as
        costing nothing, which makes §9.7's cost cap unenforceable.
        """
        from src.services.ai.pricing import SUPPORTED_MODELS

        if value not in SUPPORTED_MODELS:
            raise ValueError(f"ai_model must be one of {', '.join(SUPPORTED_MODELS)}")
        return value

    @model_validator(mode="after")
    def _reject_weak_secrets_outside_development(self) -> "Settings":
        if self.environment == Environment.development:
            return self

        # The session secrets and the browser origin belong to the web server. A job never
        # reads them (only `auth.py` and `main.py`'s CORS do), and `main.py` refuses to
        # start as a job, so skipping them here cannot let the API boot weakly.
        serves_web = self.process_role == ProcessRole.web

        errors: list[str] = []
        if serves_web:
            for field_name, secret in (
                ("jwt_access_secret", self.jwt_access_secret),
                ("jwt_refresh_secret", self.jwt_refresh_secret),
            ):
                if not secret:
                    errors.append(f"{field_name} is empty")
                elif secret in _PLACEHOLDER_SECRETS:
                    errors.append(f"{field_name} is a placeholder value")
                elif len(secret) < _MIN_SECRET_LENGTH:
                    errors.append(f"{field_name} must be at least {_MIN_SECRET_LENGTH} characters")

            if self.jwt_access_secret == self.jwt_refresh_secret:
                errors.append("jwt_access_secret and jwt_refresh_secret must be different")
        if not self.database_url:
            errors.append("database_url is empty")
        if serves_web and (
            not self.frontend_origin or self.frontend_origin.startswith("http://localhost")
        ):
            errors.append("frontend_origin must not be empty or localhost outside development")

        if errors:
            raise ValueError("Refusing to start with weak/missing secrets: " + "; ".join(errors))
        return self


settings = Settings()


def docs_urls(environment: Environment) -> dict[str, str | None]:
    """Disable API discovery routes in production for this private application."""
    if environment == Environment.production:
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {
        "docs_url": "/api/docs",
        "redoc_url": "/api/redoc",
        "openapi_url": "/api/openapi.json",
    }
