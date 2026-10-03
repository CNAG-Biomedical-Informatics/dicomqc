"""Command-line interface for dicomqc."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from dicomqc import __version__
from dicomqc.compare import compare_datasets, comparison_roots
from dicomqc.demo import run_comparison_demo, run_demo, run_large_demo, run_policy_demo, run_vendor_demo, run_uid_demo
from dicomqc.fixtures import LARGE_DEMO_FILES
from dicomqc.reports import write_csv, write_html, write_json, write_multiqc
from dicomqc.rules.builtin import DEFAULT_PROFILE_ID
from dicomqc.rules.policy import Policy, load_policy
from dicomqc.scanner import scan_paths
from dicomqc.execution import _load_requested_policy, _validate_multiqc_output
from dicomqc.parallel import DEFAULT_THREADS, MAX_THREADS


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "serve":
        from dicomqc.api.server import main as serve
        return serve(arguments[1:])
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
    subparsers.add_parser("serve", help="Start the optional authenticated local API.")
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
    scan.add_argument("--policy", type=Path, help="Add checks from a YAML policy outside the input directories.")
    scan.add_argument("--uid-checks", action="store_true",
                      help="Check top-level study, series and instance UID syntax, role reuse and hierarchy within this scan.")
    scan.add_argument("--vendor-summary", action="store_true",
                      help="Include declared manufacturer, model, software and private creator labels in reports. These values may identify people or sites.")
    scan.add_argument("-t", "--threads", type=int, default=DEFAULT_THREADS,
                      help=f"Metadata threads within this audit. Default: {DEFAULT_THREADS}; maximum: {MAX_THREADS}.")
    scan.add_argument("--quiet", action="store_true", help="Suppress the text summary.")
    demo = subparsers.add_parser("demo", help="Generate a synthetic DICOM demo dataset and dicomqc reports.")
    demo.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dicomqc-demo"),
        help="Directory where demo DICOM files and reports will be written. Default: dicomqc-demo.",
    )
    demo.add_argument("--force", action="store_true", help="Replace the output directory if it already exists.")
    demo_mode = demo.add_mutually_exclusive_group()
    demo_mode.add_argument("--compare", action="store_true", help="Demonstrate failing and corrected dataset comparisons.")
    demo_mode.add_argument("--policy-demo", action="store_true", help="Demonstrate project policy checks on synthetic metadata.")
    demo_mode.add_argument("--vendor-demo", action="store_true", help="Demonstrate scanner metadata and nested private creator blocks.")
    demo_mode.add_argument("--uid-demo", action="store_true", help="Demonstrate failing and corrected UID integrity checks.")
    demo_mode.add_argument("--large", action="store_true", help=f"Generate and audit {LARGE_DEMO_FILES} synthetic DICOM files with deterministic findings.")
    compare = subparsers.add_parser("compare", help="Audit paired source and de-identified datasets.")
    compare.add_argument("source", type=Path, help="Source DICOM directory.")
    compare.add_argument("candidate", type=Path, help="De-identified DICOM directory.")
    compare.add_argument("--manifest", type=Path, required=True, help="CSV with source,candidate relative paths.")
    compare.add_argument("--json", dest="json_path", type=Path, help="Write comparison results as JSON.")
    compare.add_argument("--csv", dest="csv_path", type=Path, help="Write comparison findings as CSV.")
    compare.add_argument("--html", dest="html_path", type=Path, help="Write a standalone offline HTML comparison report.")
    compare.add_argument("--quiet", action="store_true", help="Suppress the text summary.")
    compare.add_argument("--policy", type=Path, help="Add YAML policy checks on candidate metadata only.")
    compare.add_argument("-t", "--threads", type=int, default=DEFAULT_THREADS,
                         help=f"Metadata threads within this audit. Default: {DEFAULT_THREADS}; maximum: {MAX_THREADS}.")
    return parser


def _run_compare(args: argparse.Namespace) -> int:
    try:
        roots = comparison_roots(args.source, args.candidate)
        outputs = [path.resolve() for path in (args.json_path, args.csv_path, args.html_path) if path]
        policy = _load_requested_policy(args.policy, list(roots), outputs)
        if len(outputs) != len(set(outputs)):
            raise ValueError("Reports need different output paths.")
        for output in outputs:
            if output == args.manifest.resolve() or any(output == root or root in output.parents for root in roots):
                raise ValueError("Write reports outside the inputs and do not overwrite the manifest.")
            if output.exists() and output.stat().st_nlink > 1:
                raise ValueError("Report output must not be a hard-linked file.")
        result = compare_datasets(*roots, args.manifest, policy=policy, threads=args.threads)
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
        multiqc_path = (Path("dicomqc_mqc") if args.multiqc is True else Path(args.multiqc)) if args.multiqc is not None else None
        if multiqc_path is not None:
            _validate_multiqc_output(multiqc_path, inputs, outputs)
        policy = _load_requested_policy(args.policy, inputs, outputs, multiqc_path)
        for output in outputs:
            if output in inputs or (output.exists() and any(root in output.parents for root in inputs)):
                raise ValueError("Report output would overwrite an input file; choose a path outside the inputs.")
            if output.exists() and output.stat().st_nlink > 1:
                raise ValueError("Report output must not be a hard-linked file.")
        result = scan_paths(args.paths, profile=args.profile, policy=policy, vendor_summary=args.vendor_summary,
                            uid_checks=args.uid_checks, threads=args.threads)
        if args.json_path:
            write_json(result, args.json_path)
        if args.csv_path:
            write_csv(result, args.csv_path)
        if args.html_path:
            write_html(result, args.html_path)
        if args.multiqc is not None:
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
        if args.uid_demo:
            demo = run_uid_demo(args.output_dir, force=args.force)
            print(f"UID demo directory: {demo.output_dir}")
            print("Before: seven findings across UID syntax, role reuse, and conflicting hierarchy.")
            print(f"Before scan exit code: {demo.before.exit_code()} (expected: 2)")
            print(f"After scan exit code: {demo.after.exit_code()} (expected: 0)")
            print(f"Before HTML: {demo.output_dir / 'before.html'}")
            print(f"After HTML: {demo.output_dir / 'after.html'}")
            print("JSON, CSV and MultiQC content are alongside the HTML. All data is synthetic.")
            print("Corrected files are generated separately; dicomqc audits are read-only.")
            return 0
        if args.policy_demo:
            demo = run_policy_demo(args.output_dir, force=args.force)
            print(f"Policy demo directory: {demo.output_dir}")
            print(f"Project policy: {demo.policy_path}")
            print("Before: three findings in descriptors, comments, and the de-identification marker.")
            print(f"Before scan exit code: {demo.before.exit_code()} (expected: 2)")
            print(f"After scan exit code: {demo.after.exit_code()} (expected: 0)")
            print(f"Before HTML: {demo.output_dir / 'before.html'}")
            print(f"After HTML: {demo.output_dir / 'after.html'}")
            print("JSON and CSV reports are alongside the HTML. All data is synthetic.")
            print("Corrected files are generated separately; dicomqc audits are read-only.")
            return 0
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
        demo_function = run_large_demo if args.large else run_vendor_demo if args.vendor_demo else run_demo
        demo = demo_function(args.output_dir, force=args.force)
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
    expected = "synthetic findings are included"
    print(f"Demo scan exit code: {demo.scan_exit_code} (expected: {expected})")
    print(f"Render with MultiQC, if installed: multiqc {demo.report_dir} --outdir {demo.output_dir} --force")
    return 0


def _print_summary(result) -> None:
    if result.uid_checks is not None:
        summary = result.uid_checks
        print(f"UID integrity: {summary['profile_id']} (additive checks)")
        print(f"Usable UID hierarchies: {summary['complete_hierarchies_checked']} of {summary['files_checked']} files")
    if result.policy is not None:
        print(f"Project policy: {result.policy['id']} (additive checks)")
    if result.vendor_summary is not None:
        print(f"Equipment combinations: {len(result.vendor_summary['equipment'])}")
        print(f"Unassigned private elements: {result.vendor_summary['unassigned_private_elements']}")
        print("Vendor summary includes observed metadata labels; review reports before sharing.")
    print(f"Files scanned: {result.files_scanned}")
    print(f"Errors: {result.error_count}")
    print(f"Warnings: {result.warning_count}")
    print(f"Passed: {result.files_passed}")
    print(f"Failed: {result.files_failed}")
    if result.skipped_files:
        print(f"Skipped files: {len(result.skipped_files)}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
