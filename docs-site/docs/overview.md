---
title: Overview
---

# DICOMQC

**DICOMQC: a policy-driven, standards-aware audit framework for validating
DICOM de-identification and research-release readiness.**

DICOMQC validates DICOM metadata after anonymization or pseudonymization. It is
an independent audit layer for research-release readiness, not another DICOM
anonymizer.

The tool is designed to:

- scan one or more DICOM files or studies
- read metadata without loading pixel data
- detect direct PHI fields and risky pseudonym fields
- report private DICOM tags
- produce reproducible JSON, CSV, and MultiQC companion evidence
- integrate into automated research workflows

v0.1 is intentionally conservative. It provides a usable metadata scanner and
rule engine, while leaving standards-specific profiles and plugin discovery for
later releases.

## What DICOMQC does not do

DICOMQC never modifies original DICOM files. It also does not claim DICOM
PS3.15, BIDS, HIPAA, or GDPR compliance in v0.1. Those standards are future
profile targets that require audited rule packs.

When DICOMQC reports required changes, apply them with an external
anonymization or pseudonymization workflow and rerun the audit. See
[Remediation](usage/remediation.md) for practical examples.

For the initial large-scale multiple sclerosis MRI use case, see
[MS MRI Workflow](usage/ms-mri-workflow.md).
