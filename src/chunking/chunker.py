"""Split .md content into fixed-size overlapping chunks."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from utils.config import get_config
from utils.file_io import read_text

from exception.custom_exception import CustomException
from logger.custom_logger import CustomLogger

logger = CustomLogger().get_logger(__file__)


@dataclass
class ChunkResult:
    content: str
    index: int
    metadata: Optional[dict] = None
    start_offset: int = 0
    end_offset: int = 0


def chunk_text(
    text: str,
    size: Optional[int] = None,
    overlap: Optional[int] = None,
) -> List[ChunkResult]:
    """Split text into chunks by character count with overlap."""
    cfg = get_config()
    size = size or cfg.chunk_size
    overlap = overlap or cfg.chunk_overlap
    if overlap >= size:
        overlap = max(0, size // 4)
    out: List[ChunkResult] = []
    start = 0
    idx = 0
    while start < len(text):
        end = start + size
        chunk = text[start:end]
        chunk = chunk.strip()
        if chunk:
            # Store character offsets in original text for mapping back to document
            slice_text = text[start:end]
            pos_in_slice = slice_text.find(chunk)
            chunk_start = start + pos_in_slice if pos_in_slice >= 0 else start
            chunk_end = chunk_start + len(chunk)
            out.append(
                ChunkResult(
                    content=chunk,
                    index=idx,
                    metadata=None,
                    start_offset=chunk_start,
                    end_offset=chunk_end,
                )
            )
            idx += 1
        start = end - overlap
        if start >= len(text):
            break
    return out


def chunk_md_file(path: Path, size: Optional[int] = None, overlap: Optional[int] = None) -> List[ChunkResult]:
    """Read .md file and return chunks."""
    text = read_text(path)
    return chunk_text(text, size=size, overlap=overlap)
