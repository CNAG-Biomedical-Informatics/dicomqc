"""Command-line interface for dicomqc."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from dicomqc import __version__
from dicomqc.compare import compare_datasets, comparison_roots
from dicomqc.demo import run_comparison_demo, run_demo
from dicomqc.reports import write_csv, write_html, write_json, write_multiqc
from dicomqc.rules.builtin import DEFAULT_PROFILE_ID
from dicomqc.scanner import scan_paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "scan":
        return _run_scan(args)
    if args.command == "demo":
        return _run_demo(args)
    if args.command == "compare":
        return _run_compare(args)
    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dicomqc", description="Validate DICOM metadata for research release.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")
    scan = subparsers.add_parser("scan", help="Scan DICOM files or directories.")
    scan.add_argument("paths", nargs="+", help="DICOM file or directory paths.")
    scan.add_argument("--json", dest="json_path", type=Path, help="Write a redaction-safe JSON report.")
    scan.add_argument("--csv", dest="csv_path", type=Path, help="Write a CSV findings report.")
    scan.add_argument("--html", dest="html_path", type=Path, help="Write a standalone offline HTML report.")
    scan.add_argument(
        "--multiqc",
        nargs="?",
        const=True,
        default=None,
        help="Write a MultiQC custom-content directory. Defaults to dicomqc_mqc/ unless a path is provided.",
    )
    scan.add_argument("--profile", default=DEFAULT_PROFILE_ID, help=f"Rule profile to apply. Default: {DEFAULT_PROFILE_ID}.")
    scan.add_argument("--quiet", action="store_true", help="Suppress the text summary.")
    demo = subparsers.add_parser("demo", help="Generate a synthetic DICOM demo dataset and dicomqc reports.")
    demo.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dicomqc-demo"),
        help="Directory where demo DICOM files and reports will be written. Default: dicomqc-demo.",
    )
    demo.add_argument("--force", action="store_true", help="Replace the output directory if it already exists.")
    demo.add_argument("--compare", action="store_true", help="Demonstrate failing and corrected dataset comparisons.")
    compare = subparsers.add_parser("compare", help="Audit paired source and de-identified datasets.")
    compare.add_argument("source", type=Path, help="Source DICOM directory.")
    compare.add_argument("candidate", type=Path, help="De-identified DICOM directory.")
    compare.add_argument("--manifest", type=Path, required=True, help="CSV with source,candidate relative paths.")
    compare.add_argument("--json", dest="json_path", type=Path, help="Write comparison results as JSON.")
    compare.add_argument("--csv", dest="csv_path", type=Path, help="Write comparison findings as CSV.")
    compare.add_argument("--html", dest="html_path", type=Path, help="Write a standalone offline HTML comparison report.")
    compare.add_argument("--quiet", action="store_true", help="Suppress the text summary.")
    return parser


def _run_compare(args: argparse.Namespace) -> int:
    try:
        roots = comparison_roots(args.source, args.candidate)
        outputs = [path.resolve() for path in (args.json_path, args.csv_path, args.html_path) if path]
        if len(outputs) != len(set(outputs)):
            raise ValueError("Reports need different output paths.")
        for output in outputs:
            if output == args.manifest.resolve() or any(output == root or root in output.parents for root in roots):
                raise ValueError("Write reports outside the inputs and do not overwrite the manifest.")
            if output.exists() and output.stat().st_nlink > 1:
                raise ValueError("Report output must not be a hard-linked file.")
        result = compare_datasets(*roots, args.manifest)
        if args.json_path:
            write_json(result, args.json_path)
        if args.csv_path:
            write_csv(result, args.csv_path)
        if args.html_path:
            write_html(result, args.html_path)
    except ValueError as exc:
        print(f"dicomqc: {exc}", file=sys.stderr)
        return 2
    except OSError:
        print("dicomqc: Cannot access comparison inputs or write reports.", file=sys.stderr)
        return 2
    if not args.quiet:
        print(f"Manifest pairs: {result.comparison['manifest_pairs']}")
        print(f"Readable pairs: {result.comparison['readable_pairs']}")
        print(f"Identity pairs checked: {result.comparison['identity_pairs_checked']}")
        _print_summary(result)
    return result.exit_code()


def _run_scan(args: argparse.Namespace) -> int:
    try:
        outputs = [path.resolve() for path in (args.json_path, args.csv_path, args.html_path) if path]
        if len(outputs) != len(set(outputs)):
            raise ValueError("Reports need different output paths.")
        inputs = [Path(path).resolve() for path in args.paths]
        for output in outputs:
            if output in inputs or (output.exists() and any(root in output.parents for root in inputs)):
                raise ValueError("Report output would overwrite an input file; choose a path outside the inputs.")
            if output.exists() and output.stat().st_nlink > 1:
                raise ValueError("Report output must not be a hard-linked file.")
        result = scan_paths(args.paths, profile=args.profile)
        if args.json_path:
            write_json(result, args.json_path)
        if args.csv_path:
            write_csv(result, args.csv_path)
        if args.html_path:
            write_html(result, args.html_path)
        if args.multiqc is not None:
            multiqc_path = Path("dicomqc_mqc") if args.multiqc is True else Path(args.multiqc)
            write_multiqc(result, multiqc_path)
    except ValueError as exc:
        print(f"dicomqc: {exc}", file=sys.stderr)
        return 2
    except OSError:
        print("dicomqc: Cannot access scan inputs or write reports.", file=sys.stderr)
        return 2
    if not args.quiet:
        _print_summary(result)
    return result.exit_code()


def _run_demo(args: argparse.Namespace) -> int:
    try:
        if args.compare:
            comparison = run_comparison_demo(args.output_dir, force=args.force)
            print(f"Comparison demo directory: {comparison.output_dir}")
            print(f"Pairing manifest: {comparison.manifest}")
            print("Before: one missing output file and inconsistent pseudonyms across two visits.")
            print(f"Before comparison exit code: {comparison.before.exit_code()} (expected: 2)")
            print("After: all three files present and patient pseudonyms consistent.")
            print(f"After comparison exit code: {comparison.after.exit_code()} (expected: 0)")
            print(f"JSON, CSV, and HTML reports: {comparison.output_dir} / before.* and after.*")
            print(f"Before HTML: {comparison.output_dir / 'before.html'}")
            print(f"After HTML: {comparison.output_dir / 'after.html'}")
            print("All data is synthetic. Corrected files are generated separately; dicomqc audits are read-only.")
            return 0
        demo = run_demo(args.output_dir, force=args.force)
    except (FileExistsError, ValueError) as exc:
        print(f"dicomqc: {exc}", file=sys.stderr)
        return 2
    except OSError:
        print("dicomqc: Cannot create or replace the demo output.", file=sys.stderr)
        return 2

    print(f"Demo directory: {demo.output_dir}")
    print(f"Synthetic DICOM files: {demo.dicom_dir}")
    print(f"JSON report: {demo.json_path}")
    print(f"CSV findings: {demo.csv_path}")
    print(f"HTML report: {demo.report_dir / 'report.html'}")
    print(f"MultiQC custom content: {demo.multiqc_dir}")
    print(f"Demo scan exit code: {demo.scan_exit_code} (expected: synthetic findings are included)")
    print(f"Render with MultiQC, if installed: multiqc {demo.report_dir} --outdir {demo.output_dir} --force")
    return 0


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
