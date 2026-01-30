"""CLI: convert, chunk-store, lineage, all."""

import argparse
import sys

from logger.custom_logger import CustomLogger

logger = CustomLogger().get_logger(__file__)


def _convert() -> None:
    from src.processes.process_1_convert import run_process_1
    run_process_1()


def _chunk_store() -> None:
    from src.processes.process_2_chunk_store import run_process_2
    run_process_2()


def _lineage() -> None:
    from src.processes.process_3_lineage import run_process_3
    run_process_3()


def _all() -> None:
    _convert()
    _chunk_store()
    _lineage()


def main() -> None:
    ap = argparse.ArgumentParser(description="RiseApp Data Lineage")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("convert", help="Process-1: PDF -> HTML/MD, update documents")
    sp.add_parser("chunk-store", help="Process-2: Chunk, embed, store in DB + FAISS")
    sp.add_parser("lineage", help="Process-3: Lineage detection, store lineage")
    pa = sp.add_parser("all", help="Run convert -> chunk-store -> lineage")
    args = ap.parse_args()

    if args.cmd == "convert":
        _convert()
    elif args.cmd == "chunk-store":
        _chunk_store()
    elif args.cmd == "lineage":
        _lineage()
    elif args.cmd == "all":
        _all()
    else:
        ap.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
