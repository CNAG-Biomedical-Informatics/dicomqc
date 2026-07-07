"""Command-line interface for DICOMQC."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from dicomqc.reports import write_csv, write_json, write_multiqc
from dicomqc.rules.builtin import DEFAULT_PROFILE_ID
from dicomqc.scanner import scan_paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "scan":
        return _run_scan(args)
    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dicomqc", description="Validate DICOM metadata for research release.")
    subparsers = parser.add_subparsers(dest="command")
    scan = subparsers.add_parser("scan", help="Scan DICOM files or directories.")
    scan.add_argument("paths", nargs="+", help="DICOM file or directory paths.")
    scan.add_argument("--json", dest="json_path", type=Path, help="Write a redaction-safe JSON report.")
    scan.add_argument("--csv", dest="csv_path", type=Path, help="Write a CSV findings report.")
    scan.add_argument(
        "--multiqc",
        nargs="?",
        const=True,
        default=None,
        help="Write a MultiQC custom-content directory. Defaults to dicomqc_mqc/ unless a path is provided.",
    )
    scan.add_argument("--profile", default=DEFAULT_PROFILE_ID, help=f"Rule profile to apply. Default: {DEFAULT_PROFILE_ID}.")
    scan.add_argument("--quiet", action="store_true", help="Suppress the text summary.")
    return parser


def _run_scan(args: argparse.Namespace) -> int:
    try:
        result = scan_paths(args.paths, profile=args.profile)
    except ValueError as exc:
        print(f"dicomqc: {exc}", file=sys.stderr)
        return 2

    if args.json_path:
        write_json(result, args.json_path)
    if args.csv_path:
        write_csv(result, args.csv_path)
    if args.multiqc is not None:
        multiqc_path = Path("dicomqc_mqc") if args.multiqc is True else Path(args.multiqc)
        write_multiqc(result, multiqc_path)
    if not args.quiet:
        _print_summary(result)
    return result.exit_code()


def _print_summary(result) -> None:
    print(f"Files scanned: {result.files_scanned}")
    print(f"Errors: {result.error_count}")
    print(f"Warnings: {result.warning_count}")
    print(f"Passed: {result.files_passed}")
    print(f"Failed: {result.files_failed}")
    if result.skipped_files:
        print(f"Skipped files: {len(result.skipped_files)}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
