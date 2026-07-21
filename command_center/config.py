"""Application settings for the command-center API, read from the environment.

No connection strings, hosts, or secrets are hard-coded; every deployment
value arrives through this object. The database URL is *not* read here -- the
data layer reuses ``emctl.config.database_url`` (the single ``DATABASE_URL``
source), so there is exactly one place the connection string is read.
"""

from __future__ import annotations

from functools import cached_property, lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The repo root, used to resolve artifact files for inline preview. The service
# is colocated in the team-higgs checkout (decision #18), so this is derived
# from the package location rather than configured -- it is not a deployment
# tunable and carries no secret.
_REPO_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Runtime configuration for the web service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Session cookie signing key. Required; no default, so a missing value fails
    # loudly rather than shipping a predictable secret.
    session_secret: str = Field(..., alias="SESSION_SECRET")
    session_cookie_name: str = Field("ccenter_session", alias="SESSION_COOKIE_NAME")
    session_https_only: bool = Field(True, alias="SESSION_HTTPS_ONLY")

    # Google OIDC. Supplied by Tyler for real logins; unused by the dev-auth and
    # test paths, so they may be blank in local/CI runs.
    google_client_id: str = Field("", alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field("", alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field("", alias="GOOGLE_REDIRECT_URI")
    google_issuers_raw: str = Field(
        default="https://accounts.google.com,accounts.google.com",
        alias="GOOGLE_ISSUERS",
    )

    # Allow-list of permitted accounts (parsed by ``allowed_emails``). Tyler
    # only, per decision #17; comma-separated for config flexibility.
    allowed_emails_raw: str = Field(default="", alias="ALLOWED_EMAILS")

    # Dev-only fake login + docs exposure. Never enabled unless explicitly set,
    # and fail-closed in code: refused at startup when a production signal
    # (a configured GOOGLE_CLIENT_ID) is present -- see the validator below, so
    # a stray DEV_AUTH=1 in prod raises rather than silently arming the
    # OIDC-bypassing dev-login (PRD §6).
    dev_auth: bool = Field(False, alias="DEV_AUTH")

    # Least-privilege GitHub token (merge-only, on the two repos) injected from
    # Secret Manager by infra task #29. Blank in local/dev, where the merge
    # endpoint degrades cleanly (503, no crash) rather than merging.
    github_token: str = Field("", alias="GITHUB_TOKEN")
    github_api_url: str = Field("https://api.github.com", alias="GITHUB_API_URL")

    @model_validator(mode="after")
    def _dev_auth_fails_closed(self) -> Settings:
        """Refuse the OIDC-bypass dev-login when a production signal is present.

        ``DEV_AUTH`` arms an unauthenticated session-minting route; a configured
        ``GOOGLE_CLIENT_ID`` means real OIDC is wired up, i.e. this is a
        real/production deployment. The two are mutually exclusive, and this is
        enforced in code (raised at startup) rather than trusting deployment not
        to set the flag.
        """
        if self.dev_auth and self.google_client_id.strip():
            raise ValueError(
                "DEV_AUTH must not be enabled when GOOGLE_CLIENT_ID is "
                "configured: the dev-login bypasses OIDC and cannot run in a "
                "deployment that has real sign-in wired up."
            )
        return self

    @cached_property
    def allowed_emails(self) -> tuple[str, ...]:
        return tuple(
            part.strip().lower()
            for part in self.allowed_emails_raw.split(",")
            if part.strip()
        )

    @cached_property
    def google_issuers(self) -> tuple[str, ...]:
        return tuple(
            part.strip() for part in self.google_issuers_raw.split(",") if part.strip()
        )

    def email_allowed(self, email: str) -> bool:
        return email.strip().lower() in self.allowed_emails

    @property
    def repo_root(self) -> Path:
        return _REPO_ROOT


@lru_cache
def get_settings() -> Settings:
    return Settings()  # values are read from the environment by pydantic-settings
