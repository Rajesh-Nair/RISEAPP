"""Processes: PDF convert, chunk+store, lineage detection."""

from src.processes.process_1_convert import run_process_1
from src.processes.process_2_chunk_store import run_process_2
from src.processes.process_3_lineage import run_process_3

__all__ = ["run_process_1", "run_process_2", "run_process_3"]
