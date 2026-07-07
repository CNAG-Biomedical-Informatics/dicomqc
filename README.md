# dicomqc

**dicomqc: a policy-driven, standards-aware audit framework for validating
DICOM de-identification and research-release readiness.**

dicomqc is a Python tool for quality control and validation of DICOM metadata,
with a primary focus on verifying pseudonymization and research-release
readiness.

It is not an anonymizer. It never modifies the original DICOM files.

If dicomqc reports required changes, apply them with an external
pseudonymization or anonymization tool and rerun the audit. The docs include
remediation examples for tools such as DCMTK `dcmodify`, Orthanc, XNAT
workflows, and custom pipeline steps.

The initial real-world target is a large multiple sclerosis MRI dataset where
dicomqc acts as the release gate after pseudonymization and before research
sharing. A linkage file may exist on the data provider side, but it must remain
outside the released dataset and outside dicomqc reports.

The intended operating mode is DICOM-in and DICOM-out: raw `.dcm` files are
pseudonymized into release-candidate `.dcm` files, and dicomqc audits those
outputs.

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

## MultiQC Example

Generate synthetic `.dcm` files and render a MultiQC report:

```bash
bash examples/multiqc/run_example.sh
```

The output is written to `examples/multiqc/output/`.

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
