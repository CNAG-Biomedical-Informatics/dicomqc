# DICOMQC

**DICOMQC: a policy-driven, standards-aware audit framework for validating
DICOM de-identification and research-release readiness.**

DICOMQC is a Python tool for quality control and validation of DICOM metadata,
with a primary focus on verifying pseudonymization and research-release
readiness.

It is not an anonymizer. It never modifies the original DICOM files.

## Quick Start

```bash
python3 -m pip install -e ".[test]"
dicomqc scan study/ --json report.json --csv findings.csv --multiqc
```

Exit codes:

- `0`: no warnings or errors
- `1`: warnings only
- `2`: validation errors or fatal scan failure

## Documentation

The documentation site lives in `docs-site/` and uses Docusaurus.

```bash
cd docs-site
npm install
npm run build
```

## Prior Work

DICOMQC is intended to build on and complement related work, not duplicate it.
Known related projects include:

- [`SPMIC-UoN/xnat-dicomqc`](https://github.com/SPMIC-UoN/xnat-dicomqc): an XNAT
  container script for configurable tag-based QC on scan DICOMs.
- [`IUSCA/SQAN`](https://github.com/IUSCA/SQAN): Scalable Quality Assurance for
  Neuroimaging, a broader DICOM metadata ETL and QC verification system.

The initial DICOMQC direction is a backend-independent, policy-driven audit
framework focused on de-identification validation, release-readiness evidence,
and future standards-aware rule packs.
