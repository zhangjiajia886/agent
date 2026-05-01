from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field


def _load_dotenv():
    """Load .env file from project root if it exists."""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if key:
                    os.environ[key] = value


_load_dotenv()


@dataclass
class ModelProfile:
    """Single model endpoint configuration."""
    provider: str = "openai"
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    custcode: str = ""
    componentcode: str = ""
    extra_headers: dict = field(default_factory=dict)

    def build_headers(self) -> dict:
        headers = {}
        if self.custcode:
            headers["custCode"] = self.custcode
        if self.componentcode:
            headers["componentCode"] = self.componentcode
        headers.update(self.extra_headers)
        return headers


@dataclass
class Settings:
    # Paths
    project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent)
    db_path: str = ""
    data_dir: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"])

    # ── Database ──
    db_type: str = "sqlite"          # sqlite | mysql
    sqlite_path: str = ""

    # MySQL
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "agentflow"
    mysql_charset: str = "utf8mb4"
    mysql_pool_size: int = 10
    mysql_max_overflow: int = 20

    # ── Redis ──
    redis_mode: str = "off"          # off | standalone | cluster
    redis_uri: str = ""
    redis_password: str = ""
    redis_database: int = 0
    redis_cluster_nodes: str = ""
    redis_cluster_username: str = "default"
    redis_cluster_password: str = ""
    redis_max_connections: int = 20
    redis_socket_timeout: int = 120
    redis_connect_timeout: int = 30
    redis_retry_attempts: int = 3

    # ── Neo4j ──
    neo4j_enabled: bool = False
    neo4j_uri: str = ""
    neo4j_username: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"
    neo4j_max_connection_pool_size: int = 20
    neo4j_connection_timeout: int = 60

    # ── Milvus ──
    milvus_enabled: bool = False
    milvus_uri: str = ""
    milvus_db_name: str = "agentflow"
    milvus_timeout: int = 60

    # ── Main LLM (default for chat) ──
    llm_provider: str = "openai"
    llm_base_url: str = ""
    llm_default_model: str = ""
    llm_api_key: str = ""
    llm_custcode: str = ""
    llm_componentcode: str = ""

    # ── L1 LLM (lightweight) ──
    l1_llm_model: str = ""
    l1_llm_base_url: str = ""
    l1_llm_api_key: str = ""
    l1_llm_custcode: str = ""
    l1_llm_componentcode: str = ""

    # ── Embedding ──
    embedding_model: str = ""
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_custcode: str = ""
    embedding_componentcode: str = ""
    embedding_dim: int = 1024

    # ── AIPro 聚合平台 (OpenAI 兼容) ──
    aipro_base_url: str = ""
    aipro_api_key: str = ""
    aipro_default_model: str = ""

    # ── Reranker ──
    rerank_enabled: bool = False
    rerank_model: str = ""
    rerank_base_url: str = ""
    rerank_api_key: str = ""
    rerank_custcode: str = ""
    rerank_componentcode: str = ""

    # ── Concurrency ──
    max_concurrent_workflows: int = 3
    max_concurrent_llm_calls: int = 2
    max_concurrent_tools: int = 10
    max_async: int = 8

    # ── Document Processing ──
    chunk_size: int = 1200
    chunk_overlap_size: int = 100
    max_tokens: int = 2048
    summary_language: str = "Chinese"

    # ── Security ──
    secrets_encryption_key: str = ""

    # ── MCP ──
    mcp_config_path: str = ""

    def __post_init__(self):
        if not self.data_dir:
            self.data_dir = str(self.project_root / "data")
        if not self.db_path:
            if self.db_type == "sqlite":
                self.db_path = str(self.project_root / self.sqlite_path) if self.sqlite_path else str(Path(self.data_dir) / "agent.db")
            else:
                self.db_path = f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset={self.mysql_charset}"
        if not self.mcp_config_path:
            self.mcp_config_path = str(self.project_root / "config" / "mcp_servers.yaml")
        os.makedirs(self.data_dir, exist_ok=True)

    @property
    def main_llm(self) -> ModelProfile:
        return ModelProfile(
            provider=self.llm_provider,
            model=self.llm_default_model,
            base_url=self.llm_base_url,
            api_key=self.llm_api_key,
            custcode=self.llm_custcode,
            componentcode=self.llm_componentcode,
        )

    @property
    def l1_llm(self) -> ModelProfile:
        return ModelProfile(
            provider=self.llm_provider,
            model=self.l1_llm_model,
            base_url=self.l1_llm_base_url or self.llm_base_url,
            api_key=self.l1_llm_api_key or self.llm_api_key,
            custcode=self.l1_llm_custcode or self.llm_custcode,
            componentcode=self.l1_llm_componentcode or self.llm_componentcode,
        )

    @property
    def embedding(self) -> ModelProfile:
        return ModelProfile(
            provider=self.llm_provider,
            model=self.embedding_model,
            base_url=self.embedding_base_url or self.llm_base_url,
            api_key=self.embedding_api_key or self.llm_api_key,
            custcode=self.embedding_custcode or self.llm_custcode,
            componentcode=self.embedding_componentcode or self.llm_componentcode,
        )

    def get_model_profiles(self) -> dict[str, ModelProfile]:
        """Return all configured model profiles."""
        profiles = {}
        if self.llm_default_model:
            profiles["main"] = self.main_llm
        if self.l1_llm_model:
            profiles["l1"] = self.l1_llm
        if self.embedding_model:
            profiles["embedding"] = self.embedding
        return profiles


def _bool(val: str) -> bool:
    return val.lower() in ("1", "true", "yes", "on")


