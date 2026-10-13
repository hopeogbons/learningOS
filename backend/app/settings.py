"""Server configuration; never put secrets in frontend environment variables."""
from dataclasses import dataclass, field
import os
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

@dataclass
class Settings:
    app_mode: str = field(default_factory=lambda: os.getenv("APP_MODE", "demo"))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", f"sqlite:///{BASE / '.runtime' / 'learningos.db'}"))
    private_storage_dir: str = field(default_factory=lambda: os.getenv("PRIVATE_STORAGE_DIR", str(BASE / '.runtime' / 'private')))
    api_key: str | None = field(default_factory=lambda: os.getenv("LEARNING_OS_API_KEY"))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", os.getenv("LEARNING_OS_MODEL", "")))
    session_secret: str = field(default_factory=lambda: os.getenv("SESSION_SIGNING_KEY", os.getenv("SESSION_SECRET", "local-demo-only-not-a-production-secret")))
    oidc_issuer: str | None = field(default_factory=lambda: os.getenv("OIDC_ISSUER"))
    oidc_client_id: str | None = field(default_factory=lambda: os.getenv("OIDC_CLIENT_ID"))
    oidc_client_secret: str | None = field(default_factory=lambda: os.getenv("OIDC_CLIENT_SECRET"))
    public_url: str = field(default_factory=lambda: os.getenv("PUBLIC_URL", os.getenv("APP_ORIGIN", "http://localhost:8000")))
    frontend_url: str = field(default_factory=lambda: os.getenv("FRONTEND_URL", os.getenv("APP_ORIGIN", "http://localhost:3000")))
    credentials_key: str | None = field(default_factory=lambda: os.getenv("TOKEN_ENCRYPTION_KEY", os.getenv("CREDENTIALS_KEY")))
    drive_client_id: str | None = field(default_factory=lambda: os.getenv("DRIVE_CLIENT_ID", os.getenv("GOOGLE_CLIENT_ID")))
    drive_client_secret: str | None = field(default_factory=lambda: os.getenv("DRIVE_CLIENT_SECRET", os.getenv("GOOGLE_CLIENT_SECRET")))
    drive_redirect_uri: str | None = field(default_factory=lambda: os.getenv("DRIVE_REDIRECT_URI"))
    s3_bucket: str | None = field(default_factory=lambda: os.getenv("STORAGE_BUCKET", os.getenv("S3_BUCKET")))
    s3_endpoint_url: str | None = field(default_factory=lambda: os.getenv("STORAGE_ENDPOINT", os.getenv("S3_ENDPOINT_URL")))
    max_upload_bytes: int = field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_BYTES", "20971520")))
    session_hours: int = 24
    worker_freshness_seconds: int = 120
    version: str = "0.1.0"

    @property
    def key(self):
        return self.api_key

    @property
    def llm_model(self):
        return self.model

    @property
    def token_encryption_key(self):
        return self.credentials_key

    @property
    def mode(self):
        return self.app_mode

    @property
    def is_demo(self):
        return self.app_mode == "demo"

    def validate(self):
        if self.app_mode not in {"demo", "live", "connected", "production", "test"}:
            raise RuntimeError("Unsupported APP_MODE")
        if self.app_mode == "production":
            if not self.database_url.startswith("postgresql"):
                raise RuntimeError("Production requires PostgreSQL")
            if not all((self.oidc_issuer, self.oidc_client_id, self.oidc_client_secret)) or not self.oidc_issuer.startswith("https://"):
                raise RuntimeError("Production requires OIDC configuration")
            if not self.public_url.startswith("https://") or len(self.session_secret) < 32 or self.session_secret.startswith("local-demo"):
                raise RuntimeError("Production requires HTTPS and strong SESSION_SECRET")
            if not self.api_key or not self.model:
                raise RuntimeError("Production requires configured live model")
            if not self.credentials_key or not self.s3_bucket:
                raise RuntimeError("Production requires encrypted credentials and private object storage")
            from cryptography.fernet import Fernet
            try:
                Fernet(self.credentials_key.encode())
            except (ValueError, TypeError):
                raise RuntimeError("Production requires a valid TOKEN_ENCRYPTION_KEY") from None

settings = Settings()
