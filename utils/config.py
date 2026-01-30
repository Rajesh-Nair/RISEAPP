"""Load config from YAML and .env."""

from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv

from exception.custom_exception import CustomException
from logger.custom_logger import CustomLogger

logger = CustomLogger().get_logger(__file__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_DIR = _PROJECT_ROOT / "config"
_CONFIG_PATH = _CONFIG_DIR / "config.yaml"


def _load_env() -> None:
    env_path = _PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info("Loaded .env", path=str(env_path))


def _load_yaml() -> dict[str, Any]:
    if not _CONFIG_PATH.exists():
        raise CustomException(f"Config not found: {_CONFIG_PATH}")
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


class Config:
    """Config holder from YAML + .env."""

    def __init__(self) -> None:
        _load_env()
        self._raw = _load_yaml()
        self._project_root = _PROJECT_ROOT

    @property
    def project_root(self) -> Path:
        return self._project_root

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        v: Any = self._raw
        for k in keys:
            if isinstance(v, dict) and k in v:
                v = v[k]
            else:
                return default
        return v

    def get_path(self, key: str, default: Optional[Path] = None) -> Path:
        v = self.get(key)
        if v is None:
            if default is not None:
                return default
            raise CustomException(f"Config path missing: {key}")
        p = Path(v)
        if not p.is_absolute():
            p = self._project_root / p
        return p

    def get_model_for_agent(self, agent_name: str) -> str:
        """Return model name for an agent (e.g. lineage_detect, brand_classifier)."""
        m = self.get(f"agents.{agent_name}.model") or self.get("agents.default_model")
        if not m:
            raise CustomException(f"No model configured for agent {agent_name}")
        return str(m)

    @property
    def data_blob(self) -> Path:
        return self.get_path("data.blob", self._project_root / "data" / "blob")

    @property
    def data_sql(self) -> Path:
        return self.get_path("data.sql", self._project_root / "data" / "sql")

    @property
    def data_vectordb(self) -> Path:
        return self.get_path("data.vectordb", self._project_root / "data" / "vectordb")

    @property
    def log_dir(self) -> Path:
        return self.get_path("logs.dir", self._project_root / "logs")

    @property
    def embedding_provider(self) -> str:
        return str(self.get("embedding.provider", "huggingface"))

    @property
    def embedding_model(self) -> str:
        return str(self.get("embedding.model", "sentence-transformers/all-MiniLM-L6-v2"))

    @property
    def chunk_size(self) -> int:
        return int(self.get("chunking.size", 512))

    @property
    def chunk_overlap(self) -> int:
        return int(self.get("chunking.overlap", 64))

    @property
    def lineage_top_k(self) -> int:
        return int(self.get("lineage.top_k", 5))


# Singleton; backward-compat alias for "from utils.config import config"
_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config


config = get_config()