def get_settings() -> Settings:
    return Settings(
        # Server
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        cors_origins=[s.strip() for s in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if s.strip()],

        # Database
        db_type=os.getenv("DB_TYPE", "sqlite"),
        sqlite_path=os.getenv("SQLITE_PATH", ""),
        mysql_host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        mysql_port=int(os.getenv("MYSQL_PORT", "3306")),
        mysql_user=os.getenv("MYSQL_USER", "root"),
        mysql_password=os.getenv("MYSQL_PASSWORD", ""),
        mysql_database=os.getenv("MYSQL_DATABASE", "agentflow"),
        mysql_charset=os.getenv("MYSQL_CHARSET", "utf8mb4"),
        mysql_pool_size=int(os.getenv("MYSQL_POOL_SIZE", "10")),
        mysql_max_overflow=int(os.getenv("MYSQL_MAX_OVERFLOW", "20")),

        # Redis
        redis_mode=os.getenv("REDIS_MODE", "off"),
        redis_uri=os.getenv("REDIS_URI", ""),
        redis_password=os.getenv("REDIS_PASSWORD", ""),
        redis_database=int(os.getenv("REDIS_DATABASE", "0")),
        redis_cluster_nodes=os.getenv("REDIS_CLUSTER_NODES", ""),
        redis_cluster_username=os.getenv("REDIS_CLUSTER_USERNAME", "default"),
        redis_cluster_password=os.getenv("REDIS_CLUSTER_PASSWORD", ""),
        redis_max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "20")),
        redis_socket_timeout=int(os.getenv("REDIS_SOCKET_TIMEOUT", "120")),
        redis_connect_timeout=int(os.getenv("REDIS_CONNECT_TIMEOUT", "30")),
        redis_retry_attempts=int(os.getenv("REDIS_RETRY_ATTEMPTS", "3")),

        # Neo4j
        neo4j_enabled=_bool(os.getenv("NEO4J_ENABLED", "false")),
        neo4j_uri=os.getenv("NEO4J_URI", ""),
        neo4j_username=os.getenv("NEO4J_USERNAME", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", ""),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
        neo4j_max_connection_pool_size=int(os.getenv("NEO4J_MAX_CONNECTION_POOL_SIZE", "20")),
        neo4j_connection_timeout=int(os.getenv("NEO4J_CONNECTION_TIMEOUT", "60")),

        # Milvus
        milvus_enabled=_bool(os.getenv("MILVUS_ENABLED", "false")),
        milvus_uri=os.getenv("MILVUS_URI", ""),
        milvus_db_name=os.getenv("MILVUS_DB_NAME", "agentflow"),
        milvus_timeout=int(os.getenv("MILVUS_TIMEOUT", "60")),

        # Main LLM
        llm_provider=os.getenv("LLM_PROVIDER", "openai"),
        llm_base_url=os.getenv("LLM_BASE_URL", ""),
        llm_default_model=os.getenv("LLM_MODEL", ""),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_custcode=os.getenv("LLM_CUSTCODE", ""),
        llm_componentcode=os.getenv("LLM_COMPONENTCODE", ""),

        # L1 LLM
        l1_llm_model=os.getenv("L1_LLM_MODEL", ""),
        l1_llm_base_url=os.getenv("L1_LLM_BASE_URL", ""),
        l1_llm_api_key=os.getenv("L1_LLM_API_KEY", ""),
        l1_llm_custcode=os.getenv("L1_LLM_CUSTCODE", ""),
        l1_llm_componentcode=os.getenv("L1_LLM_COMPONENTCODE", ""),

        # Embedding
        embedding_model=os.getenv("EMBEDDING_MODEL", ""),
        embedding_base_url=os.getenv("EMBEDDING_BASE_URL", ""),
        embedding_api_key=os.getenv("EMBEDDING_API_KEY", ""),
        embedding_custcode=os.getenv("EMBEDDING_CUSTCODE", ""),
        embedding_componentcode=os.getenv("EMBEDDING_COMPONENTCODE", ""),
        embedding_dim=int(os.getenv("EMBEDDING_DIM", "1024")),

        # AIPro
        aipro_base_url=os.getenv("AIPRO_BASE_URL", ""),
        aipro_api_key=os.getenv("AIPRO_API_KEY", ""),
        aipro_default_model=os.getenv("AIPRO_DEFAULT_MODEL", ""),

        # Reranker
        rerank_enabled=_bool(os.getenv("RERANK_ENABLED", "false")),
        rerank_model=os.getenv("RERANK_MODEL", ""),
        rerank_base_url=os.getenv("RERANK_BASE_URL", ""),
        rerank_api_key=os.getenv("RERANK_API_KEY", ""),
        rerank_custcode=os.getenv("RERANK_CUSTCODE", ""),
        rerank_componentcode=os.getenv("RERANK_COMPONENTCODE", ""),

        # Concurrency
        max_concurrent_workflows=int(os.getenv("MAX_CONCURRENT_WORKFLOWS", "3")),
        max_concurrent_llm_calls=int(os.getenv("MAX_CONCURRENT_LLM_CALLS", "2")),
        max_concurrent_tools=int(os.getenv("MAX_CONCURRENT_TOOLS", "10")),
        max_async=int(os.getenv("MAX_ASYNC", "8")),

        # Document Processing
        chunk_size=int(os.getenv("CHUNK_SIZE", "1200")),
        chunk_overlap_size=int(os.getenv("CHUNK_OVERLAP_SIZE", "100")),
        max_tokens=int(os.getenv("MAX_TOKENS", "2048")),
        summary_language=os.getenv("SUMMARY_LANGUAGE", "Chinese"),

        # Security
        secrets_encryption_key=os.getenv("SECRETS_KEY", ""),

        # MCP
        mcp_config_path=os.getenv("MCP_CONFIG_PATH", ""),
    )
