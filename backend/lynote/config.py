from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", _BACKEND_ROOT / ".env", ".env"),
        extra="ignore",
        populate_by_name=True,
    )

    lynote_env: str = "dev"
    api_host: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("API_HOST", "LYNOTE_API_HOST"),
    )
    api_port: int = Field(
        default=8000,
        validation_alias=AliasChoices("API_PORT", "LYNOTE_API_PORT"),
    )
    api_reload: bool | None = None
    web_origin: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model_name: str = "gpt-4o-mini"
    llm_timeout: float = 45.0
    llm_caller: str = ""

    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model_name: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    embedding_caller: str = ""

    vector_backend: str = "lancedb"
    vector_path: str = "data/vectors"

    retrieve_top_k: int = 8
    retrieve_min_score: float = 0.12

    graph_backend: str = "kuzu"
    graph_path: str = "data/lynote.kuzu"
    workspace_state_path: str = "data/workspace.json"

    ingest_fetch_timeout: float = 20.0
    ingest_fetch_max_bytes: int = 5 * 1024 * 1024
    ingest_upload_max_bytes: int = 32 * 1024 * 1024
    ingest_user_agent: str = "LyNote/0.1 (personal knowledge ingest)"
    search_backend: str = "off"
    search_base_url: str = ""
    search_api_key: str = ""
    search_method: str = "POST"
    search_timeout: float = 8.0
    data_dir: str = Field(default="", validation_alias=AliasChoices("DATA_DIR", "LYNOTE_DATA_DIR"))

    def resolved_embedding_key(self) -> str:
        return self.embedding_api_key.strip() or self.llm_api_key.strip()

    def resolved_embedding_base_url(self) -> str:
        return (self.embedding_base_url.strip() or self.llm_base_url).rstrip("/")

    def resolved_embedding_caller(self) -> str:
        return self.embedding_caller.strip() or self.llm_caller.strip()

    def resolve_data_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        root = Path(self.data_dir.strip()) if self.data_dir.strip() else REPO_ROOT
        return root / path

    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip() or self.web_origin
        origins = [item.strip() for item in raw.split(",") if item.strip()]
        extra = self.web_origin.strip()
        if extra and extra not in origins:
            origins.append(extra)
        return origins or ["http://localhost:3000"]

    def should_reload(self) -> bool:
        if self.api_reload is not None:
            return self.api_reload
        return self.lynote_env.strip().lower() not in {"prod", "production"}


settings = Settings()
