---
title: Quickstart
---

# Quickstart

## Try the built-in demo

After installation, generate a complete synthetic DICOM demo and dicomqc report
bundle:

```bash
dicomqc demo
```

This writes:

```text
dicomqc-demo/
  dicom/
    raw_phi.dcm
    pseudonymized.dcm
    private_tags.dcm
  dicomqc/
    report.json
    findings.csv
    dicomqc_mqc/
```

The demo intentionally includes findings, so the reported scan exit code is `2`.
The `demo` command itself exits `0` when the example was generated correctly.

## Developer installation

Install the package from the repository root with test dependencies:

```bash
python3 -m pip install -e ".[test]"
```

Scan a study directory:

```bash
dicomqc scan study/ --json report.json --csv findings.csv
```

The scanner recursively attempts regular files under the provided path. DICOM
files do not need a `.dcm` extension.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | No warnings or errors |
| `1` | Warnings only |
| `2` | Validation errors or fatal scan failures |

## Default profile

The default profile is `research-release-v0.1`. It flags direct PHI fields,
warns on risky pseudonym fields, and reports private tags as release-risk
evidence.

## Fixing findings

dicomqc does not modify DICOM files. If it reports required changes, apply them
with a pseudonymization or anonymization tool, then rerun the scan. See
[Remediation](remediation.md) for examples with external tools.

For the intended multiple sclerosis MRI use case, see
[MS MRI Workflow](ms-mri-workflow.md).
