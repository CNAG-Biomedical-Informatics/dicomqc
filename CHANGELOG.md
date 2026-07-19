# Changelog

All notable changes to dicomqc are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Moved installation guidance to a dedicated documentation page and added
  Install links to the primary documentation navigation.

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

[Unreleased]: https://github.com/CNAG-Biomedical-Informatics/dicomqc/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/CNAG-Biomedical-Informatics/dicomqc/releases/tag/v0.1.0
