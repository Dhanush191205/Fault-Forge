"""Environment-only deployment configuration with explicit fixture isolation."""
from functools import lru_cache
from pydantic import model_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Read environment settings; reject unsafe production combinations at startup."""

    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")
    environment: str = "development"
    database_url: str = "sqlite:///./faultforge.db"
    demo_mode: bool = True
    rag_backend: str = "fixture"
    llm_provider: str = "fixture"
    llm_base_url: str = "https://integrate.api.nvidia.com/v1"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_timeout: int = Field(default=45, ge=5, le=90)
    embedding_base_url: str = "https://integrate.api.nvidia.com/v1"
    embedding_model: str = ""
    embedding_api_key: str = ""
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_ssl: bool = False
    chroma_token: str = ""
    chroma_collection: str = "faultforge_v1"
    retrieval_max_distance: float = 0.45
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    secure_cookies: bool = False
    session_hours: int = 8
    generator_version: str = "grounded-selector/1.0.0"
    instructor_email: str = "instructor@faultforge.local"
    trainee_email: str = "trainee@faultforge.local"
    instructor_password: str = ""
    trainee_password: str = ""

    @model_validator(mode="after")
    def enforce_configuration(self):
        """Validate config inputs; return settings or raise a startup validation error."""
        if self.rag_backend not in {"fixture", "chroma"} or self.llm_provider not in {"fixture", "nvidia"}:
            raise ValueError("Unknown provider configuration")
        if not self.demo_mode and (self.rag_backend == "fixture" or self.llm_provider == "fixture"):
            raise ValueError("Fixture providers require DEMO_MODE=true")
        if self.environment == "production":
            if self.demo_mode or not self.database_url.startswith("postgresql") or not self.secure_cookies:
                raise ValueError("Production requires PostgreSQL, secure cookies and DEMO_MODE=false")
            if not self.allowed_origins or any(not x.startswith("https://") for x in self.allowed_origins):
                raise ValueError("Production requires explicit HTTPS origins")
            if not self.llm_base_url.startswith("https://") or not self.embedding_base_url.startswith("https://"):
                raise ValueError("Production inference requires a TLS endpoint")
        if "*" in self.allowed_origins:
            raise ValueError("Wildcard origins are forbidden")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached validated environment settings; fail startup on invalid configuration."""
    return Settings()
