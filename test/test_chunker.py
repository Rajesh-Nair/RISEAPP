"""Tests for chunking."""

import pytest

from src.chunking.chunker import chunk_text, ChunkResult


def test_chunk_text_empty() -> None:
    out = chunk_text("")
    assert out == []


def test_chunk_text_small() -> None:
    text = "Hello world. " * 20
    out = chunk_text(text, size=80, overlap=10)
    assert len(out) >= 1
    assert all(isinstance(c, ChunkResult) for c in out)
    assert all(c.index == i for i, c in enumerate(out))


def test_chunk_text_overlap() -> None:
    text = "a" * 200
    out = chunk_text(text, size=50, overlap=10)
    assert len(out) >= 2
    concatenated = "".join(c.content for c in out)
    assert "a" in concatenated
