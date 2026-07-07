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
