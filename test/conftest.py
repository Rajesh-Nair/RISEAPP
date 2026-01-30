"""Pytest fixtures for RiseApp tests."""

import os
import tempfile
from pathlib import Path

import pytest

# Project root on path
_root = Path(__file__).resolve().parent.parent
if str(_root) not in os.environ.get("PYTHONPATH", "").split(os.pathsep):
    os.environ.setdefault("PYTHONPATH", str(_root))


@pytest.fixture
def project_root() -> Path:
    return _root


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def config_yaml(tmp_path: Path, project_root: Path) -> Path:
    """Override config to use tmp paths."""
    import yaml
    cfg = {
        "data": {"blob": str(project_root / "data" / "blob"), "sql": str(tmp_path / "sql"), "vectordb": str(tmp_path / "vectordb")},
        "logs": {"dir": str(tmp_path / "logs")},
        "embedding": {"provider": "huggingface", "model": "sentence-transformers/all-MiniLM-L6-v2"},
        "chunking": {"size": 256, "overlap": 32},
        "lineage": {"top_k": 3},
        "agents": {"default_model": "gemini-2.0-flash", "lineage_detect": {"model": "gemini-2.0-flash"}},
    }
    p = tmp_path / "config.yaml"
    p.write_text(yaml.dump(cfg), encoding="utf-8")
    return p
