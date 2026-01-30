"""CLI: convert, chunk-store, lineage, all."""

import argparse
import sys

from logger.custom_logger import CustomLogger

logger = CustomLogger().get_logger(__file__)


def _convert(force: bool = False) -> None:
    from src.processes.process_1_convert import run_process_1
    run_process_1(force=force)


def _chunk_store(force: bool = False) -> None:
    from src.processes.process_2_chunk_store import run_process_2
    run_process_2(force=force)


def _lineage(force: bool = False) -> None:
    from src.processes.process_3_lineage import run_process_3
    run_process_3(force=force)


def _all(force: bool = False) -> None:
    _convert(force=force)
    _chunk_store(force=force)
    _lineage(force=force)


def main() -> None:
    ap = argparse.ArgumentParser(description="RiseApp Data Lineage")
    sp = ap.add_subparsers(dest="cmd", required=True)
    
    # Process-1: convert
    p1 = sp.add_parser("convert", help="Process-1: PDF -> HTML/MD, update documents")
    p1.add_argument("--force", "-f", action="store_true", help="Force re-convert all PDFs, even if already converted")
    
    # Process-2: chunk-store
    p2 = sp.add_parser("chunk-store", help="Process-2: Chunk, embed, store in DB + FAISS")
    p2.add_argument("--force", "-f", action="store_true", help="Force re-chunk all documents, clearing vector store")
    
    # Process-3: lineage
    p3 = sp.add_parser("lineage", help="Process-3: Lineage detection, store lineage")
    p3.add_argument("--force", "-f", action="store_true", help="Force re-process lineage for all internal chunks")
    
    # All processes
    pa = sp.add_parser("all", help="Run convert -> chunk-store -> lineage")
    pa.add_argument("--force", "-f", action="store_true", help="Force re-process all steps")
    
    args = ap.parse_args()

    if args.cmd == "convert":
        _convert(force=args.force)
    elif args.cmd == "chunk-store":
        _chunk_store(force=args.force)
    elif args.cmd == "lineage":
        _lineage(force=args.force)
    elif args.cmd == "all":
        _all(force=args.force)
    else:
        ap.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
