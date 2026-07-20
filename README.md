<div align="center">
  <a href="https://github.com/CNAG-Biomedical-Informatics/dicomqc">
    <img src="https://raw.githubusercontent.com/CNAG-Biomedical-Informatics/dicomqc/main/docs-site/static/img/dicomqc-logo.png"
         width="300" alt="dicomqc">
  </a>
  <p><em>Policy-driven DICOM de-identification audit and research-release readiness reporting</em></p>
</div>

[![Build](https://github.com/CNAG-Biomedical-Informatics/dicomqc/actions/workflows/build-and-test.yml/badge.svg)](https://github.com/CNAG-Biomedical-Informatics/dicomqc/actions/workflows/build-and-test.yml)
[![Documentation](https://github.com/CNAG-Biomedical-Informatics/dicomqc/actions/workflows/documentation.yml/badge.svg)](https://github.com/CNAG-Biomedical-Informatics/dicomqc/actions/workflows/documentation.yml)
[![PyPI](https://img.shields.io/pypi/v/dicomqc.svg)](https://pypi.org/project/dicomqc/)
[![Python](https://img.shields.io/pypi/pyversions/dicomqc.svg)](https://pypi.org/project/dicomqc/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

---

**dicomqc** is a policy-driven, standards-aware audit framework for validating
DICOM de-identification and research-release readiness.

dicomqc inspects DICOM metadata after pseudonymization or anonymization and
produces redaction-safe audit evidence in JSON, CSV, and MultiQC-compatible
formats.

**Documentation:** <https://cnag-biomedical-informatics.github.io/dicomqc/>

dicomqc is **not an anonymizer**. It never modifies original DICOM files. If it
reports required changes, apply them with an external pseudonymization or
anonymization tool and rerun the audit.

The intended operating mode is DICOM-in and DICOM-out: raw `.dcm` files are
pseudonymized into release-candidate `.dcm` files, and dicomqc audits those
outputs before research sharing.

## Key Points

- Metadata-only DICOM scanning with `pydicom`
- Built-in research-release checks for direct PHI, pseudonym format, and private tags
- Redaction-safe reports that do not emit raw DICOM values
- JSON and CSV outputs for pipeline evidence
- MultiQC custom-content output with a styled example report
- Synthetic DICOM fixtures for reproducible tests and demonstrations
- Read-only design: remediation is performed by external tools such as DCMTK,
  Orthanc, XNAT workflows, or custom pipeline steps
- Future scope for policy DSLs, DICOM PS3.15 profiles, BIDS-oriented checks,
  plugin architecture, and vendor metadata fingerprinting

## Installation

Install the release from [PyPI](https://pypi.org/project/dicomqc/) in an
isolated environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install dicomqc
dicomqc --version
```

From a source checkout, install the package in editable mode:

```bash
python3 -m pip install -e .
```

Contributors who need the test and coverage tools can install the `test`
optional dependency group:

```bash
python3 -m pip install -e ".[test]"
```

For local remediation workflows, install external DICOM tools separately. For
example, DCMTK provides `dcmodify` and `dcmdump`, but dicomqc itself remains
read-only.

## Quick Start

Generate a complete synthetic DICOM demo and report bundle:

```bash
dicomqc demo
```

This creates `dicomqc-demo/` with synthetic `.dcm` files, `report.json`,
`findings.csv`, and MultiQC custom-content files. The demo includes intentional
findings so users can see what a failed release gate looks like.

Run an audit on a directory of candidate release `.dcm` files:

```bash
dicomqc scan study/ --json report.json --csv findings.csv --multiqc
```

Exit codes:

- `0`: no warnings or errors
- `1`: warnings only
- `2`: validation errors or fatal scan failure

## Reports

| Output | Purpose |
| --- | --- |
| JSON | Full structured audit result for pipelines and archival evidence |
| CSV | One row per finding for review and spreadsheet workflows |
| MultiQC | Custom-content summary for projects that aggregate QC reports |

Render the demo with MultiQC, if installed:

```bash
multiqc dicomqc-demo/dicomqc --outdir dicomqc-demo --force
```

Use `examples/multiqc/multiqc_config.yaml` when rendering the demo report if you
want the repository logo and styling in local MultiQC output.

## Documentation

The documentation site lives in `docs-site/` and uses Docusaurus.

```bash
cd docs-site
npm install
npm run build
```

Important docs:

- [Install](https://cnag-biomedical-informatics.github.io/dicomqc/docs/usage/install)
- [Quick start](https://cnag-biomedical-informatics.github.io/dicomqc/docs/usage/quickstart)
- [Reports and MultiQC](https://cnag-biomedical-informatics.github.io/dicomqc/docs/usage/reports)
- [MS MRI workflow](https://cnag-biomedical-informatics.github.io/dicomqc/docs/usage/ms-mri-workflow)
- [Remediation examples](https://cnag-biomedical-informatics.github.io/dicomqc/docs/usage/remediation)
- [Prior work](https://cnag-biomedical-informatics.github.io/dicomqc/docs/about/prior-work)
- [Changelog](https://github.com/CNAG-Biomedical-Informatics/dicomqc/blob/main/CHANGELOG.md)
- [Release process](https://github.com/CNAG-Biomedical-Informatics/dicomqc/blob/main/RELEASING.md)

## Prior Work

dicomqc is intended to build on and complement related work, not duplicate it.
Known related projects include:

- [`SPMIC-UoN/xnat-dicomqc`](https://github.com/SPMIC-UoN/xnat-dicomqc): an XNAT
  container script for configurable tag-based QC on scan DICOMs.
- [`IUSCA/SQAN`](https://github.com/IUSCA/SQAN): Scalable Quality Assurance for
  Neuroimaging, a broader DICOM metadata ETL and QC verification system.

The initial dicomqc direction is a backend-independent, policy-driven audit
framework focused on de-identification validation, release-readiness evidence,
and future standards-aware rule packs.

## Citation

dicomqc is early-stage research software. Until a stable release, archived DOI,
or manuscript is available, cite the repository URL and the exact version or
commit used in your analysis.

## Author

Written by Manuel Rueda. GitHub repository:
<https://github.com/CNAG-Biomedical-Informatics/dicomqc>.

## Copyright and License

Copyright 2026 Manuel Rueda, CNAG.

dicomqc is distributed under the [Apache License 2.0](LICENSE).
