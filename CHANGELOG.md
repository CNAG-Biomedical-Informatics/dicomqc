# Changelog

All notable changes to dicomqc are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - Unreleased

### Added

- Dataset comparisons for file completeness and patient pseudonym consistency,
  with explicit CSV pairing manifests and a before/after demo.
- Offline HTML reports with grouped findings, charts, filters, and print support.
- YAML project policies for metadata checks in scans and comparisons.
- Opt-in scanner/software and private-tag inventory, with a synthetic demo.
- UID syntax, role reuse, and hierarchy checks, with a before/after demo.
- Native desktop source with a bundled local Python API, audit queue, run history,
  cancellation, report previews and exports, and synthetic examples.
- Desktop navigation with Setup, Findings, and Reports views, searchable history,
  and output-folder selection that preserves selected inputs.
- Manual desktop test builds for macOS, Windows, and Linux.

### Changed

- Simplified documentation and demos; require pydicom 3.0 or newer.
- Safer demo overwrite checks and automated wheel/sdist release validation.
- Align HTML and MultiQC status wording and styling; refresh report screenshots.

### Fixed

- Preserve repeated metadata tags and use the correct patient-ID issuer.
- Fail safely on incomplete inventories and unreadable metadata.

Comparisons check metadata and file pairing, not pixels, date shifts, or UID references.

## [0.1.0] - 2026-07-19

### Added

- Read-only recursive scanning of DICOM files and directories.
- The built-in `research-release-v0.1` profile for direct identifier,
  pseudonym-format, private-tag, and unreadable-file findings.
- Redaction-safe JSON, CSV, and MultiQC-compatible audit outputs.
- The `dicomqc demo` command with synthetic DICOM fixtures.
- The `dicomqc --version` command.
- Docusaurus documentation covering installation, reporting, remediation,
  architecture, and an MS MRI release workflow.
- Automated tests with a 95% coverage gate and trusted-publishing workflows for
  TestPyPI and PyPI.

### Known limitations

- This alpha release audits metadata and never modifies DICOM files.
- Pixel data, burned-in text, and facial features are not inspected.
- The built-in profile does not certify DICOM PS3.15, BIDS, HIPAA, or GDPR
  compliance.

[0.2.0]: https://github.com/CNAG-Biomedical-Informatics/dicomqc/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/CNAG-Biomedical-Informatics/dicomqc/tree/v0.1.0
