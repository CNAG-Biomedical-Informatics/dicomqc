---
title: Quickstart
---

# Quickstart

Install dicomqc and verify the command before continuing. See
[Install](install.md) for PyPI, MultiQC, and source-installation instructions.

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

## Scan a dataset

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
[Remediation](remediation.mdx) for examples with external tools.

For the intended multiple sclerosis MRI use case, see
[MS MRI Workflow](ms-mri-workflow.mdx).
