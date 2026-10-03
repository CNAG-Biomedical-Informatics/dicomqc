"""Shared audit-status vocabulary for human-readable reports."""

from dicomqc.model.results import ScanResult


def audit_status(result: ScanResult) -> tuple[str, str]:
    """Return the display label and styling token, not a data-release decision."""
    if result.error_count or result.skipped_files:
        return "Errors require attention", "error"
    if result.warning_count:
        return "Warnings require review", "warning"
    if not result.files_scanned:
        return "No readable files", "warning"
    return "Checks passed", "pass"


def audit_guidance(result: ScanResult) -> str:
    """Explain the next step without implying release approval."""
    code = result.exit_code()
    if result.skipped_files:
        return "Some files could not be read. Resolve the unreadable inputs, review any findings, and rerun the audit. Coverage is incomplete."
    elif code == 2:
        return "Review the issues below, correct the files or pairing externally, then rerun the audit."
    elif code == 1:
        return "Review each warning and its recommended action. Apply any required changes with your external tools, then rerun the audit."
    elif not result.files_scanned:
        return "No readable DICOM files were audited. Check the input location and file selection before interpreting this result."
    else:
        return "No errors or warnings were recorded. Retain this report and complete the remaining data-sharing review; pixels and facial features were not checked."
