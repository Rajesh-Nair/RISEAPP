"""Safe file read/write helpers."""

from pathlib import Path
from typing import Union

from exception.custom_exception import CustomException
from logger.custom_logger import CustomLogger

logger = CustomLogger().get_logger(__file__)


def read_text(path: Union[Path, str], encoding: str = "utf-8") -> str:
    p = Path(path)
    if not p.exists():
        raise CustomException(f"File not found: {p}")
    try:
        return p.read_text(encoding=encoding)
    except Exception as e:
        raise CustomException(f"Failed to read {p}: {e}")


def write_text(path: Union[Path, str], content: str, encoding: str = "utf-8") -> None:
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding=encoding)
    except Exception as e:
        raise CustomException(f"Failed to write {p}: {e}")
